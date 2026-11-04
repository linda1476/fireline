"""Unified World Model: the pure-Python reducer behind the shared WorldState.

``WorldModel`` fuses triage results (radio), touch inputs (clip display) and
helmet-cam detections into one ``WorldState``. Every mutator bumps
``state.version``, refreshes ``updated_at``, appends human-readable
``WorldEvent`` rows and returns a ``StateDelta`` describing what changed.
No LLM calls happen here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

from fireline.models import (
    Assignment,
    Briefing,
    Cell,
    Detection,
    Hazard,
    QueueItem,
    RadioReport,
    Responder,
    ResponderStatus,
    StateDelta,
    Tag,
    TouchInput,
    TriageResult,
    VictimEstimate,
    VictimStatus,
    WorldEvent,
    WorldState,
    Zone,
    now_iso,
)
from fireline.worldmodel import spatial

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

P_SUSPECTED = 0.6
P_CONFIRMED = 0.95
P_TOUCH = 0.9
AIR_LOW = 5
MAYDAY_BONUS = 25
ACK_PENALTY = 100
RECENCY_MAX_MIN = 10

CLEAR_WORDS = ("clear", "knocked down", "under control", "extinguished")
CLEARABLE_HAZARDS = ("heavy smoke", "high heat", "smoke", "heat")
SEVERITY_5 = ("collapse", "flashover", "mayday", "trapped", "pinned")
SEVERITY_4 = ("low air", "blocked")

_STATUS_RANK = {VictimStatus.SUSPECTED: 0, VictimStatus.CONFIRMED: 1, VictimStatus.EXTRACTED: 2}
_WE_RE = re.compile(r"\bwe(?:'re|'ve| are| can| got)\b|\bboth of us\b|\ball of us\b", re.IGNORECASE)
"""An 'I'm okay' report that speaks for the crew ('we're coming down') clears crewmates too."""


# ---------------------------------------------------------------------------
# Scoring (duplicated from triage on purpose: no cross-module import)
# ---------------------------------------------------------------------------


def _age_minutes(timestamp: str) -> float:
    try:
        ts = datetime.fromisoformat(timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 60.0)
    except (ValueError, TypeError):
        return 0.0


def queue_score(item: QueueItem) -> float:
    """priority*10 + 25 if mayday + recency (0..10, fades over 10 min) - 100 if acknowledged."""
    t = item.triage
    recency = max(0.0, RECENCY_MAX_MIN - _age_minutes(item.report.timestamp))
    score = t.priority * 10 + (MAYDAY_BONUS if t.mayday else 0) + recency
    if item.acknowledged:
        score -= ACK_PENALTY
    return round(score, 3)


def hazard_severity(kind: str) -> int:
    k = kind.lower()
    if any(w in k for w in SEVERITY_5):
        return 5
    if any(w in k for w in SEVERITY_4):
        return 4
    return 3


# ---------------------------------------------------------------------------
# Change accumulator
# ---------------------------------------------------------------------------


@dataclass
class _Change:
    """Collects ids and events touched by one reducer step."""

    responders: list[str] = field(default_factory=list)
    victims: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    events: list[WorldEvent] = field(default_factory=list)

    def responder(self, rid: Optional[str]) -> None:
        if rid and rid not in self.responders:
            self.responders.append(rid)

    def victim(self, vid: str) -> None:
        if vid not in self.victims:
            self.victims.append(vid)

    def hazard(self, hid: str) -> None:
        if hid not in self.hazards:
            self.hazards.append(hid)

    def event(self, kind: str, text: str, responder_id: Optional[str] = None, ref_id: Optional[str] = None) -> None:
        self.events.append(WorldEvent(kind=kind, text=text, responder_id=responder_id, ref_id=ref_id))


# ---------------------------------------------------------------------------
# World model
# ---------------------------------------------------------------------------


class WorldModel:
    """Owns one ``WorldState`` and applies every input to it deterministically."""

    def __init__(self, state: WorldState):
        self.state = state
        self._seq: dict[str, int] = {q.report.id: i for i, q in enumerate(state.queue)}

    # -- public: queries ---------------------------------------------------

    @property
    def building(self):
        return self.state.building

    def snapshot(self) -> dict:
        """JSON-safe dump of the whole state."""
        return self.state.model_dump(mode="json")

    def resolve_zone(self, name: Optional[str], floor: Optional[int] = None) -> Optional[Cell]:
        """Zone centre for a zone name/alias, preferring ``floor``; None if unknown."""
        zone = spatial.find_zone(self.building, name, floor)
        return zone.center if zone else None

    def nearby_responders(self, cell: Cell, max_cells: int = 8) -> list[Responder]:
        """Responders within ``max_cells`` travel distance of ``cell`` (any floor), nearest first."""
        scored = []
        for r in self.state.responders.values():
            if r.cell is None:
                continue
            d = spatial.cell_distance(self.building, cell, r.cell)
            if d <= max_cells:
                scored.append((d, r.id, r))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [r for _, _, r in scored]

    # -- public: reducers --------------------------------------------------

    def apply_triage(self, result: TriageResult, report: RadioReport) -> StateDelta:
        """Fuse one triage result into the state and push it on the queue."""
        ch = _Change()
        rid = result.responder_id or report.responder_id
        responder = self.state.responders.get(rid) if rid else None
        zone = spatial.find_zone(self.building, result.zone, result.floor)
        pre_cell = responder.cell if responder else None
        label = rid or "unknown unit"

        if result.victim_certainty != "none":
            self._triage_victims(result, report, zone, responder, pre_cell, label, ch)
        if responder is not None:
            self._triage_responder(result, report, zone, responder, ch)
        self._triage_hazards(result, report, zone, responder, label, ch)
        if result.mayday:
            where = self._where(zone, result.floor)
            ch.event("triage", f"MAYDAY from {label} at {where}", rid, report.id)
        if not ch.events:
            ch.event("triage", f"{label}: {result.summary}", rid, report.id)

        self._seq[report.id] = len(self._seq)
        self.state.queue.append(QueueItem(triage=result, report=report))
        self._rescore_queue()
        return self._commit(ch, triage=result)

    def apply_touch(self, touch: TouchInput) -> StateDelta:
        """Apply one clip-display button press."""
        ch = _Change()
        rid = touch.responder_id
        responder = self.state.responders.get(rid)
        handler = {
            "mark_victim": self._touch_mark_victim,
            "need_help": self._touch_status,
            "im_ok": self._touch_status,
            "clear_danger": self._touch_status,
            "victim_out": self._touch_victim_out,
            "ack": self._touch_ack,
        }[touch.action]
        if responder is None and touch.action != "ack":
            ch.event("touch", f"{rid} pressed {touch.action} (unknown responder)", rid, touch.id)
        else:
            handler(touch, responder, ch)
        return self._commit(ch, touch=touch)

    def apply_detections(self, responder_id: str, detections: list[Detection], photo_id: str) -> StateDelta:
        """Fuse helmet-cam person detections into a victim estimate at the responder's cell."""
        ch = _Change()
        n = len(detections)
        responder = self.state.responders.get(responder_id)
        cell = responder.cell if responder else None
        if n == 0 or cell is None:
            why = "no people detected" if n == 0 else "responder position unknown"
            ch.event("photo", f"{responder_id} helmet cam: {why}", responder_id, photo_id)
            return self._commit(ch, detections=detections)

        p = min(P_CONFIRMED, 0.5 + 0.4 * max(d.score for d in detections))
        zone = spatial.zone_containing(self.building, cell)
        victim = self._upsert_victim(
            cell=cell, zone=zone, probability=p, status=VictimStatus.SUSPECTED, count=n,
            condition=None, source="camera", source_id=photo_id, ch=ch,
        )
        where = zone.name if zone else f"floor {cell.floor} ({cell.x},{cell.y})"
        ch.event("photo", f"{responder_id} helmet cam sees {n} person(s) in {where} (p={victim.probability:.2f})",
                 responder_id, photo_id)
        return self._commit(ch, detections=detections)

    def ack(self, report_id: str) -> StateDelta:
        """Commander acknowledges a queue item; it sinks to the bottom."""
        ch = _Change()
        for item in self.state.queue:
            if item.report.id == report_id and not item.acknowledged:
                item.acknowledged = True
                ch.event("system", f"Command acknowledged {item.triage.responder_id or '?'}: {item.triage.summary}",
                         item.triage.responder_id, report_id)
                break
        self._rescore_queue()
        return self._commit(ch)

    def set_assignment(self, victim_id: str, responder_id: str) -> StateDelta:
        """Assign a responder to a victim estimate."""
        ch = _Change()
        victim = self.state.victims.get(victim_id)
        if victim is not None:
            victim.assigned_responder_id = responder_id
            victim.updated_at = now_iso()
            ch.victim(victim_id)
            ch.responder(responder_id)
            ch.event("assignment", f"{responder_id} assigned to victim in {victim.zone or 'unknown zone'}",
                     responder_id, victim_id)
        return self._commit(ch)

    def record_briefing(self, briefing: Briefing) -> StateDelta:
        """Log a briefing the briefer pushed to a responder."""
        ch = _Change()
        ch.event("briefing", f"-> {briefing.responder_id} [{briefing.urgency.value}]: {briefing.text}",
                 briefing.responder_id, briefing.id)
        return self._commit(ch)

    def record_assignment(self, assignment: Assignment) -> StateDelta:
        """Log an assignment proposal; an accepted victim assignment is also applied."""
        ch = _Change()
        verb = {True: "accepted", False: "declined", None: "proposed"}[assignment.accepted]
        ch.event("assignment", f"Assignment {verb}: {assignment.responder_id} -> {assignment.target_kind} "
                 f"{assignment.target_id} ({assignment.reason})", assignment.responder_id, assignment.id)
        if assignment.accepted and assignment.target_kind == "victim":
            victim = self.state.victims.get(assignment.target_id)
            if victim is not None:
                victim.assigned_responder_id = assignment.responder_id
                victim.updated_at = now_iso()
                ch.victim(victim.id)
                ch.responder(assignment.responder_id)
        return self._commit(ch)

    # -- triage sub-steps --------------------------------------------------

    def _triage_responder(self, result: TriageResult, report: RadioReport, zone: Optional[Zone],
                          responder: Responder, ch: _Change) -> None:
        """Move / restatus / decrement air for the reporting responder."""
        if zone is not None:
            cell = zone.center
            if responder.cell is None or responder.cell != cell:
                responder.track.append(cell)
                responder.track = responder.track[-50:]
            responder.cell = cell
            responder.zone = zone.name
        prev_status = responder.status
        new_status = self._status_for(result, responder.status)
        if new_status != responder.status:
            responder.status = new_status
            ch.event("triage", f"{responder.id} status -> {new_status.value}", responder.id, report.id)
        if responder.air_minutes is not None and responder.cell and responder.cell.floor > 0:
            responder.air_minutes = max(0, responder.air_minutes - 1)
        self._apply_low_air(result, report, responder, ch)
        responder.last_report_id = report.id
        responder.last_seen = result.timestamp or now_iso()
        ch.responder(responder.id)
        if result.mayday:
            self._mayday_crewmates(result, report, responder, zone, ch)
        elif (prev_status == ResponderStatus.IN_DANGER and new_status == ResponderStatus.OK
              and _WE_RE.search(report.transcript or "")):
            self._mayday_resolved_crewmates(report, responder, ch)

    def _mayday_resolved_crewmates(self, report: RadioReport, reporter: Responder, ch: _Change) -> None:
        """Mirror of :meth:`_mayday_crewmates`: 'I'm okay, we're coming down' from a crew that was in a
        mayday clears the same-unit crewmates on that floor too (the RIT got them out together)."""
        floor = reporter.cell.floor if reporter.cell else None
        for r in self.state.responders.values():
            if r.id == reporter.id or r.unit != reporter.unit or r.status != ResponderStatus.IN_DANGER:
                continue
            if floor is not None and r.cell is not None and r.cell.floor != floor:
                continue
            r.status = ResponderStatus.OK
            ch.event("triage", f"{r.id} status -> OK (crew of {reporter.id} reports okay)", r.id, report.id)
            ch.responder(r.id)

    @staticmethod
    def _status_for(result: TriageResult, current: ResponderStatus) -> ResponderStatus:
        if result.mayday:
            return ResponderStatus.IN_DANGER
        if result.responder_status != ResponderStatus.UNKNOWN:
            return result.responder_status
        if result.tag == Tag.HELP_NEEDED:
            return ResponderStatus.NEEDS_HELP
        return current

    def _mayday_crewmates(self, result: TriageResult, report: RadioReport, reporter: Responder,
                          zone: Optional[Zone], ch: _Change) -> None:
        """A mayday also flags same-unit crew on that floor (they are usually the casualty)."""
        floor = zone.floor if zone else (result.floor if result.floor is not None else
                                         (reporter.cell.floor if reporter.cell else None))
        for r in self.state.responders.values():
            if r.id == reporter.id or r.unit != reporter.unit or r.cell is None:
                continue
            if floor is not None and r.cell.floor != floor:
                continue
            if r.status != ResponderStatus.IN_DANGER:
                r.status = ResponderStatus.IN_DANGER
                ch.event("triage", f"{r.id} status -> InDanger (crew of {reporter.id} mayday)", r.id, report.id)
            ch.responder(r.id)

    def _apply_low_air(self, result: TriageResult, report: RadioReport, reporter: Responder, ch: _Change) -> None:
        if not any("low air" in h.lower() for h in result.hazards):
            return
        for r in self._low_air_targets(report.transcript, reporter):
            r.air_minutes = min(AIR_LOW, r.air_minutes) if r.air_minutes is not None else AIR_LOW
            ch.responder(r.id)
            ch.event("triage", f"{r.id} low air ({r.air_minutes} min)", r.id, report.id)

    def _low_air_targets(self, transcript: str, reporter: Responder) -> list[Responder]:
        """Crewmates named by number in the transcript ("low air on 1-2"), else the reporter."""
        hits = []
        for r in self.state.responders.values():
            if r.unit != reporter.unit or r.id == reporter.id:
                continue
            number = re.sub(r"^[A-Za-z]+", "", r.id)
            if number and re.search(rf"(?<![\w-]){re.escape(number)}(?![\w-])", transcript):
                hits.append(r)
        return hits or [reporter]

    def _triage_victims(self, result: TriageResult, report: RadioReport, zone: Optional[Zone],
                        responder: Optional[Responder], pre_cell: Optional[Cell], label: str, ch: _Change) -> None:
        """Create / merge / extract victims for one triage result."""
        if result.victim_certainty == "extracted":
            self._extract_victim(result, report, zone, pre_cell, label, ch)
            return
        if zone is None:
            if pre_cell is None:
                ch.event("triage", f"{label} reports a victim but location is unknown: {result.summary}",
                         responder.id if responder else None, report.id)
                return
            zone = spatial.zone_containing(self.building, pre_cell)
            cell = pre_cell
        else:
            cell = None
        status = VictimStatus.CONFIRMED if result.victim_certainty == "confirmed" else VictimStatus.SUSPECTED
        p = P_CONFIRMED if status == VictimStatus.CONFIRMED else P_SUSPECTED
        count = max(1, result.victim_count)
        victim = self._upsert_victim(
            cell=cell, zone=zone, probability=p, status=status, count=count,
            condition=result.victim_condition, source="radio", source_id=report.id, ch=ch,
        )
        where = zone.name if zone else self._where(None, cell.floor if cell else result.floor)
        ch.event("triage", f"{label} reports {victim.count} victim(s) in {where} ({victim.status.value})",
                 responder.id if responder else None, report.id)

    def _extract_victim(self, result: TriageResult, report: RadioReport, zone: Optional[Zone],
                        pre_cell: Optional[Cell], label: str, ch: _Change) -> None:
        """Mark the victim being carried out: in the report zone, else nearest to the responder, else new."""
        victim = None
        if zone is not None:
            victim = self._find_victim_in_zone(zone)
        if victim is None and pre_cell is not None:
            victim = self._nearest_victim(pre_cell)
        if victim is None:
            anchor = zone.center if zone else pre_cell
            if anchor is None:
                ch.event("triage", f"{label} reports a victim extracted (location unknown)", None, report.id)
                return
            victim = VictimEstimate(cell=anchor, zone=zone.name if zone else None, probability=P_CONFIRMED,
                                    status=VictimStatus.EXTRACTED, count=max(1, result.victim_count),
                                    condition=result.victim_condition, source="radio")
            self.state.victims[victim.id] = victim
        victim.status = VictimStatus.EXTRACTED
        victim.count = max(victim.count, result.victim_count)
        victim.condition = victim.condition or result.victim_condition
        if report.id not in victim.source_report_ids:
            victim.source_report_ids.append(report.id)
        victim.updated_at = now_iso()
        ch.victim(victim.id)
        ch.event("triage", f"{label} extracted {victim.count} victim(s) from {victim.zone or 'unknown zone'}",
                 None, report.id)

    def _triage_hazards(self, result: TriageResult, report: RadioReport, zone: Optional[Zone],
                        responder: Optional[Responder], label: str, ch: _Change) -> None:
        """One Hazard per reported string (deduped); Status "clear" reports deactivate smoke/heat."""
        anchor = zone.center if zone else (responder.cell if responder else None)
        if result.hazards and anchor is not None:
            kinds = []
            for raw in result.hazards:
                kind = raw.strip().lower()
                if not kind:
                    continue
                # "stairwell B blocked" reported from stairwell A belongs on stairwell B.
                named = self._stair_named_in(kind, result.floor if result.floor is not None else anchor.floor)
                hz_zone, hz_cell = (named, named.center) if named else (zone, anchor)
                hazard = self._upsert_hazard(kind, hz_cell, hz_zone, report.id)
                ch.hazard(hazard.id)
                kinds.append(kind)
            if kinds:
                ch.event("triage", f"{label} reports {', '.join(kinds)} at {self._where(zone, anchor.floor)}",
                         responder.id if responder else None, report.id)
        elif result.hazards:
            ch.event("triage", f"{label} reports {', '.join(result.hazards)} (location unknown)",
                     responder.id if responder else None, report.id)
        elif result.tag == Tag.STATUS and zone is not None and self._says_clear(result, report):
            cleared = self._clear_zone_hazards(zone)
            for h in cleared:
                ch.hazard(h.id)
            if cleared:
                ch.event("triage", f"{label} reports {zone.name} clear: {', '.join(h.kind for h in cleared)} cleared",
                         responder.id if responder else None, report.id)

    def _stair_named_in(self, kind: str, floor: Optional[int]) -> Optional[Zone]:
        """The stair zone a hazard string names ('stairwell B blocked', 'stair A collapse'), on ``floor``."""
        for z in self.building.zones:
            if z.kind != "stair":
                continue
            names = [z.name.lower(), *(a.lower() for a in z.aliases)]
            if any(re.search(rf"\b{re.escape(n)}\b", kind) for n in names):
                return spatial.find_zone(self.building, z.name, floor) or z
        return None

    @staticmethod
    def _says_clear(result: TriageResult, report: RadioReport) -> bool:
        text = f"{result.summary} {report.transcript}".lower()
        return any(w in text for w in CLEAR_WORDS)

    def _clear_zone_hazards(self, zone: Zone) -> list[Hazard]:
        cleared = []
        for h in self.state.hazards.values():
            if h.active and zone.contains(h.cell) and any(k in h.kind.lower() for k in CLEARABLE_HAZARDS):
                h.active = False
                cleared.append(h)
        return cleared

    # -- touch sub-steps ---------------------------------------------------

    def _touch_mark_victim(self, touch: TouchInput, responder: Responder, ch: _Change) -> None:
        cell = touch.cell or responder.cell
        if cell is None:
            ch.event("touch", f"{responder.id} marked a victim but has no position", responder.id, touch.id)
            return
        zone = spatial.zone_containing(self.building, cell)
        self._upsert_victim(cell=cell, zone=zone, probability=P_TOUCH, status=VictimStatus.CONFIRMED,
                            count=1, condition=None, source="touch", source_id=touch.id, ch=ch)
        where = zone.name if zone else self._where(None, cell.floor)
        ch.event("touch", f"{responder.id} marked a victim in {where} (confirmed)", responder.id, touch.id)
        ch.responder(responder.id)

    def _touch_status(self, touch: TouchInput, responder: Responder, ch: _Change) -> None:
        new_status = ResponderStatus.NEEDS_HELP if touch.action == "need_help" else ResponderStatus.OK
        responder.status = new_status
        responder.last_seen = touch.timestamp
        ch.responder(responder.id)
        text = {"need_help": "needs help", "im_ok": "reports OK", "clear_danger": "cleared danger"}[touch.action]
        ch.event("touch", f"{responder.id} {text} (status {new_status.value})", responder.id, touch.id)
        if touch.action == "clear_danger":
            for h in self._hazards_near(touch.cell or responder.cell, "collapse"):
                h.active = False
                ch.hazard(h.id)
                ch.event("touch", f"{responder.id} cleared {h.kind} at {h.zone or 'their position'}",
                         responder.id, touch.id)

    def _touch_victim_out(self, touch: TouchInput, responder: Responder, ch: _Change) -> None:
        victim = self.state.victims.get(touch.victim_id) if touch.victim_id else None
        if victim is None and responder.cell is not None:
            victim = self._nearest_victim(responder.cell)
        if victim is None:
            ch.event("touch", f"{responder.id} reports victim out (no known victim nearby)", responder.id, touch.id)
            return
        victim.status = VictimStatus.EXTRACTED
        if touch.id not in victim.source_report_ids:
            victim.source_report_ids.append(touch.id)
        victim.updated_at = now_iso()
        ch.victim(victim.id)
        ch.responder(responder.id)
        ch.event("touch", f"{responder.id} extracted victim from {victim.zone or 'unknown zone'}",
                 responder.id, touch.id)

    def _touch_ack(self, touch: TouchInput, responder: Optional[Responder], ch: _Change) -> None:
        rid = touch.responder_id
        candidates = [q for q in self.state.queue
                      if not q.acknowledged and (q.triage.responder_id or q.report.responder_id) == rid]
        if not candidates:
            ch.event("touch", f"{rid} ack (nothing pending)", rid, touch.id)
            return
        # Timestamps are millisecond-resolution, so the push sequence breaks ties.
        newest = max(candidates, key=lambda q: (q.report.timestamp, self._seq.get(q.report.id, 0)))
        newest.acknowledged = True
        self._rescore_queue()
        ch.event("touch", f"{rid} acknowledged: {newest.triage.summary}", rid, newest.report.id)

    # -- victims -----------------------------------------------------------

    def _victims_in_zone(self, zone: Zone) -> list[VictimEstimate]:
        return [v for v in self.state.victims.values()
                if v.cell.floor == zone.floor and (v.zone == zone.name or zone.contains(v.cell))]

    def _find_victim_in_zone(self, zone: Zone) -> Optional[VictimEstimate]:
        """Oldest non-extracted victim in the zone, if any."""
        live = [v for v in self._victims_in_zone(zone) if v.status != VictimStatus.EXTRACTED]
        return min(live, key=lambda v: v.created_at) if live else None

    def _nearest_victim(self, cell: Cell) -> Optional[VictimEstimate]:
        live = [v for v in self.state.victims.values() if v.status != VictimStatus.EXTRACTED]
        if not live:
            return None
        return min(live, key=lambda v: (spatial.cell_distance(self.building, cell, v.cell), v.created_at))

    def _upsert_victim(self, *, cell: Optional[Cell], zone: Optional[Zone], probability: float,
                       status: VictimStatus, count: int, condition: Optional[str], source: str,
                       source_id: str, ch: _Change) -> VictimEstimate:
        """Merge into the live victim in the same floor+zone (or same cell), else create."""
        existing = self._find_victim_in_zone(zone) if zone else self._victim_at(cell)
        if existing is not None:
            self._merge_victim(existing, cell, probability, status, count, condition, source, source_id)
            ch.victim(existing.id)
            return existing
        if cell is None:
            assert zone is not None
            cell = spatial.victim_cell(zone, len(self._victims_in_zone(zone)))
        elif self._victim_at(cell) is not None:
            cell = spatial.offset_cell(self.building, cell, 1, 0)
        victim = VictimEstimate(cell=cell, zone=zone.name if zone else None, probability=probability,
                                status=status, count=count, condition=condition,
                                source_report_ids=[source_id], source=source)
        self.state.victims[victim.id] = victim
        ch.victim(victim.id)
        return victim

    def _victim_at(self, cell: Optional[Cell]) -> Optional[VictimEstimate]:
        if cell is None:
            return None
        for v in self.state.victims.values():
            if v.cell == cell and v.status != VictimStatus.EXTRACTED:
                return v
        return None

    @staticmethod
    def _merge_victim(v: VictimEstimate, cell: Optional[Cell], probability: float, status: VictimStatus,
                      count: int, condition: Optional[str], source: str, source_id: str) -> None:
        v.probability = max(v.probability, probability)
        v.count = max(v.count, count)
        if _STATUS_RANK[status] > _STATUS_RANK[v.status]:
            v.status = status
        if cell is not None and source == "touch":
            v.cell = cell  # a tap is more precise than a zone centre
        v.condition = v.condition or condition
        if source_id not in v.source_report_ids:
            v.source_report_ids.append(source_id)
        if v.source != source:
            v.source = "fused"
        v.updated_at = now_iso()

    # -- hazards -----------------------------------------------------------

    def _upsert_hazard(self, kind: str, cell: Cell, zone: Optional[Zone], report_id: str) -> Hazard:
        """Dedupe by kind + floor + zone; refresh timestamp and reactivate."""
        zname = zone.name if zone else None
        for h in self.state.hazards.values():
            if h.kind == kind and h.cell.floor == cell.floor and h.zone == zname:
                h.active = True
                h.created_at = now_iso()
                if report_id not in h.source_report_ids:
                    h.source_report_ids.append(report_id)
                return h
        hazard = Hazard(kind=kind, cell=cell, zone=zname, severity=hazard_severity(kind),
                        source_report_ids=[report_id])
        self.state.hazards[hazard.id] = hazard
        return hazard

    def _hazards_near(self, cell: Optional[Cell], kind_contains: str, radius: int = 2) -> list[Hazard]:
        """Active hazards of a kind in the cell's zone or within ``radius`` cells on that floor."""
        if cell is None:
            return []
        zone = spatial.zone_containing(self.building, cell)
        out = []
        for h in self.state.hazards.values():
            if not h.active or kind_contains not in h.kind.lower() or h.cell.floor != cell.floor:
                continue
            if (zone is not None and zone.contains(h.cell)) or spatial.chebyshev(h.cell, cell) <= radius:
                out.append(h)
        return out

    # -- plumbing ----------------------------------------------------------

    def _where(self, zone: Optional[Zone], floor: Optional[int]) -> str:
        if zone is not None:
            return f"{zone.name} (floor {zone.floor})" if zone.floor else zone.name
        if floor is not None:
            return f"floor {floor}" if floor else "outside"
        return "unknown location"

    def _rescore_queue(self) -> None:
        for item in self.state.queue:
            item.score = queue_score(item)
        self.state.queue.sort(key=lambda q: (q.score, q.report.timestamp), reverse=True)

    def _commit(self, ch: _Change, *, triage: Optional[TriageResult] = None, touch: Optional[TouchInput] = None,
                detections: Iterable[Detection] = ()) -> StateDelta:
        """Bump version, stamp time, append events, build the delta."""
        s = self.state
        s.version += 1
        s.updated_at = now_iso()
        s.events.extend(ch.events)
        self._rescore_queue()  # recency decays with wall-clock: keep "sorted" true after every apply
        return StateDelta(
            version=s.version, triage=triage, touch=touch, detections=list(detections),
            changed_responders=list(ch.responders), changed_victims=list(ch.victims),
            changed_hazards=list(ch.hazards), new_events=list(ch.events),
        )
