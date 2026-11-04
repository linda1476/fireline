"""Radio transmission -> :class:`~fireline.models.TriageResult`.

    from fireline.triage import Triager, PriorityQueue
    t = Triager(settings=None)                 # Muse Spark when a key is present, else mock
    result = await t.triage(report, building, roster)
    result = t.triage_sync(report, building, roster)   # outside an event loop

Live path: :func:`build_system_prompt` + :func:`build_user_prompt` -> ``SparkClient.acomplete_json``
with the flat :class:`TriageExtraction` schema -> :func:`extraction_to_result` (zone/floor
normalisation, call-sign -> responder id, mayday enforcement). Any failure (``MockMode``,
API error, bad JSON, timeout) degrades to :func:`mock_triage` with low confidence; the
pipeline never raises on a model answer.

CLI: ``python -m fireline.triage "Engine 1 on three, heavy smoke"`` prints the result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from typing import Optional

from fireline.config import Settings, get_settings
from fireline.meta import MetaAPIError, MockMode
from fireline.models import Building, RadioReport, Responder, TriageResult
from fireline.triage.extract import (
    TriageExtraction,
    build_system_prompt,
    build_user_prompt,
    extraction_to_result,
    find_zone_mentions,
    infer_responder_id,
    normalize_zone,
    parse_floor_phrase,
    reconcile_floor,
    resolve_zone,
    transcript_declares_mayday,
)
from fireline.triage.mock import MOCK_MODEL, mock_triage
from fireline.triage.queue import MAYDAY_BONUS, PriorityQueue, compute_score

__all__ = [
    "Triager",
    "PriorityQueue",
    "TriageExtraction",
    "MOCK_MODEL",
    "MAYDAY_BONUS",
    "build_system_prompt",
    "build_user_prompt",
    "compute_score",
    "extraction_to_result",
    "find_zone_mentions",
    "infer_responder_id",
    "mock_triage",
    "normalize_zone",
    "parse_floor_phrase",
    "reconcile_floor",
    "resolve_zone",
    "transcript_declares_mayday",
    "main",
]

log = logging.getLogger("fireline.triage")

FALLBACK_CONFIDENCE = 0.3


class Triager:
    """Turns one :class:`RadioReport` into a :class:`TriageResult`.

    ``settings`` is forwarded to the Spark client, so a caller can pass a live
    :class:`~fireline.config.Settings` even when the process default is mock.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._spark = None
        self._prompt_cache: dict[tuple[str, int, tuple[str, ...]], str] = {}

    # ------------------------------------------------------------- helpers
    @property
    def live(self) -> bool:
        return not self.settings.mock

    @property
    def model_name(self) -> str:
        return self.settings.spark_model if self.live else MOCK_MODEL

    def _client(self):
        """Lazy SparkClient (import kept local so mock mode never needs the openai stack)."""
        if self._spark is None:
            from fireline.meta.spark import SparkClient

            self._spark = SparkClient(self.settings)
        return self._spark

    def system_prompt(self, building: Building, roster: list[Responder]) -> str:
        """Cached per (building, roster) since it is identical for every report."""
        key = (building.name, len(building.zones), tuple(r.id for r in roster))
        if key not in self._prompt_cache:
            self._prompt_cache[key] = build_system_prompt(building, roster)
        return self._prompt_cache[key]

    # ---------------------------------------------------------------- main
    async def triage(self, report: RadioReport, building: Building, roster: list[Responder]) -> TriageResult:
        """Live Spark structured output when possible, deterministic mock otherwise."""
        t0 = time.perf_counter()
        if not self.live:
            return mock_triage(report, building, roster, latency_ms=_ms(t0))
        try:
            extraction, latency = await self._client().acomplete_json(
                self.system_prompt(building, roster),
                build_user_prompt(report, roster),
                TriageExtraction,
                temperature=0.0,
                max_tokens=700,
            )
            return extraction_to_result(
                extraction, report, building, roster, model=self.settings.spark_model, latency_ms=latency
            )
        except MockMode:
            return mock_triage(report, building, roster, latency_ms=_ms(t0))
        except (MetaAPIError, asyncio.TimeoutError) as e:
            log.warning("triage: Spark failed (%s); using mock for %s", e, report.id)
        except Exception as e:  # openai / httpx / parsing surprises: never crash the pipeline
            log.warning("triage: Spark call failed (%r); using mock for %s", e, report.id)
        return self._fallback(report, building, roster, t0)

    def _fallback(self, report: RadioReport, building: Building, roster: list[Responder], t0: float) -> TriageResult:
        result = mock_triage(report, building, roster, latency_ms=_ms(t0))
        result.confidence = min(result.confidence, FALLBACK_CONFIDENCE)
        return result

    def triage_sync(self, report: RadioReport, building: Building, roster: list[Responder]) -> TriageResult:
        """Blocking wrapper for the CLI and tests. The server should ``await triage()``.

        Each call runs in its own event loop (in a helper thread if a loop is already
        running), and in live mode the Spark client is discarded afterwards because the
        async HTTP client is bound to the loop that first used it.
        """
        coro = self.triage(report, building, roster)
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(coro)
            box: dict[str, object] = {}

            def _run() -> None:
                try:
                    box["result"] = asyncio.run(coro)
                except BaseException as e:  # pragma: no cover - re-raised below
                    box["error"] = e

            th = threading.Thread(target=_run, daemon=True)
            th.start()
            th.join()
            if "error" in box:
                raise box["error"]  # type: ignore[misc]
            return box["result"]  # type: ignore[return-value]
        finally:
            if self.live:
                self._spark = None


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


# --------------------------------------------------------------------------- CLI


def main(argv: Optional[list[str]] = None) -> int:
    """``python -m fireline.triage "text" [--responder E1-1] [--prompt]``."""
    import argparse

    from fireline.scenario import load_scenario

    ap = argparse.ArgumentParser(prog="python -m fireline.triage", description="Triage one radio line (mock or live).")
    ap.add_argument("text", nargs="*", help="transcript text (quote it)")
    ap.add_argument("--responder", "-r", default=None, help="responder id if known, e.g. E1-2")
    ap.add_argument("--prompt", action="store_true", help="print the live system prompt and exit")
    ap.add_argument("--scenario", default=None, help="path to a scenario.json (default: data/scenario.json)")
    args = ap.parse_args(argv)

    sc = load_scenario(args.scenario)
    if args.prompt:
        print(build_system_prompt(sc.building, sc.responders))
        return 0
    text = " ".join(args.text).strip()
    if not text:
        ap.error("give the transmission text")
    settings = get_settings()
    t = Triager(settings)
    report = RadioReport(responder_id=args.responder, transcript=text, source="text")
    result = t.triage_sync(report, sc.building, sc.responders)
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    print(f"# mode={'live' if t.live else 'mock'} model={result.model} latency_ms={result.latency_ms}", file=sys.stderr)
    return 0
