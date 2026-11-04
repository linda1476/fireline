"""Deterministic zone-match router: used when the agent is cut, errors or times out (docs/CONTRACT.md).

route(event, world) -> list[Brief]. Push triage.crew_brief (or a template) to crew units whose zone/assignment is
the event zone, its parent/children or vertical neighbour (same rule as checker invariant 1); every crew unit for
MAYDAY (P0); hold for everyone else with reason "not your sector (zone X)".
"""

from __future__ import annotations

from typing import Any

from server.checker import related_zones, unit_in_zones
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


def route(event: Event, world: Any, wake_id: str = "fallback", reason: str = "agent unavailable",
          skip_units: set[str] | None = None) -> list[Brief]:
    st = world.state
    tag = event.triage.tag
    if tag == "ROUTINE":
        return []
    lang = st.lang
    text = (event.triage.crew_brief or "").strip() or template_text(event, lang)
    if len(text) > 140:
        text = text[:139] + "…"
    wake_reason = f"event:{event.id} {tag}"
    world.add_trace(wake_id=wake_id, wake_reason=wake_reason, kind="fallback", payload={"reason": reason})
    rel = related_zones(event.zone_id_snapped, st)
    briefs: list[Brief] = []
    speaker = event.speaker_unit_snapped
    for uid, u in st.units.items():
        if u.role not in CREW_ROLES or uid == speaker or uid in (skip_units or ()):
            continue
        if tag == "MAYDAY":
            push, prio = True, "P0"
        else:
            push, prio = unit_in_zones(uid, rel, st), "P1"
        if push:
            b = world.add_brief(unit_id=uid, decision="push", text=text, priority=prio,
                                reason=f"zone match {event.zone_id_snapped}" if tag != "MAYDAY" else "MAYDAY: all units",
                                evidence_event_id=event.id, source="router")
        else:
            zone = u.zone_id or u.assignment or "?"
            b = world.add_brief(unit_id=uid, decision="hold", text=text, priority="P2",
                                reason=f"not your sector (zone {zone})", evidence_event_id=event.id, source="router")
        world.add_trace(wake_id=wake_id, wake_reason=wake_reason, kind="delivery",
                        payload={"brief_id": getattr(b, "id", None), "unit_id": uid, "decision": "push" if push else "hold",
                                 "source": "router"})
        briefs.append(b)
    return briefs
