"""ScenarioPlayer: replays data/scenario_<id>.yaml on a shared clock.

Per radio channel (CMD, TAC) one continuous PCM buffer (silence + line clips at their key-up) is streamed at 1x
into one RealtimeTranscriber (ENDPOINTING). ASR turns are merged into Transmissions per CONTRACT: a Transmission
= all turns inside [t_keyup, t_keyup + clip + 0.5]; finalised at the first speechComplete after the clip ends,
or turn_merge_gap_s (1.5 s) after the last speechComplete (hard stop clip_end + 5 s).
`speed` compresses only the silence BETWEEN clips (wall gap >= min(gap, 2 s)); audio itself is always 1x.
asr="file" = Risk #3 fallback: one POST /v1/asr/transcribe per clip at key-up + duration.

Callbacks (sync or async; async ones are spawned as tasks so the ASR reader never blocks):
  on_transmission(tx)  partial updates (same tx id)       on_final(tx)   final transcript
  on_audio_cue(cue)    {channel, line_id, audio_url, t}   on_ptt_line(line) / on_agent_line(line)  raw yaml dicts
Per-transmission measured latency: player.asr_ms[tx.id], player.keyup_wall[tx.id] (perf_counter seconds).
"""

from __future__ import annotations

import asyncio
import logging
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from server.config import get_settings
from server.models import Transmission

log = logging.getLogger("earshot.scenario")
RADIO_CHANNELS = ("CMD", "TAC")
SR = 16000
MIN_GAP_S = 2.0
TAIL_S = 4.0


def load_scenario(scenario_id: str = "hanbit") -> dict[str, Any]:
    path = get_settings().data_dir / f"scenario_{scenario_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def _maybe_call(cb: Callable | None, *args: Any) -> None:
    if cb is None:
        return
    try:
        res = cb(*args)
        if asyncio.iscoroutine(res):
            asyncio.ensure_future(res)
    except Exception:
        log.exception("scenario callback failed")


class Timeline:
    """Monotone scenario-t ↔ wall-offset map: 1x inside audio, 1/speed in silence (gaps clamped >= 2 s)."""

    def __init__(self, intervals: list[tuple[float, float]], speed: float = 1.0):
        self.speed = max(speed, 1e-6)
        merged: list[list[float]] = []
        for a, b in sorted(intervals):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        # anchors: (t, wall) at each segment boundary
        self.anchors: list[tuple[float, float, float]] = []  # (t_start, wall_start, rate wall/t) piecewise
        cur_t, cur_w = 0.0, 0.0
        for a, b in merged:
            if a > cur_t:
                gap = a - cur_t
                wgap = max(gap / self.speed, min(gap, MIN_GAP_S))
                self.anchors.append((cur_t, cur_w, wgap / gap))
                cur_w += wgap
                cur_t = a
            self.anchors.append((cur_t, cur_w, 1.0))
            cur_w += b - cur_t
            cur_t = b
        self.anchors.append((cur_t, cur_w, 1.0 / self.speed))

    def wall_of(self, t: float) -> float:
        seg = self.anchors[0]
        for s in self.anchors:
            if s[0] <= t:
                seg = s
            else:
                break
        return seg[1] + (t - seg[0]) * seg[2]

    def t_of(self, w: float) -> float:
        seg = self.anchors[0]
        for s in self.anchors:
            if s[1] <= w:
                seg = s
            else:
                break
        return seg[0] + (w - seg[1]) / seg[2]


@dataclass
class _Open:
    tx: Transmission
    clip_start_wall: float          # perf_counter seconds
    clip_end_wall: float
    turns: list[str] = field(default_factory=list)
    partial: str = ""
    last_sc: float | None = None
    sc_after_end: bool = False
    done: bool = False


class ScenarioPlayer:
    def __init__(self, scenario_id: str = "hanbit", lang: str = "ko", audio: str = "radio", mode: str = "LIVE", *,
                 asr: str = "realtime", speed: float = 1.0, max_t: float | None = None,
                 on_transmission: Callable | None = None, on_final: Callable | None = None,
                 on_audio_cue: Callable | None = None, on_ptt_line: Callable | None = None,
                 on_agent_line: Callable | None = None, clock: Callable[[], float] = time.perf_counter,
                 id_factory: Callable[[], str] | None = None):
        self.settings = get_settings()
        self.scenario = load_scenario(scenario_id)
        self.scenario_id, self.lang, self.audio, self.mode, self.asr = scenario_id, lang, audio, mode, asr
        self.speed, self.max_t = speed, max_t
        self.on_transmission, self.on_final, self.on_audio_cue = on_transmission, on_final, on_audio_cue
        self.on_ptt_line, self.on_agent_line = on_ptt_line, on_agent_line
        self.clock = clock
        self._n = 0
        self._id_factory = id_factory
        self.asr_ms: dict[str, int] = {}
        self.keyup_wall: dict[str, float] = {}
        self.start_wall: float | None = None
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._rts: dict[str, Any] = {}
        self._open: dict[str, _Open | None] = {c: None for c in RADIO_CHANNELS}
        self._prepare()

    # ------------------------------------------------------------------ data
    def lines(self) -> list[dict[str, Any]]:
        return list(self.scenario.get("lines", []))

    def wav_path(self, line_id: str) -> Path:
        return self.settings.audio_dir / self.audio / f"{line_id}.wav"

    def audio_url(self, line_id: str) -> str:
        return f"/samples/{self.audio}/{line_id}.wav"

    def _prepare(self) -> None:
        self._lines = [ln for ln in self.lines() if self.max_t is None or float(ln["t"]) <= self.max_t]
        self._dur: dict[str, float] = {}
        intervals = []
        for ln in self._lines:
            p = self.wav_path(ln["id"])
            if ln.get("kind") == "radio" and p.exists():
                d = wav_duration(p)
                self._dur[ln["id"]] = d
                intervals.append((float(ln["t"]), float(ln["t"]) + d))
        self.timeline = Timeline(intervals, self.speed)
        # actual wall start per radio line (same-channel overlap pushed after the previous clip)
        self._wall_start: dict[str, float] = {}
        last_end: dict[str, float] = {c: -1e9 for c in RADIO_CHANNELS}
        for ln in sorted(self._lines, key=lambda x: float(x["t"])):
            w = self.timeline.wall_of(float(ln["t"]))
            if ln["id"] in self._dur and ln["channel"] in RADIO_CHANNELS:
                w = max(w, last_end[ln["channel"]] + 0.5)
                last_end[ln["channel"]] = w + self._dur[ln["id"]]
            self._wall_start[ln["id"]] = w
        self.end_wall = max(list(last_end.values()) + [max(self._wall_start.values(), default=0)]) + TAIL_S

    def _next_id(self) -> str:
        if self._id_factory:
            return self._id_factory()
        self._n += 1
        return f"tx_{self._n:04d}"

    def t(self) -> float:
        """Current scenario seconds."""
        if self.start_wall is None:
            return 0.0
        return self.timeline.t_of(self.clock() - self.start_wall)

    def _channel_pcm(self, channel: str) -> bytes:
        from server.meta.asr import read_pcm, silence

        buf = bytearray()
        for ln in sorted(self._lines, key=lambda x: self._wall_start[x["id"]]):
            if ln["channel"] != channel or ln["id"] not in self._dur:
                continue
            pos = int(round(self._wall_start[ln["id"]] * SR)) * 2
            if len(buf) < pos:
                buf += b"\x00" * (pos - len(buf))
            buf += read_pcm(self.wav_path(ln["id"]))
        tail = int(round(self.end_wall * SR)) * 2
        if len(buf) < tail:
            buf += b"\x00" * (tail - len(buf))
        return bytes(buf) + silence(0.0)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self._main = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self.running = False
        main = getattr(self, "_main", None)
        if main is not None and main is not asyncio.current_task() and not main.done():
            main.cancel()  # no tail sleep → _finalise after a stop
        for ch in list(self._open):
            self._open[ch] = None
        for t in self._tasks:
            t.cancel()
        for rt in self._rts.values():
            try:
                await rt.close(wait=2)
            except Exception:
                pass

    async def run(self) -> None:
        self.running = True
        if self.asr == "realtime":
            await self._connect_all()
            if not self.running:  # stopped while connecting: close what connected, never start streaming
                for rt in self._rts.values():
                    try:
                        await rt.close(wait=0)
                    except Exception:
                        pass
                return
        self.start_wall = self.clock()
        if self.asr == "realtime":
            for ch, rt in self._rts.items():
                self._tasks.append(asyncio.create_task(self._stream(ch, rt)))
        sched = asyncio.create_task(self._schedule())
        self._tasks.append(sched)
        try:
            await sched
            remaining = self.end_wall - (self.clock() - self.start_wall)
            if remaining > 0:
                await asyncio.sleep(remaining)
            # force-finalise anything still open
            for ch in RADIO_CHANNELS:
                self._finalise(ch)
            await asyncio.gather(*[t for t in self._tasks if t is not sched], return_exceptions=True)
        finally:
            for rt in self._rts.values():
                try:
                    await rt.close(wait=3)
                except Exception:
                    log.exception("close failed")
            self.running = False

    async def _connect_all(self) -> None:
        from server.meta.asr import RealtimeTranscriber

        for ch in RADIO_CHANNELS:
            if not any(ln["channel"] == ch and ln["id"] in self._dur for ln in self._lines):
                continue
            rt = RealtimeTranscriber(on_event=lambda ev, ch=ch: self._on_asr(ch, ev))
            try:
                await rt.connect(lang=self.lang, mode="ENDPOINTING")
                self._rts[ch] = rt
            except Exception as e:
                log.error("ASR connect failed on %s: %s (channel continues without ASR)", ch, e)

    async def _stream(self, ch: str, rt: Any) -> None:
        try:
            await rt.stream_pcm(self._channel_pcm(ch), t0=self.start_wall)
        except Exception as e:
            log.error("ASR stream error on %s: %s (other channel keeps going)", ch, e)

    async def _sleep_until(self, wall_offset: float) -> None:
        assert self.start_wall is not None
        d = self.start_wall + wall_offset - self.clock()
        if d > 0:
            await asyncio.sleep(d)

    async def _schedule(self) -> None:
        for ln in sorted(self._lines, key=lambda x: self._wall_start[x["id"]]):
            await self._sleep_until(self._wall_start[ln["id"]])
            if not self.running:
                return
            kind = ln.get("kind")
            if kind == "ptt":
                _maybe_call(self.on_ptt_line, ln)
            elif kind == "agent":
                _maybe_call(self.on_agent_line, ln)
            elif ln["id"] in self._dur and ln["channel"] in RADIO_CHANNELS:
                self._keyup(ln)

    def _keyup(self, ln: dict[str, Any]) -> None:
        ch = ln["channel"]
        _maybe_call(self.on_audio_cue, {"channel": ch, "line_id": ln["id"], "audio_url": self.audio_url(ln["id"]),
                                        "t": float(ln["t"])})
        tx = Transmission(id=self._next_id(), channel=ch, unit_id=ln.get("unit"), line_id=ln["id"],
                          t_keyup=float(ln["t"]), audio_url=self.audio_url(ln["id"]), source="replay",
                          lang=self.lang if self.lang in ("ko", "en") else "ko")
        now = self.clock()
        self.keyup_wall[tx.id] = now
        assert self.start_wall is not None
        start = self.start_wall + self._wall_start[ln["id"]]
        end = start + self._dur[ln["id"]]
        _maybe_call(self.on_transmission, tx)
        if self.asr == "file":
            self._tasks.append(asyncio.create_task(self._file_asr(tx, end)))
            return
        if ch not in self._rts:
            log.warning("no ASR on %s; %s not transcribed", ch, ln["id"])
            return
        self._finalise(ch)  # next key-up on the channel closes the previous transmission
        op = _Open(tx=tx, clip_start_wall=start, clip_end_wall=end)
        self._open[ch] = op
        self._tasks.append(asyncio.create_task(self._watchdog(ch, op)))

    # ------------------------------------------------------------------ realtime merge
    def _on_asr(self, ch: str, ev: dict[str, Any]) -> None:
        typ = ev.get("type")
        if typ == "error":
            log.error("ASR error on %s: %s", ch, ev.get("message"))
            return
        op = self._open.get(ch)
        if op is None or op.done:
            if typ == "speechComplete" and ev.get("transcript"):
                log.info("late/orphan turn on %s dropped: %s", ch, ev.get("transcript"))
            return
        now = ev.get("_recv_ts") or self.clock()
        if typ == "transcript" and not ev.get("final"):
            op.partial = (ev.get("transcript") or "").strip()
            op.tx.text_partial = " ".join([*op.turns, op.partial]).strip()
            _maybe_call(self.on_transmission, op.tx)
        elif typ == "speechComplete" or (typ == "transcript" and ev.get("final")):
            txt = (ev.get("transcript") or op.partial or "").strip()
            if txt:
                op.turns.append(txt)
            op.partial = ""
            op.last_sc = now
            op.tx.text_partial = " ".join(op.turns)
            _maybe_call(self.on_transmission, op.tx)
            if now >= op.clip_end_wall:
                op.sc_after_end = True
                self._finalise(ch)

    async def _watchdog(self, ch: str, op: _Open) -> None:
        gap = self.settings.turn_merge_gap_s
        while not op.done:
            await asyncio.sleep(0.1)
            now = self.clock()
            if now < op.clip_end_wall:
                continue
            if op.last_sc is not None and now - op.last_sc >= gap and now >= op.clip_end_wall + 0.5:
                break
            if now >= op.clip_end_wall + 5.0:
                break
        if not op.done and self._open.get(ch) is op:
            self._finalise(ch)

    def _finalise(self, ch: str) -> None:
        op = self._open.get(ch)
        if op is None or op.done:
            return
        op.done = True
        self._open[ch] = None
        text = " ".join([*op.turns, op.partial]).strip()
        now = self.clock()
        tx = op.tx
        tx.text_final = text
        tx.text_partial = text
        assert self.start_wall is not None
        tx.t_final = round(self.timeline.t_of(now - self.start_wall), 2)
        self.asr_ms[tx.id] = max(0, int((now - op.clip_end_wall) * 1000))
        _maybe_call(self.on_final, tx)

    # ------------------------------------------------------------------ file fallback
    async def _file_asr(self, tx: Transmission, clip_end_wall: float) -> None:
        from server.meta.asr import ASRClient

        d = clip_end_wall - self.clock()
        if d > 0:
            await asyncio.sleep(d)
        try:
            res = await ASRClient().transcribe_file(self.wav_path(tx.line_id or ""), lang=self.lang)
        except Exception as e:
            log.error("file ASR failed for %s: %s", tx.line_id, e)
            return
        tx.text_final = res.text
        tx.text_partial = res.text
        assert self.start_wall is not None
        tx.t_final = round(self.timeline.t_of(self.clock() - self.start_wall), 2)
        self.asr_ms[tx.id] = res.latency_ms
        _maybe_call(self.on_final, tx)
