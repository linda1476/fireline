"""Load data/scenario.json into typed objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fireline.config import DATA_DIR
from fireline.models import Building, Responder, WorldState


@dataclass
class ScriptLine:
    t: float
    responder_id: str
    text: str
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    incident_name: str
    building: Building
    responders: list[Responder]
    script: list[ScriptLine]
    eval_extra: list[ScriptLine]

    def initial_state(self) -> WorldState:
        return WorldState(
            incident_name=self.incident_name,
            building=self.building,
            responders={r.id: r.model_copy(deep=True) for r in self.responders},
        )


def _line(d: dict[str, Any]) -> ScriptLine:
    expect = {k: v for k, v in d.items() if k.startswith("expect_")}
    return ScriptLine(t=float(d.get("t", 0)), responder_id=d["responder_id"], text=d["text"], expect=expect)


def load_scenario(path: str | Path | None = None) -> Scenario:
    p = Path(path) if path else DATA_DIR / "scenario.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    return Scenario(
        incident_name=raw["incident_name"],
        building=Building.model_validate(raw["building"]),
        responders=[Responder.model_validate(r) for r in raw["responders"]],
        script=[_line(d) for d in raw.get("script", [])],
        eval_extra=[_line(d) for d in raw.get("triage_eval_extra", [])],
    )
