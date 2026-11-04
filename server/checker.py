"""Invariant checker for relevance-agent tool calls (docs/CONTRACT.md "Checker invariants").

check(tool, args, state, now_t, recent_pushes) -> (ok, error|None). Pure: never mutates state.

Invariants enforced per call:
  (1) send_brief target is in / entering / assigned to the event zone, its parent, its children, or the zone
      directly above/below it (vertical neighbour: floor ±1 with overlapping footprint) unless priority P0.
  (2) ≤1 non-P0 push per unit per 20 s (recent_pushes[unit_id] = t of the last non-P0 push).
  (3) brief text ≤2 sentences and ≤140 chars.
  (4) propose_order only creates a Proposal (args validated: kind in ProposalKind; never a crew brief).
  (6) every call cites an existing evidence_event_id (get_unit_state / ping_unit exempt).
Invariant (5) (MAYDAY ack/escalation) is checked at wake end: see open_unescalated_maydays().
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from server.config import get_settings
from server.models import Event, State, Zone

PUSH_GAP_S = 20.0
MAX_CHARS = 140
MAX_SENTENCES = 2
TOOLS = {"get_unit_state", "send_brief", "hold", "request_missing_field", "escalate_to_ic", "propose_order", "ping_unit"}
PROPOSAL_KINDS = {"RADIO_SILENCE", "RIT_DEPLOY", "WITHDRAW", "CONFIRM_STRATEGY", "ASSIGN"}
MISSING_FIELDS = {"who", "what", "where", "needs", "air"}



@lru_cache(maxsize=1)
def _file_zones() -> dict[str, Zone]:
    try:
        data = json.loads((get_settings().data_dir / "zones.json").read_text(encoding="utf-8"))
        return {z["id"]: Zone(**{k: v for k, v in z.items() if k in Zone.model_fields}) for z in data["zones"]}
    except Exception:
        return {}


def zones_of(state: State) -> dict[str, Zone]:
    return state.zones or _file_zones()


def _bbox(z: Zone) -> tuple[float, float, float, float] | None:
    if not z.polygon:
        return None
    xs = [p[0] for p in z.polygon]
    ys = [p[1] for p in z.polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _overlap(a: Zone, b: Zone) -> bool:
    ba, bb = _bbox(a), _bbox(b)
    if ba is None or bb is None:
        return True
    return min(ba[2], bb[2]) - max(ba[0], bb[0]) > 0 and min(ba[3], bb[3]) - max(ba[1], bb[1]) > 0


def related_zones(zone_id: str | None, state: State) -> set[str]:
    """Event zone + parent + children (+ siblings via parent) + vertical neighbours (floor ±1, overlapping)."""
    if not zone_id:
        return set()
    zones = zones_of(state)
    out = {zone_id}
    z = zones.get(zone_id)
    if z is None:
        return out
    if z.parent:
        out.add(z.parent)
    out |= {c.id for c in zones.values() if c.parent == zone_id}
    if z.kind == "indoor" and z.floor is not None:
        for o in zones.values():
            if o.kind == "indoor" and o.floor is not None and abs(o.floor - z.floor) == 1 and _overlap(o, z):
                out.add(o.id)
                if o.parent:
                    out.add(o.parent)
                out |= {c.id for c in zones.values() if c.parent == o.id}
    return out


def unit_in_zones(unit_id: str, zone_ids: set[str], state: State) -> bool:
    u = state.units.get(unit_id)
    if u is None:
        return False
    return (u.zone_id in zone_ids) or (u.assignment in zone_ids)


def find_event(state: State, event_id: str | None) -> Event | None:
    if not event_id:
        return None
    for e in state.events:
        if e.id == event_id:
            return e
    return None


def count_sentences(text: str) -> int:
    t = text.strip()
    if not t:
        return 0
    parts = [p for p in re.split(r"(?<=[.!?。？！])\s+", t) if p.strip()]
    return len(parts)


def check_text(text: Any) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return "text must be a non-empty string"
    if len(text) > MAX_CHARS:
        return f"text is {len(text)} chars; max {MAX_CHARS}"
    n = count_sentences(text)
    if n > MAX_SENTENCES:
        return f"text has {n} sentences; max {MAX_SENTENCES}"
    return None


def check(
    tool: str,
    args: dict[str, Any],
    world_state: State,
    now_t: float,
    recent_pushes: dict[str, float] | None = None,
) -> tuple[bool, str | None]:
    recent_pushes = recent_pushes or {}
    st = world_state
    if tool not in TOOLS:
        return False, f"unknown tool {tool}"
    if not isinstance(args, dict):
        return False, "arguments must be an object"

    # unit existence for unit-targeted tools
    if tool in ("get_unit_state", "send_brief", "hold", "request_missing_field", "ping_unit"):
        uid = args.get("unit_id")
        if uid not in st.units:
            return False, f"unknown unit_id {uid!r}; valid: {', '.join(sorted(st.units))}"

    if tool in ("get_unit_state", "ping_unit"):
        return True, None

    # (6) evidence
    ev_key = "event_id" if tool in ("hold", "escalate_to_ic") else "evidence_event_id"
    ev_id = args.get(ev_key) or args.get("evidence_event_id") or args.get("event_id")
    event = find_event(st, ev_id)
    if event is None:
        return False, f"{ev_key} {ev_id!r} does not exist in state.events (invariant 6)"

    if tool == "send_brief":
        prio = args.get("priority")
        if prio not in ("P0", "P1", "P2"):
            return False, "priority must be P0, P1 or P2"
        err = check_text(args.get("text"))
        if err:
            return False, f"{err} (invariant 3)"
        uid = args["unit_id"]
        if prio != "P0":
            ez = event.zone_id_snapped
            rel = related_zones(ez, st)
            if ez is None or not unit_in_zones(uid, rel, st):
                u = st.units[uid]
                return False, (
                    f"unit {uid} (zone {u.zone_id}, assignment {u.assignment}) is not in/assigned to event zone "
                    f"{ez} or its parent/children; use hold, or P0 only for crew-safety (invariant 1)"
                )
            last = recent_pushes.get(uid)
            if last is not None and now_t - last < PUSH_GAP_S:
                return False, f"unit {uid} got a non-P0 push {now_t - last:.0f} s ago; max 1 per {PUSH_GAP_S:.0f} s (invariant 2)"
        return True, None

    if tool == "request_missing_field":
        if args.get("field") not in MISSING_FIELDS:
            return False, f"field must be one of {sorted(MISSING_FIELDS)}"
        return True, None

    if tool == "propose_order":
        if args.get("kind") not in PROPOSAL_KINDS:
            return False, f"kind must be one of {sorted(PROPOSAL_KINDS)}"
        units = args.get("units") or []
        bad = [u for u in units if u not in st.units]
        if bad:
            return False, f"unknown units {bad}"
        if not isinstance(args.get("text"), str) or not args["text"].strip():
            return False, "text must be a non-empty string"
        return True, None

    # hold, escalate_to_ic
    if not isinstance(args.get("reason"), str) or not args["reason"].strip():
        return False, "reason must be a non-empty string"
    return True, None


def open_unescalated_maydays(state: State) -> list:
    """Invariant 5: MAYDAY (or RULE R2 = MAYDAY-equivalent) cards that are neither acked nor escalated."""
    out = []
    for c in state.cards:
        is_mayday = c.kind == "MAYDAY" or (c.kind == "RULE" and c.priority == 0)
        if is_mayday and c.state == "open" and c.acked_t is None and c.escalation_level < 1:
            out.append(c)
    return out
