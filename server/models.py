"""Shared data model (pydantic) + the strict JSON schema sent to muse-spark-1.3.

Every module imports from here. Field names are the wire format for the WebSocket
and REST API (see docs/CONTRACT.md). Timestamps:
  t  = scenario seconds (float, 0 at scenario start; the UI incident clock)
  ts = wall-clock unix seconds (float), for logs only
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------- enums
Tag = Literal["MAYDAY", "DANGER", "VICTIM_FOUND", "HELP_NEEDED", "ROUTINE"]
TAGS: list[str] = ["MAYDAY", "DANGER", "VICTIM_FOUND", "HELP_NEEDED", "ROUTINE"]
# SOP 107 priority order: 대원안전 > 구조대상자 > 주요요소 > 전략. Lower = more urgent.
TAG_PRIORITY: dict[str, int] = {"MAYDAY": 0, "DANGER": 1, "VICTIM_FOUND": 2, "HELP_NEEDED": 3, "ROUTINE": 9}

DistressWhat = Literal["TRAPPED", "FALL", "INJURY", "MISSING", "COLLAPSE", "GAS", "LOW_AIR", "LOST", "OTHER", "UNKNOWN"]
# SOP 109 §1.2.2 cause vocabulary shown in the UI
DISTRESS_WHAT_KO: dict[str, str] = {
    "TRAPPED": "대원고립", "FALL": "대원추락", "INJURY": "대원부상", "MISSING": "대원실종",
    "COLLAPSE": "붕괴위험", "GAS": "가스누출", "LOW_AIR": "공기부족", "LOST": "퇴로상실",
    "OTHER": "기타", "UNKNOWN": "미상",
}
VictimState = Literal["REPORTED", "FOUND", "EXTRACTING", "UNKNOWN"]
StatusChange = Literal["ENTERING", "EXITING", "LOW_AIR", "TRAPPED", "OK", "NONE"]
Strategy = Literal["OFFENSIVE", "DEFENSIVE", "NONE"]

Channel = Literal["CMD", "TAC", "PTT"]
UnitStatus = Literal["IN", "OUT", "TRAPPED", "LOW_AIR", "OK", "UNKNOWN"]
UnitRole = Literal["IC", "CREW", "RIT", "EXTERIOR", "DISPATCH"]
ZoneKind = Literal["indoor", "outdoor"]
SearchState = Literal["none", "primary", "cross", "searched"]
CardKind = Literal["MAYDAY", "DANGER", "VICTIM_FOUND", "HELP_NEEDED", "RULE"]
CardState = Literal["open", "escalated", "acked", "resolved"]
ProposalKind = Literal["RADIO_SILENCE", "RIT_DEPLOY", "WITHDRAW", "CONFIRM_STRATEGY", "ASSIGN"]
ProposalState = Literal["pending", "approved", "edited", "rejected"]
BriefDecision = Literal["push", "hold"]
BriefPriority = Literal["P0", "P1", "P2"]
BriefSource = Literal["agent", "router", "rule"]
TraceKind = Literal["reasoning", "tool_call", "checker", "delivery", "fallback", "wake"]
Mode = Literal["LIVE", "REPLAY"]
CrewButton = Literal["EVACUATE", "VICTIM_HERE", "SEARCH_DONE", "NEED_HELP"]
CREW_BUTTON_KO: dict[str, str] = {
    "EVACUATE": "긴급탈출", "VICTIM_HERE": "구조대상자 여기", "SEARCH_DONE": "검색완료", "NEED_HELP": "지원요청",
}


# ----------------------------------------------------------------------------- triage (Spark output)
class Location(BaseModel):
    floor: int | None = None
    zone_hint: str | None = None
    raw: str | None = None


class Distress(BaseModel):
    who: str | None = None
    what: DistressWhat = "UNKNOWN"
    where_raw: str | None = None
    needs: str | None = None
    air: str | None = None


class Victims(BaseModel):
    count: int | None = None
    where_raw: str | None = None
    state: VictimState = "UNKNOWN"


class Triage(BaseModel):
    """Exactly what muse-spark-1.3 returns under TRIAGE_SCHEMA (strict)."""

    tag: Tag
    speaker_unit: str | None = None
    addressee: str | None = None
    location: Location = Field(default_factory=Location)
    distress: Distress | None = None
    victims: Victims | None = None
    hazard_terms: list[str] = Field(default_factory=list)
    status_change: StatusChange = "NONE"
    strategy_declared: Strategy = "NONE"
    needs_ack: bool = False
    confidence: float = 0.0
    asr_uncertain: bool = False
    uncertain_reason: str | None = None
    evidence_span: str = ""
    crew_brief: str | None = None


def _nullable(t: str, **extra: Any) -> dict[str, Any]:
    return {"anyOf": [{"type": t, **extra}, {"type": "null"}]}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props.keys()), "additionalProperties": False}


_LOCATION = _obj({"floor": _nullable("integer"), "zone_hint": _nullable("string"), "raw": _nullable("string")})
_DISTRESS = _obj({
    "who": _nullable("string"),
    "what": {"type": "string", "enum": ["TRAPPED", "FALL", "INJURY", "MISSING", "COLLAPSE", "GAS", "LOW_AIR", "LOST", "OTHER", "UNKNOWN"]},
    "where_raw": _nullable("string"),
    "needs": _nullable("string"),
    "air": _nullable("string"),
})
_VICTIMS = _obj({
    "count": _nullable("integer"),
    "where_raw": _nullable("string"),
    "state": {"type": "string", "enum": ["REPORTED", "FOUND", "EXTRACTING", "UNKNOWN"]},
})

# Strict-mode subset (dev.meta.ai/docs/structured-output): root object, additionalProperties:false
# everywhere, required = all keys, anyOf allowed below the root, ASCII enums only.
# If research/smoke_b1.md says anyOf-null is rejected, switch SENTINEL_MODE in triage.py.
TRIAGE_SCHEMA: dict[str, Any] = _obj({
    "tag": {"type": "string", "enum": TAGS},
    "speaker_unit": _nullable("string"),
    "addressee": _nullable("string"),
    "location": _LOCATION,
    "distress": {"anyOf": [_DISTRESS, {"type": "null"}]},
    "victims": {"anyOf": [_VICTIMS, {"type": "null"}]},
    "hazard_terms": {"type": "array", "items": {"type": "string"}},
    "status_change": {"type": "string", "enum": ["ENTERING", "EXITING", "LOW_AIR", "TRAPPED", "OK", "NONE"]},
    "strategy_declared": {"type": "string", "enum": ["OFFENSIVE", "DEFENSIVE", "NONE"]},
    "needs_ack": {"type": "boolean"},
    "confidence": {"type": "number"},
    "asr_uncertain": {"type": "boolean"},
    "uncertain_reason": _nullable("string"),
    "evidence_span": {"type": "string"},
    "crew_brief": _nullable("string"),
})


# ----------------------------------------------------------------------------- world objects
class Unit(BaseModel):
    id: str
    callsign: str
    name: str | None = None
    crew: int = 1
    channel: Channel = "TAC"
    role: UnitRole = "CREW"
    lang: Literal["ko", "en"] = "ko"
    aliases: list[str] = Field(default_factory=list)
    assignment: str | None = None
    zone_id: str | None = None
    status: UnitStatus = "UNKNOWN"
    interior: bool = False            # True once status IN; R2 applies only to interior units
    last_heard_t: float | None = None
    unanswered_pings: int = 0
    heard_count: int = 0              # briefs pushed to this unit
    total_count: int = 0              # non-ROUTINE events + rule firings this unit could have heard
    label_en: str | None = None       # "FF Kim (Hanbit Rescue)" for subtitles


class HazardNote(BaseModel):
    event_id: str
    text: str
    t: float


class VictimReport(BaseModel):
    event_id: str
    count: int | None = None
    state: VictimState = "UNKNOWN"
    text: str = ""
    t: float


class Zone(BaseModel):
    id: str
    floor: int | None = None          # None for outdoor; 4 = roof
    label_ko: str
    label_en: str
    kind: ZoneKind = "indoor"
    parent: str | None = None
    polygon: list[list[float]] = Field(default_factory=list)   # metres, site frame (see data/zones.json)
    aliases: list[str] = Field(default_factory=list)
    hazards: list[HazardNote] = Field(default_factory=list)
    victim_reports: list[VictimReport] = Field(default_factory=list)
    search_state: SearchState = "none"


class Transmission(BaseModel):
    id: str
    channel: Channel
    turn_id: str | None = None
    unit_id: str | None = None        # known for replay/ptt; None for live until snapped
    line_id: str | None = None        # scenario line (L01..) when replayed
    t_keyup: float
    t_final: float | None = None
    text_partial: str = ""
    text_final: str | None = None
    audio_url: str | None = None      # "/samples/radio/L08.wav"
    source: Literal["replay", "live", "ptt"] = "replay"
    lang: Literal["ko", "en"] = "ko"


class Latency(BaseModel):
    asr_ms: int = 0        # key-up (or end of speech) → final transcript
    triage_ms: int = 0     # final → Triage
    total_ms: int = 0      # key-up → Event


class Event(BaseModel):
    id: str
    transmission_id: str
    t: float
    channel: Channel
    text: str
    triage: Triage
    speaker_unit_snapped: str | None = None   # Unit.id
    zone_id_snapped: str | None = None        # Zone.id
    latency: Latency = Field(default_factory=Latency)
    evidence_verified: bool = False           # evidence_span found verbatim (normalised) in text
    source: Literal["replay", "live", "ptt", "button"] = "replay"


class Card(BaseModel):
    id: str
    kind: CardKind
    title: str                                 # e.g. "긴급탈출 · 한빛구조대 김하늘 · 2F-E-STORE"
    title_en: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    rule_id: str | None = None                 # "R1".."R5" for RULE cards and escalations
    priority: int = 9                          # TAG_PRIORITY; lower first
    state: CardState = "open"
    unit_id: str | None = None
    zone_id: str | None = None
    fields: dict[str, str | None] = Field(default_factory=dict)   # who / what / where / needs / air
    missing_fields: list[str] = Field(default_factory=list)
    evidence_span: str = ""
    channel: Channel | None = None
    created_t: float
    acked_t: float | None = None
    resolved_t: float | None = None
    escalation_level: int = 0                  # 0 none, 1 at 10 s, 2 at 20 s (R1)
    latency_ms: int = 0                        # key-up → card
    note: str | None = None                    # resolution note, e.g. "found OK (L13)"


class Proposal(BaseModel):
    id: str
    card_id: str | None = None
    kind: ProposalKind
    units: list[str] = Field(default_factory=list)
    text: str
    rationale: str
    state: ProposalState = "pending"
    evidence_event_id: str | None = None
    created_t: float
    decided_t: float | None = None
    source: BriefSource = "agent"


class Brief(BaseModel):
    id: str
    unit_id: str
    decision: BriefDecision
    text: str
    priority: BriefPriority = "P1"
    reason: str
    evidence_event_id: str | None = None
    created_t: float
    spoken_t: float | None = None
    source: BriefSource = "agent"
    lang: Literal["ko", "en"] = "ko"


class TraceEntry(BaseModel):
    id: str
    t: float
    wake_id: str
    wake_reason: str                           # "event:evt_12 MAYDAY" / "rule:R2 park" / "button:kim VICTIM_HERE"
    kind: TraceKind
    payload: dict[str, Any] = Field(default_factory=dict)
    # tool_call: {tool, args, call_id}; checker: {tool, call_id, ok, error}; delivery: {brief_id, unit_id, decision}
    # reasoning: {summary}; fallback: {reason}; wake: {snapshot_size, round}


class Counters(BaseModel):
    transmissions: int = 0
    events: int = 0
    cards_open: int = 0
    cards_total: int = 0
    cards_queued: int = 0                       # overflow beyond max_open_cards
    unacked: int = 0
    held: int = 0
    pushed: int = 0
    checker_rejections: int = 0
    agent_wakes: int = 0
    fallback_routes: int = 0


class State(BaseModel):
    """Full snapshot sent on WS connect and GET /api/state."""

    scenario_id: str
    mode: Mode = "LIVE"
    lang: Literal["ko", "en"] = "ko"
    running: bool = False
    t: float = 0.0
    strategy: Strategy = "NONE"
    strategy_event_id: str | None = None
    units: dict[str, Unit] = Field(default_factory=dict)
    zones: dict[str, Zone] = Field(default_factory=dict)
    transmissions: list[Transmission] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    briefs: list[Brief] = Field(default_factory=list)
    trace: list[TraceEntry] = Field(default_factory=list)
    counters: Counters = Field(default_factory=Counters)
    building: dict[str, Any] = Field(default_factory=dict)      # from scenario yaml (height_m, footprint_m, collapse_ring)
    thresholds: dict[str, float] = Field(default_factory=dict)  # R1..R5 seconds, for the UI "demo timescale" labels


class WsMessage(BaseModel):
    """Envelope for every WebSocket frame server → client."""

    type: str
    payload: dict[str, Any]
