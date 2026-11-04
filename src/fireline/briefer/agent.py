"""Live briefing agent on Muse Spark structured output.

The model sees a compact text rendering of the world state, the delta and the last
few briefings, and returns a flat ``BrieferOut``. Everything it says is then passed
through ``to_decision`` which enforces the hard rules (known responder ids, no
self-briefing except a mayday ack, <= 25 words, one briefing per responder, no exact
repeats) so a sloppy model answer can never break the pipeline.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from fireline.config import Settings, get_settings
from fireline.meta.spark import SparkClient
from fireline.models import (
    Assignment,
    Briefing,
    BrieferDecision,
    Cell,
    StateDelta,
    Urgency,
    WorldState,
)

from .mock import (
    MAX_WORDS,
    MAYDAY_ACK,
    callsign,
    clip_words,
    dedupe_assignments,
    dedupe_per_responder,
    is_mayday,
    reporter_of,
    resolve_zone,
    suppress_repeats,
    zone_at,
)

log = logging.getLogger("fireline.briefer")

RECENT_LIMIT = 6


# ---------------------------------------------------------------------------
# Structured output schema (flat objects, one level of nesting)
# ---------------------------------------------------------------------------


class BriefingOut(BaseModel):
    responder_id: str
    text: str
    urgency: Literal["low", "normal", "high", "critical"] = "normal"
    reason: str = ""
    trigger_ids: list[str] = Field(default_factory=list)
    show_floor: Optional[int] = None
    show_x: Optional[int] = None
    show_y: Optional[int] = None


class AssignmentOut(BaseModel):
    responder_id: str
    target_kind: Literal["victim", "hazard", "responder"]
    target_id: str
    reason: str = ""


class BrieferOut(BaseModel):
    briefings: list[BriefingOut] = Field(default_factory=list)
    assignments: list[AssignmentOut] = Field(default_factory=list)
    commander_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are the incident communications agent for a structure fire. After every change in the
world state you decide, per responder, whether to interrupt them through their bone-conduction
earpiece and what to say. Silence is the default: only interrupt someone whose safety or task changed.

RULES
1. Never brief the reporter about their own report. Exception: if the delta is a MAYDAY, the caller
   gets exactly one line: "<callsign>: {MAYDAY_ACK}"
2. MAYDAY: brief every responder on the mayday floor, the floor above and the floor below, plus the
   nearest available crew, with the exact location (floor + zone), the hazard and who is down. If a
   stairwell is involved, tell them not to use it. Propose an Assignment: nearest OK responder who
   is NOT on the mayday crew -> target_kind "responder", target_id = the mayday caller.
3. Confirmed or suspected victim: brief the nearest non-busy responder (status OK, no victim assigned,
   not the reporter) with the zone, floor, count and condition. For a confirmed victim with no
   assignee, propose an Assignment (target_kind "victim", target_id = victim id from the VICTIMS table).
4. Hazard such as a blocked stairwell or collapse: brief anyone whose egress runs through it, name
   the alternative stairwell. Smoke/heat: brief responders on that floor only.
5. Low air: brief the partner (same unit) to back out together.
6. Help needed: brief the nearest available responder with the location and what is needed.
7. Routine status or position updates: no briefings. Keep silence when nothing changed for a responder.
8. At most ONE briefing per responder per delta. Do not repeat a RECENT briefing with the same meaning.

STYLE
- Radio style. Start with the responder's callsign followed by a colon (callsigns are in the table).
- At most {MAX_WORDS} words. Numbers as digits ("floor 5", "2 victims"). No pleasantries.
- urgency: critical = mayday/life threat, high = confirmed victim/collapse/low air, normal = otherwise, low = FYI.
- show_floor/show_x/show_y: the grid cell to highlight on the responder's display (victim, mayday or
  hazard cell from the tables), or null.
- commander_note: one short line for the command dashboard, or null.
- Only use responder ids, victim ids and hazard ids that appear in the tables.
Return JSON only, matching the schema."""


def _fmt_cell(cell: Optional[Cell]) -> str:
    return f"{cell.floor}/{cell.x},{cell.y}" if cell else "-"


def compact_state(state: WorldState) -> str:
    """The compact world-state text the model sees (also handy for debugging)."""
    roster = list(state.responders.values())
    busy = {v.assigned_responder_id: v.id for v in state.victims.values() if v.assigned_responder_id}
    lines = [f"INCIDENT: {state.incident_name}", f"BUILDING: {state.building.name}, floors 1-{state.building.floors}; floor 0 = outdoors; cell = floor/x,y"]
    stairs = sorted({z.name for z in state.building.zones if z.kind == "stair"})
    if stairs:
        lines.append("STAIRWELLS (every floor): " + ", ".join(stairs))
    lines.append("RESPONDERS: id | callsign | name | floor | zone | cell | status | air_min | assigned_victim")
    for r in roster:
        floor = r.cell.floor if r.cell else "?"
        zone = r.zone or (zone_at(state.building, r.cell).name if zone_at(state.building, r.cell) else "?")
        lines.append(
            f"{r.id} | {callsign(r, roster)} | {r.name} | {floor} | {zone} | {_fmt_cell(r.cell)} | "
            f"{r.status.value} | {r.air_minutes if r.air_minutes is not None else '?'} | {busy.get(r.id, '-')}"
        )
    active = [v for v in state.victims.values() if v.status.value != "extracted"]
    lines.append("VICTIMS (active): id | floor | zone | cell | status | p | count | condition | assigned")
    for v in active:
        lines.append(
            f"{v.id} | {v.cell.floor} | {v.zone or '?'} | {_fmt_cell(v.cell)} | {v.status.value} | {v.probability:.2f} | "
            f"{v.count} | {v.condition or '-'} | {v.assigned_responder_id or '-'}"
        )
    if not active:
        lines.append("(none)")
    hazards = [h for h in state.hazards.values() if h.active]
    lines.append("HAZARDS (active): id | kind | floor | zone | cell | severity")
    for h in hazards:
        lines.append(f"{h.id} | {h.kind} | {h.cell.floor} | {h.zone or '?'} | {_fmt_cell(h.cell)} | {h.severity}")
    if not hazards:
        lines.append("(none)")
    return "\n".join(lines)


def compact_delta(delta: StateDelta, state: WorldState) -> str:
    """One paragraph describing what just changed."""
    roster = list(state.responders.values())
    rid = reporter_of(delta)
    rep = state.responders.get(rid) if rid else None
    who = f"{rid} ({callsign(rep, roster)})" if rep else (rid or "unknown")
    lines = [f"DELTA v{delta.version} from {who}:"]
    tr = delta.triage
    if tr:
        lines.append(
            f"radio report {tr.report_id}: tag={tr.tag.value} priority={tr.priority} mayday={'YES' if tr.mayday else 'no'} "
            f"floor={tr.floor} zone={tr.zone} responder_status={tr.responder_status.value}"
        )
        lines.append(f"summary: {tr.summary}")
        lines.append(
            f"victim: certainty={tr.victim_certainty} count={tr.victim_count} condition={tr.victim_condition or '-'}; "
            f"hazards={tr.hazards or []}; needs={tr.needs or []}"
        )
    if delta.touch:
        t = delta.touch
        lines.append(f"touch {t.id}: action={t.action} cell={_fmt_cell(t.cell)} victim_id={t.victim_id or '-'}")
    if delta.detections:
        best = max(d.score for d in delta.detections)
        lines.append(f"helmet-cam: {len(delta.detections)} person detection(s), best score {best:.2f}, at the reporter's cell")
    if delta.changed_responders:
        lines.append(f"changed responders: {delta.changed_responders}")
    if delta.changed_victims:
        lines.append(f"changed victims: {delta.changed_victims}")
    if delta.changed_hazards:
        lines.append(f"changed hazards: {delta.changed_hazards}")
    return "\n".join(lines)


def compact_recent(recent: list[Briefing]) -> str:
    tail = recent[-RECENT_LIMIT:]
    if not tail:
        return "RECENT BRIEFINGS: none"
    return "RECENT BRIEFINGS (do not repeat):\n" + "\n".join(f"- {b.responder_id} [{b.urgency.value}]: {b.text}" for b in tail)


def build_user_prompt(delta: StateDelta, state: WorldState, recent: list[Briefing]) -> str:
    return "\n\n".join([compact_state(state), compact_delta(delta, state), compact_recent(recent)])


# ---------------------------------------------------------------------------
# Model output -> BrieferDecision
# ---------------------------------------------------------------------------


def _show_cell(b: BriefingOut) -> Optional[Cell]:
    if b.show_floor is None or b.show_x is None or b.show_y is None:
        return None
    return Cell(floor=b.show_floor, x=b.show_x, y=b.show_y)


def _target_exists(a: AssignmentOut, state: WorldState) -> bool:
    table = {"victim": state.victims, "hazard": state.hazards, "responder": state.responders}[a.target_kind]
    return a.target_id in table


def to_decision(out: BrieferOut, state: WorldState, delta: StateDelta, recent: list[Briefing] | None = None) -> BrieferDecision:
    """Validate and normalise a model answer into the shared decision type."""
    mayday = is_mayday(delta)
    reporter = reporter_of(delta)
    briefings: list[Briefing] = []
    for b in out.briefings:
        if b.responder_id not in state.responders:
            log.warning("briefer: dropping briefing for unknown responder %r", b.responder_id)
            continue
        if b.responder_id == reporter:
            # The reporter never hears about their own report; a mayday caller gets the
            # fixed one-line ack (appended below) whatever the model wrote.
            log.info("briefer: dropping self-briefing for %s", b.responder_id)
            continue
        text = clip_words(b.text)
        if not text:
            continue
        briefings.append(
            Briefing(
                responder_id=b.responder_id,
                text=text,
                urgency=Urgency(b.urgency),
                reason=b.reason,
                trigger_ids=[t for t in b.trigger_ids if t],
                show_cell=_show_cell(b),
            )
        )
    if mayday and reporter in state.responders:
        briefings.append(_mayday_ack(reporter, state, delta))
    briefings = suppress_repeats(dedupe_per_responder(briefings), recent or [])

    assignments = [
        Assignment(responder_id=a.responder_id, target_kind=a.target_kind, target_id=a.target_id, reason=a.reason or "proposed by briefer")
        for a in out.assignments
        if a.responder_id in state.responders and _target_exists(a, state)
    ]
    note = out.commander_note.strip() if out.commander_note else None
    return BrieferDecision(briefings=briefings, assignments=dedupe_assignments(assignments), commander_note=note or None)


def _mayday_ack(reporter_id: str, state: WorldState, delta: StateDelta) -> Briefing:
    rep = state.responders[reporter_id]
    tr = delta.triage
    zone = resolve_zone(state.building, tr.zone, tr.floor) if tr else None
    return Briefing(
        responder_id=reporter_id,
        text=f"{callsign(rep, list(state.responders.values()))}: {MAYDAY_ACK}",
        urgency=Urgency.CRITICAL,
        reason="mayday acknowledgement to the caller (fixed line, enforced by post-processing)",
        trigger_ids=[tr.report_id] if tr else [],
        show_cell=zone.center if zone else rep.cell,
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class SparkBriefer:
    """Briefing agent backed by Muse Spark structured output."""

    temperature = 0.2
    max_tokens = 1200

    def __init__(self, settings: Settings | None = None, client: SparkClient | None = None):
        self.settings = settings or get_settings()
        self.client = client or SparkClient(self.settings)

    async def decide(self, delta: StateDelta, state: WorldState, recent: list[Briefing] | None = None) -> BrieferDecision:
        """Async live decision. Raises MockMode in mock mode, MetaAPIError on bad output."""
        recent = recent or []
        out, latency = await self.client.acomplete_json(
            SYSTEM_PROMPT,
            build_user_prompt(delta, state, recent),
            BrieferOut,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self._finish(out, latency, state, delta, recent)

    def decide_sync(self, delta: StateDelta, state: WorldState, recent: list[Briefing] | None = None) -> BrieferDecision:
        """Blocking variant (safe to call from a thread; never spins its own event loop)."""
        recent = recent or []
        out, latency = self.client.complete_json(
            SYSTEM_PROMPT,
            build_user_prompt(delta, state, recent),
            BrieferOut,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self._finish(out, latency, state, delta, recent)

    def _finish(self, out: BrieferOut, latency: int, state: WorldState, delta: StateDelta, recent: list[Briefing]) -> BrieferDecision:
        decision = to_decision(out, state, delta, recent)
        decision.model = self.settings.spark_model
        decision.latency_ms = latency
        return decision
