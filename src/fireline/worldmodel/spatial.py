"""Pure spatial helpers for the world model (no state, no LLM).

Everything here is a function over the shared ``Building`` / ``Zone`` / ``Cell``
models. Distances are in grid cells (one cell ~ 1.5 m). Moving between floors
costs ``FLOOR_COST`` cells per floor via the nearest stairwell.
"""

from __future__ import annotations

from typing import Iterable, Optional

from fireline.models import Building, Cell, Hazard, Zone

FLOOR_COST = 6
"""Extra cell-distance charged per floor travelled through a stairwell."""

BLOCKING_KEYWORDS = ("collapse", "blocked")
"""A hazard whose kind contains one of these blocks the stairwell it sits in."""


# ---------------------------------------------------------------------------
# Zone lookup
# ---------------------------------------------------------------------------


def _zone_matches(zone: Zone, key: str) -> bool:
    return zone.name.lower() == key or key in (a.lower() for a in zone.aliases)


def find_zone(building: Building, name: Optional[str], floor: Optional[int] = None) -> Optional[Zone]:
    """Floor-aware zone lookup by exact name or alias (case-insensitive).

    Stairwells share a name across floors and their aliases live on one floor
    only, so: prefer a direct match on ``floor``; otherwise look for a zone with
    the same canonical name on ``floor``; otherwise the first match anywhere.
    """
    if not name:
        return None
    key = name.strip().lower()
    matches = [z for z in building.zones if _zone_matches(z, key)]
    if not matches:
        return None
    if floor is None:
        return matches[0]
    for z in matches:
        if z.floor == floor:
            return z
    canonical = matches[0].name.lower()
    for z in building.zones:
        if z.floor == floor and z.name.lower() == canonical:
            return z
    return matches[0]


def zone_center(zone: Zone) -> Cell:
    """Centre cell of a zone (floor-aware)."""
    return zone.center


def zone_containing(building: Building, cell: Optional[Cell]) -> Optional[Zone]:
    """The zone whose rectangle contains ``cell`` on its floor, if any."""
    if cell is None:
        return None
    for z in building.zones:
        if z.contains(cell):
            return z
    return None


def stairwells_on_floor(building: Building, floor: int) -> list[Zone]:
    return [z for z in building.zones_on_floor(floor) if z.kind == "stair"]


def nearest_stairwell(building: Building, cell: Cell) -> Optional[Zone]:
    """Closest stairwell (Chebyshev) on the cell's floor; None if the floor has none."""
    stairs = stairwells_on_floor(building, cell.floor)
    if not stairs:
        return None
    return min(stairs, key=lambda z: chebyshev(cell, z.center))


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------


def chebyshev(a: Cell, b: Cell) -> int:
    """King-move distance on one grid (floors ignored)."""
    return max(abs(a.x - b.x), abs(a.y - b.y))


def _site(building: Building, cell: Cell) -> Cell:
    return building.indoor_to_site(cell)


def cell_distance(building: Building, a: Cell, b: Cell) -> int:
    """Travel distance in cells between two cells, possibly on different floors.

    * Same floor: Chebyshev.
    * Both indoors on different floors: walk to a stairwell on ``a``'s floor,
      climb ``FLOOR_COST`` per floor, walk from the matching stairwell to ``b``.
      Minimised over all stairwells (matched by name across floors).
    * One outdoors: project the indoor cell onto the site grid, add
      ``FLOOR_COST`` per floor above ground.
    """
    if a.floor == b.floor:
        return chebyshev(a, b)
    if a.floor == 0 or b.floor == 0:
        indoor, outdoor = (a, b) if b.floor == 0 else (b, a)
        return chebyshev(_site(building, indoor), outdoor) + FLOOR_COST * indoor.floor
    climb = FLOOR_COST * abs(a.floor - b.floor)
    best: Optional[int] = None
    for sa in stairwells_on_floor(building, a.floor):
        sb = find_zone(building, sa.name, b.floor)
        if sb is None:
            continue
        d = chebyshev(a, sa.center) + climb + chebyshev(sb.center, b)
        best = d if best is None else min(best, d)
    if best is None:  # no stairwells modelled: fall back to projected distance
        best = chebyshev(a, b) + climb
    return best


# ---------------------------------------------------------------------------
# Hazards and stairwells
# ---------------------------------------------------------------------------


def is_blocking_hazard(hazard: Hazard) -> bool:
    kind = hazard.kind.lower()
    return hazard.active and any(k in kind for k in BLOCKING_KEYWORDS)


def is_stairwell_blocked(building: Building, hazards: Iterable[Hazard], stair_name: str, floor: int) -> bool:
    """True if an active collapse/blocked hazard sits in ``stair_name`` at or below ``floor``.

    A blocked landing on floor N cuts the stairwell for N and every floor above.
    """
    key = stair_name.strip().lower()
    for h in hazards:
        if not is_blocking_hazard(h):
            continue
        zone = zone_containing(building, h.cell)
        if zone is None or zone.kind != "stair" or zone.name.lower() != key:
            continue
        if zone.floor <= floor:
            return True
    return False


def blocked_stairwells(building: Building, hazards: Iterable[Hazard], floor: int) -> list[str]:
    """Names of stairwells unusable from ``floor`` (blocked there or below)."""
    hz = list(hazards)
    return [z.name for z in stairwells_on_floor(building, floor) if is_stairwell_blocked(building, hz, z.name, floor)]


# ---------------------------------------------------------------------------
# Victim placement
# ---------------------------------------------------------------------------


def victim_cell(zone: Zone, n_existing: int = 0) -> Cell:
    """Deterministic cell for a victim inside ``zone``: centre, then +x per extra."""
    c = zone.center
    x = min(zone.x1, c.x + n_existing)
    return Cell(floor=zone.floor, x=x, y=c.y)


def offset_cell(building: Building, cell: Cell, dx: int, dy: int = 0) -> Cell:
    """Cell shifted by (dx, dy), clamped to the floor's grid."""
    if cell.floor == 0:
        w, h = building.site_width, building.site_height
    else:
        w, h = building.width, building.height
    return Cell(floor=cell.floor, x=max(0, min(w - 1, cell.x + dx)), y=max(0, min(h - 1, cell.y + dy)))
