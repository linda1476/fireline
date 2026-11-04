"""Structured extraction for one radio transmission (live Muse Spark path + normalizers).

This file holds everything the LIVE path needs that is not network code:

* :class:`TriageExtraction` -- the flat JSON schema the model fills in. String enums are
  ``Literal``, lists hold strings only, no nested objects, every field has a description.
  ``mode="before"`` validators coerce sloppy model output (``"null"``, ``"3rd"``, ``85``
  for confidence, comma strings for lists) so a slightly wrong answer never fails
  validation.
* :func:`build_system_prompt` / :func:`build_user_prompt` -- prompt built from the
  :class:`~fireline.models.Building` and roster (zones grouped by floor with aliases, call
  signs, tag definitions, priority rubric, few-shot examples).
* Normalizers shared with the mock: :func:`normalize_zone`, :func:`infer_responder_id`,
  :func:`find_zone_mentions`, :func:`parse_floor_phrase`, :func:`unit_floor`.
* :func:`extraction_to_result` -- turns a validated extraction into the shared
  :class:`~fireline.models.TriageResult` (zone must be an exact building zone name or
  ``None``; mayday forces Danger / priority 5 / InDanger).

Nothing in here imports ``fireline.triage`` itself, so ``mock.py`` and ``__init__.py``
can import it freely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fireline.models import (
    Building,
    RadioReport,
    Responder,
    ResponderStatus,
    Tag,
    TriageResult,
    Zone,
)

TagLiteral = Literal["Danger", "VictimFound", "HelpNeeded", "Status"]
StatusLiteral = Literal["OK", "InDanger", "NeedsHelp", "Evacuating", "Unknown"]
CertaintyLiteral = Literal["none", "suspected", "confirmed", "extracted"]

SUMMARY_MAX_WORDS = 15

# Words the model (or a radio operator) uses for "no value".
_NULL_WORDS = {"", "null", "none", "n/a", "na", "unknown", "nil", "-", "?"}

_NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_ORDINAL_WORDS: dict[str, int] = {
    "ground": 1, "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9, "tenth": 10, "10th": 10,
}
_ORDINAL_FOR_FLOOR = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
                      6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}

_MAYDAY_RE = re.compile(r"\bmay\s?day\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Small coercion helpers used by the validators
# ---------------------------------------------------------------------------


def _is_null(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in _NULL_WORDS)


def _to_int(v: Any) -> Optional[int]:
    """Coerce ints, numeric strings, number words and ordinals ('3rd', 'third') to int."""
    if _is_null(v):
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lower()
    if s in _NUMBER_WORDS:
        return _NUMBER_WORDS[s]
    if s in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[s]
    m = re.search(r"-?\d+", s)
    return int(m.group()) if m else None


def _to_str_list(v: Any) -> list[str]:
    if _is_null(v):
        return []
    if isinstance(v, str):
        parts = re.split(r"[,;\n|]+", v)
    elif isinstance(v, (list, tuple, set)):
        parts = [str(p) for p in v]
    else:
        parts = [str(v)]
    out: list[str] = []
    for p in parts:
        p = p.strip().strip(".").strip()
        if p and p.lower() not in _NULL_WORDS and p.lower() not in {x.lower() for x in out}:
            out.append(p)
    return out


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in {"true", "yes", "y", "1", "mayday"}


def _canon_enum(v: Any, options: tuple[str, ...], default: str) -> str:
    """Map a case/space/underscore-insensitive string onto one of ``options``."""
    if _is_null(v):
        return default
    key = re.sub(r"[\s_\-]+", "", str(v)).lower()
    for opt in options:
        if re.sub(r"[\s_\-]+", "", opt).lower() == key:
            return opt
    for opt in options:  # prefix / containment fallback ("victim" -> "VictimFound")
        if key and (opt.lower().startswith(key) or key in opt.lower()):
            return opt
    return default


# ---------------------------------------------------------------------------
# Model output schema
# ---------------------------------------------------------------------------


class TriageExtraction(BaseModel):
    """Flat structured output filled in by Muse Spark for ONE radio transmission.

    Flat on purpose: string enums are ``Literal``, lists contain strings only, no nested
    objects. Validators coerce sloppy values instead of failing.
    """

    model_config = ConfigDict(extra="ignore")

    tag: TagLiteral = Field(
        ...,
        description="Danger (mayday/trapped/collapse/low air/flashover), VictimFound (victim seen, heard or reported), HelpNeeded (needs people, tools, water, relief), Status (routine progress or position).",
    )
    priority: int = Field(
        ..., ge=1, le=5,
        description="1-5. 5 = mayday/trapped/collapse/lost/low air with no egress; 4 = confirmed victim or urgent help; 3 = hazard or suspected victim; 2 = routine progress; 1 = admin.",
    )
    summary: str = Field(..., description="At most 15 words, plain English, for the commander's queue card.")
    responder_callsign: str = Field(
        "unknown", description="Call sign the speaker identifies with, e.g. 'Engine 1-2', 'Ladder 2', or 'unknown'.",
    )
    floor: Optional[int] = Field(
        None, description="Floor the EVENT is on (0 = outdoors, 1 = ground floor). Unit numbers encode the floor (404 -> 4). null if unknown.",
    )
    zone: Optional[str] = Field(
        None, description="Exact zone name from the building vocabulary where the event is (destination if the speaker is moving). null if unknown.",
    )
    responder_status: StatusLiteral = Field(
        "Unknown", description="Speaker's own status: OK, InDanger, NeedsHelp, Evacuating or Unknown.",
    )
    victim_count: int = Field(0, ge=0, description="Number of victims this transmission is about; 0 if none.")
    victim_condition: Optional[str] = Field(
        None, description="Short victim description, e.g. 'adult male, unconscious' or 'child, responsive'. null if no victim.",
    )
    victim_certainty: CertaintyLiteral = Field(
        "none", description="none; suspected (heard / second-hand / may still be inside); confirmed (responder has eyes or hands on); extracted (out of the building / handed to EMS).",
    )
    hazards: list[str] = Field(
        default_factory=list, description="Hazards mentioned, short phrases: 'heavy smoke', 'zero visibility', 'ceiling collapse', 'stairwell B blocked', 'low air', 'flashover'. When a stairwell is blocked or collapsed, name it in the phrase ('stairwell B blocked'), even if the speaker is elsewhere. Empty list if none.",
    )
    needs: list[str] = Field(
        default_factory=list, description="Resources requested, short phrases: 'RIT', 'irons', 'hose line', 'relief crew', 'extra hands'. Empty list if none.",
    )
    mayday: bool = Field(False, description="true only if the speaker declares a mayday or an equivalent life-threatening emergency for a firefighter.")
    confidence: float = Field(0.8, ge=0, le=1, description="Your confidence 0-1 that tag, floor and zone are right.")

    # --------------------------------------------------------------- coercion
    @field_validator("tag", mode="before")
    @classmethod
    def _v_tag(cls, v: Any) -> str:
        return _canon_enum(v, ("Danger", "VictimFound", "HelpNeeded", "Status"), "Status")

    @field_validator("responder_status", mode="before")
    @classmethod
    def _v_status(cls, v: Any) -> str:
        return _canon_enum(v, ("OK", "InDanger", "NeedsHelp", "Evacuating", "Unknown"), "Unknown")

    @field_validator("victim_certainty", mode="before")
    @classmethod
    def _v_certainty(cls, v: Any) -> str:
        return _canon_enum(v, ("none", "suspected", "confirmed", "extracted"), "none")

    @field_validator("priority", mode="before")
    @classmethod
    def _v_priority(cls, v: Any) -> int:
        n = _to_int(v)
        return 3 if n is None else max(1, min(5, n))

    @field_validator("victim_count", mode="before")
    @classmethod
    def _v_count(cls, v: Any) -> int:
        n = _to_int(v)
        return 0 if n is None else max(0, n)

    @field_validator("floor", mode="before")
    @classmethod
    def _v_floor(cls, v: Any) -> Optional[int]:
        n = _to_int(v)
        return None if n is None or n < 0 else n

    @field_validator("zone", "victim_condition", mode="before")
    @classmethod
    def _v_nullable_str(cls, v: Any) -> Optional[str]:
        return None if _is_null(v) else str(v).strip()

    @field_validator("summary", "responder_callsign", mode="before")
    @classmethod
    def _v_str(cls, v: Any) -> str:
        return "" if v is None else str(v).strip()

    @field_validator("hazards", "needs", mode="before")
    @classmethod
    def _v_lists(cls, v: Any) -> list[str]:
        return _to_str_list(v)

    @field_validator("mayday", mode="before")
    @classmethod
    def _v_mayday(cls, v: Any) -> bool:
        return _to_bool(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _v_conf(cls, v: Any) -> float:
        if _is_null(v):
            return 0.5
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.5
        if f > 1.0:
            f = f / 100.0
        return max(0.0, min(1.0, f))


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

TAG_DEFINITIONS = (
    "TAGS\n"
    "- Danger: a firefighter is in danger or a life-threatening condition exists: mayday, trapped, pinned, lost, "
    "low/out of air, flashover, backdraft, structural collapse, 'everybody out'.\n"
    "- VictimFound: a civilian victim is seen, heard, reported second-hand, suspected still inside, or being carried out.\n"
    "- HelpNeeded: the speaker asks for people, tools, water, a relief crew, RIT (without a mayday), or any resource.\n"
    "- Status: routine progress, position update, PAR, rehab, admin. Hazard observations without a victim or request are Status (or Danger if people are at risk).\n"
    "If several apply: Danger beats VictimFound beats HelpNeeded beats Status. A declared mayday is ALWAYS Danger."
)

PRIORITY_RUBRIC = (
    "PRIORITY (1-5)\n"
    "- 5: mayday, trapped, pinned, collapse on people, lost, low/out of air with no egress.\n"
    "- 4: confirmed victim (eyes or hands on), or urgent help needed now.\n"
    "- 3: hazard observed (heavy smoke, high heat, blocked route), suspected victim, routine help request.\n"
    "- 2: routine progress or position update.\n"
    "- 1: admin (PAR complete, rehab, bottle swap, out of the building with nothing new)."
)

LOCATION_RULES = (
    "LOCATION RULES\n"
    "- Unit numbers encode the floor: 404 -> floor 4, 302 -> floor 3, 501 -> floor 5.\n"
    "- 'on three' / 'on the third floor' / 'up to three' means floor 3; 'first floor' or 'ground floor' is floor 1; "
    "staging, the entrance, the street and the command post are floor 0 (outdoors).\n"
    "- The zone is where the EVENT is (the victim, the hazard, the problem), not where the speaker came from.\n"
    "- If the speaker only reports movement, zone = their destination.\n"
    "- Stairwells keep the same name on every floor: report the floor the speaker is on.\n"
    "- A blocked or collapsed stairwell is named in the hazard string ('stairwell B blocked'), even when the "
    "speaker is in the other stairwell ('coming down A, B is blocked' -> hazards ['stairwell B blocked']).\n"
    "- Use the EXACT zone name from the list (e.g. 'unit 404', 'east corridor 3', 'stairwell B'); never invent one. "
    "If no listed zone fits, zone = null."
)

FEW_SHOT_EXAMPLES: list[tuple[str, dict[str, Any]]] = [
    (
        "Ladder 2, primary search complete in the second floor gym, all clear, moving to the restaurant.",
        {"tag": "Status", "priority": 2, "summary": "Ladder 2: gym search clear, moving to restaurant",
         "responder_callsign": "Ladder 2", "floor": 2, "zone": "restaurant", "responder_status": "OK",
         "victim_count": 0, "victim_condition": None, "victim_certainty": "none", "hazards": [], "needs": [],
         "mayday": False, "confidence": 0.9},
    ),
    (
        "Command, Rescue 3-2, I've got an elderly male in 401, conscious but he can't walk, I need a second set of hands to get him out.",
        {"tag": "VictimFound", "priority": 4, "summary": "Elderly male in unit 401, conscious, cannot walk; needs hands",
         "responder_callsign": "Rescue 3-2", "floor": 4, "zone": "unit 401", "responder_status": "NeedsHelp",
         "victim_count": 1, "victim_condition": "elderly male, conscious, cannot walk", "victim_certainty": "confirmed",
         "hazards": [], "needs": ["extra responder"], "mayday": False, "confidence": 0.9},
    ),
    (
        "Mayday mayday mayday, Engine 1-2, I'm out of air and I can't find the stairs, I'm on three in the west hallway.",
        {"tag": "Danger", "priority": 5, "summary": "MAYDAY: Engine 1-2 out of air, lost in west corridor 3",
         "responder_callsign": "Engine 1-2", "floor": 3, "zone": "west corridor 3", "responder_status": "InDanger",
         "victim_count": 0, "victim_condition": None, "victim_certainty": "none", "hazards": ["out of air"],
         "needs": ["RIT"], "mayday": True, "confidence": 0.95},
    ),
    (
        "Rescue 3 to Command, the convenience store has partial ceiling failure, keep everybody out of it, we're routing through stairwell B.",
        {"tag": "Danger", "priority": 3, "summary": "Partial ceiling collapse in convenience store; avoid it",
         "responder_callsign": "Rescue 3", "floor": 1, "zone": "convenience store", "responder_status": "OK",
         "victim_count": 0, "victim_condition": None, "victim_certainty": "none", "hazards": ["partial ceiling collapse"],
         "needs": [], "mayday": False, "confidence": 0.85},
    ),
    (
        "Ladder 2, a resident downstairs says there might still be somebody in 503, we're going to check.",
        {"tag": "VictimFound", "priority": 3, "summary": "Possible occupant still in unit 503, Ladder 2 checking",
         "responder_callsign": "Ladder 2", "floor": 5, "zone": "unit 503", "responder_status": "OK",
         "victim_count": 1, "victim_condition": None, "victim_certainty": "suspected", "hazards": [], "needs": [],
         "mayday": False, "confidence": 0.8},
    ),
    (
        "Rescue 3-1, I need water on the fifth floor, the line went dry in the east hallway.",
        {"tag": "HelpNeeded", "priority": 4, "summary": "Rescue 3-1 needs water, dry line in east corridor 5",
         "responder_callsign": "Rescue 3-1", "floor": 5, "zone": "east corridor 5", "responder_status": "NeedsHelp",
         "victim_count": 0, "victim_condition": None, "victim_certainty": "none", "hazards": ["dry hose line"],
         "needs": ["water supply"], "mayday": False, "confidence": 0.9},
    ),
    (
        "Engine 1 at staging, swapped bottles, ready for reassignment.",
        {"tag": "Status", "priority": 1, "summary": "Engine 1 at staging, bottles swapped, available",
         "responder_callsign": "Engine 1", "floor": 0, "zone": "staging area", "responder_status": "OK",
         "victim_count": 0, "victim_condition": None, "victim_certainty": "none", "hazards": [], "needs": [],
         "mayday": False, "confidence": 0.95},
    ),
]


def _floor_label(floor: int) -> str:
    if floor == 0:
        return "Floor 0 (outdoors / site)"
    ordinal = _ORDINAL_FOR_FLOOR.get(floor, f"{floor}th")
    return f"Floor {floor} ({ordinal} floor)"


def _zone_line(z: Zone) -> str:
    alias = f" ({', '.join(z.aliases)})" if z.aliases else ""
    return f"{z.name}{alias} [{z.kind}]"


def describe_zones(building: Building) -> str:
    """Zones grouped by floor, each with its aliases, for the system prompt."""
    floors = sorted({z.floor for z in building.zones})
    lines: list[str] = []
    for f in floors:
        zones = ", ".join(_zone_line(z) for z in building.zones_on_floor(f))
        lines.append(f"- {_floor_label(f)}: {zones}")
    return "\n".join(lines)


def _callsigns_for(r: Responder, roster: list[Responder]) -> str:
    """Human call signs a responder answers to ('Engine 1' and 'Engine 1-1' for the lead)."""
    member = _member_number(r.id)
    mates = [x for x in roster if x.unit.lower() == r.unit.lower()]
    is_lead = (member == 1) or (member is None and mates and mates[0].id == r.id)
    signs = []
    if is_lead:
        signs.append(r.unit)
    if member is not None:
        signs.append(f"{r.unit}-{member}")
    return " / ".join(signs) if signs else r.unit


def describe_roster(roster: list[Responder]) -> str:
    """One line per responder: id, name, unit, role, call signs."""
    return "\n".join(
        f"- {r.id}: {r.name}, {r.unit}{' (' + r.role + ')' if r.role else ''}; call signs: {_callsigns_for(r, roster)}"
        for r in roster
    )


def _example_block() -> str:
    import json

    parts = []
    for text, out in FEW_SHOT_EXAMPLES:
        parts.append(f'Radio: "{text}"\nJSON: {json.dumps(out)}')
    return "\n\n".join(parts)


def build_system_prompt(building: Building, roster: list[Responder]) -> str:
    """System prompt for the live triage call, built from the building and roster."""
    return (
        "You are the triage officer at a structure fire. You read ONE radio transmission from a "
        "firefighter and fill in a JSON record for the incident commander's priority queue. "
        "Be precise about tag, priority, floor and zone; lives depend on the location being right. "
        "Answer with JSON only, matching the schema exactly.\n\n"
        f"BUILDING: {building.name}, {building.floors} floors. {building.address}\n"
        "ZONES BY FLOOR (exact name first, aliases in parentheses, kind in brackets):\n"
        f"{describe_zones(building)}\n\n"
        "ROSTER (responder id: name, unit; call signs). 'Engine 1' alone is the unit lead (E1-1); "
        "'Engine 1-2' is the second member.\n"
        f"{describe_roster(roster)}\n\n"
        f"{TAG_DEFINITIONS}\n\n{PRIORITY_RUBRIC}\n\n{LOCATION_RULES}\n\n"
        "OTHER RULES\n"
        "- summary: at most 15 words, start with the call sign, say what and where.\n"
        "- responder_callsign: the call sign the speaker uses for themselves, or 'unknown'.\n"
        "- victim_count: number of victims referred to (1 if 'someone'/'a kid'); 0 when none.\n"
        "- victim_certainty: suspected = heard, second-hand or 'never came out'; confirmed = seen or being carried; "
        "extracted = out of the building / handed to EMS.\n"
        "- hazards / needs: short phrases, empty lists when none. A firefighter pinned or trapped is a Danger, not a victim.\n"
        "- mayday: true only when the speaker declares a mayday or says a firefighter is trapped/pinned/out of air.\n\n"
        "EXAMPLES\n"
        f"{_example_block()}"
    )


def build_user_prompt(report: RadioReport, roster: list[Responder] | None = None) -> str:
    """User turn: the transmission plus whatever attribution we already have."""
    who = "unknown speaker"
    if report.responder_id:
        who = report.responder_id
        if roster:
            r = next((x for x in roster if x.id == report.responder_id), None)
            if r:
                who = f"{r.id} ({r.name}, {r.unit})"
    elif report.speaker_label:
        who = f"diarized speaker {report.speaker_label}"
    return f"Transmission from {who} at {report.timestamp}:\n\"{report.transcript.strip()}\"\n\nReturn the JSON record."


# ---------------------------------------------------------------------------
# Zone / floor normalisation
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(r"\b(?:(?:unit|apartment|apt\.?|room|suite)\s+)?([1-9]\d{2})\b", re.IGNORECASE)
_STAIR_RE = re.compile(r"\b(?:stairwell|stairway|stair|stairs)\s*([a-z])\b|\b([a-z])\s+(?:stairwell|stairway|stair|stairs)\b", re.IGNORECASE)
_CORRIDOR_RE = re.compile(
    r"(?:\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|\d)\s*(?:floor|fl\.?)?\s+)?"
    r"\b(east|west|north|south)\s+(?:corridor|hallway|hall|wing)(?:\s*(\d))?\b",
    re.IGNORECASE,
)


def unit_floor(name: str) -> Optional[int]:
    """'unit 404' / 'apartment 302' / '501' -> 4 / 3 / 5 (first digit of a 3-digit unit)."""
    m = _UNIT_RE.search(name or "")
    return int(m.group(1)[0]) if m else None


def _stair_zone(building: Building, letter: str, floor: Optional[int]) -> Optional[Zone]:
    """The stairwell zone with that letter, on ``floor`` if it exists there, else the first."""
    letter = letter.upper()
    candidates = [z for z in building.zones if z.kind == "stair" and z.name.lower() == f"stairwell {letter.lower()}"]
    if not candidates:
        candidates = [z for z in building.zones if z.kind == "stair" and re.search(rf"\b{letter}\b", z.name, re.IGNORECASE)]
    if not candidates:
        return None
    if floor is not None:
        for z in candidates:
            if z.floor == floor:
                return z
    return candidates[0]


def _corridor_zone(building: Building, m: re.Match[str], floor: Optional[int]) -> Optional[Zone]:
    """Resolve 'third floor east corridor' / 'east hallway' (+known floor) -> 'east corridor 3'."""
    ordinal, side, trailing = m.group(1), m.group(2).lower(), m.group(3)
    f = floor
    if ordinal:
        f = _to_int(ordinal)
    if trailing:
        f = int(trailing)
    if f is None:
        return None
    return building.zone_by_name(f"{side} corridor {f}")


def _longest_contained_zone(building: Building, name: str) -> Optional[Zone]:
    """A zone whose exact name or alias appears as a whole phrase inside ``name``."""
    best: tuple[int, Optional[Zone]] = (0, None)
    for z in building.zones:
        for label in [z.name, *z.aliases]:
            if len(label) <= 3:
                continue
            if re.search(rf"\b{re.escape(label.lower())}\b", name) and len(label) > best[0]:
                best = (len(label), z)
    return best[1]


def resolve_zone(building: Building, name: Optional[str], floor: Optional[int] = None) -> Optional[Zone]:
    """Free-text zone -> :class:`Zone` or ``None`` (aliases, unit digits, stair letters, corridors)."""
    if not name or _is_null(name):
        return None
    raw = name.strip().lower()
    z = building.zone_by_name(raw)
    if z is None:
        stripped = re.sub(r"^(?:the|unit|apartment|apt\.?|room|suite)\s+", "", raw).strip()
        z = building.zone_by_name(stripped)
    if z is None:
        m = _UNIT_RE.search(raw)
        if m:
            z = building.zone_by_name(f"unit {m.group(1)}") or building.zone_by_name(m.group(1))
    if z is None:
        m = _STAIR_RE.search(raw)
        if m:
            z = _stair_zone(building, m.group(1) or m.group(2), floor)
    if z is None:
        m = _CORRIDOR_RE.search(raw)
        if m:
            z = _corridor_zone(building, m, floor)
    if z is None:
        z = _longest_contained_zone(building, raw)
    if z is not None and z.kind == "stair" and floor is not None:
        z = _stair_zone(building, z.name.split()[-1], floor) or z
    return z


def stair_label_is_floor_specific(building: Building, label: str) -> bool:
    """True when ``label`` names a stair zone on exactly one floor ('stairwell B landing');
    False for the generic name shared by every floor ('stairwell B')."""
    key = (label or "").strip().lower()
    hits = [z for z in building.zones if z.kind == "stair" and (z.name.lower() == key or key in (a.lower() for a in z.aliases))]
    return len(hits) == 1


def reconcile_floor(zone: Optional[Zone], floor: Optional[int], *, stair_floor_known: bool = False) -> Optional[int]:
    """Floor after the zone is known.

    Stairs exist on every floor under the same name, so they keep the spoken floor; with no
    spoken floor the result is ``None`` (unknown beats a guess) unless the stair label itself
    was floor-specific. Every other kind is unique to its floor and overrides a conflicting
    spoken floor (lobby -> 1, outdoor -> 0, unit 302 -> 3).
    """
    if zone is None:
        return floor
    if zone.kind == "stair":
        if floor is not None:
            return floor
        return zone.floor if stair_floor_known else None
    return zone.floor


def normalize_zone(
    building: Building, name: Optional[str], floor: Optional[int] = None
) -> tuple[Optional[str], Optional[int]]:
    """Map free text to an exact zone name and reconcile the floor.

    Returns ``(zone_name_or_None, floor_or_None)``. The zone name is always an exact
    :attr:`Zone.name` from the building (or ``None``).
    """
    z = resolve_zone(building, name, floor)
    if z is None:
        return None, floor
    specific = z.kind == "stair" and stair_label_is_floor_specific(building, name or "")
    return z.name, reconcile_floor(z, floor, stair_floor_known=specific)


# ---------------------------------------------------------------------------
# Floor phrases and zone mentions inside free speech (shared with the mock)
# ---------------------------------------------------------------------------

_FLOOR_PHRASE_RES: list[re.Pattern[str]] = [
    # "on three", "to three", "at five", "up to four", "down to two", "of two"
    re.compile(
        r"\b(?:on|to|at|of)\s+(?:the\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|[1-9]|10)(?![\d\-:])\b",
        re.IGNORECASE,
    ),
    # "fifth floor", "3rd floor", "ground floor", "floor 5"
    re.compile(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|ground)\s+floor\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bfloor\s+([1-9]|10)\b", re.IGNORECASE),
]

_OUTDOOR_WORDS_RE = re.compile(
    r"\b(staging|outside|exterior|street|command post|rehab|apparatus|parking|hydrant|alley)\b", re.IGNORECASE
)


def parse_floor_phrase(text: str, max_floor: int = 10) -> Optional[int]:
    """First spoken floor in the text ('on three', 'fifth floor', 'floor 2'), else None."""
    hits: list[tuple[int, int]] = []
    for rx in _FLOOR_PHRASE_RES:
        for m in rx.finditer(text):
            n = _to_int(m.group(1))
            if n is not None and 0 <= n <= max_floor:
                hits.append((m.start(), n))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


@dataclass
class ZoneMention:
    """One place in the transcript where a building zone is referred to."""

    start: int
    end: int
    zone: Zone
    text: str
    preposition: Optional[str] = None  # at / in / inside / to / into / through / up / down


# "Command" is the addressee of nearly every transmission, never a location; very short
# aliases (CP, ICP, ATM) are skipped as well because they collide with ordinary words.
_GENERIC_ALIASES = {"command"}
_PREP_RE = re.compile(r"\b(at|in|inside|into|to|through|toward|towards|up|down|via|from|out)\b", re.IGNORECASE)


def _preposition_before(text: str, start: int, window: int = 4) -> Optional[str]:
    """Last preposition within ``window`` words before ``start``."""
    before = text[:start]
    words = re.findall(r"[A-Za-z']+", before)[-window:]
    for w in reversed(words):
        if _PREP_RE.fullmatch(w):
            return w.lower()
    return None


def find_zone_mentions(building: Building, text: str, floor: Optional[int] = None) -> list[ZoneMention]:
    """Every zone referred to in ``text`` (names, aliases, unit numbers, stair letters,
    '<side> corridor'), left to right, overlaps resolved to the longest match."""
    low = text.lower()
    raw: list[ZoneMention] = []

    for z in building.zones:
        for label in [z.name, *z.aliases]:
            lab = label.lower()
            if lab in _GENERIC_ALIASES or (len(lab) <= 3 and label != z.name):
                continue
            for m in re.finditer(rf"\b{re.escape(lab)}\b", low):
                raw.append(ZoneMention(m.start(), m.end(), z, m.group()))

    for m in _UNIT_RE.finditer(low):
        z = building.zone_by_name(f"unit {m.group(1)}") or building.zone_by_name(m.group(1))
        if z:
            raw.append(ZoneMention(m.start(), m.end(), z, m.group()))

    for m in _STAIR_RE.finditer(low):
        z = _stair_zone(building, m.group(1) or m.group(2), floor)
        if z:
            raw.append(ZoneMention(m.start(), m.end(), z, m.group()))

    for m in _CORRIDOR_RE.finditer(low):
        z = _corridor_zone(building, m, floor)
        if z:
            raw.append(ZoneMention(m.start(), m.end(), z, m.group()))

    # Longest match wins on overlap; stairwells snap to the known floor.
    raw.sort(key=lambda mn: (mn.start, -(mn.end - mn.start)))
    out: list[ZoneMention] = []
    for mn in raw:
        if out and mn.start < out[-1].end:
            continue
        if mn.zone.kind == "stair" and floor is not None:
            mn.zone = _stair_zone(building, mn.zone.name.split()[-1], floor) or mn.zone
        mn.preposition = _preposition_before(text, mn.start)
        out.append(mn)
    return out


# ---------------------------------------------------------------------------
# Call sign -> responder id
# ---------------------------------------------------------------------------

_CALLSIGN_RE = re.compile(
    r"\b(engine|ladder|rescue|truck|squad|medic|tower|battalion|chief|command|ems|hazmat|brush|tanker|quint)"
    r"\s*[\s\-]?\s*(one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})"
    r"(?:\s*(?:-|\s|dash)\s*(one|two|three|four|five|six|seven|eight|nine|ten|\d))?(?![\d])",
    re.IGNORECASE,
)


def _member_number(responder_id: str) -> Optional[int]:
    m = re.search(r"-(\d+)$", responder_id)
    return int(m.group(1)) if m else None


def _unit_key(unit: str) -> tuple[str, Optional[int]]:
    m = re.match(r"\s*([A-Za-z]+)\s*[\s\-]?\s*(\d+)?", unit or "")
    if not m:
        return (unit or "").strip().lower(), None
    return m.group(1).lower(), (int(m.group(2)) if m.group(2) else None)


def responder_for_callsign(roster: list[Responder], unit_word: str, unit_num: Optional[int], member: Optional[int]) -> Optional[Responder]:
    """'engine', 1, 2 -> the Engine 1 responder whose id ends in '-2'; member None -> lead."""
    crew = [r for r in roster if _unit_key(r.unit) == (unit_word.lower(), unit_num)]
    if not crew:
        crew = [r for r in roster if _unit_key(r.unit)[0] == unit_word.lower() and unit_num is None]
    if not crew:
        return None
    want = member if member is not None else 1
    for r in crew:
        if _member_number(r.id) == want:
            return r
    if member is None or member <= len(crew):
        return crew[(want - 1) if 0 < want <= len(crew) else 0]
    return None


def parse_callsign(text: str) -> Optional[tuple[str, int, Optional[int]]]:
    """'Rescue 3-2 to Command' -> ('rescue', 3, 2); 'engine one' -> ('engine', 1, None)."""
    for m in _CALLSIGN_RE.finditer(text or ""):
        unit_word = m.group(1).lower()
        unit_num = _to_int(m.group(2))
        if unit_num is None or unit_word in {"command", "ems"}:
            continue
        member = _to_int(m.group(3)) if m.group(3) else None
        return unit_word, unit_num, member
    return None


def infer_responder_id(text: str, roster: list[Responder]) -> Optional[str]:
    """Responder id from the first call sign spoken in ``text`` ('Engine 1-2' -> 'E1-2')."""
    parsed = parse_callsign(text)
    if not parsed:
        return None
    r = responder_for_callsign(roster, *parsed)
    return r.id if r else None


# ---------------------------------------------------------------------------
# Extraction -> TriageResult
# ---------------------------------------------------------------------------


def clip_summary(text: str, max_words: int = SUMMARY_MAX_WORDS) -> str:
    words = (text or "").split()
    if not words:
        return "Radio report"
    return " ".join(words[:max_words])


def transcript_declares_mayday(text: str) -> bool:
    return bool(_MAYDAY_RE.search(text or ""))


def extraction_to_result(
    extraction: TriageExtraction,
    report: RadioReport,
    building: Building,
    roster: list[Responder],
    *,
    model: str,
    latency_ms: int,
) -> TriageResult:
    """Normalise a model extraction into the shared :class:`TriageResult`.

    * zone -> exact building name via :func:`normalize_zone` (aliases, digits, stairs, corridors)
      and the floor reconciled with it; an unresolvable zone becomes ``None`` and lowers confidence.
    * responder_id -> ``report.responder_id`` if set, else the model's call sign, else the
      call sign heard in the transcript.
    * mayday (model flag OR the word in the transcript) -> Danger, priority 5, InDanger.
    """
    confidence = extraction.confidence
    floor = extraction.floor
    if floor is None and extraction.zone:
        floor = unit_floor(extraction.zone)
    if floor is None:  # spoken floors ("on three", "fifth floor") are the one thing regexes get right
        floor = parse_floor_phrase(report.transcript)
    zone_name, floor = normalize_zone(building, extraction.zone, floor)
    if extraction.zone and zone_name is None:
        confidence = min(confidence, 0.5)

    responder_id = report.responder_id
    if not responder_id and extraction.responder_callsign:
        responder_id = infer_responder_id(extraction.responder_callsign, roster)
    if not responder_id:
        responder_id = infer_responder_id(report.transcript, roster)

    tag = Tag(extraction.tag)
    priority = extraction.priority
    status = ResponderStatus(extraction.responder_status)
    mayday = extraction.mayday or transcript_declares_mayday(report.transcript)
    if mayday:
        tag, priority, status = Tag.DANGER, 5, ResponderStatus.IN_DANGER

    certainty = extraction.victim_certainty
    victim_count = extraction.victim_count
    if certainty != "none" and victim_count == 0:
        victim_count = 1
    if certainty == "none" and victim_count > 0:
        certainty = "suspected"

    return TriageResult(
        report_id=report.id,
        responder_id=responder_id,
        tag=tag,
        priority=priority,
        summary=clip_summary(extraction.summary),
        floor=floor,
        zone=zone_name,
        responder_status=status,
        victim_count=victim_count,
        victim_condition=extraction.victim_condition,
        victim_certainty=certainty,
        hazards=list(extraction.hazards),
        needs=list(extraction.needs),
        mayday=mayday,
        confidence=round(confidence, 3),
        model=model,
        latency_ms=latency_ms,
    )
