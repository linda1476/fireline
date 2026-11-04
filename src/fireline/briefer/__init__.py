"""Hands-free briefing agent.

After every world-state change the ``Briefer`` decides, per responder, whether to
interrupt them through their earpiece and what to say (<= 25 words), and proposes
assignments to the commander. Live decisions come from Muse Spark structured output
(``SparkBriefer``); in mock mode, on timeout or on any model/API error it falls back
to the deterministic ``RuleBriefer`` so the pipeline never stalls or crashes.

Usage::

    from fireline.briefer import Briefer
    b = Briefer()
    decision = await b.decide(delta, state, recent)   # BrieferDecision
"""

from __future__ import annotations

import asyncio
import logging
import time

from fireline.config import Settings, get_settings
from fireline.meta import MockMode
from fireline.models import BrieferDecision, Briefing, StateDelta, WorldState

from .agent import BrieferOut, SparkBriefer, build_user_prompt, compact_state, to_decision
from .mock import MAX_WORDS, RuleBriefer, callsign, clip_words, words

__all__ = [
    "Briefer",
    "BrieferOut",
    "MAX_WORDS",
    "RuleBriefer",
    "SparkBriefer",
    "build_user_prompt",
    "callsign",
    "clip_words",
    "compact_state",
    "to_decision",
    "words",
]

log = logging.getLogger("fireline.briefer")


class Briefer:
    """Facade: Spark when live, rules otherwise. Always returns a BrieferDecision."""

    timeout_s: float = 20.0

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.rules = RuleBriefer()
        self.spark = SparkBriefer(self.settings)

    async def decide(self, delta: StateDelta, state: WorldState, recent: list[Briefing] | None = None) -> BrieferDecision:
        """Decide briefings/assignments for one delta. Never raises; never blocks > timeout_s."""
        recent = recent or []
        t0 = time.perf_counter()
        try:
            if self.settings.mock:
                raise MockMode("briefer: mock mode")
            decision = await asyncio.wait_for(self.spark.decide(delta, state, recent), timeout=self.timeout_s)
        except MockMode:
            decision = self.rules.decide(delta, state, recent)
            decision.model = "mock"
        except Exception as e:  # noqa: BLE001 - any model/API failure degrades to rules
            log.warning("briefer: live decision failed (%s: %s); using rules", type(e).__name__, e)
            decision = self.rules.decide(delta, state, recent)
            decision.model = "mock-fallback"
        decision.latency_ms = int((time.perf_counter() - t0) * 1000)
        return decision

    def decide_sync(self, delta: StateDelta, state: WorldState, recent: list[Briefing] | None = None) -> BrieferDecision:
        """Blocking variant for scripts/threads. Does not create an event loop."""
        recent = recent or []
        t0 = time.perf_counter()
        try:
            if self.settings.mock:
                raise MockMode("briefer: mock mode")
            decision = self.spark.decide_sync(delta, state, recent)
        except MockMode:
            decision = self.rules.decide(delta, state, recent)
            decision.model = "mock"
        except Exception as e:  # noqa: BLE001
            log.warning("briefer: live decision failed (%s: %s); using rules", type(e).__name__, e)
            decision = self.rules.decide(delta, state, recent)
            decision.model = "mock-fallback"
        decision.latency_ms = int((time.perf_counter() - t0) * 1000)
        return decision
