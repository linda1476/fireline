"""Unified World Model Harness: pure-Python spatial state engine (no LLM calls).

    from fireline.worldmodel import WorldModel
    wm = WorldModel(scenario.initial_state())
    delta = wm.apply_triage(result, report)
"""

from fireline.worldmodel.spatial import (
    FLOOR_COST,
    blocked_stairwells,
    cell_distance,
    chebyshev,
    find_zone,
    is_stairwell_blocked,
    nearest_stairwell,
    victim_cell,
    zone_center,
    zone_containing,
)
from fireline.worldmodel.state import WorldModel, hazard_severity, queue_score

__all__ = [
    "WorldModel",
    "queue_score",
    "hazard_severity",
    "FLOOR_COST",
    "blocked_stairwells",
    "cell_distance",
    "chebyshev",
    "find_zone",
    "is_stairwell_blocked",
    "nearest_stairwell",
    "victim_cell",
    "zone_center",
    "zone_containing",
]
