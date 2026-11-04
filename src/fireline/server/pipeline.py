"""Per-input pipeline: radio / touch / photo -> world model -> broadcast -> briefer.

    pipe = Pipeline(scenario, settings=None, hub=None)
    outcome = await pipe.handle_report(RadioReport(...))     # ReportOutcome
    outcome = await pipe.handle_touch(TouchInput(...))       # TouchOutcome
    outcome = await pipe.handle_photo(PhotoInput(...))       # PhotoOutcome
    outcome = await pipe.handle_audio_file(wav_path, "E1-1") # AudioOutcome (ASR, mock-aware)
    await pipe.ack(report_id); await pipe.decide_assignment(assignment_id, True)
    pipe.start_demo("text", speed=3.0); await pipe.stop_demo(); await pipe.reset()

Wire order per report (docs/CONTRACT.md): ``transcript`` -> Triager -> WorldModel.apply_triage ->
broadcast ``delta`` + ``event``(s) + ``state`` -> Briefer.decide -> ``briefing``(s) /
``assignment``(s) -> ``state`` again. The Meta clients all live in the owning modules
(triage/briefer/vision/meta.asr); this file only catches ``MockMode`` for ASR and keeps
per-surface latency / fallback statistics for ``/api/health``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from fireline.briefer import Briefer, callsign, clip_words
from fireline.config import DATA_DIR, Settings, get_settings
from fireline.meta import MockMode
from fireline.models import (
    Assignment,
    Briefing,
    Building,
    Detection,
    PhotoInput,
    RadioReport,
    Responder,
    StateDelta,
    TouchInput,
    TriageResult,
    Urgency,
    WorldEvent,
    WorldState,
    WsMessage,
)
from fireline.scenario import Scenario, ScriptLine
from fireline.server.hub import Hub, message
from fireline.triage import Triager
from fireline.vision import HelmetCam, describe
from fireline.worldmodel import WorldModel

log = logging.getLogger("fireline.server")

AUDIO_DIR = DATA_DIR / "audio"
MOCK_TRANSCRIPT = "[mock transcript]"
RECENT_WINDOW = 10
"""How many recent briefings the briefer sees for repeat suppression (it stores 50)."""

_WAV_RE = re.compile(r"^(\d{2})_(.+)\.wav$", re.IGNORECASE)
REPLAY_MAX_AGE_S = 120.0
"""Briefings older than this are not replayed to a (re)connecting WebSocket client."""
FINAL_TRANSCRIPT_GRACE_S = 1.5
"""Mic: file a report this long after a final transcript if no speechComplete arrives."""


def _parse_ts(ts: str) -> datetime:
    try:
        d = datetime.fromisoformat(ts)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Demo audio naming (shared with scripts/make_demo_audio.py)
# ---------------------------------------------------------------------------


def audio_path_for(index: int, responder_id: str, audio_dir: Path | None = None) -> Path:
    """``data/audio/{index:02d}_{responder_id}.wav`` — ``index`` is 1-based (01 .. 12)."""
    return (audio_dir or AUDIO_DIR) / f"{index:02d}_{responder_id}.wav"


def script_line_for_wav(path: str | Path, scenario: Scenario) -> Optional[ScriptLine]:
    """Inverse of :func:`audio_path_for`: the script line a demo WAV was generated from."""
    m = _WAV_RE.match(Path(path).name)
    if not m:
        return None
    idx = int(m.group(1)) - 1
    if not 0 <= idx < len(scenario.script):
        return None
    line = scenario.script[idx]
    return line if line.responder_id.lower() == m.group(2).lower() else None


# ---------------------------------------------------------------------------
# Outcomes (what the HTTP routes and demo.py get back)
# ---------------------------------------------------------------------------


class ReportOutcome(BaseModel):
    report: RadioReport
    triage: TriageResult
    delta: StateDelta
    briefings: list[Briefing] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    commander_note: Optional[str] = None
    briefer_model: str = "mock"
    briefer_latency_ms: int = 0


class AudioOutcome(ReportOutcome):
    transcript: str
    asr_model: str = "mock"
    asr_latency_ms: int = 0


class TouchOutcome(BaseModel):
    delta: StateDelta
    briefings: list[Briefing] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    commander_note: Optional[str] = None


class PhotoOutcome(BaseModel):
    detections: list[Detection]
    delta: StateDelta
    latency_ms: int
    raw: str = "mock"
    model: str = "mock"
    briefings: list[Briefing] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    commander_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-surface statistics for /api/health
# ---------------------------------------------------------------------------


@dataclass
class SurfaceStats:
    model: str
    live: bool
    calls: int = 0
    fallbacks: int = 0
    total_latency_ms: int = 0
    last_latency_ms: int = 0

    def record(self, latency_ms: int, fallback: bool = False) -> None:
        self.calls += 1
        self.total_latency_ms += int(latency_ms)
        self.last_latency_ms = int(latency_ms)
        if fallback:
            self.fallbacks += 1

    def as_dict(self) -> dict[str, Any]:
        avg = int(self.total_latency_ms / self.calls) if self.calls else 0
        return {
            "model": self.model,
            "live": self.live,
            "mock": not self.live,
            "calls": self.calls,
            "fallbacks": self.fallbacks,
            "avg_latency_ms": avg,
            "last_latency_ms": self.last_latency_ms,
        }


@dataclass
class _MicSession:
    transcriber: Any
    streamer: Any
    responder_id: Optional[str]
    session_id: str
    speaker: Optional[str] = None
    turns: int = 0
    tasks: list[asyncio.Task] = field(default_factory=list)
    pending_final: Optional[str] = None
    grace_task: Optional[asyncio.Task] = None


ResultCallback = Callable[[ScriptLine, ReportOutcome], Optional[Awaitable[None]]]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    """Owns the world model and the three AI modules; serialises every state change."""

    def __init__(self, scenario: Scenario, settings: Settings | None = None, hub: Hub | None = None):
        self.scenario = scenario
        self.settings = settings or get_settings()
        self.hub = hub or Hub()
        self.hub.snapshot_fn = self.snapshot
        self.wm = WorldModel(scenario.initial_state())
        self.triager = Triager(self.settings)
        self.briefer = Briefer(self.settings)
        self.helmetcam = HelmetCam(self.settings)
        self.recent: deque[Briefing] = deque(maxlen=50)
        self.assignments: dict[str, Assignment] = {}
        self.lock = asyncio.Lock()
        self.demo_task: asyncio.Task | None = None
        self.demo_mode: Optional[str] = None
        self._asr: Any = None
        self._mic: _MicSession | None = None
        self.started_at = time.time()
        self._init_stats()

    def _init_stats(self) -> None:
        live = not self.settings.mock
        s = self.settings
        self.stats: dict[str, SurfaceStats] = {
            "spark": SurfaceStats(s.spark_model if live else "mock", live),
            "briefer": SurfaceStats(s.spark_model if live else "mock", live),
            "asr": SurfaceStats(s.asr_model if live else "mock", live),
            "sam": SurfaceStats(s.sam_model if live else "mock", live),
        }

    # ------------------------------------------------------------ accessors
    @property
    def state(self) -> WorldState:
        return self.wm.state

    @property
    def building(self) -> Building:
        return self.wm.state.building

    @property
    def roster(self) -> list[Responder]:
        return list(self.wm.state.responders.values())

    @property
    def live(self) -> bool:
        return not self.settings.mock

    @property
    def demo_running(self) -> bool:
        return self.demo_task is not None and not self.demo_task.done()

    def snapshot(self) -> dict:
        return self.wm.snapshot()

    def pending_assignments(self) -> list[Assignment]:
        return [a for a in self.assignments.values() if a.accepted is None]

    def recent_briefings(self, n: int = RECENT_WINDOW, max_age_s: Optional[float] = None) -> list[Briefing]:
        """Last ``n`` briefings; with ``max_age_s`` only those issued within that many seconds."""
        items = list(self.recent)[-n:]
        if max_age_s is None:
            return items
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_s)
        return [b for b in items if _parse_ts(b.timestamp) >= cutoff]

    def health(self) -> dict[str, Any]:
        """Payload for ``GET /api/health``."""
        return {
            "mock": self.settings.mock,
            "models": {k: v.as_dict() for k, v in self.stats.items()},
            "version": self.state.version,
            "incident": self.state.incident_name,
            "clients": len(self.hub),
            "demo_running": self.demo_running,
            "demo_mode": self.demo_mode if self.demo_running else None,
            "mic_session": self._mic.session_id if self._mic else None,
            "uptime_s": int(time.time() - self.started_at),
        }

    def resolve_responder_id(self, rid: Optional[str]) -> Optional[str]:
        """Map an id / callsign / name / unique unit to a roster id; None if unknown."""
        if not rid or not rid.strip():
            return None
        key = rid.strip()
        responders = self.state.responders
        if key in responders:
            return key
        low = key.lower()
        roster = self.roster
        for r in roster:
            if low in (r.id.lower(), r.name.lower(), callsign(r, roster).lower()):
                return r.id
        units = [r for r in roster if r.unit.lower() == low]
        return units[0].id if len(units) == 1 else None

    # ------------------------------------------------------------ broadcast
    async def _broadcast(self, kind: str, payload: Any) -> None:
        await self.hub.broadcast(message(kind, payload))

    async def _publish_delta(self, delta: StateDelta) -> None:
        """delta -> event(s) -> state, the order the UIs rely on."""
        await self._broadcast("delta", delta)
        for ev in delta.new_events:
            await self._broadcast("event", ev)
        await self._broadcast("state", self.snapshot())

    async def _publish_events_and_state(self, events: list[WorldEvent]) -> None:
        for ev in events:
            await self._broadcast("event", ev)
        await self._broadcast("state", self.snapshot())

    # ------------------------------------------------------------ reports
    async def handle_report(self, report: RadioReport) -> ReportOutcome:
        """Full pipeline for one radio transmission (typed, scripted, file or mic)."""
        report.responder_id = self.resolve_responder_id(report.responder_id)
        await self._broadcast("transcript", {
            "text": report.transcript, "final": True, "speaker": report.speaker_label,
            "responder_id": report.responder_id, "source": report.source, "report_id": report.id,
        })
        triage = await self._triage(report)
        async with self.lock:
            delta = self.wm.apply_triage(triage, report)
            await self._publish_delta(delta)
            briefings, assignments, note, decision = await self._brief(delta)
        log.info("report %s %s -> %s p%d zone=%s floor=%s mayday=%s (%s %dms) briefings=%d",
                 report.id, report.responder_id or "?", triage.tag.value, triage.priority, triage.zone,
                 triage.floor, triage.mayday, triage.model, triage.latency_ms, len(briefings))
        return ReportOutcome(report=report, triage=triage, delta=delta, briefings=briefings,
                             assignments=assignments, commander_note=note,
                             briefer_model=decision.model, briefer_latency_ms=decision.latency_ms)

    async def _triage(self, report: RadioReport) -> TriageResult:
        """Triager never raises; record whether the live path fell back to the mock."""
        result = await self.triager.triage(report, self.building, self.roster)
        fallback = self.live and result.model == "mock"
        self.stats["spark"].record(result.latency_ms, fallback)
        if fallback:
            log.warning("triage fell back to mock for %s (confidence %.2f)", report.id, result.confidence)
        return result

    async def _brief(self, delta: StateDelta):
        """Run the briefer on a committed delta; record + broadcast what it decided. Lock held."""
        decision = await self.briefer.decide(delta, self.state, self.recent_briefings())
        self.stats["briefer"].record(decision.latency_ms, decision.model == "mock-fallback")
        changed = False
        for b in decision.briefings:
            d = self.wm.record_briefing(b)
            self.recent.append(b)
            await self._broadcast("briefing", b)
            for ev in d.new_events:
                await self._broadcast("event", ev)
            changed = True
        accepted: list[Assignment] = []
        for a in decision.assignments:
            if self._assignment_known(a):
                continue
            self.assignments[a.id] = a
            d = self.wm.record_assignment(a)
            await self._broadcast("assignment", a)
            for ev in d.new_events:
                await self._broadcast("event", ev)
            accepted.append(a)
            changed = True
        if decision.commander_note:
            ev = WorldEvent(kind="briefing", text=f"Agent: {decision.commander_note}")
            self.state.events.append(ev)
            await self._broadcast("event", ev)
            changed = True
        if changed:
            await self._broadcast("state", self.snapshot())
        return list(decision.briefings), accepted, decision.commander_note, decision

    def _assignment_known(self, a: Assignment) -> bool:
        """Same (responder, kind, target) already proposed (pending or decided) -> skip."""
        key = (a.responder_id, a.target_kind, a.target_id)
        return any((x.responder_id, x.target_kind, x.target_id) == key for x in self.assignments.values())

    # ------------------------------------------------------------ touch / photo
    async def handle_touch(self, touch: TouchInput) -> TouchOutcome:
        """One clip-display button press."""
        touch.responder_id = self.resolve_responder_id(touch.responder_id) or touch.responder_id
        async with self.lock:
            delta = self.wm.apply_touch(touch)
            await self._publish_delta(delta)
            briefings, assignments, note, _ = await self._brief(delta)
        log.info("touch %s %s cell=%s", touch.responder_id, touch.action, touch.cell)
        return TouchOutcome(delta=delta, briefings=briefings, assignments=assignments, commander_note=note)

    async def handle_photo(self, photo: PhotoInput) -> PhotoOutcome:
        """Helmet-cam frame -> SAM (or mock) -> victim estimate at the responder's cell."""
        photo.responder_id = self.resolve_responder_id(photo.responder_id) or photo.responder_id
        dets, latency_ms, raw = await self.helmetcam.find_people(photo)
        fallback = raw.startswith("mock-fallback")
        self.stats["sam"].record(latency_ms, fallback)
        async with self.lock:
            delta = self.wm.apply_detections(photo.responder_id, dets, photo.id)
            await self._publish_delta(delta)
            briefings, assignments, note, _ = await self._brief(delta)
        log.info("photo %s from %s: %s (%s %dms)", photo.id, photo.responder_id, describe(dets),
                 self.helmetcam.model, latency_ms)
        return PhotoOutcome(detections=dets, delta=delta, latency_ms=latency_ms, raw=raw,
                            model=self.helmetcam.model, briefings=briefings, assignments=assignments,
                            commander_note=note)

    # ------------------------------------------------------------ commander actions
    async def ack(self, report_id: str) -> bool:
        """Acknowledge a queue item; False if no unacknowledged item had that report id."""
        async with self.lock:
            delta = self.wm.ack(report_id)
            ok = bool(delta.new_events)
            await self._publish_events_and_state(delta.new_events)
        return ok

    async def decide_assignment(self, assignment_id: str, accepted: bool) -> bool:
        """Commander accepts / declines a proposal; an accepted one is briefed to the responder."""
        async with self.lock:
            a = self.assignments.get(assignment_id)
            if a is None:
                return False
            a.accepted = bool(accepted)
            delta = self.wm.record_assignment(a)
            await self._broadcast("assignment", a)
            events = list(delta.new_events)
            if a.accepted and self._target_stale(a):
                # Victim already out by the time the commander clicked: no "go rescue them" voice line.
                log.info("assignment %s accepted after its victim was extracted; no briefing", a.id)
            elif a.accepted:
                b = self._assignment_briefing(a)
                if b is not None:
                    d = self.wm.record_briefing(b)
                    self.recent.append(b)
                    await self._broadcast("briefing", b)
                    events.extend(d.new_events)
            await self._publish_events_and_state(events)
        return True

    def _target_stale(self, a: Assignment) -> bool:
        """True when a victim assignment's target has already been extracted."""
        if a.target_kind != "victim":
            return False
        v = self.state.victims.get(a.target_id)
        return v is not None and v.status.value == "extracted"

    def _assignment_briefing(self, a: Assignment) -> Optional[Briefing]:
        """'Engine 1: Command assigns you to confirmed victim floor 4 unit 404.'"""
        r = self.state.responders.get(a.responder_id)
        if r is None:
            return None
        cs = callsign(r, self.roster)
        target, cell = self._describe_target(a)
        text = clip_words(f"{cs}: Command assigns you to {target}. Acknowledge and proceed.")
        return Briefing(responder_id=r.id, text=text, urgency=Urgency.HIGH,
                        reason="commander accepted the assignment", trigger_ids=[a.id, a.target_id], show_cell=cell)

    def _describe_target(self, a: Assignment) -> tuple[str, Any]:
        if a.target_kind == "victim":
            v = self.state.victims.get(a.target_id)
            if v is None:
                return "the victim", None
            noun = f"{v.count} victims" if v.count > 1 else "victim"
            return f"{v.status.value} {noun} {self._where(v.cell.floor, v.zone)}", v.cell
        if a.target_kind == "responder":
            t = self.state.responders.get(a.target_id)
            if t is None:
                return "the mayday", None
            return f"{callsign(t, self.roster)} (mayday) {self._where(t.cell.floor if t.cell else None, t.zone)}", t.cell
        h = self.state.hazards.get(a.target_id)
        if h is None:
            return "the hazard", None
        return f"{h.kind} {self._where(h.cell.floor, h.zone)}", h.cell

    @staticmethod
    def _where(floor: Optional[int], zone: Optional[str]) -> str:
        if floor is not None and floor >= 1:
            return f"floor {floor} {zone}" if zone else f"floor {floor}"
        return f"outside {zone}" if zone else "location unknown"

    # ------------------------------------------------------------ reset / demo
    async def reset(self) -> None:
        """Stop demo + mic, reload the scenario's initial state (version 0) and broadcast it."""
        await self.stop_demo()
        await self.stop_mic()
        async with self.lock:
            self.wm = WorldModel(self.scenario.initial_state())
            self.recent.clear()
            self.assignments.clear()
            self._init_stats()
            await self._broadcast("state", self.snapshot())
        log.info("scenario reset")

    def start_demo(self, mode: str = "text", speed: float = 1.0) -> asyncio.Task:
        """Run the scripted scenario in the background (cancels a running one first)."""
        if self.demo_task is not None and not self.demo_task.done():
            self.demo_task.cancel()
        self.demo_mode = mode
        self.demo_task = asyncio.create_task(self._demo_main(mode, speed), name="fireline-demo")
        return self.demo_task

    async def _demo_main(self, mode: str, speed: float) -> None:
        try:
            await self.run_script(mode=mode, speed=speed)
            log.info("demo (%s) finished", mode)
        except asyncio.CancelledError:
            log.info("demo (%s) cancelled", mode)
            raise
        except Exception:  # noqa: BLE001
            log.exception("demo (%s) crashed", mode)

    async def stop_demo(self) -> bool:
        """Cancel the background demo if running; True if one was stopped."""
        task = self.demo_task
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        return True

    async def run_script(self, mode: str = "text", speed: float = 1.0,
                         on_result: ResultCallback | None = None) -> list[ReportOutcome]:
        """Play every scenario script line, paced by ``line.t / speed`` (speed <= 0 = no pacing).

        ``mode == "audio"`` uses ``data/audio/NN_<responder>.wav`` through ASR when the file
        exists (mock ASR returns the script text), else the line's text.
        """
        outcomes: list[ReportOutcome] = []
        loop = asyncio.get_running_loop()
        start = loop.time()
        for index, line in enumerate(self.scenario.script, start=1):
            if speed > 0:  # absolute schedule: model latency does not accumulate as drift
                await asyncio.sleep(max(0.0, start + line.t / speed - loop.time()))
            wav = audio_path_for(index, line.responder_id)
            if mode == "audio" and wav.is_file():
                outcome: ReportOutcome = await self.handle_audio_file(wav, line.responder_id)
            else:
                report = RadioReport(responder_id=line.responder_id, transcript=line.text, source="scripted")
                outcome = await self.handle_report(report)
            outcomes.append(outcome)
            if on_result is not None:
                res = on_result(line, outcome)
                if asyncio.iscoroutine(res):
                    await res
        return outcomes

    # ------------------------------------------------------------ audio (ASR)
    def _asr_client(self):
        if self._asr is None:
            from fireline.meta.asr import ASRClient

            self._asr = ASRClient(self.settings)
        return self._asr

    async def transcribe(self, wav_path: str | Path, responder_id: Optional[str] = None) -> tuple[str, Optional[str], int]:
        """(text, speaker_label, latency_ms). Live ASR when possible, else the script text / mock."""
        path = Path(wav_path)
        t0 = time.perf_counter()
        if self.live:
            try:
                res = await self._asr_client().transcribe_file(path)
                latency = int((time.perf_counter() - t0) * 1000)
                self.stats["asr"].record(latency)
                speaker = res.turns[0].speaker if res.turns else None
                return res.text, speaker, latency
            except MockMode:
                pass
            except Exception as e:  # noqa: BLE001 - never crash on an ASR failure
                log.warning("asr: transcribe failed for %s (%s); using mock transcript", path.name, e)
                latency = int((time.perf_counter() - t0) * 1000)
                self.stats["asr"].record(latency, fallback=True)
                return self._mock_transcript(path), None, latency
        latency = int((time.perf_counter() - t0) * 1000)
        self.stats["asr"].record(latency)
        return self._mock_transcript(path), None, latency

    def _mock_transcript(self, path: Path) -> str:
        line = script_line_for_wav(path, self.scenario)
        return line.text if line else MOCK_TRANSCRIPT

    async def handle_audio_file(self, wav_path: str | Path, responder_id: Optional[str] = None) -> AudioOutcome:
        """Transcribe a WAV (16 kHz mono s16) and push it through :meth:`handle_report`."""
        path = Path(wav_path)
        text, speaker, latency = await self.transcribe(path, responder_id)
        report = RadioReport(responder_id=responder_id, speaker_label=speaker, transcript=text,
                             source="file", audio_path=str(path))
        out = await self.handle_report(report)
        return AudioOutcome(**out.model_dump(), transcript=text, asr_model=self.stats["asr"].model,
                            asr_latency_ms=latency)

    # ------------------------------------------------------------ live mic
    async def start_mic(self, responder_id: Optional[str] = None) -> dict[str, Any]:
        """PC microphone -> realtime ASR (ENDPOINTING) -> one report per completed turn."""
        rid = self.resolve_responder_id(responder_id)
        if not self.live:
            return {"session_id": "mock", "note": "no API key: mic disabled, use the inject box", "responder_id": rid}
        await self.stop_mic()
        from fireline.meta.asr import MicStreamer, RealtimeTranscriber

        rt = RealtimeTranscriber(on_event=self._on_asr_event, settings=self.settings)
        session_id = await rt.connect(mode="ENDPOINTING")
        streamer = MicStreamer(rt)
        try:
            await streamer.start()
        except Exception:
            await rt.close(wait=1.0)
            raise
        self._mic = _MicSession(transcriber=rt, streamer=streamer, responder_id=rid, session_id=session_id)
        log.info("mic session %s started as %s", session_id, rid)
        return {"session_id": session_id, "responder_id": rid}

    async def stop_mic(self) -> bool:
        mic, self._mic = self._mic, None
        if mic is None:
            return False
        self._cancel_final_grace(mic)
        try:
            await mic.streamer.stop()
        except Exception as e:  # noqa: BLE001
            log.warning("mic streamer stop failed: %s", e)
        try:
            await mic.transcriber.close(wait=3.0)
        except Exception as e:  # noqa: BLE001
            log.warning("mic transcriber close failed: %s", e)
        log.info("mic session %s stopped after %d turn(s)", mic.session_id, mic.turns)
        return True

    async def _on_asr_event(self, event: dict[str, Any]) -> None:
        """Realtime ASR events -> ``transcript`` broadcasts; completed turns -> reports."""
        mic = self._mic
        if mic is None:
            return
        kind = event.get("type")
        if kind == "speaker":
            mic.speaker = event.get("label") or mic.speaker
        elif kind == "transcript":
            text = event.get("transcript") or ""
            final = bool(event.get("final"))
            await self._broadcast("transcript", {
                "text": text, "final": final, "speaker": mic.speaker,
                "responder_id": mic.responder_id, "source": "mic",
            })
            if final and text.strip():
                self._arm_final_grace(mic, text.strip())
        elif kind == "speechComplete":
            self._cancel_final_grace(mic)
            self._file_mic_report(mic, (event.get("transcript") or mic.pending_final or "").strip())
        elif kind == "error":
            await self._broadcast("error", {"message": f"ASR: {event.get('message')}"})

    def _file_mic_report(self, mic: _MicSession, text: str) -> None:
        """One completed spoken turn -> RadioReport(source="mic") handled in its own task."""
        mic.pending_final = None
        if not text:
            return
        mic.turns += 1
        report = RadioReport(responder_id=mic.responder_id, speaker_label=mic.speaker, transcript=text, source="mic")
        task = asyncio.create_task(self.handle_report(report))
        mic.tasks.append(task)
        task.add_done_callback(lambda t: mic.tasks.remove(t) if t in mic.tasks else None)

    def _arm_final_grace(self, mic: _MicSession, text: str) -> None:
        """If the API sends a final transcript but no speechComplete, file the report anyway."""
        self._cancel_final_grace(mic)
        mic.pending_final = text

        async def _grace() -> None:
            await asyncio.sleep(FINAL_TRANSCRIPT_GRACE_S)
            if mic.pending_final == text:
                log.info("mic: no speechComplete after final transcript; filing report")
                self._file_mic_report(mic, text)

        mic.grace_task = asyncio.create_task(_grace())

    @staticmethod
    def _cancel_final_grace(mic: _MicSession) -> None:
        if mic.grace_task is not None and not mic.grace_task.done():
            mic.grace_task.cancel()
        mic.grace_task = None

    # ------------------------------------------------------------ misc
    async def close(self) -> None:
        await self.stop_demo()
        await self.stop_mic()


__all__ = [
    "AUDIO_DIR", "MOCK_TRANSCRIPT", "RECENT_WINDOW", "REPLAY_MAX_AGE_S", "FINAL_TRANSCRIPT_GRACE_S", "Pipeline", "ReportOutcome", "AudioOutcome",
    "TouchOutcome", "PhotoOutcome", "SurfaceStats", "audio_path_for", "script_line_for_wav",
]
