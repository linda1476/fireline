"""Deterministic zone-match router: used when the agent is cut, errors or times out (docs/CONTRACT.md).

route(event, world) -> list[Brief]. Push triage.crew_brief (or a template) to crew units whose zone/assignment is
the event zone, its parent/children or vertical neighbour (same rule as checker invariant 1); every crew unit for
MAYDAY (P0) EXCEPT the member in distress (checker.distressed_unit, invariant 7: never brief a unit about its own
mayday; it is held and gets a hold-position brief only when the IC approves RIT_DEPLOY); hold for everyone else with
reason "not your sector (zone X)".
"""

from __future__ import annotations

from typing import Any

from server.checker import PUSH_GAP_S, check_text, distressed_unit, related_zones, unit_in_zones
from server.models import Brief, Event

CREW_ROLES = ("CREW", "RIT", "EXTERIOR")

_TEMPLATES = {
    "ko": {
        "MAYDAY": "긴급탈출 상황: {where}. 무선 침묵, 지휘대장 지시 대기.",
        "DANGER": "위험 정보: {where} {terms}. 퇴로 확인.",
        "VICTIM_FOUND": "구조대상자 발견: {where}.",
        "HELP_NEEDED": "지원 요청: {where}.",
    },
    "en": {
        "MAYDAY": "Mayday: {where}. Radio silence, stand by for Command.",
        "DANGER": "Hazard at {where}: {terms}. Check your exit.",
        "VICTIM_FOUND": "Victim found at {where}.",
        "HELP_NEEDED": "Help requested at {where}.",
    },
}


def template_text(event: Event, lang: str) -> str:
    tr = event.triage
    where = event.zone_id_snapped or tr.location.raw or tr.location.zone_hint or "?"
    terms = ", ".join(tr.hazard_terms) if tr.hazard_terms else ""
    tpl = _TEMPLATES.get(lang, _TEMPLATES["en"]).get(tr.tag, "{where}")
    return tpl.format(where=where, terms=terms).replace("  ", " ").strip()[:140]


def _last_non_p0_push(st: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for b in st.briefs:
        if b.decision == "push" and b.priority != "P0":
            out[b.unit_id] = max(out.get(b.unit_id, -1e9), b.created_t)
    return out


def route(event: Event, world: Any, wake_id: str = "fallback", reason: str = "agent unavailable",
          skip_units: set[str] | None = None, wake_reason: str | None = None, gap_fill: bool = False) -> list[Brief]:
    """Same invariants as the checker: text <=2 sentences / 140 chars (else the template), <=1 non-P0 push per unit
    per PUSH_GAP_S (else hold "rate limited"), never the distressed unit about its own mayday."""
    st = world.state
    tag = event.triage.tag
    if tag == "ROUTINE":
        return []
    lang = st.lang
    speaker = event.speaker_unit_snapped
    wake_reason = wake_reason or f"event:{event.id} {tag}"
    targets = [(uid, u) for uid, u in st.units.items()
               if u.role in CREW_ROLES and uid != speaker and uid not in (skip_units or ())
               # gap fill after a healthy agent wake: exterior units the agent rightly ignored are not a gap
               and (not gap_fill or tag == "MAYDAY" or u.interior)]
    if not gap_fill:  # a real fallback is always traced, even when the agent had already decided every unit
        world.add_trace(wake_id=wake_id, wake_reason=wake_reason, kind="fallback", payload={"reason": reason})
    if not targets:
        return []
    if gap_fill:  # not a fallback: the agent ran fine, the router only covers units it left undecided
        world.add_trace(wake_id=wake_id, wake_reason=wake_reason, kind="wake",
                        payload={"gap_fill": reason, "units": [uid for uid, _ in targets]})
    text = (event.triage.crew_brief or "").strip()
    if not text or check_text(text) is not None:
        text = template_text(event, lang)
    if len(text) > 140:
        text = text[:139] + "…"
    rel = related_zones(event.zone_id_snapped, st)
    briefs: list[Brief] = []
    subject = distressed_unit(event, st) if tag == "MAYDAY" else None
    last_push = _last_non_p0_push(st)
    for uid, u in targets:
        hold_reason = None
        if uid == subject:
            push, prio = False, "P2"
            hold_reason = "member in distress: own mayday not re-broadcast (invariant 7)"
        elif tag == "MAYDAY":
            push, prio = True, "P0"
        else:
            push, prio = unit_in_zones(uid, rel, st), "P1"
            if push and uid in last_push and st.t - last_push[uid] < PUSH_GAP_S:
                push, hold_reason = False, f"rate limited ({PUSH_GAP_S:.0f} s)"
        if push:
            b = world.add_brief(unit_id=uid, decision="push", text=text, priority=prio,
                                reason=f"zone match {event.zone_id_snapped}" if tag != "MAYDAY" else "MAYDAY: all units",
                                evidence_event_id=event.id, source="router")
        else:
            zone = u.zone_id or u.assignment or "?"
            b = world.add_brief(unit_id=uid, decision="hold", text=text, priority="P2",
                                reason=hold_reason or f"not your sector (zone {zone})", evidence_event_id=event.id,
                                source="router")
        world.add_trace(wake_id=wake_id, wake_reason=wake_reason, kind="delivery",
                        payload={"brief_id": getattr(b, "id", None), "unit_id": uid, "decision": "push" if push else "hold",
                                 "source": "router"})
        briefs.append(b)
    return briefs
