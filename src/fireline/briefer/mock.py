"""Rule-based briefer (deterministic stand-in for Muse Spark) and shared helpers.

``RuleBriefer`` implements the contract rules with plain Python so the pipeline
behaves identically with or without an API key. The helper functions at the top
(word counting, callsigns, floor-aware zone lookup, distances, dedupe) are shared
with the live ``SparkBriefer`` so both paths produce the same shape and obey the
same hard limits.
"""

from __future__ import annotations

from typing import Iterable, Optional

from fireline.models import (
    Assignment,
    Briefing,
    BrieferDecision,
    Building,
    Cell,
    Hazard,
    Responder,
    ResponderStatus,
    StateDelta,
    TriageResult,
    Urgency,
    VictimEstimate,
    VictimStatus,
    WorldState,
    Zone,
)

MAX_WORDS = 25
FLOOR_PENALTY = 10  # one floor of separation counts as this many grid cells
MAYDAY_ACK = "Command copies your mayday, RIT is coming."

_URGENCY_RANK = {Urgency.CRITICAL: 3, Urgency.HIGH: 2, Urgency.NORMAL: 1, Urgency.LOW: 0}
_STAIR_WORDS = ("stair", "stairwell")
_EGRESS_WORDS = ("collapse", "blocked", "stair", "flashover", "backdraft")
_LOW_AIR_WORDS = ("low air", "air alarm", "out of air", "bottle")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def words(text: str) -> int:
    """Number of whitespace-separated words in ``text``."""
    return len(text.split())


def clip_words(text: str, limit: int = MAX_WORDS) -> str:
    """Collapse whitespace and keep at most ``limit`` words."""
    parts = text.split()
    return " ".join(parts[:limit])


def callsign(responder: Responder, roster: Iterable[Responder]) -> str:
    """Radio callsign: bare unit when unique in the roster, else ``unit-suffix``.

    E.g. L2-1 -> "Ladder 2", E1-2 -> "Engine 1-2".
    """
    shared = sum(1 for r in roster if r.unit == responder.unit) > 1
    suffix = responder.id.rsplit("-", 1)[-1] if "-" in responder.id else ""
    if shared and suffix:
        return f"{responder.unit}-{suffix}"
    return responder.unit


def norm_text(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------


def resolve_zone(building: Building, name: Optional[str], floor: Optional[int] = None) -> Optional[Zone]:
    """Floor-aware zone lookup (stairwells repeat on every floor)."""
    if not name:
        return None
    key = name.strip().lower()
    matches = [z for z in building.zones if z.name.lower() == key or key in (a.lower() for a in z.aliases)]
    if not matches:
        return None
    if floor is not None:
        for z in matches:
            if z.floor == floor:
                return z
    return matches[0]


def zone_at(building: Building, cell: Optional[Cell]) -> Optional[Zone]:
    """Zone containing ``cell`` (first match), or None."""
    if cell is None:
        return None
    for z in building.zones:
        if z.contains(cell):
            return z
    return None


def cell_distance(building: Building, a: Optional[Cell], b: Optional[Cell]) -> float:
    """Manhattan distance on the site grid plus a heavy per-floor penalty."""
    if a is None or b is None:
        return float("inf")
    pa, pb = building.indoor_to_site(a), building.indoor_to_site(b)
    return abs(pa.x - pb.x) + abs(pa.y - pb.y) + FLOOR_PENALTY * abs(a.floor - b.floor)


def nearest_responders(
    state: WorldState,
    cell: Optional[Cell],
    *,
    exclude: Iterable[str] = (),
    only_ok: bool = True,
    exclude_busy: bool = True,
) -> list[Responder]:
    """Responders sorted by distance to ``cell`` (ties by id); filtered as requested."""
    skip = set(exclude)
    busy = {v.assigned_responder_id for v in state.victims.values() if v.status != VictimStatus.EXTRACTED}
    out = []
    for r in state.responders.values():
        if r.id in skip:
            continue
        if only_ok and r.status != ResponderStatus.OK:
            continue
        if exclude_busy and r.id in busy:
            continue
        out.append(r)
    out.sort(key=lambda r: (cell_distance(state.building, r.cell, cell), r.id))
    return out


def nearest_stair(building: Building, cell: Optional[Cell]) -> Optional[Zone]:
    """The stair zone on the cell's floor closest to it (the responder's likely egress)."""
    if cell is None or cell.floor < 1:
        return None
    stairs = [z for z in building.zones_on_floor(cell.floor) if z.kind == "stair"]
    if not stairs:
        return None
    return min(stairs, key=lambda z: (cell_distance(building, cell, z.center), z.name))


def other_stair(building: Building, floor: int, avoid: str) -> Optional[str]:
    for z in building.zones_on_floor(floor):
        if z.kind == "stair" and z.name.lower() != avoid.lower():
            return z.name
    return None


# ---------------------------------------------------------------------------
# Delta helpers
# ---------------------------------------------------------------------------


def reporter_of(delta: StateDelta) -> Optional[str]:
    """Responder whose action produced this delta (radio, touch or helmet cam)."""
    if delta.triage and delta.triage.responder_id:
        return delta.triage.responder_id
    if delta.touch:
        return delta.touch.responder_id
    for ev in delta.new_events:
        if ev.kind == "photo" and ev.responder_id:
            return ev.responder_id
    if delta.changed_responders:
        return delta.changed_responders[0]
    return None


def is_mayday(delta: StateDelta) -> bool:
    return bool(delta.triage and delta.triage.mayday)


def changed_victims(delta: StateDelta, state: WorldState) -> list[VictimEstimate]:
    return [state.victims[v] for v in delta.changed_victims if v in state.victims]


def changed_hazards(delta: StateDelta, state: WorldState) -> list[Hazard]:
    return [state.hazards[h] for h in delta.changed_hazards if h in state.hazards]


# ---------------------------------------------------------------------------
# Output hygiene (shared with the live path)
# ---------------------------------------------------------------------------


def dedupe_per_responder(briefings: list[Briefing]) -> list[Briefing]:
    """Keep one briefing per responder: the most urgent (first one wins on ties)."""
    best: dict[str, Briefing] = {}
    for b in briefings:
        cur = best.get(b.responder_id)
        if cur is None or _URGENCY_RANK[b.urgency] > _URGENCY_RANK[cur.urgency]:
            best[b.responder_id] = b
    return list(best.values())


def suppress_repeats(briefings: list[Briefing], recent: Iterable[Briefing]) -> list[Briefing]:
    """Drop briefings whose (responder, text) already went out recently."""
    seen = {(r.responder_id, norm_text(r.text)) for r in recent}
    return [b for b in briefings if (b.responder_id, norm_text(b.text)) not in seen]


def dedupe_assignments(assignments: list[Assignment]) -> list[Assignment]:
    seen: set[tuple[str, str, str]] = set()
    out = []
    for a in assignments:
        key = (a.responder_id, a.target_kind, a.target_id)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


# ---------------------------------------------------------------------------
# Rule briefer
# ---------------------------------------------------------------------------


class RuleBriefer:
    """Deterministic briefing agent implementing the contract rules."""

    def decide(self, delta: StateDelta, state: WorldState, recent: list[Briefing] | None = None) -> BrieferDecision:
        """Decide who to interrupt and what to propose, from the delta and world state only."""
        ctx = _Ctx(delta, state)
        briefings: list[Briefing] = []
        assignments: list[Assignment] = []
        notes: list[str] = []

        if delta.triage:
            self._from_triage(ctx, briefings, assignments, notes)
        if delta.touch:
            self._from_touch(ctx, briefings, assignments, notes)
        if delta.detections and not delta.triage and not delta.touch:
            self._from_detections(ctx, briefings, assignments, notes)

        briefings = dedupe_per_responder(briefings)
        briefings = suppress_repeats(briefings, recent or [])
        for b in briefings:
            b.text = clip_words(b.text)
        return BrieferDecision(
            briefings=briefings,
            assignments=dedupe_assignments(assignments),
            commander_note=" | ".join(notes) if notes else None,
            model="mock",
            latency_ms=0,
        )

    # ------------------------------------------------------------ triggers
    def _from_triage(self, ctx: "_Ctx", briefings, assignments, notes) -> None:
        tr = ctx.delta.triage
        assert tr is not None
        if tr.mayday:
            self._mayday(ctx, tr, briefings, assignments, notes)
            return
        if tr.victim_certainty in ("suspected", "confirmed"):
            self._victims(ctx, briefings, assignments, notes)
        elif tr.victim_certainty == "extracted":
            notes.append(f"{ctx.reporter_cs} reports victim extracted ({ctx.where(tr.floor, tr.zone)}).")
        for hz in tr.hazards:
            self._hazard(ctx, hz, tr.floor, tr.zone, briefings, notes)
        if tr.tag.value == "HelpNeeded" or tr.needs:
            self._help(ctx, tr, briefings, notes)

    def _from_touch(self, ctx: "_Ctx", briefings, assignments, notes) -> None:
        touch = ctx.delta.touch
        assert touch is not None
        if touch.action == "mark_victim":
            self._victims(ctx, briefings, assignments, notes)
        elif touch.action == "need_help":
            cell = ctx.reporter.cell if ctx.reporter else touch.cell
            self._help_at(ctx, cell, [], briefings, notes, urgency=Urgency.HIGH)
        elif touch.action == "victim_out":
            notes.append(f"{ctx.reporter_cs} reports victim out.")
        elif touch.action in ("im_ok", "clear_danger"):
            notes.append(f"{ctx.reporter_cs} reports OK.")

    def _from_detections(self, ctx: "_Ctx", briefings, assignments, notes) -> None:
        self._victims(ctx, briefings, assignments, notes)

    # --------------------------------------------------------------- rules
    def _mayday(self, ctx: "_Ctx", tr: TriageResult, briefings, assignments, notes) -> None:
        state = ctx.state
        floor = tr.floor if tr.floor is not None else (ctx.reporter.cell.floor if ctx.reporter and ctx.reporter.cell else None)
        zone = resolve_zone(state.building, tr.zone, floor)
        cell = zone.center if zone else (ctx.reporter.cell if ctx.reporter else None)
        where = ctx.where(floor, zone.name if zone else tr.zone)
        hazard = tr.hazards[0] if tr.hazards else "responder in trouble"
        avoid = ""
        if zone and zone.kind == "stair" and any(w in " ".join(tr.hazards).lower() for w in ("collapse", "blocked")):
            avoid = f"Do not use {zone.name}. "
        text = f"mayday {where}, {hazard}, {ctx.reporter_cs} needs RIT. {avoid}RIT en route."
        trigger = [tr.report_id]

        if ctx.reporter:
            briefings.append(
                Briefing(
                    responder_id=ctx.reporter.id,
                    text=f"{ctx.reporter_cs}: {MAYDAY_ACK}",
                    urgency=Urgency.CRITICAL,
                    reason="mayday acknowledgement to the caller",
                    trigger_ids=trigger,
                    show_cell=cell,
                )
            )

        targets: dict[str, str] = {}
        for r in state.responders.values():
            if ctx.reporter and r.id == ctx.reporter.id:
                continue
            if r.cell is not None and floor is not None and r.cell.floor >= 1 and abs(r.cell.floor - floor) <= 1:
                targets[r.id] = f"on floor {r.cell.floor}, within one floor of the mayday"
            elif ctx.reporter and r.unit == ctx.reporter.unit:
                targets[r.id] = "same crew as the mayday caller"

        crew_unit = ctx.reporter.unit if ctx.reporter else None
        nearest = [
            r
            for r in nearest_responders(state, cell, exclude=[ctx.reporter.id] if ctx.reporter else [], exclude_busy=False)
            if r.unit != crew_unit
        ]
        rit = nearest[0] if nearest else None
        if rit is not None:
            targets.setdefault(rit.id, "nearest available crew to the mayday")
            assignments.append(
                Assignment(
                    responder_id=rit.id,
                    target_kind="responder",
                    target_id=ctx.reporter.id if ctx.reporter else rit.id,
                    reason=f"Nearest available crew to mayday {where}; propose as RIT.",
                )
            )

        for rid, reason in targets.items():
            r = state.responders[rid]
            briefings.append(
                Briefing(
                    responder_id=rid,
                    text=f"{ctx.cs(r)}: {text}",
                    urgency=Urgency.CRITICAL,
                    reason=reason,
                    trigger_ids=trigger,
                    show_cell=cell,
                )
            )
        rit_cs = ctx.cs(rit) if rit else "none available"
        notes.append(f"MAYDAY {ctx.reporter_cs} {where} ({hazard}). RIT proposed: {rit_cs}.")

    def _victims(self, ctx: "_Ctx", briefings, assignments, notes) -> None:
        state = ctx.state
        vics = changed_victims(ctx.delta, state)
        if not vics and ctx.delta.triage:
            vics = [self._synthetic_victim(ctx, ctx.delta.triage)]
        if not vics and ctx.delta.touch and ctx.delta.touch.cell:
            vics = [VictimEstimate(id="", cell=ctx.delta.touch.cell, zone=None, probability=0.9, status=VictimStatus.CONFIRMED)]
        if not vics and ctx.reporter and ctx.reporter.cell:
            vics = [VictimEstimate(id="", cell=ctx.reporter.cell, probability=0.6, status=VictimStatus.SUSPECTED)]
        for v in vics:
            if v.status == VictimStatus.EXTRACTED:
                continue
            self._victim(ctx, v, briefings, assignments, notes)

    def _victim(self, ctx: "_Ctx", v: VictimEstimate, briefings, assignments, notes) -> None:
        state = ctx.state
        zone = v.zone or (zone_at(state.building, v.cell).name if zone_at(state.building, v.cell) else None)
        where = ctx.where(v.cell.floor, zone)
        status = "confirmed" if v.status == VictimStatus.CONFIRMED else "possible"
        urgency = Urgency.HIGH if v.status == VictimStatus.CONFIRMED else Urgency.NORMAL
        count = f"{v.count} victims" if v.count > 1 else "victim"
        cond = f", {v.condition}" if v.condition else ""
        exclude = [ctx.reporter.id] if ctx.reporter else []
        candidates = nearest_responders(state, v.cell, exclude=exclude)
        if candidates:
            r = candidates[0]
            briefings.append(
                Briefing(
                    responder_id=r.id,
                    text=f"{ctx.cs(r)}: {status} {count} {where}{cond}, reported by {ctx.reporter_cs}. Stand by to assist.",
                    urgency=urgency,
                    reason=f"nearest available responder to {status} victim {where}",
                    trigger_ids=[i for i in [v.id, *ctx.trigger_ids()] if i],
                    show_cell=v.cell,
                )
            )
        if v.status == VictimStatus.CONFIRMED and v.id and not v.assigned_responder_id:
            assignee = self._assignee_for(ctx, v, candidates)
            if assignee is not None:
                assignments.append(
                    Assignment(
                        responder_id=assignee.id,
                        target_kind="victim",
                        target_id=v.id,
                        reason=f"Nearest available responder to confirmed {count} {where}.",
                    )
                )
        notes.append(f"{status.capitalize()} {count} {where} via {ctx.reporter_cs}.")

    def _assignee_for(self, ctx: "_Ctx", v: VictimEstimate, others: list[Responder]) -> Optional[Responder]:
        """Reporter if they are OK and on the victim's floor (they have eyes on), else nearest other."""
        rep = ctx.reporter
        if rep and rep.status == ResponderStatus.OK and rep.cell and rep.cell.floor == v.cell.floor:
            return rep
        return others[0] if others else None

    def _hazard(self, ctx: "_Ctx", hazard: str, floor: Optional[int], zone_name: Optional[str], briefings, notes) -> None:
        state = ctx.state
        hz = hazard.lower()
        if any(w in hz for w in _LOW_AIR_WORDS):
            self._low_air(ctx, briefings, notes)
            return
        stair = self._stair_for_hazard(ctx, hz, floor, zone_name)
        if stair is not None:
            self._egress(ctx, hazard, stair, briefings, notes)
            return
        if floor is None or floor < 1:
            return
        if not any(w in hz for w in ("collapse", "flashover", "backdraft", "smoke", "heat", "fire")):
            return
        zone = resolve_zone(state.building, zone_name, floor)
        where = ctx.where(floor, zone.name if zone else zone_name)
        cell = zone.center if zone else None
        urgency = Urgency.HIGH if any(w in hz for w in ("collapse", "flashover", "backdraft")) else Urgency.NORMAL
        for r in state.responders.values():
            if ctx.reporter and r.id == ctx.reporter.id:
                continue
            if r.cell and r.cell.floor == floor:
                briefings.append(
                    Briefing(
                        responder_id=r.id,
                        text=f"{ctx.cs(r)}: {hazard} {where}, reported by {ctx.reporter_cs}. Use caution.",
                        urgency=urgency,
                        reason=f"on the same floor as reported hazard '{hazard}'",
                        trigger_ids=ctx.trigger_ids(),
                        show_cell=cell,
                    )
                )
        notes.append(f"Hazard: {hazard} {where}.")

    def _stair_for_hazard(self, ctx: "_Ctx", hz: str, floor: Optional[int], zone_name: Optional[str]) -> Optional[Zone]:
        """Stair zone affected by a hazard, from its text or its zone; None if not an egress hazard."""
        building = ctx.state.building
        for z in building.zones:
            if z.kind != "stair":
                continue
            names = [z.name.lower(), *(a.lower() for a in z.aliases)]
            if any(n in hz for n in names):
                return resolve_zone(building, z.name, floor) or z
        zone = resolve_zone(building, zone_name, floor)
        if zone and zone.kind == "stair" and any(w in hz for w in _EGRESS_WORDS):
            return zone
        return None

    def _egress(self, ctx: "_Ctx", hazard: str, stair: Zone, briefings, notes) -> None:
        state = ctx.state
        # "stairwell B blocked floor 5 stairwell B" reads badly: drop the zone when the hazard names it.
        where = ctx.where(stair.floor, None if stair.name.lower() in hazard.lower() else stair.name)
        alt = other_stair(state.building, stair.floor, stair.name)
        alt_txt = f", egress via {alt}" if alt else ""
        urgency = Urgency.HIGH if any(w in hazard.lower() for w in ("collapse", "blocked", "flashover")) else Urgency.NORMAL
        for r in state.responders.values():
            if ctx.reporter and r.id == ctx.reporter.id:
                continue
            egress = nearest_stair(state.building, r.cell)
            if egress is None or egress.name.lower() != stair.name.lower():
                continue
            briefings.append(
                Briefing(
                    responder_id=r.id,
                    text=f"{ctx.cs(r)}: {hazard} {where}. Do not use {stair.name}{alt_txt}.",
                    urgency=urgency,
                    reason=f"egress runs through {stair.name}",
                    trigger_ids=ctx.trigger_ids(),
                    show_cell=stair.center,
                )
            )
        notes.append(f"{stair.name} compromised at floor {stair.floor}: {hazard}.")

    def _low_air(self, ctx: "_Ctx", briefings, notes) -> None:
        rep = ctx.reporter
        if rep is None:
            return
        stair = nearest_stair(ctx.state.building, rep.cell)
        via = f" via {stair.name}" if stair else ""
        for r in ctx.state.responders.values():
            if r.id == rep.id or r.unit != rep.unit:
                continue
            briefings.append(
                Briefing(
                    responder_id=r.id,
                    text=f"{ctx.cs(r)}: {ctx.reporter_cs} reports low air in your crew. Back out together now{via}.",
                    urgency=Urgency.HIGH,
                    reason="partner of a responder with low air",
                    trigger_ids=ctx.trigger_ids(),
                    show_cell=stair.center if stair else rep.cell,
                )
            )
        notes.append(f"Low air: {ctx.reporter_cs}.")

    def _help(self, ctx: "_Ctx", tr: TriageResult, briefings, notes) -> None:
        zone = resolve_zone(ctx.state.building, tr.zone, tr.floor)
        cell = zone.center if zone else (ctx.reporter.cell if ctx.reporter else None)
        self._help_at(ctx, cell, tr.needs, briefings, notes, urgency=Urgency.NORMAL)

    def _help_at(self, ctx: "_Ctx", cell: Optional[Cell], needs: list[str], briefings, notes, *, urgency: Urgency) -> None:
        state = ctx.state
        zone = zone_at(state.building, cell)
        where = ctx.where(cell.floor if cell else None, zone.name if zone else None)
        need = f": {', '.join(needs[:2])}" if needs else ""
        exclude = [ctx.reporter.id] if ctx.reporter else []
        candidates = nearest_responders(state, cell, exclude=exclude)
        if candidates:
            r = candidates[0]
            briefings.append(
                Briefing(
                    responder_id=r.id,
                    text=f"{ctx.cs(r)}: {ctx.reporter_cs} needs help {where}{need}. Respond if able.",
                    urgency=urgency,
                    reason=f"nearest available responder to help request {where}",
                    trigger_ids=ctx.trigger_ids(),
                    show_cell=cell,
                )
            )
        notes.append(f"{ctx.reporter_cs} needs help {where}{need}.")

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _synthetic_victim(ctx: "_Ctx", tr: TriageResult) -> VictimEstimate:
        """Victim placeholder when the world model did not hand us a victim id."""
        zone = resolve_zone(ctx.state.building, tr.zone, tr.floor)
        cell = zone.center if zone else (ctx.reporter.cell if ctx.reporter and ctx.reporter.cell else Cell(floor=tr.floor or 0, x=0, y=0))
        status = VictimStatus.CONFIRMED if tr.victim_certainty == "confirmed" else VictimStatus.SUSPECTED
        return VictimEstimate(
            id="",
            cell=cell,
            zone=zone.name if zone else tr.zone,
            probability=0.95 if status == VictimStatus.CONFIRMED else 0.6,
            status=status,
            count=max(1, tr.victim_count),
            condition=tr.victim_condition,
        )


class _Ctx:
    """Per-decision view of the delta and state with cached lookups."""

    def __init__(self, delta: StateDelta, state: WorldState):
        self.delta = delta
        self.state = state
        rid = reporter_of(delta)
        self.reporter: Optional[Responder] = state.responders.get(rid) if rid else None
        self.roster = list(state.responders.values())
        self.reporter_cs = self.cs(self.reporter) if self.reporter else "a responder"

    def cs(self, r: Optional[Responder]) -> str:
        return callsign(r, self.roster) if r else "unknown"

    def where(self, floor: Optional[int], zone: Optional[str]) -> str:
        """'floor 5 stairwell B' / 'floor 5' / 'outside staging area'."""
        if floor is not None and floor >= 1:
            return f"floor {floor} {zone}" if zone else f"floor {floor}"
        if zone:
            return f"outside {zone}"
        return "location unknown"

    def trigger_ids(self) -> list[str]:
        ids: list[str] = []
        if self.delta.triage:
            ids.append(self.delta.triage.report_id)
        if self.delta.touch:
            ids.append(self.delta.touch.id)
        ids.extend(self.delta.changed_hazards)
        return ids
