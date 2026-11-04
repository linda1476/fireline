"""Scripted end-to-end demo without the web server.

    fireline-demo [--mode text|audio] [--speed 3] [--live] [--scenario path]
    python -m fireline.demo --speed 100

Runs every scenario script line through the full pipeline (Triager -> WorldModel ->
Briefer, plus ASR for ``--mode audio`` when data/audio/NN_<responder>.wav exist) and
prints a timeline table, the briefings issued per line, a final state summary and
model / latency statistics. Mock mode unless ``--live`` and MODEL_API_KEY are present.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from typing import Optional

from fireline.briefer import callsign
from fireline.config import Settings, get_settings
from fireline.models import ResponderStatus, VictimStatus
from fireline.scenario import ScriptLine, load_scenario
from fireline.server.hub import Hub
from fireline.server.pipeline import AUDIO_DIR, AudioOutcome, Pipeline, ReportOutcome

W_SUMMARY = 54


def _row(cols: list[str], widths: list[int]) -> str:
    return "  ".join(c.ljust(w)[:w] if w else c for c, w in zip(cols, widths)).rstrip()


def _clip(text: Optional[str], n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


class Printer:
    """Prints the timeline as it happens and keeps the per-line data for the footer."""

    widths = [6, 6, 14, 18, W_SUMMARY, 24]

    def __init__(self, pipe: Pipeline):
        self.pipe = pipe
        self.outcomes: list[ReportOutcome] = []
        self.t0 = time.perf_counter()

    def header(self) -> None:
        print(_row(["t", "unit", "tag/prio", "zone", "summary", "model/ms"], self.widths))
        print(_row(["-" * w for w in self.widths], self.widths))

    def __call__(self, line: ScriptLine, out: ReportOutcome) -> None:
        tr = out.triage
        tag = f"{tr.tag.value}/P{tr.priority}" + (" MAYDAY" if tr.mayday else "")
        zone = tr.zone or "-"
        if tr.floor is not None and tr.zone:
            zone = f"{tr.zone} (F{tr.floor})"
        model = f"{tr.model}/{tr.latency_ms}"
        if isinstance(out, AudioOutcome):
            model = f"asr:{out.asr_latency_ms}+{model}"
        print(_row([f"{line.t:>5.0f}", line.responder_id, tag, zone, _clip(tr.summary, W_SUMMARY), model], self.widths))
        if isinstance(out, AudioOutcome) and out.transcript != line.text:
            print(f"        asr: {_clip(out.transcript, 100)}")
        for b in out.briefings:
            print(f"        -> {b.responder_id:<5} [{b.urgency.value:<8}] {b.text}")
        for a in out.assignments:
            print(f"        ?? propose {a.responder_id} -> {a.target_kind} {a.target_id}: {_clip(a.reason, 70)}")
        if out.commander_note:
            print(f"        note: {_clip(out.commander_note, 110)}")
        self.outcomes.append(out)


def print_state_summary(pipe: Pipeline) -> None:
    state = pipe.state
    roster = pipe.roster
    print()
    print("RESPONDERS")
    for r in roster:
        cell = f"F{r.cell.floor} ({r.cell.x},{r.cell.y})" if r.cell else "-"
        flag = "" if r.status == ResponderStatus.OK else f"  <-- {r.status.value}"
        print(f"  {r.id:<5} {callsign(r, roster):<11} {r.status.value:<10} {r.zone or '-':<18} {cell:<14} air={r.air_minutes}{flag}")
    print("VICTIMS")
    for v in state.victims.values():
        extra = f", assigned {v.assigned_responder_id}" if v.assigned_responder_id else ""
        print(f"  {v.id:<15} {v.status.value:<10} p={v.probability:.2f} x{v.count} {v.zone or '-'} F{v.cell.floor} "
              f"{v.condition or ''} [{v.source}{extra}]")
    if not state.victims:
        print("  (none)")
    print("HAZARDS")
    for h in state.hazards.values():
        print(f"  {h.id:<15} {'active' if h.active else 'cleared':<8} sev={h.severity} {h.kind} @ {h.zone or '-'} F{h.cell.floor}")
    if not state.hazards:
        print("  (none)")
    live = [v for v in state.victims.values() if v.status != VictimStatus.EXTRACTED]
    print(f"QUEUE {len(state.queue)} items, top: " + (
        f"{state.queue[0].triage.tag.value} P{state.queue[0].triage.priority} {state.queue[0].triage.responder_id} "
        f"score={state.queue[0].score:.1f}" if state.queue else "-"))
    print(f"state version {state.version}, {len(state.events)} events, {len(live)} victim(s) still inside")


def print_stats(pipe: Pipeline, printer: Printer, elapsed_s: float) -> None:
    print()
    print("MODELS")
    for name, st in pipe.stats.items():
        d = st.as_dict()
        mode = "live" if d["live"] else "mock"
        print(f"  {name:<8} {d['model']:<24} {mode:<5} calls={d['calls']:<3} fallbacks={d['fallbacks']:<2} "
              f"avg={d['avg_latency_ms']} ms")
    briefings = sum(len(o.briefings) for o in printer.outcomes)
    assignments = sum(len(o.assignments) for o in printer.outcomes)
    print(f"  {len(printer.outcomes)} reports, {briefings} briefings, {assignments} assignment proposals, "
          f"{pipe.hub.sent} ws messages, wall {elapsed_s:.1f}s")


def _settings(live: bool) -> Settings:
    if not live:
        return get_settings()
    s = Settings(force_mock=False)
    if not s.api_key:
        print("warning: --live given but MODEL_API_KEY is not set; running in mock mode", file=sys.stderr)
    return s


async def run(mode: str, speed: float, live: bool, scenario_path: Optional[str]) -> int:
    scenario = load_scenario(scenario_path)
    settings = _settings(live)
    pipe = Pipeline(scenario, settings, Hub())
    printer = Printer(pipe)
    mode_txt = "LIVE" if not settings.mock else "MOCK"
    audio = f"data/audio ({'present' if AUDIO_DIR.is_dir() and any(AUDIO_DIR.glob('*.wav')) else 'missing -> text'})"
    print(f"Fireline demo — {scenario.incident_name}")
    print(f"mode={mode} speed={speed}x models={mode_txt} spark={pipe.stats['spark'].model} "
          f"asr={pipe.stats['asr'].model} sam={pipe.stats['sam'].model}"
          + (f" {audio}" if mode == "audio" else ""))
    print()
    printer.header()
    t0 = time.perf_counter()
    try:
        await pipe.run_script(mode=mode, speed=speed, on_result=printer)
    finally:
        await pipe.close()
    print_state_summary(pipe)
    print_stats(pipe, printer, time.perf_counter() - t0)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Console entry point (``fireline-demo``)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="fireline-demo", description=__doc__.split("\n\n")[1])
    ap.add_argument("--mode", choices=["text", "audio"], default="text")
    ap.add_argument("--speed", type=float, default=3.0, help="script pacing divisor (0 = no pacing)")
    ap.add_argument("--live", action="store_true", help="use the Meta Model API (needs MODEL_API_KEY)")
    ap.add_argument("--scenario", default=None, help="path to a scenario.json")
    ap.add_argument("-v", "--verbose", action="store_true", help="show pipeline logs")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(args.mode, args.speed, args.live, args.scenario))


if __name__ == "__main__":
    raise SystemExit(main())
