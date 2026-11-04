"""Deterministic keyword triage used when there is no Meta API key (or as a fallback).

The rules are tuned so every ``expect_*`` key in ``data/scenario.json`` holds, while
staying generic enough for ad-hoc demo lines. Order of precedence for the tag:

    mayday / tier-A danger  >  victim cues  >  collapse-only danger  >  help cues  >  Status

Zone choice (in order): the room a victim event is in (unless the victim is already
extracted), then the first zone preceded by at/in/inside, then the first zone mentioned.
Floors: spoken floor ("on three", "fifth floor"), unit digits, and the chosen zone's own
floor (which wins for every non-stair zone).
"""

from __future__ import annotations

import re
from typing import Optional

from fireline.models import Building, RadioReport, Responder, ResponderStatus, Tag, TriageResult
from fireline.triage.extract import (
    ZoneMention,
    clip_summary,
    find_zone_mentions,
    infer_responder_id,
    parse_callsign,
    parse_floor_phrase,
    reconcile_floor,
    stair_label_is_floor_specific,
    transcript_declares_mayday,
)

MOCK_MODEL = "mock"

# --------------------------------------------------------------------------- cue tables

_W = lambda *alts: re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.IGNORECASE)  # noqa: E731

# A firefighter is in trouble right now.
DANGER_CRITICAL = _W(
    r"mayday", r"pinned", r"trapped", r"flashover", r"backdraft", r"out of air", r"no air",
    r"i'?m lost", r"we'?re lost", r"lost", r"can'?t move", r"can'?t find the (?:wall|door|stairs|way|exit)",
    r"fell through", r"firefighter down", r"man down", r"pass alarm", r"emergency traffic",
    r"everybody out", r"everyone out", r"get out now", r"evacuate(?: the building)?",
)
# Still Danger, but with egress / less acute.
DANGER_ELEVATED = _W(r"low air", r"low on air", r"air alarm", r"running low", r"no egress")
# Collapse is a hazard; it only flips the tag when nothing else is going on.
COLLAPSE = _W(r"collapse[ds]?", r"came down", r"caved in", r"ceiling (?:failure|fell|down)", r"structural (?:failure|damage)")

VICTIM_CUE = _W(
    r"victims?", r"found", r"someone", r"somebody", r"yelling", r"screaming", r"occupants?",
    r"residents?", r"kids?", r"child(?:ren)?", r"baby", r"infant", r"unconscious", r"bringing (?:him|her|them) out",
    r"pulling (?:him|her|them)", r"elderly", r"patients?", r"never came out", r"still inside", r"people inside",
)
VICTIM_HEARSAY = _W(
    r"never came out", r"saying", r"says", r"said", r"might", r"maybe", r"possibly", r"possible", r"may still",
    r"still inside", r"reported", r"report of", r"neighbor", r"told us",
)
VICTIM_CONFIRMED = _W(
    r"found", r"forced", r"pulling", r"bringing", r"carrying", r"got eyes on", r"eyes on", r"have (?:one|two|three|a|an)",
    r"with the victims?", r"unconscious", r"responsive", r"unresponsive", r"breathing", r"conscious",
)
VICTIM_HEARD = _W(r"hear", r"heard", r"yelling", r"screaming", r"banging", r"knocking")
VICTIM_EXTRACTED = _W(r"out the", r"handing off", r"handed (?:off|over|to)", r"turned over to ems", r"to ems", r"with ems")

HELP_CUE = _W(r"needs?", r"send", r"request(?:ing)?", r"get us", r"bring (?:up|us)", r"we could use", r"give us")
URGENT = _W(r"now", r"urgent", r"immediately", r"asap", r"right away", r"hurry")
ADMIN = _W(r"par complete", r"par is complete", r"rehab", r"swapping bottles", r"bottle swap", r"accounted for",
           r"ready for reassignment", r"available", r"checking in", r"on scene")
OK_CUE = _W(r"i'?m ok(?:ay)?", r"we'?re ok(?:ay)?", r"we'?re good", r"all good", r"i can walk", r"unhurt", r"we'?re fine")
EVAC_CUE = _W(r"backing out", r"coming down", r"heading out", r"exiting", r"going down", r"taking (?:him|her|them) down",
              r"evacuating", r"bailing", r"out the")
OUTDOOR_CUE = _W(r"staging", r"outside", r"exterior", r"street", r"command post", r"rehab", r"apparatus", r"parking lot",
                 r"hydrant", r"alley")

# (regex, canonical hazard phrase)
HAZARD_RULES: list[tuple[re.Pattern[str], str]] = [
    (_W(r"heavy smoke", r"thick smoke", r"black smoke"), "heavy smoke"),
    (_W(r"smoke (?:is )?banking", r"smoke banking down"), "smoke banking down"),
    (_W(r"zero visibility", r"no visibility", r"can'?t see"), "zero visibility"),
    (_W(r"high heat", r"extreme heat", r"heat is"), "high heat"),
    (_W(r"flashover"), "flashover"),
    (_W(r"backdraft"), "backdraft"),
    (_W(r"ceiling (?:came down|fell|collapsed|failure)", r"came down"), "ceiling collapse"),
    (_W(r"collapse[ds]?", r"caved in", r"structural"), "structural collapse"),
    (_W(r"low air", r"low on air", r"air alarm", r"out of air", r"no air"), "low air"),
    # A named stair takes precedence over the generic "blocked route" (see _hazards):
    # "coming down stairwell A, not B. B is blocked at five" must block B, not A.
    (_W(r"stair(?:well|way|s)? A (?:is |was |got )?blocked", r"A is blocked", r"stair(?:well)? alpha (?:is )?blocked"),
     "stairwell A blocked"),
    (_W(r"stair(?:well|way|s)? B (?:is |was |got )?blocked", r"B is blocked", r"stair(?:well)? bravo (?:is )?blocked"),
     "stairwell B blocked"),
    (_W(r"blocked"), "blocked route"),
    (_W(r"jammed", r"door is stuck"), "jammed door"),
    (_W(r"line (?:is|went) dry", r"dry line"), "dry hose line"),
    (_W(r"pinned", r"trapped"), "firefighter trapped"),
    (_W(r"fire (?:is )?(?:in|on)", r"working fire", r"fully involved"), "active fire"),
]

# (regex, canonical need phrase) -- only applied when a help cue is present.
NEED_RULES: list[tuple[re.Pattern[str], str]] = [
    (_W(r"rit", r"rapid intervention"), "RIT"),
    (_W(r"irons", r"halligan", r"axe"), "irons"),
    (_W(r"water", r"hose", r"a line", r"second line", r"supply"), "water supply"),
    (_W(r"relief", r"fresh crew", r"relief crew"), "relief crew"),
    (_W(r"a hand", r"hands", r"more people", r"manpower", r"backup", r"another crew", r"second set"), "extra hands"),
    (_W(r"(?:ground|a|the|another) ladder", r"ladder (?:up|to the)"), "ladder"),
    (_W(r"ems", r"medic", r"ambulance", r"stretcher", r"stokes"), "EMS"),
    (_W(r"saw", r"fan", r"ppv", r"thermal", r"tic"), "equipment"),
]

CONDITION_WORDS = _W(
    r"unconscious", r"unresponsive", r"responsive", r"conscious", r"not breathing", r"breathing", r"adult", r"elderly",
    r"male", r"female", r"woman", r"man", r"child", r"kid", r"baby", r"infant", r"injured", r"burned", r"ambulatory",
)

_COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "a": 1, "an": 1, "another": 1}
_COUNT_RE = re.compile(
    r"\b(one|two|three|four|five|six|a|an|another|\d)\s+(?:more\s+)?"
    r"(victims?|people|persons?|kids?|child(?:ren)?|occupants?|residents?|adults?|patients?|males?|females?|women|woman|men|man|bab(?:y|ies))\b",
    re.IGNORECASE,
)
_SINGLE_RE = _W(r"someone", r"somebody", r"a kid", r"a child", r"an? (?:adult|male|female|woman|man|occupant|resident|victim|patient|baby)",
                r"her neighbor", r"his neighbor", r"the victim")


# --------------------------------------------------------------------------- pieces


_TRANSPORT_RE = re.compile(r"\bwith (?:the|a|an|our|that|this|one|two|three) victims?\b", re.IGNORECASE)
"""'backing out down stairwell A with the victim' moves a known victim; it is not a new find."""


def _victim_certainty(text: str) -> str:
    """none / suspected / confirmed / extracted from the cue tables (see module docstring)."""
    if not VICTIM_CUE.search(text):
        return "none"
    if VICTIM_EXTRACTED.search(text):
        return "extracted"
    if not VICTIM_CUE.search(_TRANSPORT_RE.sub("", text)):
        return "none"  # still carrying a victim, not a new one
    if VICTIM_HEARSAY.search(text):
        return "suspected"
    if VICTIM_CONFIRMED.search(text):
        return "confirmed"
    return "suspected"


def _victim_count(text: str, certainty: str) -> int:
    if certainty == "none":
        return 0
    counts = []
    for m in _COUNT_RE.finditer(text):
        w = m.group(1).lower()
        counts.append(int(w) if w.isdigit() else _COUNT_WORDS.get(w, 1))
    if counts:
        return max(counts)
    return 1


def _victim_condition(text: str, certainty: str) -> Optional[str]:
    if certainty == "none":
        return None
    seen: list[str] = []
    for m in CONDITION_WORDS.finditer(text):
        w = m.group().lower()
        if w not in seen:
            seen.append(w)
    return ", ".join(seen) if seen else None


def _hazards(text: str) -> list[str]:
    out: list[str] = []
    for rx, label in HAZARD_RULES:
        if rx.search(text) and label not in out:
            out.append(label)
    if any(label.startswith("stairwell ") and label.endswith(" blocked") for label in out):
        # The named-stair hazard already says where the blockage is; the generic one would be
        # anchored at the reporter's own zone (often the *other* stair).
        out = [label for label in out if label != "blocked route"]
    return out


def _needs(text: str) -> list[str]:
    if not HELP_CUE.search(text):
        return []
    out: list[str] = []
    for rx, label in NEED_RULES:
        if rx.search(text) and label not in out:
            out.append(label)
    return out or ["assistance"]


def _tag(text: str, certainty: str, mayday: bool) -> Tag:
    if mayday or DANGER_CRITICAL.search(text) or DANGER_ELEVATED.search(text):
        return Tag.DANGER
    if certainty != "none":
        return Tag.VICTIM_FOUND
    if COLLAPSE.search(text):
        return Tag.DANGER
    if HELP_CUE.search(text):
        return Tag.HELP_NEEDED
    return Tag.STATUS


def _priority(text: str, tag: Tag, certainty: str, mayday: bool, hazards: list[str]) -> int:
    if mayday:
        return 5
    if tag == Tag.DANGER:
        if DANGER_CRITICAL.search(text):
            return 5
        if DANGER_ELEVATED.search(text):
            return 4
        return 3  # collapse observed, nobody reported hurt
    if tag == Tag.VICTIM_FOUND:
        return {"confirmed": 4, "suspected": 3, "extracted": 2}.get(certainty, 3)
    if tag == Tag.HELP_NEEDED:
        return 4 if URGENT.search(text) else 3
    if hazards:
        return 3
    if ADMIN.search(text):
        return 1
    return 2


def _status(text: str, tag: Tag, floor: Optional[int]) -> ResponderStatus:
    if tag == Tag.DANGER:
        return ResponderStatus.IN_DANGER
    if tag == Tag.HELP_NEEDED:
        return ResponderStatus.NEEDS_HELP
    if OK_CUE.search(text):
        return ResponderStatus.OK
    if EVAC_CUE.search(text) and floor != 0:
        return ResponderStatus.EVACUATING
    return ResponderStatus.OK


def _pick_zone(mentions: list[ZoneMention], certainty: str) -> Optional[ZoneMention]:
    """Victim room > location preposition (at/in/inside) > first mention."""
    if not mentions:
        return None
    if certainty not in ("none", "extracted"):
        for mn in mentions:
            if mn.zone.kind == "room":
                return mn
    for mn in mentions:
        if mn.preposition in ("at", "in", "inside", "into"):
            return mn
    return mentions[0]


def _callsign_label(report: RadioReport, roster: list[Responder], responder_id: Optional[str]) -> str:
    r = next((x for x in roster if x.id == responder_id), None)
    if r:
        member = re.search(r"-(\d+)$", r.id)
        return r.unit if (not member or member.group(1) == "1") else f"{r.unit}-{member.group(1)}"
    parsed = parse_callsign(report.transcript)
    if parsed:
        unit, num, member = parsed
        return f"{unit.title()} {num}" + (f"-{member}" if member else "")
    return "Unknown unit"


def _where(zone: Optional[str], floor: Optional[int]) -> str:
    if zone and floor is not None and floor > 0 and not re.search(r"\d", zone):
        return f"{zone} floor {floor}"
    if zone:
        return zone
    if floor is not None:
        return "outdoors" if floor == 0 else f"floor {floor}"
    return "location unknown"


_LEAD_IN_RE = re.compile(
    r"^(?:command[,.:]?\s*)?(?:(?:engine|ladder|rescue|truck|squad|medic)\s*\d+(?:\s*-\s*\d)?\s*(?:to command)?[,.:]?\s*)?(?:command[,.:]?\s*)?",
    re.IGNORECASE,
)


def _first_clause(text: str) -> str:
    """First sentence with the radio lead-in ('Command, Engine 1,' / 'Ladder 2 to Command,') removed."""
    first = re.split(r"[.!?]", text, maxsplit=1)[0].strip()
    first = _LEAD_IN_RE.sub("", first).strip(" ,.-")
    return first[:1].upper() + first[1:] if first else ""


def _summary(label: str, tag: Tag, mayday: bool, certainty: str, count: int, hazards: list[str], needs: list[str],
             zone: Optional[str], floor: Optional[int], text: str) -> str:
    where = _where(zone, floor)
    if mayday:
        head = f"MAYDAY {label} {where}: " + (", ".join(hazards[:2]) if hazards else "firefighter emergency")
    elif tag == Tag.DANGER:
        head = f"{label} {where}: " + (", ".join(hazards[:2]) if hazards else "in danger")
    elif tag == Tag.VICTIM_FOUND:
        noun = "victim" if count == 1 else "victims"
        head = f"{label}: {count} {noun} {certainty} {where}"
    elif tag == Tag.HELP_NEEDED:
        head = f"{label} {where} needs " + ", ".join(needs[:3])
    else:
        first = _first_clause(text)
        head = f"{label}: {first}" if first else f"{label} {where}: status"
        if hazards:
            head = f"{label} {where}: " + ", ".join(hazards[:3])
    return clip_summary(head)


# --------------------------------------------------------------------------- entry point


def mock_triage(report: RadioReport, building: Building, roster: list[Responder], latency_ms: int = 0) -> TriageResult:
    """Keyword triage of one transmission; always succeeds, never touches the network."""
    text = report.transcript or ""
    mayday = transcript_declares_mayday(text)
    certainty = _victim_certainty(text)
    tag = _tag(text, certainty, mayday)
    hazards = _hazards(text)
    needs = _needs(text)

    spoken_floor = parse_floor_phrase(text, max_floor=max(building.floors, 1))
    mentions = find_zone_mentions(building, text, spoken_floor)
    pick = _pick_zone(mentions, certainty)
    zone_name = pick.zone.name if pick else None
    if pick:
        specific = pick.zone.kind == "stair" and stair_label_is_floor_specific(building, pick.text)
        floor = reconcile_floor(pick.zone, spoken_floor, stair_floor_known=specific)
    else:
        floor = spoken_floor
    if floor is None and zone_name is None and OUTDOOR_CUE.search(text):
        floor = 0

    responder_id = report.responder_id or infer_responder_id(text, roster)
    label = _callsign_label(report, roster, responder_id)
    count = _victim_count(text, certainty)
    priority = _priority(text, tag, certainty, mayday, hazards)
    status = _status(text, tag, floor)

    confidence = 0.55
    if zone_name:
        confidence += 0.15
    if tag in (Tag.DANGER, Tag.VICTIM_FOUND) or mayday:
        confidence += 0.1

    return TriageResult(
        report_id=report.id,
        responder_id=responder_id,
        tag=tag,
        priority=priority,
        summary=_summary(label, tag, mayday, certainty, count, hazards, needs, zone_name, floor, text),
        floor=floor,
        zone=zone_name,
        responder_status=status,
        victim_count=count,
        victim_condition=_victim_condition(text, certainty),
        victim_certainty=certainty,  # type: ignore[arg-type]
        hazards=hazards,
        needs=needs,
        mayday=mayday,
        confidence=round(min(confidence, 0.9), 2),
        model=MOCK_MODEL,
        latency_ms=latency_ms,
    )
