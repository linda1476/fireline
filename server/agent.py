"""Relevance agent: muse-spark-1.3 Responses API tool loop (docs/CONTRACT.md "Relevance agent").

"Autonomy over information, not over orders": the agent pushes/holds briefs, asks for missing SOP 109 fields,
escalates to the IC and *proposes* orders; it never sends orders to crews. Every tool call goes through
server.checker first; rejections are returned as {"ok": false, "error"} plus an explicit retry request
(the model does not retry on its own, research/smoke_b1.md §6). Wall timeout -> server.router_fallback delivers
immediately, and the wake keeps running in the background: late tool calls are still applied when they pass the
checker and are not duplicates of a brief already delivered to that unit for the same evidence event.

Demo (network): uv run python -m server.agent demo [danger|mayday]
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from server import checker, router_fallback
from server.config import Settings, get_settings
from server.models import Brief, Card, Event, Proposal, State, TraceEntry, Triage, Unit

MAX_ROUNDS = 3
# round 1 is kept cheap (small snapshot, short budget); later rounds 4000. Env override for measurement only.
ROUND1_MAX_OUTPUT_TOKENS = int(os.environ.get("EARSHOT_AGENT_ROUND1_TOKENS", "1500"))
LATER_MAX_OUTPUT_TOKENS = 4000
LATE_WAKE_CAP_S = 45.0            # a wake that missed agent_timeout_s may keep running in the background this long
CREW_ROLES = ("CREW", "RIT", "EXTERIOR")
log = logging.getLogger("earshot.agent")
_EV = {"evidence_event_id": {"type": "string", "description": "id of the Event that justifies this call (evt_...)"}}


def _fn(name: str, desc: str, props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "name": name, "description": desc, "strict": True,
            "parameters": {"type": "object", "additionalProperties": False, "properties": props,
                           "required": list(props.keys())}}


_S = {"type": "string"}
TOOLS: list[dict[str, Any]] = [
    _fn("get_unit_state", "Read one unit's current state (zone, assignment, status, last briefs).", {"unit_id": _S}),
    _fn("send_brief", "Push a short information brief (max 2 sentences, 140 chars, in the incident language) to ONE crew "
        "unit. Information only, never an order. P1/P2 only to units in/assigned to the affected sector; P0 only for "
        "crew-safety (MAYDAY). Never to the unit in distress about its own mayday.",
        {"unit_id": _S, "text": _S, "priority": {"type": "string", "enum": ["P0", "P1", "P2"]},
         "reason": _S, **_EV}),
    _fn("hold", "Deliberately do NOT interrupt a unit with this event (not their sector / not actionable for them).",
        {"unit_id": _S, "event_id": _S, "reason": _S}),
    _fn("request_missing_field", "Ask a unit for a missing SOP 109 MAYDAY field (who/what/where/needs/air).",
        {"unit_id": _S, "field": {"type": "string", "enum": ["who", "what", "where", "needs", "air"]}, **_EV}),
    _fn("escalate_to_ic", "Escalate the card of this event to the Incident Commander.", {"event_id": _S, "reason": _S}),
    _fn("propose_order", "Propose an order for the IC to approve (never sent to crews directly).",
        {"kind": {"type": "string", "enum": ["RADIO_SILENCE", "RIT_DEPLOY", "WITHDRAW", "CONFIRM_STRATEGY", "ASSIGN"]},
         "units": {"type": "array", "items": _S}, "text": _S, "rationale": _S, **_EV}),
    _fn("ping_unit", "Radio check a unit that has gone silent.", {"unit_id": _S}),
]

SYSTEM_PROMPT = """You are Earshot's relevance agent on a Korean fireground radio net. Principle: autonomy over information, not over orders.
- You decide WHO hears WHAT. You never send orders to crews: only short information briefs. Any order (radio silence, RIT deploy, withdraw, strategy, assignment) becomes propose_order for the Incident Commander to approve.
- Crew attention is scarce. Push P1/P2 briefs ONLY to units in, entering or assigned to the affected sector (the event zone, its parent/child zones, or the zone directly above/below it). For every other interior crew unit call hold with a reason like "not your sector (zone X)".
- MAYDAY (긴급탈출) = crew safety: P0 brief to all OTHER interior units, escalate_to_ic, and use request_missing_field for missing SOP 109 fields (who/what/where/needs/air) from the unit in distress. Never brief the unit in distress (event.distressed_unit) about its own mayday.
- Brief text: at most 2 sentences and 140 characters, in language "{lang}" (ko = Korean, keep terms 긴급탈출/구조대상자/우선탐색/인화물질). State the fact and where; an exit/safety reminder is fine, commands are not.
- Every call cites the triggering event id (evidence_event_id or event_id). Use only unit ids from the snapshot.
- Call all needed tools in one turn when you can. If a call is rejected, fix it and call again."""

FIELD_Q = {
    "ko": {"who": "소속과 성명 알려주세요.", "what": "현재 상황 알려주세요.", "where": "현재 위치 알려주세요.",
           "needs": "필요한 지원 알려주세요.", "air": "공기잔량 알려주세요."},
    "en": {"who": "Say your unit and name.", "what": "Say your situation.", "where": "Say your location.",
           "needs": "Say what you need.", "air": "Say your air remaining."},
}


class WorldLike(Protocol):
    """What the agent needs from server.world.World (CONTRACT)."""

    state: State

    def add_brief(self, **kw: Any) -> Brief: ...
    def add_trace(self, **kw: Any) -> TraceEntry: ...
    def add_proposal(self, **kw: Any) -> Proposal: ...
    def escalate(self, card_id: str, level: int, reason: str | None = None) -> Any: ...
    def ping_unit(self, unit_id: str) -> Any: ...
    def broadcast(self, type: str, payload: dict[str, Any]) -> Any: ...


# ----------------------------------------------------------------------------- helpers
def recent_pushes(state: State) -> dict[str, float]:
    out: dict[str, float] = {}
    for b in state.briefs:
        if b.decision == "push" and b.priority != "P0":
            out[b.unit_id] = max(out.get(b.unit_id, -1e9), b.created_t)
    return out


def card_for_event(state: State, event_id: str) -> Card | None:
    for c in state.cards:
        if event_id in c.event_ids:
            return c
    return None


def _event_view(event: Event, state: State) -> dict[str, Any]:
    return {"id": event.id, "t": event.t, "channel": event.channel, "text": event.text,
            "tag": event.triage.tag, "speaker_unit": event.speaker_unit_snapped,
            "distressed_unit": checker.distressed_unit(event, state),
            "zone_id": event.zone_id_snapped, "hazard_terms": event.triage.hazard_terms,
            "distress": event.triage.distress.model_dump() if event.triage.distress else None,
            "victims": event.triage.victims.model_dump() if event.triage.victims else None,
            "crew_brief": event.triage.crew_brief, "evidence_span": event.triage.evidence_span,
            "related_zones": sorted(checker.related_zones(event.zone_id_snapped, state))}


def snapshot(state: State, event: Event | None) -> dict[str, Any]:
    """Full snapshot (all units, all zones, last 3 briefs per unit). Kept for debugging / get_unit_state-style reads."""
    briefs: dict[str, list[dict[str, Any]]] = {}
    for b in state.briefs:
        briefs.setdefault(b.unit_id, []).append({"t": b.created_t, "decision": b.decision, "priority": b.priority, "text": b.text})
    units = [{"id": u.id, "callsign": u.callsign, "name": u.name, "role": u.role, "zone_id": u.zone_id,
              "assignment": u.assignment, "status": u.status, "interior": u.interior, "last_heard_t": u.last_heard_t,
              "last_briefs": briefs.get(u.id, [])[-3:]} for u in state.units.values()]
    zones = [{"id": z.id, "floor": z.floor, "label": z.label_ko if state.lang == "ko" else z.label_en, "parent": z.parent,
              "hazards": [h.text for h in z.hazards]} for z in checker.zones_of(state).values()]
    cards = [{"id": c.id, "kind": c.kind, "title": c.title, "state": c.state, "unit_id": c.unit_id, "zone_id": c.zone_id,
              "event_ids": c.event_ids, "missing_fields": c.missing_fields, "escalation_level": c.escalation_level}
             for c in state.cards if c.state in ("open", "escalated")]
    snap: dict[str, Any] = {"t": state.t, "lang": state.lang, "strategy": state.strategy, "units": units, "zones": zones,
                            "open_cards": cards}
    if event is not None:
        snap["event"] = _event_view(event, state)
    return snap


def snapshot_round1(state: State, event: Event | None) -> dict[str, Any]:
    """Cheap first-round snapshot: open cards only, crew-type units only (CREW/RIT/EXTERIOR), zones that carry
    hazards/victims (plus the event zone), last 1 brief per unit. The event carries related_zones, so sector
    adjacency is still decidable."""
    last: dict[str, dict[str, Any]] = {}
    for b in state.briefs:
        last[b.unit_id] = {"t": b.created_t, "decision": b.decision, "priority": b.priority, "text": b.text}
    units = [{"id": u.id, "callsign": u.callsign, "name": u.name, "role": u.role, "zone_id": u.zone_id,
              "assignment": u.assignment, "status": u.status, "interior": u.interior,
              **({"last_brief": last[u.id]} if u.id in last else {})}
             for u in state.units.values() if u.role in CREW_ROLES]
    ez = event.zone_id_snapped if event is not None else None
    zones = [{"id": z.id, "floor": z.floor, "parent": z.parent, "hazards": [h.text for h in z.hazards][-3:],
              "victims": len(z.victim_reports)}
             for z in checker.zones_of(state).values() if z.hazards or z.victim_reports or z.id == ez]
    cards = [{"id": c.id, "kind": c.kind, "state": c.state, "unit_id": c.unit_id, "zone_id": c.zone_id,
              "event_ids": c.event_ids, "missing_fields": c.missing_fields, "escalation_level": c.escalation_level}
             for c in state.cards if c.state in ("open", "escalated")]
    snap: dict[str, Any] = {"t": state.t, "lang": state.lang, "strategy": state.strategy, "units": units,
                            "zones": zones, "open_cards": cards}
    if event is not None:
        snap["event"] = _event_view(event, state)
    return snap


def _reasoning_summary(item: Any) -> str:
    parts = []
    for s in getattr(item, "summary", None) or []:
        txt = getattr(s, "text", None) if not isinstance(s, dict) else s.get("text")
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


@dataclass
class WakeCtx:
    """Per-wake state, so a wake that keeps running in the background does not clobber the next wake."""

    wake_id: str
    reason: str
    t0: float = field(default_factory=time.perf_counter)
    decided: set[str] = field(default_factory=set)
    late: bool = False          # True once the router fallback has delivered (agent_timeout_s passed)
    first_call_ms: int | None = None
    round_ms: list[int] = field(default_factory=list)


# ----------------------------------------------------------------------------- agent
class RelevanceAgent:
    def __init__(self, world: Any, spark: Any, settings: Settings | None = None):
        self.world = world
        self.spark = spark
        self.settings = settings or get_settings()
        self._n = 0
        self._bg: set[asyncio.Task] = set()   # wakes still running after the fallback delivered
        # default context for direct execute() calls (tests); wake() passes its own WakeCtx
        self._wake_id, self._reason, self._decided = "local", "local", set()

    def _default_ctx(self) -> WakeCtx:
        return WakeCtx(self._wake_id, self._reason, decided=self._decided)

    def _trace(self, kind: str, payload: dict[str, Any], ctx: WakeCtx | None = None) -> None:
        ctx = ctx or self._default_ctx()
        if ctx.late:
            payload = {**payload, "late": True}
        self.world.add_trace(wake_id=ctx.wake_id, wake_reason=ctx.reason, kind=kind, payload=payload)

    async def wake(self, reason: str, event: Event | None = None) -> dict[str, Any]:
        """Run the tool loop. At agent_timeout_s the router fallback delivers and wake() returns, but the loop keeps
        running in the background (≤ LATE_WAKE_CAP_S); its late calls go through the checker + duplicate filter."""
        self._n += 1
        wid = f"wake_{self._n:04d}_{int(time.time() * 1000) % 100000}"
        ctx = WakeCtx(wid, f"{reason} {event.triage.tag}" if event is not None and event.id in reason else reason)
        st = self.world.state
        st.counters.agent_wakes += 1
        result: dict[str, Any] = {"wake_id": wid, "fallback": False, "calls": 0, "rejections": 0}
        task = asyncio.ensure_future(self._loop(event, result, ctx))
        try:
            done, _ = await asyncio.wait({task}, timeout=self.settings.agent_timeout_s)
        except asyncio.CancelledError:
            task.cancel()
            raise
        why: str | None = None
        if task in done:
            exc = task.exception()
            if exc is not None:
                why = f"error: {type(exc).__name__}: {str(exc)[:160]}"
        else:
            why = "timeout"
        if why is not None:
            result["fallback"] = True
            result["fallback_reason"] = why
            st.counters.fallback_routes += 1
            if event is not None and event.triage.tag != "ROUTINE":
                self._fallback(event, why, ctx)
            else:
                self._trace("fallback", {"reason": why}, ctx)
        elif event is not None and event.triage.tag != "ROUTINE":
            # the loop ended on its own (text-only answer, rejected retry, partial calls): crew units the agent left
            # undecided still get the router's decision, so nobody misses a MAYDAY P0 or a hold
            gap = router_fallback.route(event, self.world, wake_id=ctx.wake_id, reason="agent gap fill",
                                        skip_units=set(ctx.decided), wake_reason=ctx.reason, gap_fill=True)
            if gap:
                result["gap_filled"] = [b.unit_id for b in gap]
        if task not in done:
            ctx.late = True
            result["late"] = True
            self._continue_late(task, ctx, result)
        result["first_call_ms"] = ctx.first_call_ms
        result["round_ms"] = list(ctx.round_ms)
        result["wake_ms"] = int((time.perf_counter() - ctx.t0) * 1000)
        self._ensure_mayday_escalated(ctx)
        return result

    def _continue_late(self, task: asyncio.Future, ctx: WakeCtx, result: dict[str, Any]) -> None:
        async def _finish() -> None:
            try:
                await asyncio.wait_for(task, timeout=max(0.0, LATE_WAKE_CAP_S - self.settings.agent_timeout_s))
                self._trace("wake", {"late_done_ms": int((time.perf_counter() - ctx.t0) * 1000),
                                     "first_call_ms": ctx.first_call_ms, "calls": result["calls"]}, ctx)
            except asyncio.CancelledError:
                task.cancel()
                raise
            except Exception as e:  # late timeout / API error: the fallback already delivered
                log.info("late wake %s ended: %s", ctx.wake_id, type(e).__name__)
            self._ensure_mayday_escalated(ctx)

        bg = asyncio.ensure_future(_finish())
        self._bg.add(bg)
        bg.add_done_callback(self._bg.discard)

    def cancel_all(self) -> None:
        """Stop background (late) wakes: called when the run stops / restarts so they never write to a new run."""
        for t in list(self._bg):
            t.cancel()
        self._bg.clear()

    async def drain(self, timeout: float = LATE_WAKE_CAP_S) -> None:
        """Wait for background (late) wakes; used by the demo / CLI."""
        if self._bg:
            await asyncio.wait(set(self._bg), timeout=timeout)

    def _fallback(self, event: Event, why: str, ctx: WakeCtx | None = None) -> None:
        ctx = ctx or self._default_ctx()
        # Units the agent already handled before the cut keep the agent's decision.
        router_fallback.route(event, self.world, wake_id=ctx.wake_id, reason=why, skip_units=set(ctx.decided),
                              wake_reason=ctx.reason)

    def _ensure_mayday_escalated(self, ctx: WakeCtx | None = None) -> None:
        """Invariant 5 at wake end."""
        for c in checker.open_unescalated_maydays(self.world.state):
            ev_id = c.event_ids[0] if c.event_ids else None
            self._trace("tool_call", {"tool": "escalate_to_ic", "args": {"event_id": ev_id, "reason": "invariant 5: MAYDAY unacked"},
                                      "call_id": "auto", "auto": True}, ctx)
            self.world.escalate(c.id, max(1, c.escalation_level), "invariant 5: MAYDAY unacked")
            self._trace("delivery", {"card_id": c.id, "decision": "escalate", "auto": True}, ctx)

    async def _loop(self, event: Event | None, result: dict[str, Any], ctx: WakeCtx) -> None:
        st = self.world.state
        client = self.spark.async_client
        snap = snapshot_round1(st, event)
        user = (f"Wake reason: {ctx.reason}\nDecide who hears this. Snapshot (JSON):\n"
                + json.dumps(snap, ensure_ascii=False, separators=(",", ":")))
        inp: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT.replace("{lang}", st.lang)},
            {"role": "user", "content": user},
        ]
        prev_id: str | None = None
        rnd = 0
        budget = ROUND1_MAX_OUTPUT_TOKENS
        pending_rejections: list[str] = []
        while rnd < MAX_ROUNDS:
            rnd += 1
            self._trace("wake", {"snapshot_size": len(user), "round": rnd, "max_output_tokens": budget,
                                 "effort": self.settings.agent_round1_reasoning_effort if rnd == 1
                                 else self.settings.agent_reasoning_effort}, ctx)
            kwargs: dict[str, Any] = dict(
                model=self.settings.spark_model, input=inp, tools=TOOLS, tool_choice="auto",
                reasoning={"effort": self.settings.agent_round1_reasoning_effort if rnd == 1 and prev_id is None
                           else self.settings.agent_reasoning_effort, "summary": "concise"},
                max_output_tokens=budget,
            )
            if prev_id:
                kwargs["previous_response_id"] = prev_id
            r0 = time.perf_counter()
            resp = await client.responses.create(**kwargs)
            rtt = int((time.perf_counter() - r0) * 1000)
            ctx.round_ms.append(rtt)
            calls = []
            summaries: list[str] = []
            messages: list[str] = []
            for item in resp.output or []:
                typ = getattr(item, "type", None)
                if typ == "reasoning":
                    s = _reasoning_summary(item)
                    if s:
                        summaries.append(s)
                elif typ == "function_call":
                    calls.append(item)
                elif typ == "message":
                    m = _message_text(item)
                    if m:
                        messages.append(m)
            status = getattr(resp, "status", None)
            if not calls and status == "incomplete" and budget < LATER_MAX_OUTPUT_TOKENS:
                # the short round-1 budget ran out inside reasoning: re-issue the same round with the full budget
                self._trace("wake", {"round": rnd, "rtt_ms": rtt, "status": status, "retry_budget": LATER_MAX_OUTPUT_TOKENS}, ctx)
                budget = LATER_MAX_OUTPUT_TOKENS
                rnd -= 1
                continue
            prev_id = resp.id
            budget = LATER_MAX_OUTPUT_TOKENS
            for s in summaries:
                self._trace("reasoning", {"summary": s, "round": rnd}, ctx)
            for m in messages:  # text answers (commentary, refusal to retry) explain why a wake ended
                self._trace("reasoning", {"summary": m[:500], "round": rnd, "from": "message"}, ctx)
            if not calls:
                if pending_rejections:
                    self._trace("reasoning", {"summary": "retry abandoned after rejection: "
                                              + " | ".join(pending_rejections)[:300], "round": rnd, "from": "agent"}, ctx)
                break
            if ctx.first_call_ms is None:
                ctx.first_call_ms = int((time.perf_counter() - ctx.t0) * 1000)
            if not summaries:
                for c in calls:
                    a = _parse_args(c.arguments)
                    if isinstance(a, dict) and a.get("reason"):
                        self._trace("reasoning", {"summary": a["reason"], "round": rnd, "from": "tool args"}, ctx)
                        break
            outputs: list[dict[str, Any]] = []
            rejected: list[str] = []
            for c in calls:
                res = self.execute(c.name, _parse_args(c.arguments), c.call_id, ctx)
                result["calls"] += 1
                if not res.get("ok"):
                    result["rejections"] += 1
                    rejected.append(f"{c.name}: {res.get('error')}")
                outputs.append({"type": "function_call_output", "call_id": c.call_id,
                                "output": json.dumps(res, ensure_ascii=False)})
            inp = outputs
            pending_rejections = rejected
            if rejected:
                inp = outputs + [{"role": "user", "content": "Call rejected: " + " | ".join(rejected)
                                  + ". Retry with a corrected call or choose another action."}]
            elif not any(c.name == "get_unit_state" for c in calls):
                # all ok: one more round only if the model might want to follow up (e.g. after get_unit_state)
                break

    # ------------------------------------------------------------------ tool execution (also used by tests)
    def execute(self, tool: str, args: Any, call_id: str = "local", ctx: WakeCtx | None = None) -> dict[str, Any]:
        st = self.world.state
        ctx = ctx or self._default_ctx()
        self._trace("tool_call", {"tool": tool, "args": args, "call_id": call_id}, ctx)
        # duplicate first: a late call after the router already pushed this event to this unit is a no-op, not a
        # rejection (the rate limit, invariant 2, would otherwise reject it and prompt a pointless retry)
        dup = duplicate_brief(st, tool, args) if isinstance(args, dict) else None
        if dup is not None:
            self._trace("delivery", {"unit_id": args.get("unit_id"), "decision": "duplicate", "brief_id": dup.id}, ctx)
            return {"ok": True, "deduped": True, "brief_id": dup.id}
        if not isinstance(args, dict):
            ok, err = False, "arguments are not valid JSON object"
        else:
            ok, err = checker.check(tool, args, st, st.t, recent_pushes(st))
        self._trace("checker", {"tool": tool, "call_id": call_id, "ok": ok, "error": err}, ctx)
        if not ok:
            st.counters.checker_rejections += 1
            return {"ok": False, "error": err}
        try:
            return self._apply(tool, args, ctx)
        except Exception as e:
            return {"ok": False, "error": f"apply failed: {type(e).__name__}: {e}"}

    def _apply(self, tool: str, a: dict[str, Any], ctx: WakeCtx | None = None) -> dict[str, Any]:
        ctx = ctx or self._default_ctx()
        st = self.world.state
        if tool == "get_unit_state":
            u = st.units[a["unit_id"]]
            data = u.model_dump(mode="json")
            data["last_briefs"] = [b.model_dump(mode="json") for b in st.briefs if b.unit_id == u.id][-3:]
            return {"ok": True, "unit": data}
        if tool == "ping_unit":
            self.world.ping_unit(a["unit_id"])
            self._trace("delivery", {"unit_id": a["unit_id"], "decision": "ping"}, ctx)
            return {"ok": True}
        if tool in ("send_brief", "hold"):
            push = tool == "send_brief"
            text = a.get("text") or ""
            if not push:  # held briefs carry what was held (event crew_brief) so the UI can show it
                ev = checker.find_event(st, a.get("event_id"))
                text = (ev.triage.crew_brief or ev.text[:140]) if ev else ""
            b = self.world.add_brief(
                unit_id=a["unit_id"], decision="push" if push else "hold",
                text=text, priority=a.get("priority", "P2") if push else "P2",
                reason=a.get("reason", ""), evidence_event_id=a.get("evidence_event_id") or a.get("event_id"),
                source="agent")
            ctx.decided.add(a["unit_id"])
            self._trace("delivery", {"brief_id": b.id, "unit_id": a["unit_id"], "decision": b.decision}, ctx)
            return {"ok": True, "brief_id": b.id}
        if tool == "request_missing_field":
            lang = st.lang if st.lang in FIELD_Q else "en"
            u = st.units[a["unit_id"]]
            text = f"{u.callsign}, {FIELD_Q[lang][a['field']]}"
            self.world.broadcast("ask", {"unit_id": u.id, "field": a["field"], "text": text})
            b = self.world.add_brief(unit_id=u.id, decision="push", text=text, priority="P0",
                                     reason=f"SOP 109 missing field: {a['field']}",
                                     evidence_event_id=a.get("evidence_event_id"), source="agent")
            ctx.decided.add(u.id)
            self._trace("delivery", {"brief_id": b.id, "unit_id": u.id, "decision": "push", "ask": a["field"]}, ctx)
            return {"ok": True, "brief_id": b.id}
        if tool == "escalate_to_ic":
            card = card_for_event(st, a["event_id"])
            if card is None:
                return {"ok": False, "error": f"no card for event {a['event_id']}"}
            level = max(1, card.escalation_level)
            self.world.escalate(card.id, level, a.get("reason"))
            self._trace("delivery", {"card_id": card.id, "decision": "escalate", "level": level}, ctx)
            return {"ok": True, "card_id": card.id, "level": level}
        if tool == "propose_order":
            card = card_for_event(st, a["evidence_event_id"])
            dup = next((p for p in st.proposals if p.kind == a["kind"] and p.state in ("pending", "edited")
                        and p.evidence_event_id == a["evidence_event_id"]), None)
            if dup is not None:
                return {"ok": True, "deduped": True, "proposal_id": dup.id, "state": dup.state}
            p = self.world.add_proposal(kind=a["kind"], units=list(a.get("units") or []), text=a["text"],
                                        rationale=a.get("rationale", ""), evidence_event_id=a["evidence_event_id"],
                                        card_id=card.id if card else None, source="agent")
            self._trace("delivery", {"proposal_id": p.id, "decision": "proposal", "kind": a["kind"]}, ctx)
            return {"ok": True, "proposal_id": p.id, "state": p.state}
        return {"ok": False, "error": f"unknown tool {tool}"}


def duplicate_brief(st: State, tool: str, a: dict[str, Any]) -> Brief | None:
    """A brief already delivered to this unit for the same evidence event: for send_brief an existing push
    (e.g. the router fallback pushed it before a late agent call); for hold any existing brief."""
    if tool not in ("send_brief", "hold"):
        return None
    uid = a.get("unit_id")
    ev = a.get("evidence_event_id") or a.get("event_id")
    for b in reversed(st.briefs):
        if b.unit_id != uid or b.evidence_event_id != ev:
            continue
        if tool == "hold" or b.decision == "push":
            return b
    return None


def _message_text(item: Any) -> str:
    parts = []
    for c in getattr(item, "content", None) or []:
        txt = c.get("text") if isinstance(c, dict) else getattr(c, "text", None)
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


def _parse_args(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return None


# ----------------------------------------------------------------------------- in-memory world (demo + tests)
class MemoryWorld:
    """Minimal World stand-in implementing WorldLike; used by the demo and unit tests."""

    def __init__(self, state: State):
        self.state = state
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._ids: dict[str, int] = {}

    def _id(self, p: str) -> str:
        self._ids[p] = self._ids.get(p, 0) + 1
        return f"{p}_{self._ids[p]:04d}"

    def broadcast(self, type: str, payload: dict[str, Any]) -> None:
        self.sent.append((type, payload))

    def add_brief(self, **kw: Any) -> Brief:
        kw.setdefault("lang", self.state.lang)
        b = Brief(id=self._id("brief"), created_t=self.state.t, **kw)
        self.state.briefs.append(b)
        if b.decision == "push":
            self.state.counters.pushed += 1
            if b.unit_id in self.state.units:
                self.state.units[b.unit_id].heard_count += 1
        else:
            self.state.counters.held += 1
        self.broadcast("brief", b.model_dump(mode="json"))
        return b

    def add_trace(self, **kw: Any) -> TraceEntry:
        tr = TraceEntry(id=self._id("tr"), t=self.state.t, **kw)
        self.state.trace.append(tr)
        self.broadcast("trace", tr.model_dump(mode="json"))
        return tr

    def add_proposal(self, **kw: Any) -> Proposal:
        p = Proposal(id=self._id("prop"), created_t=self.state.t, **kw)
        self.state.proposals.append(p)
        self.broadcast("proposal", p.model_dump(mode="json"))
        return p

    def escalate(self, card_id: str, level: int, reason: str | None = None) -> None:
        for c in self.state.cards:
            if c.id == card_id:
                c.escalation_level = max(c.escalation_level, level)
                c.state = "escalated"
                self.broadcast("escalation", {"card_id": c.id, "level": c.escalation_level})

    def ping_unit(self, unit_id: str) -> None:
        u = self.state.units[unit_id]
        u.unanswered_pings += 1
        self.broadcast("ping", {"unit_id": unit_id, "n": u.unanswered_pings, "t": self.state.t, "ping_id": self._id("ping")})


def demo_state() -> State:
    zones = checker._file_zones()
    units = {
        "kim": Unit(id="kim", callsign="한빛구조대", name="김하늘", role="CREW", zone_id="2F-E", status="IN", interior=True, last_heard_t=20),
        "park": Unit(id="park", callsign="한빛펌프", name="박누리", role="CREW", zone_id="1F-W", status="IN", interior=True, last_heard_t=25),
        "rit": Unit(id="rit", callsign="신속동료구조팀", role="RIT", zone_id="OUT-RIT", status="OUT"),
        "ic": Unit(id="ic", callsign="지휘대장", role="IC", zone_id="OUT-CP", status="OUT"),
        "hanbit_center": Unit(id="hanbit_center", callsign="한빛119안전센터 팀장", role="EXTERIOR", zone_id="OUT-FRONT", status="OUT"),
    }
    text = "지휘대장, 여기 한빛119안전센터 팀장. 정면에서 3층 창문으로 확인, 도장공장 신나 드럼 다수, 인화물질 확인. 2층 동측 천장으로 연소 확대 우려."
    ev = Event(id="evt_0004", transmission_id="tx_0004", t=34.0, channel="TAC", text=text,
               triage=Triage(tag="DANGER", speaker_unit="한빛119안전센터 팀장", hazard_terms=["인화물질", "신나 드럼"],
                             evidence_span="인화물질 확인", crew_brief="3층 인화물질 확인, 2층 동측 천장으로 연소 확대 우려.",
                             confidence=0.9),
               speaker_unit_snapped="hanbit_center", zone_id_snapped="3F", evidence_verified=True)
    card = Card(id="card_0001", kind="DANGER", title="위험 · 3F · 인화물질", event_ids=[ev.id], priority=1, zone_id="3F",
                created_t=34.0, evidence_span="인화물질 확인", channel="TAC")
    return State(scenario_id="hanbit", lang="ko", running=True, t=35.0, strategy="OFFENSIVE", units=units, zones=zones,
                 events=[ev], cards=[card])


def demo_state_mayday() -> State:
    """L08-like: kim declares 긴급탈출 in 2F-E-STORE (the heavier wake: P0 to others + ask + escalate + proposals)."""
    from server.models import Distress, HazardNote

    st = demo_state()
    st.t = 92.0
    st.units["kim"].zone_id = "2F-E-STORE"
    st.zones["3F"].hazards.append(HazardNote(event_id="evt_0004", text="인화물질, 신나 드럼", t=34.0))
    text = "긴급탈출 긴급탈출, 지휘대장 여기 한빛구조대 김하늘. 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽. 공기 얼마 안 남았다."
    ev = Event(id="evt_0009", transmission_id="tx_0009", t=78.0, channel="TAC", text=text,
               triage=Triage(tag="MAYDAY", speaker_unit="한빛구조대 김하늘", addressee="지휘대장",
                             distress=Distress(who="한빛구조대 김하늘", what="TRAPPED", where_raw="2층 동쪽 창고 쪽",
                                               air="공기 얼마 안 남았다"),
                             hazard_terms=["천장 무너져서"], evidence_span="긴급탈출 긴급탈출", status_change="TRAPPED",
                             needs_ack=True, confidence=0.95,
                             crew_brief="한빛구조대 김하늘 긴급탈출, 2층 동쪽 창고 쪽 고립. 공기 부족."),
               speaker_unit_snapped="kim", zone_id_snapped="2F-E-STORE", evidence_verified=True)
    st.events.append(ev)
    st.cards.append(Card(id="card_0002", kind="MAYDAY", title="긴급탈출 · 한빛구조대 김하늘 · 2F-E-STORE",
                         event_ids=[ev.id], priority=0, unit_id="kim", zone_id="2F-E-STORE",
                         fields={"who": "한빛구조대 김하늘", "what": "대원고립", "where": "2층 동쪽 창고", "needs": None,
                                 "air": "공기 얼마 안 남았다"}, missing_fields=["needs"], created_t=92.0, event_t=78.0))
    return st


async def _demo(which: str = "danger") -> None:
    from server.meta.spark import SparkClient

    st = demo_state_mayday() if which == "mayday" else demo_state()
    ev = st.events[-1]
    world = MemoryWorld(st)
    agent = RelevanceAgent(world, SparkClient(timeout=60), get_settings())
    t0 = time.perf_counter()
    res = await agent.wake(f"event:{ev.id}", ev)
    print(f"wake returned in {time.perf_counter() - t0:.2f} s (timeout {agent.settings.agent_timeout_s} s): {res}")
    if agent._bg:
        await agent.drain()
        print(f"background (late) wake finished at {time.perf_counter() - t0:.2f} s")
    for tr in st.trace:
        print(f"[{tr.kind:9}] {json.dumps(tr.payload, ensure_ascii=False)}")
    for b in st.briefs:
        print(f"BRIEF {b.unit_id:6} {b.decision:4} {b.priority} {b.source:6} {b.text!r} why={b.reason!r}")
    for p in st.proposals:
        print(f"PROPOSAL {p.kind} {p.units} {p.text!r}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(_demo(sys.argv[2] if len(sys.argv) > 2 else "danger"))
    else:
        print("usage: python -m server.agent demo [danger|mayday]")
