"""Shared data contracts for Fireline.

Every module (triage, worldmodel, briefer, vision, server) imports from here and
nowhere else for its types. Keep this file dependency-free except pydantic.

Spatial conventions
-------------------
* Indoor positions are grid cells on a floor: ``floor`` (1-based), ``x`` (0..W-1,
  west->east), ``y`` (0..H-1, north->south). One cell ~ 1.5 m.
* Outdoor positions are WGS84 ``lat``/``lon``. The building has a ``geo_origin``
  (its north-west corner) and a ``meters_per_cell`` so indoor cells can be
  projected onto the outdoor map and vice versa.
* ``zone`` names are the human vocabulary used on the radio ("stairwell A",
  "unit 302", "east corridor", "staging area"). Each zone has a floor (0 =
  outdoor), a cell rectangle and aliases. The triage model maps free speech to a
  zone name; the world model turns the zone into a cell.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Tag(str, Enum):
    """Priority tag assigned to every radio report by the triage model."""

    DANGER = "Danger"            # mayday, collapse, trapped, low air, flashover
    VICTIM_FOUND = "VictimFound"  # victim located / heard / suspected
    HELP_NEEDED = "HelpNeeded"    # needs more hands, tools, water, relief
    STATUS = "Status"             # routine progress / position update


class ResponderStatus(str, Enum):
    OK = "OK"
    IN_DANGER = "InDanger"
    NEEDS_HELP = "NeedsHelp"
    EVACUATING = "Evacuating"
    UNKNOWN = "Unknown"


class VictimStatus(str, Enum):
    SUSPECTED = "suspected"   # heard / reported second-hand / detected on camera
    CONFIRMED = "confirmed"   # responder has eyes on the victim
    EXTRACTED = "extracted"   # out of the building


class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Spatial primitives
# ---------------------------------------------------------------------------


class Cell(BaseModel):
    floor: int = Field(..., description="1-based floor; 0 means outdoors")
    x: int
    y: int


class GeoPos(BaseModel):
    lat: float
    lon: float


class Zone(BaseModel):
    name: str
    floor: int = Field(..., description="0 = outdoor zone")
    x0: int
    y0: int
    x1: int = Field(..., description="inclusive")
    y1: int = Field(..., description="inclusive")
    aliases: list[str] = Field(default_factory=list)
    kind: Literal["room", "corridor", "stair", "lobby", "roof", "outdoor"] = "room"

    @property
    def center(self) -> Cell:
        return Cell(floor=self.floor, x=(self.x0 + self.x1) // 2, y=(self.y0 + self.y1) // 2)

    def contains(self, cell: Cell) -> bool:
        return (
            cell.floor == self.floor
            and self.x0 <= cell.x <= self.x1
            and self.y0 <= cell.y <= self.y1
        )


class Building(BaseModel):
    name: str
    address: str = ""
    floors: int
    width: int = Field(..., description="grid cells west->east")
    height: int = Field(..., description="grid cells north->south")
    geo_origin: GeoPos = Field(..., description="north-west corner of the SITE grid")
    meters_per_cell: float = 1.5
    bearing_deg: float = Field(0.0, description="rotation of grid +x axis from true east, clockwise")
    site_width: int = Field(60, description="outdoor site grid cells west->east (floor 0)")
    site_height: int = Field(40, description="outdoor site grid cells north->south (floor 0)")
    footprint_x: int = Field(18, description="site-grid x of the building's north-west corner")
    footprint_y: int = Field(13, description="site-grid y of the building's north-west corner")
    zones: list[Zone] = Field(default_factory=list)

    def indoor_to_site(self, cell: "Cell") -> "Cell":
        """Project an indoor cell onto the outdoor site grid (floor 0)."""
        if cell.floor == 0:
            return cell
        return Cell(floor=0, x=self.footprint_x + cell.x, y=self.footprint_y + cell.y)

    def site_to_geo(self, cell: "Cell") -> "GeoPos":
        """Site-grid cell -> WGS84, ignoring bearing for simplicity (bearing_deg=0)."""
        import math

        site = self.indoor_to_site(cell)
        dx_m = (site.x + 0.5) * self.meters_per_cell
        dy_m = (site.y + 0.5) * self.meters_per_cell
        lat = self.geo_origin.lat - dy_m / 111_320.0
        lon = self.geo_origin.lon + dx_m / (111_320.0 * math.cos(math.radians(self.geo_origin.lat)))
        return GeoPos(lat=lat, lon=lon)

    def zone_by_name(self, name: str) -> Optional[Zone]:
        if not name:
            return None
        key = name.strip().lower()
        for z in self.zones:
            if z.name.lower() == key or key in (a.lower() for a in z.aliases):
                return z
        return None

    def zones_on_floor(self, floor: int) -> list[Zone]:
        return [z for z in self.zones if z.floor == floor]

    def zone_names(self) -> list[str]:
        return [z.name for z in self.zones]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class RadioReport(BaseModel):
    """One radio transmission after speech-to-text (or typed text)."""

    id: str = Field(default_factory=lambda: new_id("rpt"))
    responder_id: Optional[str] = Field(None, description="None if speaker not yet attributed")
    speaker_label: Optional[str] = Field(None, description="ASR diarization label, e.g. 'A'")
    transcript: str
    language: str = "en"
    audio_path: Optional[str] = None
    source: Literal["mic", "file", "text", "scripted"] = "text"
    timestamp: str = Field(default_factory=now_iso)


class TouchInput(BaseModel):
    """One-touch action from the responder's clip-on display."""

    id: str = Field(default_factory=lambda: new_id("tch"))
    responder_id: str
    action: Literal["mark_victim", "need_help", "victim_out", "ack", "clear_danger", "im_ok"]
    cell: Optional[Cell] = Field(None, description="where on the mini-map they tapped")
    victim_id: Optional[str] = None
    timestamp: str = Field(default_factory=now_iso)


class PhotoInput(BaseModel):
    """A helmet-cam frame sent for SAM 3.1 person detection."""

    id: str = Field(default_factory=lambda: new_id("pho"))
    responder_id: str
    image_b64: str = Field(..., description="base64 JPEG/PNG without data: prefix")
    mime: str = "image/jpeg"
    timestamp: str = Field(default_factory=now_iso)


# ---------------------------------------------------------------------------
# Triage (Muse Spark structured output)
# ---------------------------------------------------------------------------


class TriageResult(BaseModel):
    """What the triage model extracts from one radio report."""

    report_id: str
    responder_id: Optional[str] = None
    tag: Tag
    priority: int = Field(..., ge=1, le=5, description="5 = life-threatening right now")
    summary: str = Field(..., description="<= 15 words, plain English, for the command queue")
    floor: Optional[int] = Field(None, description="floor the report is about (0 = outdoors)")
    zone: Optional[str] = Field(None, description="exact zone name from the building vocabulary")
    responder_status: ResponderStatus = ResponderStatus.UNKNOWN
    victim_count: int = Field(0, ge=0)
    victim_condition: Optional[str] = Field(None, description="e.g. 'unconscious adult', 'child, responsive'")
    victim_certainty: Literal["none", "suspected", "confirmed", "extracted"] = "none"
    hazards: list[str] = Field(default_factory=list, description="e.g. 'ceiling collapse', 'low air', 'heavy smoke'")
    needs: list[str] = Field(default_factory=list, description="requested resources e.g. 'RIT', 'hose line', 'relief crew'")
    mayday: bool = False
    confidence: float = Field(0.8, ge=0, le=1)
    model: str = "mock"
    latency_ms: int = 0
    timestamp: str = Field(default_factory=now_iso)


class QueueItem(BaseModel):
    """A triage result as shown in the commander's priority queue."""

    triage: TriageResult
    report: RadioReport
    acknowledged: bool = False
    score: float = Field(0.0, description="priority with recency / mayday boost; higher first")


# ---------------------------------------------------------------------------
# World model
# ---------------------------------------------------------------------------


class Responder(BaseModel):
    id: str
    name: str
    unit: str = Field(..., description="e.g. 'Engine 1', 'Ladder 2', 'Rescue 3'")
    role: str = ""
    status: ResponderStatus = ResponderStatus.OK
    cell: Optional[Cell] = None
    zone: Optional[str] = None
    air_minutes: Optional[int] = Field(None, description="estimated SCBA air remaining, if known")
    last_report_id: Optional[str] = None
    last_seen: str = Field(default_factory=now_iso)
    track: list[Cell] = Field(default_factory=list, description="recent positions, newest last")


class VictimEstimate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("vic"))
    cell: Cell
    zone: Optional[str] = None
    probability: float = Field(..., ge=0, le=1)
    status: VictimStatus = VictimStatus.SUSPECTED
    count: int = 1
    condition: Optional[str] = None
    source_report_ids: list[str] = Field(default_factory=list)
    source: Literal["radio", "touch", "camera", "fused"] = "radio"
    assigned_responder_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Hazard(BaseModel):
    id: str = Field(default_factory=lambda: new_id("haz"))
    kind: str
    cell: Cell
    zone: Optional[str] = None
    severity: int = Field(3, ge=1, le=5)
    source_report_ids: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: str = Field(default_factory=now_iso)


class Detection(BaseModel):
    """One SAM 3.1 detection (normalized coordinates 0..1)."""

    label: str
    score: float
    x0: float
    y0: float
    x1: float
    y1: float


class WorldEvent(BaseModel):
    """Append-only log entry; the dashboard timeline renders these."""

    id: str = Field(default_factory=lambda: new_id("evt"))
    kind: Literal["report", "triage", "touch", "photo", "briefing", "assignment", "system"]
    responder_id: Optional[str] = None
    text: str
    ref_id: Optional[str] = Field(None, description="id of the report/triage/briefing this refers to")
    timestamp: str = Field(default_factory=now_iso)


class WorldState(BaseModel):
    version: int = 0
    incident_name: str = "Incident"
    building: Building
    responders: dict[str, Responder] = Field(default_factory=dict)
    victims: dict[str, VictimEstimate] = Field(default_factory=dict)
    hazards: dict[str, Hazard] = Field(default_factory=dict)
    queue: list[QueueItem] = Field(default_factory=list, description="sorted, highest score first")
    events: list[WorldEvent] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class StateDelta(BaseModel):
    """What changed in one reducer step; the briefer reasons over this."""

    version: int
    triage: Optional[TriageResult] = None
    touch: Optional[TouchInput] = None
    detections: list[Detection] = Field(default_factory=list)
    changed_responders: list[str] = Field(default_factory=list)
    changed_victims: list[str] = Field(default_factory=list)
    changed_hazards: list[str] = Field(default_factory=list)
    new_events: list[WorldEvent] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)


# ---------------------------------------------------------------------------
# Briefer (agent output)
# ---------------------------------------------------------------------------


class Briefing(BaseModel):
    """One spoken message pushed to one responder's earpiece / clip display."""

    id: str = Field(default_factory=lambda: new_id("brf"))
    responder_id: str
    text: str = Field(..., description="<= 25 words, spoken aloud by TTS")
    urgency: Urgency = Urgency.NORMAL
    reason: str = Field("", description="why the agent decided to interrupt this responder")
    trigger_ids: list[str] = Field(default_factory=list, description="report/victim/hazard ids")
    show_cell: Optional[Cell] = Field(None, description="cell to highlight on the clip display")
    timestamp: str = Field(default_factory=now_iso)


class Assignment(BaseModel):
    """Agent proposal to the commander: send responder X to victim/hazard Y."""

    id: str = Field(default_factory=lambda: new_id("asg"))
    responder_id: str
    target_kind: Literal["victim", "hazard", "responder"]
    target_id: str
    reason: str
    accepted: Optional[bool] = None
    timestamp: str = Field(default_factory=now_iso)


class BrieferDecision(BaseModel):
    """Structured output of one briefer agent step."""

    briefings: list[Briefing] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    commander_note: Optional[str] = Field(None, description="one line for the command dashboard, if any")
    model: str = "mock"
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# WebSocket envelope
# ---------------------------------------------------------------------------


class WsMessage(BaseModel):
    """Everything on the wire is one of these."""

    type: Literal[
        "state",        # full WorldState snapshot
        "delta",        # StateDelta
        "transcript",   # live partial/final transcript {text, final, speaker, responder_id}
        "briefing",     # Briefing for one responder
        "assignment",   # Assignment proposal
        "event",        # WorldEvent
        "touch",        # client -> server TouchInput
        "error",
    ]
    payload: dict
