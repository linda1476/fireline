"""R1..R5 (docs/CONTRACT.md "Rules"). Pure functions over a models.State + scenario clock t.

evaluate(state, t, thresholds) -> list[Action]; World applies the actions. Every rule is idempotent
(re-evaluated each 1 Hz tick), so actions are only returned when they change something.
R3 fires on DANGER events and is exposed separately as r3_on_event(event, state).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.config import Settings, get_settings
from server.models import Event, State

OPEN_STATES = ("open", "escalated")

R2_TITLE_KO = "3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1)"
R2_TITLE_EN = "3 unanswered pings = MAYDAY condition (SOP 109 §1.1)"


# ----------------------------------------------------------------------------- actions
@dataclass
class Escalate:
    card_id: str
    level: int
    rule_id: str


@dataclass
class Ping:
    unit_id: str
    n: int                 # the ping number (1-based) after this ping
    rule_id: str = "R2"


@dataclass
class RuleCard:
    rule_id: str
    unit_id: str
    zone_id: str | None
    title: str
    title_en: str
    priority: int = 0
    last_heard_t: float | None = None


@dataclass
class ProposeOrder:
    kind: str
    units: list[str]
    text: str
    rationale: str
    rule_id: str
    card_id: str | None = None
    evidence_event_id: str | None = None


Action = Escalate | Ping | RuleCard | ProposeOrder


# ----------------------------------------------------------------------------- helpers
def _open_cards(state: State):
    return [c for c in state.cards if c.state in OPEN_STATES]


def _has_open_mayday(state: State, unit_id: str) -> bool:
    return any(
        c.unit_id == unit_id and (c.kind == "MAYDAY" or (c.kind == "RULE" and c.rule_id == "R2"))
        for c in _open_cards(state)
    )


def _has_proposal(state: State, card_id: str | None, kind: str) -> bool:
    return any(p.card_id == card_id and p.kind == kind for p in state.proposals)


def _event(state: State, event_id: str) -> Event | None:
    for e in state.events:
        if e.id == event_id:
            return e
    return None


def _fmt_t(t: float | None) -> str:
    if t is None:
        return "?"
    m, s = divmod(int(t), 60)
    return f"{m}:{s:02d}"


# ----------------------------------------------------------------------------- rules
def r1(state: State, t: float, th: Settings) -> list[Action]:
    """MAYDAY / R2 cards unacked: level 1 at ≥ r1_ack_s, level 2 at ≥ r1_level2_s.
    Evaluated on open|escalated (state 'escalated' is itself set by level 1)."""
    out: list[Action] = []
    for c in _open_cards(state):
        if not (c.kind == "MAYDAY" or (c.kind == "RULE" and c.rule_id == "R2")):
            continue
        age = t - c.created_t
        target = 2 if age >= th.r1_level2_s else 1 if age >= th.r1_ack_s else 0
        if target > c.escalation_level:
            out.append(Escalate(c.id, target, "R1"))
    return out


def r2(state: State, t: float, th: Settings) -> list[Action]:
    """Interior unit silent ≥ r2_silent_s: ping every r2_ping_gap_s; RULE card at the r2_pings-th ping.
    Stateless: next ping time = last_heard_t + silent_s + unanswered_pings * gap."""
    out: list[Action] = []
    for u in state.units.values():
        if not u.interior or u.status == "OUT" or u.last_heard_t is None:
            continue
        if _has_open_mayday(state, u.id):
            continue
        n = u.unanswered_pings
        if n >= th.r2_pings:
            continue
        due = u.last_heard_t + th.r2_silent_s + n * th.r2_ping_gap_s
        if t + 1e-9 >= due:
            out.append(Ping(u.id, n + 1))
            if n + 1 >= th.r2_pings:
                out.append(RuleCard(
                    "R2", u.id, u.zone_id,
                    title=f"{R2_TITLE_KO} · {u.name or u.callsign} · last heard {_fmt_t(u.last_heard_t)}",
                    title_en=f"{R2_TITLE_EN} · {u.label_en or u.callsign}",
                    priority=0, last_heard_t=u.last_heard_t,
                ))
    return out


def r3_on_event(event: Event, state: State) -> list[Action]:
    """DANGER event while strategy OFFENSIVE → Proposal CONFIRM_STRATEGY linked to the DANGER card."""
    if event.triage.tag != "DANGER" or state.strategy != "OFFENSIVE":
        return []
    card = next((c for c in state.cards if event.id in c.event_ids), None)
    card_id = card.id if card else None
    if _has_proposal(state, card_id, "CONFIRM_STRATEGY") and card_id is not None:
        return []
    terms = ", ".join(event.triage.hazard_terms) or event.triage.evidence_span or "위험 보고"
    where = (card.fields.get("where") if card else None) or event.zone_id_snapped or "?"
    crews = [u.id for u in state.units.values() if u.role == "CREW" and u.interior]
    return [ProposeOrder(
        kind="CONFIRM_STRATEGY", units=crews,
        text=f"공격전략 유지 재확인 — {where} 위험: {terms}",
        rationale=f"R3: DANGER ({terms}) while strategy OFFENSIVE; confirm or switch to DEFENSIVE",
        rule_id="R3", card_id=card_id, evidence_event_id=event.id,
    )]


def r4(state: State, t: float, th: Settings) -> list[Action]:
    """VICTIM_FOUND card, victims not EXTRACTING, no unit assigned within r4_assign_s → Proposal ASSIGN."""
    out: list[Action] = []
    for c in _open_cards(state):
        if c.kind != "VICTIM_FOUND" or t - c.created_t < th.r4_assign_s:
            continue
        if _has_proposal(state, c.id, "ASSIGN"):
            continue
        extracting = False
        for eid in c.event_ids:
            e = _event(state, eid)
            if e and e.triage.victims and e.triage.victims.state == "EXTRACTING":
                extracting = True
        if extracting or (c.fields.get("state") == "EXTRACTING"):
            continue
        if c.zone_id and any(u.assignment == c.zone_id for u in state.units.values()):
            continue
        cand = [u.id for u in state.units.values() if u.role in ("CREW", "RIT") and u.id != c.unit_id
                and u.status not in ("TRAPPED", "LOW_AIR")]
        units = cand[:1]
        where = c.fields.get("where") or c.zone_id or "?"
        out.append(ProposeOrder(
            kind="ASSIGN", units=units, text=f"구조대상자 {where} 구조 배정",
            rationale=f"R4: victim reported {_fmt_t(c.created_t)}, nobody assigned after {int(th.r4_assign_s)} s",
            rule_id="R4", card_id=c.id, evidence_event_id=c.event_ids[0] if c.event_ids else None,
        ))
    return out


def r5(state: State, t: float, th: Settings) -> list[Action]:
    """Unit LOW_AIR or HELP_NEEDED card without an EXITING event from that unit within r5_exit_s → escalate level 1."""
    out: list[Action] = []
    low_air = {u.id for u in state.units.values() if u.status == "LOW_AIR"}
    for c in _open_cards(state):
        if c.escalation_level >= 1:
            continue
        if not (c.kind == "HELP_NEEDED" or (c.unit_id in low_air and c.kind != "RULE")):
            continue
        if t - c.created_t < th.r5_exit_s:
            continue
        exited = any(
            (e.speaker_unit_snapped == c.unit_id) and e.triage.status_change == "EXITING" and e.t >= c.created_t
            for e in state.events
        )
        if not exited:
            out.append(Escalate(c.id, 1, "R5"))
    return out


def evaluate(state: State, t: float, thresholds: Settings | None = None) -> list[Action]:
    th = thresholds or get_settings()
    actions: list[Action] = []
    actions += r1(state, t, th)
    actions += r2(state, t, th)
    actions += r4(state, t, th)
    # R5 must not re-escalate a card R1 already escalates in this tick
    seen = {a.card_id for a in actions if isinstance(a, Escalate)}
    actions += [a for a in r5(state, t, th) if a.card_id not in seen]
    return actions


__all__ = ["Escalate", "Ping", "RuleCard", "ProposeOrder", "Action", "evaluate", "r3_on_event",
           "R2_TITLE_KO", "R2_TITLE_EN", "field"]
