"""World model tests: the 12 scripted scenario lines, hand-triaged (no fireline.triage import)."""

import json

import pytest

from fireline.models import (
    Cell,
    Detection,
    RadioReport,
    ResponderStatus,
    Tag,
    TouchInput,
    TriageResult,
    VictimStatus,
)
from fireline.worldmodel import (
    WorldModel,
    cell_distance,
    find_zone,
    is_stairwell_blocked,
    nearest_stairwell,
    queue_score,
    victim_cell,
)

# Hand-built triage for data/scenario.json "script" lines, in order. Each entry mirrors
# the line's expect_* hints (tag, floor, zone, certainty, count, mayday, hazards).
SCRIPT_TRIAGE = [
    dict(tag=Tag.STATUS, priority=2, summary="Engine 1 entering via lobby, taking stairwell A to 3",
         floor=1, zone="stairwell A", responder_status=ResponderStatus.OK),
    dict(tag=Tag.STATUS, priority=2, summary="Ladder 2 starting primary search on 4 west via stairwell B",
         floor=4, zone="west corridor 4", responder_status=ResponderStatus.OK),
    dict(tag=Tag.DANGER, priority=3, summary="Engine 1 on 3 east corridor, heavy smoke, high heat, fire in 302",
         floor=3, zone="east corridor 3", hazards=["heavy smoke", "high heat"]),
    dict(tag=Tag.VICTIM_FOUND, priority=4, summary="Possible occupant in 504 who never came out",
         floor=5, zone="unit 504", victim_certainty="suspected", victim_count=1),
    dict(tag=Tag.VICTIM_FOUND, priority=4, summary="Someone yelling inside 404, door jammed, need irons",
         floor=4, zone="unit 404", victim_certainty="suspected", victim_count=1, needs=["irons"]),
    dict(tag=Tag.VICTIM_FOUND, priority=5, summary="One unconscious adult male found in 302, moving to stairwell A",
         floor=3, zone="unit 302", victim_certainty="confirmed", victim_count=1,
         victim_condition="adult male, unconscious"),
    dict(tag=Tag.DANGER, priority=5, summary="MAYDAY: ceiling collapse, Choi pinned at stairwell B landing on 5",
         floor=5, zone="stairwell B", mayday=True, hazards=["ceiling collapse"], needs=["RIT"]),
    dict(tag=Tag.VICTIM_FOUND, priority=5, summary="Two responsive victims in 404, woman and child, bringing down",
         floor=4, zone="unit 404", victim_certainty="confirmed", victim_count=2,
         victim_condition="woman and child, responsive"),
    dict(tag=Tag.DANGER, priority=4, summary="Low air on 1-2, backing out via stairwell A, need relief on 3",
         floor=3, zone="stairwell A", hazards=["low air"], needs=["relief crew"],
         responder_status=ResponderStatus.EVACUATING),
    dict(tag=Tag.STATUS, priority=3, summary="Rescue 3-1 freed and okay, coming down stairwell A; B blocked at 5",
         floor=5, zone="stairwell B", hazards=["stairwell B blocked"], responder_status=ResponderStatus.OK),
    dict(tag=Tag.STATUS, priority=2, summary="Ladder 2 out the north entrance with two victims to EMS",
         floor=0, zone="north entrance", victim_certainty="extracted", victim_count=2),
    dict(tag=Tag.STATUS, priority=2, summary="Engine 1 at lobby, victim handed to EMS, going to rehab; 303 unchecked",
         floor=1, zone="lobby", victim_certainty="extracted", victim_count=1),
]


def _build_inputs(scenario):
    pairs = []
    for line, kw in zip(scenario.script, SCRIPT_TRIAGE):
        report = RadioReport(responder_id=line.responder_id, transcript=line.text, source="scripted")
        pairs.append((TriageResult(report_id=report.id, responder_id=line.responder_id, **kw), report))
    return pairs


@pytest.fixture
def wm(scenario):
    return WorldModel(scenario.initial_state())


@pytest.fixture
def played(scenario):
    """World model after all 12 script lines, plus the per-step deltas."""
    model = WorldModel(scenario.initial_state())
    deltas = [model.apply_triage(t, r) for t, r in _build_inputs(scenario)]
    return model, deltas


def _victims_in(model, zone):
    return [v for v in model.state.victims.values() if v.zone == zone]


# ---------------------------------------------------------------------------
# Scripted run
# ---------------------------------------------------------------------------


def test_versions_and_deltas(played):
    model, deltas = played
    assert model.state.version == 12
    assert [d.version for d in deltas] == list(range(1, 13))
    assert all(d.triage is not None and d.new_events for d in deltas)
    assert len(model.state.events) >= 12


def test_e1_1_ends_in_lobby(played):
    model, _ = played
    r = model.state.responders["E1-1"]
    assert r.cell.floor == 1
    assert r.zone == "lobby"
    assert len(r.track) >= 3
    last_e1_1 = [q for q in model.state.queue if q.report.responder_id == "E1-1"]
    assert r.last_report_id in {q.report.id for q in last_e1_1}
    assert r.status == ResponderStatus.EVACUATING  # line 9 said so; line 12 gave no status


def test_unit_302_victim_confirmed_then_extracted(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:6]:
        model.apply_triage(t, r)
    vs = _victims_in(model, "unit 302")
    assert len(vs) == 1
    assert vs[0].status == VictimStatus.CONFIRMED
    assert vs[0].probability == pytest.approx(0.95)
    assert vs[0].condition == "adult male, unconscious"
    for t, r in inputs[6:]:
        model.apply_triage(t, r)
    vs = _victims_in(model, "unit 302")
    assert len(vs) == 1 and vs[0].status == VictimStatus.EXTRACTED
    assert vs[0].probability == pytest.approx(0.95)


def test_unit_404_two_victims_merge_then_extracted(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:5]:
        model.apply_triage(t, r)
    v = _victims_in(model, "unit 404")
    assert len(v) == 1 and v[0].status == VictimStatus.SUSPECTED and v[0].probability == pytest.approx(0.6)
    for t, r in inputs[5:8]:
        model.apply_triage(t, r)
    v = _victims_in(model, "unit 404")
    assert len(v) == 1, "second 404 report merges into the existing estimate"
    assert v[0].status == VictimStatus.CONFIRMED and v[0].count == 2
    assert v[0].probability == pytest.approx(0.95)
    assert len(v[0].source_report_ids) == 2
    for t, r in inputs[8:11]:
        model.apply_triage(t, r)
    v = _victims_in(model, "unit 404")
    assert v[0].status == VictimStatus.EXTRACTED and v[0].count == 2


def test_r3_1_in_danger_after_mayday_then_ok(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:7]:
        model.apply_triage(t, r)
    assert model.state.responders["R3-2"].status == ResponderStatus.IN_DANGER
    assert model.state.responders["R3-1"].status == ResponderStatus.IN_DANGER
    for t, r in inputs[7:10]:
        model.apply_triage(t, r)
    assert model.state.responders["R3-1"].status == ResponderStatus.OK


def test_stairwell_b_blocked_at_five(played):
    model, _ = played
    b = model.building
    collapse = [h for h in model.state.hazards.values() if "collapse" in h.kind]
    assert len(collapse) == 1 and collapse[0].active and collapse[0].severity == 5
    assert collapse[0].cell.floor == 5 and collapse[0].zone == "stairwell B"
    blocked = [h for h in model.state.hazards.values() if "blocked" in h.kind]
    assert len(blocked) == 1 and blocked[0].severity == 4
    hz = model.state.hazards.values()
    assert is_stairwell_blocked(b, hz, "stairwell B", 5)
    assert not is_stairwell_blocked(b, hz, "stairwell B", 4)
    assert not is_stairwell_blocked(b, hz, "stairwell A", 5)


def test_hazard_dedupe_and_severity(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    t, r = inputs[2]
    model.apply_triage(t, r)
    model.apply_triage(t.model_copy(update={"report_id": "x"}), r.model_copy(update={"id": "x"}))
    kinds = sorted(h.kind for h in model.state.hazards.values())
    assert kinds == ["heavy smoke", "high heat"]
    assert all(h.severity == 3 and h.zone == "east corridor 3" for h in model.state.hazards.values())
    assert all(len(h.source_report_ids) == 2 for h in model.state.hazards.values())


def test_status_clear_deactivates_smoke_and_heat(scenario):
    model = WorldModel(scenario.initial_state())
    t, r = _build_inputs(scenario)[2]
    model.apply_triage(t, r)
    rep = RadioReport(responder_id="E1-1", transcript="Engine 1, east corridor on three is clear, fire knocked down.")
    res = TriageResult(report_id=rep.id, responder_id="E1-1", tag=Tag.STATUS, priority=1,
                       summary="East corridor 3 clear", floor=3, zone="east corridor 3")
    delta = model.apply_triage(res, rep)
    assert len(delta.changed_hazards) == 2
    assert all(not h.active for h in model.state.hazards.values())


def test_queue_mayday_first_then_ack(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:8]:
        model.apply_triage(t, r)
    top = model.state.queue[0]
    assert top.triage.mayday and top.report.responder_id == "R3-2"
    assert top.score > model.state.queue[1].score
    scores = [q.score for q in model.state.queue]
    assert scores == sorted(scores, reverse=True)
    delta = model.ack(top.report.id)
    assert delta.version == model.state.version
    acked = next(q for q in model.state.queue if q.report.id == top.report.id)
    assert acked.acknowledged and acked.score < 0
    assert model.state.queue[0].report.id != top.report.id
    assert model.state.queue[-1].report.id == top.report.id


def test_queue_score_formula():
    rep = RadioReport(responder_id="E1-1", transcript="x")
    t = TriageResult(report_id=rep.id, tag=Tag.DANGER, priority=5, summary="s", mayday=True)
    from fireline.models import QueueItem
    item = QueueItem(triage=t, report=rep)
    assert 75 <= queue_score(item) <= 85
    item.acknowledged = True
    assert queue_score(item) < 0


def test_air_minutes(played):
    model, _ = played
    rs = model.state.responders
    assert rs["E1-2"].air_minutes == 5, "low air alarm named 1-2"
    assert rs["E1-1"].air_minutes < 30
    assert rs["L2-1"].air_minutes < 30


# ---------------------------------------------------------------------------
# Touch
# ---------------------------------------------------------------------------


def test_touch_mark_victim_adds_victim(played):
    model, _ = played
    before = len(model.state.victims)
    tap = Cell(floor=3, x=4, y=11)  # unit 303, no victim there yet
    delta = model.apply_touch(TouchInput(responder_id="E1-1", action="mark_victim", cell=tap))
    assert len(model.state.victims) == before + 1
    v = model.state.victims[delta.changed_victims[0]]
    assert v.cell == tap and v.zone == "unit 303" and v.source == "touch"
    assert v.status == VictimStatus.CONFIRMED and v.probability == pytest.approx(0.9)
    assert delta.touch is not None and delta.version == model.state.version


def test_touch_mark_victim_merges_into_same_zone(scenario):
    model = WorldModel(scenario.initial_state())
    for t, r in _build_inputs(scenario)[:8]:
        model.apply_triage(t, r)
    before = len(model.state.victims)
    tap = Cell(floor=4, x=16, y=10)  # inside unit 404, which already has a radio victim
    delta = model.apply_touch(TouchInput(responder_id="L2-1", action="mark_victim", cell=tap))
    assert len(model.state.victims) == before
    v = _victims_in(model, "unit 404")[0]
    assert delta.changed_victims == [v.id]
    assert v.source == "fused" and v.cell == tap and v.count == 2
    assert v.status == VictimStatus.CONFIRMED and v.probability == pytest.approx(0.95)
    assert len(v.source_report_ids) == 3


def test_touch_status_buttons(wm):
    wm.apply_touch(TouchInput(responder_id="R3-1", action="need_help"))
    assert wm.state.responders["R3-1"].status == ResponderStatus.NEEDS_HELP
    wm.apply_touch(TouchInput(responder_id="R3-1", action="im_ok"))
    assert wm.state.responders["R3-1"].status == ResponderStatus.OK


def test_touch_clear_danger_deactivates_collapse(scenario):
    model = WorldModel(scenario.initial_state())
    for t, r in _build_inputs(scenario)[:7]:
        model.apply_triage(t, r)
    delta = model.apply_touch(TouchInput(responder_id="R3-2", action="clear_danger"))
    assert model.state.responders["R3-2"].status == ResponderStatus.OK
    assert delta.changed_hazards
    assert not any(h.active for h in model.state.hazards.values() if "collapse" in h.kind)


def test_touch_victim_out_nearest_and_explicit(scenario):
    model = WorldModel(scenario.initial_state())
    for t, r in _build_inputs(scenario)[:8]:
        model.apply_triage(t, r)
    model.apply_touch(TouchInput(responder_id="L2-1", action="victim_out"))
    v404 = _victims_in(model, "unit 404")[0]
    assert v404.status == VictimStatus.EXTRACTED
    v302 = _victims_in(model, "unit 302")[0]
    assert v302.status == VictimStatus.CONFIRMED
    model.apply_touch(TouchInput(responder_id="L2-1", action="victim_out", victim_id=v302.id))
    assert v302.status == VictimStatus.EXTRACTED


def test_touch_ack_acknowledges_newest(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:3]:
        model.apply_triage(t, r)
    model.apply_touch(TouchInput(responder_id="E1-1", action="ack"))
    by_id = {q.report.id: q for q in model.state.queue}
    assert by_id[inputs[2][1].id].acknowledged, "E1-1's newest report (line 3) is acked"
    assert not by_id[inputs[0][1].id].acknowledged
    assert sum(q.acknowledged for q in model.state.queue) == 1


# ---------------------------------------------------------------------------
# Detections
# ---------------------------------------------------------------------------


def test_detections_add_camera_victim(played):
    model, _ = played
    dets = [Detection(label="person", score=0.8, x0=0.1, y0=0.1, x1=0.4, y1=0.9),
            Detection(label="person", score=0.6, x0=0.5, y0=0.2, x1=0.8, y1=0.9)]
    before = len(model.state.victims)
    delta = model.apply_detections("L2-1", dets, "pho_1")
    assert len(model.state.victims) == before + 1
    v = model.state.victims[delta.changed_victims[0]]
    assert v.source == "camera" and v.count == 2 and v.status == VictimStatus.SUSPECTED
    assert v.probability == pytest.approx(0.5 + 0.4 * 0.8)
    assert v.cell == model.state.responders["L2-1"].cell
    assert delta.detections == dets


def test_detections_empty_is_event_only(wm):
    before = dict(wm.state.victims)
    delta = wm.apply_detections("E1-1", [], "pho_0")
    assert wm.state.victims == before
    assert delta.new_events and delta.new_events[0].kind == "photo"
    assert not delta.changed_victims


# ---------------------------------------------------------------------------
# Spatial
# ---------------------------------------------------------------------------


def test_resolve_zone_floor_aware(wm):
    assert wm.resolve_zone("stair B", 5) == Cell(floor=5, x=1, y=6)
    assert wm.resolve_zone("stairwell A", None).floor == 1
    assert wm.resolve_zone("302", 3) == Cell(floor=3, x=19, y=2)
    assert wm.resolve_zone("CP", None).floor == 0
    assert wm.resolve_zone("nowhere", 3) is None
    assert wm.resolve_zone(None, 3) is None


def test_distance_and_stairs(scenario):
    b = scenario.building
    a, c = Cell(floor=3, x=19, y=2), Cell(floor=3, x=17, y=6)
    assert cell_distance(b, a, c) == 4
    up = Cell(floor=4, x=19, y=2)
    assert cell_distance(b, a, up) == cell_distance(b, a, Cell(floor=3, x=22, y=6)) * 2 + 6
    assert nearest_stairwell(b, a).name == "stairwell A"
    assert nearest_stairwell(b, Cell(floor=3, x=1, y=11)).name == "stairwell B"
    assert cell_distance(b, Cell(floor=1, x=11, y=2), Cell(floor=0, x=29, y=15)) == 6
    z = find_zone(b, "unit 404", 4)
    assert victim_cell(z, 0) == z.center and victim_cell(z, 1).x == z.center.x + 1


def test_nearby_responders_across_floors(played):
    model, _ = played
    rs = model.state.responders
    rs["E1-1"].cell = Cell(floor=3, x=18, y=6)   # east corridor 3
    rs["E1-2"].cell = Cell(floor=4, x=22, y=6)   # stairwell A, floor 4
    rs["L2-1"].cell = Cell(floor=3, x=4, y=6)    # west corridor 3
    near = model.nearby_responders(Cell(floor=3, x=19, y=6), max_cells=12)
    ids = [r.id for r in near]
    assert ids[:2] == ["E1-1", "E1-2"]
    assert "L2-1" not in ids


def test_assignment_and_briefing_events(played):
    from fireline.models import Assignment, Briefing
    model, _ = played
    vid = next(iter(model.state.victims))
    d1 = model.set_assignment(vid, "R3-2")
    assert model.state.victims[vid].assigned_responder_id == "R3-2" and vid in d1.changed_victims
    d2 = model.record_briefing(Briefing(responder_id="L2-1", text="Stairwell B blocked at five, use A."))
    assert d2.new_events[0].kind == "briefing" and d2.version == model.state.version
    d3 = model.record_assignment(Assignment(responder_id="E1-2", target_kind="victim", target_id=vid, reason="nearest"))
    assert d3.new_events[0].kind == "assignment"


def test_snapshot_is_json_serialisable(played):
    model, _ = played
    snap = model.snapshot()
    text = json.dumps(snap)
    back = json.loads(text)
    assert back["version"] == 12
    assert set(back["responders"]) == {"E1-1", "E1-2", "L2-1", "R3-1", "R3-2"}
    assert back["queue"][0]["score"] >= back["queue"][-1]["score"]


# ---------------------------------------------------------------------------
# Named-stair hazards and crew-resolved maydays (integration fixes)
# ---------------------------------------------------------------------------


def test_named_stair_hazard_anchors_at_that_stair(scenario):
    """'B is blocked at five' reported from stairwell A must block B, not the reporter's stair."""
    model = WorldModel(scenario.initial_state())
    report = RadioReport(responder_id="R3-1", transcript="We're coming down stairwell A, not B. B is blocked at five.")
    result = TriageResult(report_id=report.id, responder_id="R3-1", tag=Tag.STATUS, priority=3,
                          summary="B blocked at 5", floor=5, zone="stairwell A", hazards=["stairwell B blocked"],
                          responder_status=ResponderStatus.OK)
    model.apply_triage(result, report)
    hz = list(model.state.hazards.values())
    assert len(hz) == 1 and hz[0].zone == "stairwell B" and hz[0].cell.floor == 5
    assert model.state.responders["R3-1"].zone == "stairwell A"
    assert is_stairwell_blocked(model.building, hz, "stairwell B", 5)
    assert not is_stairwell_blocked(model.building, hz, "stairwell A", 5)


def test_crew_okay_report_clears_crewmates_mayday(scenario):
    model = WorldModel(scenario.initial_state())
    inputs = _build_inputs(scenario)
    for t, r in inputs[:7]:
        model.apply_triage(t, r)
    assert model.state.responders["R3-2"].status == ResponderStatus.IN_DANGER
    # line 10: R3-1 "I'm okay ... we're coming down" -> R3-2 (same unit, same floor) is cleared too
    for t, r in inputs[7:10]:
        model.apply_triage(t, r)
    assert model.state.responders["R3-1"].status == ResponderStatus.OK
    assert model.state.responders["R3-2"].status == ResponderStatus.OK
    assert any("R3-2 status -> OK" in e.text for e in model.state.events)
