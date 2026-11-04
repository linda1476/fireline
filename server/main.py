"""Earshot FastAPI app: REST under /api, WS /ws, static /samples (docs/CONTRACT.md).

Run: uv run uvicorn server.main:app --port 8000
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

import asyncio
import json
import logging
import time
from typing import Any

import yaml
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server import cache as cache_mod
from server.cache import RunRecorder, RunReplayer
from server.config import ROOT, get_settings
from server.models import CREW_BUTTON_KO, Event, Latency, State, Transmission, Triage, WsMessage
from server.world import World
from server import rules

log = logging.getLogger("earshot")

# ----------------------------------------------------------------------------- optional siblings
try:
    from server.scenario import ScenarioPlayer
except Exception as e:  # pragma: no cover
    ScenarioPlayer = None  # type: ignore[assignment]
    log.warning("scenario unavailable: %s", e)
try:
    from server import gate
except Exception:  # pragma: no cover
    gate = None  # type: ignore[assignment]
try:
    from server import triage as triage_mod
except Exception:  # pragma: no cover
    triage_mod = None  # type: ignore[assignment]
try:
    from server import verify as verify_mod
except Exception:  # pragma: no cover
    verify_mod = None  # type: ignore[assignment]
try:
    from server.agent import RelevanceAgent
except Exception as e:  # pragma: no cover
    RelevanceAgent = None  # type: ignore[assignment]
    log.warning("agent unavailable: %s", e)
try:
    from server.router_fallback import route as router_route
except Exception:  # pragma: no cover
    router_route = None  # type: ignore[assignment]

S = get_settings()
RECORDER_GRACE_S = 30.0   # keep recording REST acks / late agent output this long after a LIVE run stops


# ----------------------------------------------------------------------------- runtime
class Runtime:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.world: World = World("hanbit", "ko", "LIVE", S, None, log_path=None)
        self.player: Any = None
        self.replayer: RunReplayer | None = None
        self.recorder: RunRecorder | None = None
        self.agent: Any = None
        self.audio = "radio"
        self.tasks: set[asyncio.Task] = set()       # per-run work (wakes, triage, PTT): cancelled on stop / start / reset
        self.service_tasks: set[asyncio.Task] = set()  # clock loop, recorder retirement: survive run changes

    def spawn(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
        return t

    def spawn_service(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self.service_tasks.add(t)
        t.add_done_callback(self.service_tasks.discard)
        return t

    async def cancel_run_tasks(self) -> None:
        """Cancel in-flight wakes / triage / PTT of the previous run (and the agent's late background wakes) so
        nothing stale reaches the next run's screens or its run file."""
        if self.agent is not None and hasattr(self.agent, "cancel_all"):
            self.agent.cancel_all()
        self.agent = None
        cur = asyncio.current_task()
        pending = [t for t in list(self.tasks) if t is not cur and not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.wait(pending, timeout=2)

    # -------------------------------------------------- broadcast
    async def send(self, msg: WsMessage) -> None:
        data = msg.model_dump(mode="json")
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def broadcast(self, msg: WsMessage):
        if self.recorder is not None and self.world.state.mode == "LIVE":
            self.recorder.record_ws(self.now_t(), msg)  # player clock, not the 1 Hz world tick (lags ≤1 s)
        return self.send(msg)

    def retire_recorder(self, delay: float = 0.0) -> None:
        """Close the LIVE run recorder now (delay 0) or after `delay` s, so late REST acks are still recorded."""
        rec = self.recorder
        if rec is None:
            return

        def _close() -> None:
            rec.close()
            if self.recorder is rec:
                self.recorder = None

        if delay <= 0:
            _close()
            return

        async def _later() -> None:
            await asyncio.sleep(delay)
            _close()

        self.spawn_service(_later())

    def record_rest(self, method: str, path: str, body: Any = None) -> None:
        if self.recorder is not None and self.world.state.mode == "LIVE":
            self.recorder.record_rest(self.now_t(), method, path, body)

    def now_t(self) -> float:
        if self.player is not None and getattr(self.player, "start_wall", None) is not None:
            return float(self.player.t())
        if self.replayer is not None and self.replayer.start_wall is not None:
            return float(self.replayer.t())
        return self.world.state.t

    @property
    def running(self) -> bool:
        if self.player is not None:
            return bool(getattr(self.player, "running", False))
        if self.replayer is not None:
            return self.replayer.running
        return False


RT = Runtime()
app = FastAPI(title="Earshot")


# ----------------------------------------------------------------------------- pipeline
async def wake(reason: str, event: Event | None) -> None:
    w = RT.world
    agent = RT.agent
    try:
        if agent is not None and getattr(agent, "world", w) is w:
            await asyncio.wait_for(agent.wake(reason, event), timeout=S.agent_timeout_s + 4)
            return
    except Exception as e:
        log.warning("agent wake failed: %s", type(e).__name__)
        w.state.counters.fallback_routes += 1
    if event is not None and router_route is not None and RT.world is w:
        try:
            router_route(event, w, reason="agent unavailable")
        except Exception:
            log.exception("router fallback failed")


def _local_button_triage(unit_id: str, kind: str) -> Triage:
    """Used only if server.triage is missing."""
    label = CREW_BUTTON_KO[kind]
    tag = {"EVACUATE": "MAYDAY", "VICTIM_HERE": "VICTIM_FOUND", "SEARCH_DONE": "ROUTINE", "NEED_HELP": "HELP_NEEDED"}[kind]
    data: dict[str, Any] = {"tag": tag, "speaker_unit": unit_id, "evidence_span": label, "needs_ack": tag != "ROUTINE",
                            "confidence": 1.0}
    if kind == "EVACUATE":
        data["distress"] = {"who": unit_id, "what": "OTHER"}
    if kind == "VICTIM_HERE":
        data["victims"] = {"state": "FOUND"}
    if kind == "SEARCH_DONE":
        data["status_change"] = "OK"
    return Triage.model_validate(data)


def _apply_and_wake(ev: Event, reason: str) -> list:
    # the world clock otherwise lags the 1 Hz tick; cards are stamped created_t = clock at creation (R1)
    RT.world.set_t(max(RT.world.state.t, RT.now_t()))
    cards = RT.world.apply_event(ev)
    if ev.triage.tag != "ROUTINE":
        RT.spawn(wake(reason, ev))
    return cards


async def process_final(tx: Transmission, keyup_wall: float | None = None, asr_ms: int | None = None,
                        source: str | None = None) -> Event | None:
    """text_final → gate → triage → verify/snap → Event → world.apply_event → agent ‖ router."""
    w = RT.world
    w.upsert_transmission(tx)
    text = tx.text_final or ""
    if gate is not None and not gate.should_triage(text):
        return None
    if not text.strip() or triage_mod is None:
        return None
    lang = w.state.lang
    try:
        tr, triage_ms, _usage = await triage_mod.triage(text, lang, tx.channel)
    except Exception as e:
        log.warning("triage failed for %s: %s", tx.id, type(e).__name__)
        w.add_trace(f"triage_{tx.id}", f"triage:{tx.id}", "fallback", {"reason": f"triage error {type(e).__name__}"})
        return None
    if RT.world is not w:
        return None  # reset while waiting
    verified, unit_id, zone_id = False, None, None
    if verify_mod is not None:
        try:
            verified, tr, unit_id, zone_id = verify_mod.snap_event(tr, text, lang)
        except Exception:
            log.exception("verify failed")
    if asr_ms is None and RT.player is not None:
        asr_ms = int(getattr(RT.player, "asr_ms", {}).get(tx.id, 0))
    if keyup_wall is None and RT.player is not None:
        keyup_wall = getattr(RT.player, "keyup_wall", {}).get(tx.id)
    total = int((time.perf_counter() - keyup_wall) * 1000) if keyup_wall else int((asr_ms or 0) + triage_ms)
    ev = Event(
        id=w.new_id("evt"), transmission_id=tx.id, t=float(tx.t_keyup), channel=tx.channel, text=text, triage=tr,
        speaker_unit_snapped=unit_id or tx.unit_id, zone_id_snapped=zone_id,
        latency=Latency(asr_ms=int(asr_ms or 0), triage_ms=int(triage_ms), total_ms=total),
        evidence_verified=verified, source=source or tx.source,
    )
    _apply_and_wake(ev, f"event:{ev.id}")
    return ev


async def ptt_clip(unit_id: str, clip_id: str, tx: Transmission) -> None:
    """One PUSH_TO_TALK realtime session per hold: stream the clip at 1x, endStream, take the final."""
    from server.meta.asr import RealtimeTranscriber, read_pcm

    w = RT.world
    wav = S.audio_dir / RT.audio / f"{clip_id}.wav"
    if not wav.exists():
        w.add_trace(f"ptt_{tx.id}", f"ptt:{unit_id}", "fallback", {"reason": f"clip {clip_id} missing"})
        return
    final = asyncio.Event()
    state: dict[str, Any] = {}

    def on_event(e: dict[str, Any]) -> None:
        if e.get("type") != "transcript":
            return
        text = e.get("transcript") or ""
        if text:
            tx.text_partial = text
        if e.get("final"):
            state["final_ts"] = e.get("_recv_ts", time.perf_counter())
            state["text"] = text or tx.text_partial
            final.set()
        elif RT.world is w:
            w.upsert_transmission(tx)

    keyup = time.perf_counter()
    rt = RealtimeTranscriber(on_event=on_event)
    try:
        await rt.connect(lang=w.state.lang, mode="PUSH_TO_TALK")
        w.emit("audio_cue", {"channel": "PTT", "line_id": clip_id, "audio_url": tx.audio_url, "t": tx.t_keyup})
        await rt.stream_pcm(read_pcm(wav))
        end_ts = time.perf_counter()
        await rt.end_stream()
        try:
            await asyncio.wait_for(final.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass
    except Exception as e:
        w.add_trace(f"ptt_{tx.id}", f"ptt:{unit_id}", "fallback", {"reason": f"ASR error {type(e).__name__}"})
        return
    finally:  # never leak the realtime socket (connect / stream errors, cancellation on stop)
        try:
            await rt.close(wait=2)
        except Exception:
            pass
    if RT.world is not w:
        return
    tx.text_final = state.get("text") or tx.text_partial or None
    tx.t_final = RT.now_t()
    asr_ms = int((state.get("final_ts", time.perf_counter()) - end_ts) * 1000)
    if tx.text_final:
        await process_final(tx, keyup_wall=keyup, asr_ms=asr_ms, source="ptt")
    else:
        w.upsert_transmission(tx)


def start_ptt(unit_id: str, clip_id: str) -> Transmission:
    w = RT.world
    t = RT.now_t()
    tx = Transmission(id=w.new_id("tx"), channel="PTT", unit_id=unit_id, line_id=clip_id, t_keyup=t,
                      audio_url=f"/samples/{RT.audio}/{clip_id}.wav", source="ptt", lang=w.state.lang)
    w.upsert_transmission(tx)
    RT.spawn(ptt_clip(unit_id, clip_id, tx))
    return tx


# ----------------------------------------------------------------------------- clock
async def clock_loop() -> None:
    while True:
        await asyncio.sleep(1.0)
        try:
            w = RT.world
            running = RT.running
            if running:
                t = RT.now_t()
                if w.state.mode == "LIVE":
                    actions = w.tick(t)
                    for a in actions:
                        if isinstance(a, rules.RuleCard):
                            RT.spawn(wake(f"rule:{a.rule_id}:{a.unit_id}", None))
                else:
                    w.set_t(t)
            if w.state.running and not running:
                w.state.running = False
                RT.retire_recorder(RECORDER_GRACE_S)
            await RT.send(WsMessage(type="clock", payload={"t": w.state.t, "running": w.state.running,
                                                           "mode": w.state.mode}))
        except Exception:
            log.exception("clock loop")


@app.on_event("startup")
async def _startup() -> None:
    RT.spawn_service(clock_loop())


# ----------------------------------------------------------------------------- replay fold (GET /api/state during REPLAY)
_LISTS = {"transmission": "transmissions", "event": "events", "card": "cards", "proposal": "proposals",
          "brief": "briefs", "trace": "trace"}


def fold_replay(w: World, msg: WsMessage) -> None:
    st, p = w.state, msg.payload
    try:
        if msg.type in _LISTS:
            lst = getattr(st, _LISTS[msg.type])
            model = type(lst[0]) if lst else None
            from server import models as M
            cls = {"transmission": M.Transmission, "event": M.Event, "card": M.Card, "proposal": M.Proposal,
                   "brief": M.Brief, "trace": M.TraceEntry}[msg.type]
            obj = cls.model_validate(p)
            for i, o in enumerate(lst):
                if o.id == obj.id:
                    lst[i] = obj
                    break
            else:
                lst.append(obj)
            del model
        elif msg.type == "unit":
            from server.models import Unit
            st.units[p["id"]] = Unit.model_validate(p)
        elif msg.type == "zone":
            from server.models import Zone
            st.zones[p["id"]] = Zone.model_validate(p)
        elif msg.type == "counters":
            from server.models import Counters
            st.counters = Counters.model_validate(p)
        elif msg.type == "strategy":
            st.strategy, st.strategy_event_id = p.get("strategy", st.strategy), p.get("event_id")
    except Exception:
        pass


# ----------------------------------------------------------------------------- REST
def _state() -> dict[str, Any]:
    st = RT.world.state
    st.running = RT.running if (RT.player or RT.replayer) else st.running
    return st.model_dump(mode="json")


async def _stop_all(recorder_grace_s: float = 0.0) -> None:
    if RT.player is not None:
        try:
            await RT.player.stop()
        except Exception:
            log.exception("player stop")
        RT.player = None
    if RT.replayer is not None:
        await RT.replayer.stop()
        RT.replayer = None
    if recorder_grace_s <= 0:
        # restart / reset: the previous run is over for good. (On a plain stop, in-flight wakes may still finish
        # into the same world during the recorder grace period.)
        await RT.cancel_run_tasks()
    RT.retire_recorder(recorder_grace_s)
    RT.world.state.running = False


@app.post("/api/scenario/start")
async def scenario_start(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    mode = (body.get("mode") or "LIVE").upper()
    scen = body.get("scenario") or "hanbit"
    lang = body.get("lang") or "ko"
    RT.audio = body.get("audio") or "radio"
    try:
        speed = float(body["speed"]) if body.get("speed") is not None else 1.0
    except (TypeError, ValueError):
        raise HTTPException(422, "speed must be a number")
    if speed <= 0:
        raise HTTPException(422, "speed must be > 0")
    await _stop_all()
    if mode == "REPLAY":
        w = World(scen, lang, "REPLAY", S, None, log_path=None)
        RT.world = w

        def on_replay(msg: WsMessage):
            fold_replay(w, msg)
            return RT.send(msg)

        run = body.get("run") or "best"
        note: str | None = None
        if run == "best" and not (cache_mod.CACHE_DIR / cache_mod.BEST_NAME).exists():
            newest = cache_mod.newest_run()
            if newest is not None:  # no best.jsonl promoted yet: play the newest recorded run, and say so
                run = newest.name
                note = f"best.jsonl missing, playing newest run {newest.name}"
        try:
            RT.replayer = RunReplayer(run, on_replay, on_t=w.set_t)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        w.state.running = True
        await RT.send(WsMessage(type="snapshot", payload=w.state.model_dump(mode="json")))
        if note:
            log.warning(note)
            await RT.send(WsMessage(type="toast", payload={"method": "INFO", "path": note, "body": {"run": run}, "t": 0.0}))
        await RT.replayer.start()
        out = _state()
        if note:
            out["replay_note"] = note
        return out

    if ScenarioPlayer is None:
        raise HTTPException(503, "scenario player unavailable")
    RT.recorder = RunRecorder()
    w = World(scen, lang, "LIVE", S, RT.broadcast)
    RT.world = w
    RT.agent = None
    if RelevanceAgent is not None:
        try:
            from server.meta.spark import SparkClient
            RT.agent = RelevanceAgent(w, SparkClient(S))
        except Exception as e:
            log.warning("agent init failed: %s", type(e).__name__)
    RT.record_rest("POST", "/api/scenario/start", body)

    def on_final(tx: Transmission):
        if RT.world is w:  # a stopped player finalising its tail must not land in the next run
            RT.spawn(process_final(tx))

    def on_ptt_line(ln: dict[str, Any]):
        start_ptt(ln.get("unit") or "kim", ln["id"])

    RT.player = ScenarioPlayer(
        scen, lang, RT.audio, "LIVE",
        on_transmission=w.upsert_transmission, on_final=on_final,
        on_audio_cue=lambda cue: w.emit("audio_cue", cue), on_ptt_line=on_ptt_line,
        on_agent_line=lambda ln: None,  # L12 is produced by R2 itself
        clock=time.perf_counter, id_factory=lambda: w.new_id("tx"), speed=speed,
    )
    w.state.running = True
    await RT.send(WsMessage(type="snapshot", payload=w.state.model_dump(mode="json")))
    await RT.player.start()
    return _state()


@app.post("/api/scenario/stop")
async def scenario_stop() -> dict[str, Any]:
    RT.record_rest("POST", "/api/scenario/stop")
    await _stop_all(recorder_grace_s=RECORDER_GRACE_S)
    return _state()


@app.post("/api/scenario/reset")
async def scenario_reset() -> dict[str, Any]:
    st = RT.world.state
    await _stop_all()  # also cancels in-flight wakes and drops RT.agent (crew buttons then use the router)
    RT.world = World(st.scenario_id, st.lang, st.mode, S, RT.broadcast if st.mode == "LIVE" else None, log_path=None)
    await RT.send(WsMessage(type="snapshot", payload=RT.world.state.model_dump(mode="json")))
    return _state()


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    return _state()


@app.get("/api/scenario/lines")
async def scenario_lines(scenario: str = "hanbit") -> list[dict[str, Any]]:
    p = S.data_dir / f"scenario_{scenario}.yaml"
    if not p.exists():
        raise HTTPException(404, "scenario not found")
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("lines", [])


def _replay_guard() -> bool:
    return RT.world.state.mode == "REPLAY"


def _sync_t() -> None:
    """REST actions carry the current scenario clock (the 1 Hz tick may lag; after the run it stays put)."""
    RT.world.set_t(max(RT.world.state.t, RT.now_t()))


@app.get("/api/runs")
async def list_runs() -> list[dict[str, Any]]:
    return cache_mod.list_runs()


@app.post("/api/runs/{file}/promote")
async def promote_run(file: str) -> dict[str, Any]:
    try:
        dst = cache_mod.promote(file)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"promoted": file, "best": dst.name, "size": dst.stat().st_size, "t_max": cache_mod.run_t_max(dst)}


@app.post("/api/cards/{card_id}/ack")
async def card_ack(card_id: str) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    _sync_t()
    RT.record_rest("POST", f"/api/cards/{card_id}/ack")
    c = RT.world.ack_card(card_id)
    if c is None:
        raise HTTPException(404, "card not found")
    return c.model_dump(mode="json")


@app.post("/api/cards/{card_id}/resolve")
async def card_resolve(card_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    _sync_t()
    RT.record_rest("POST", f"/api/cards/{card_id}/resolve", body)
    c = RT.world.resolve_card(card_id, body.get("note"))
    if c is None:
        raise HTTPException(404, "card not found")
    return c.model_dump(mode="json")


async def _decide(pid: str, approve: bool) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    _sync_t()
    RT.record_rest("POST", f"/api/proposals/{pid}/{'approve' if approve else 'reject'}")
    p = RT.world.decide_proposal(pid, approve)
    if p is None:
        raise HTTPException(404, "proposal not found")
    if approve and p.state == "approved":
        RT.spawn(wake(f"proposal_approved:{p.id}", None))
    return p.model_dump(mode="json")


@app.post("/api/proposals/{pid}/approve")
async def proposal_approve(pid: str) -> dict[str, Any]:
    return await _decide(pid, True)


@app.post("/api/proposals/{pid}/reject")
async def proposal_reject(pid: str) -> dict[str, Any]:
    return await _decide(pid, False)


@app.patch("/api/proposals/{pid}")
async def proposal_edit(pid: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    RT.record_rest("PATCH", f"/api/proposals/{pid}", body)
    p = RT.world.edit_proposal(pid, str(body.get("text") or ""))
    if p is None:
        raise HTTPException(404, "proposal not found")
    return p.model_dump(mode="json")


@app.post("/api/crew/{unit_id}/button")
async def crew_button(unit_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    kind = body.get("kind")
    w = RT.world
    u = w.state.units.get(unit_id)
    if u is None:
        raise HTTPException(404, "unit not found")
    if kind not in CREW_BUTTON_KO:
        raise HTTPException(422, "kind must be EVACUATE/VICTIM_HERE/SEARCH_DONE/NEED_HELP")
    RT.record_rest("POST", f"/api/crew/{unit_id}/button", body)
    t = RT.now_t()
    w.set_t(t)
    zone = w.state.zones.get(u.zone_id) if u.zone_id else None
    zone_label = (zone.label_ko if w.state.lang == "ko" else zone.label_en) if zone else None
    if triage_mod is not None and hasattr(triage_mod, "triage_button"):
        tr = triage_mod.triage_button(u, kind, w.state.lang, zone_label=zone_label, floor=zone.floor if zone else None)
        text = triage_mod.button_label(kind, w.state.lang)
    else:
        tr, text = _local_button_triage(unit_id, kind), CREW_BUTTON_KO[kind]
    tx = Transmission(id=w.new_id("tx"), channel="PTT", unit_id=unit_id, t_keyup=t, t_final=t, text_final=text,
                      source="ptt", lang=w.state.lang)
    w.upsert_transmission(tx)
    ev = Event(id=w.new_id("evt"), transmission_id=tx.id, t=t, channel="PTT", text=text, triage=tr,
               speaker_unit_snapped=unit_id, zone_id_snapped=u.zone_id, evidence_verified=True, source="button")
    if kind == "SEARCH_DONE" and zone is not None:
        zone.search_state = "searched"
        w.emit("zone", zone)
    _apply_and_wake(ev, f"button:{unit_id}:{kind}")
    return ev.model_dump(mode="json")


@app.post("/api/crew/{unit_id}/ptt")
async def crew_ptt(unit_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    if unit_id not in RT.world.state.units:
        raise HTTPException(404, "unit not found")
    clip = body.get("clip_id")
    if not clip:
        raise HTTPException(422, "clip_id required")
    RT.record_rest("POST", f"/api/crew/{unit_id}/ptt", body)
    return start_ptt(unit_id, clip).model_dump(mode="json")


@app.post("/api/crew/{unit_id}/ack")
async def crew_ack(unit_id: str) -> dict[str, Any]:
    if _replay_guard():
        raise HTTPException(409, "REPLAY: actions are ignored")
    RT.record_rest("POST", f"/api/crew/{unit_id}/ack")
    RT.world.set_t(RT.now_t())
    u = RT.world.crew_ack(unit_id)
    if u is None:
        raise HTTPException(404, "unit not found")
    return u.model_dump(mode="json")


@app.get("/api/eval/results")
async def eval_results():
    p = S.eval_dir / "results.json"
    if not p.exists():
        raise HTTPException(404, "eval/results.json not found (run eval/run_eval.py)")
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")))


# ----------------------------------------------------------------------------- WS
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json({"type": "snapshot", "payload": _state()})
    RT.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # client → server: nothing; just detect disconnect
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        RT.clients.discard(ws)


# static audio (after routes)
if S.audio_dir.exists():
    app.mount("/samples", StaticFiles(directory=str(S.audio_dir)), name="samples")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="127.0.0.1", port=8000)
