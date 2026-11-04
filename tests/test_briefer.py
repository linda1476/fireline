"""Briefer tests (mock mode). Builds WorldStates from the scenario and hand-crafted deltas."""

from __future__ import annotations

import pytest

from fireline.briefer import Briefer, BrieferOut, RuleBriefer, SparkBriefer, compact_state, to_decision, words
from fireline.briefer.agent import AssignmentOut, BriefingOut, build_user_prompt
from fireline.briefer.mock import callsign, resolve_zone
from fireline.models import (
    Cell,
    Detection,
    Hazard,
    ResponderStatus,
    StateDelta,
    Tag,
    TouchInput,
    TriageResult,
    Urgency,
    VictimEstimate,
    VictimStatus,
    WorldEvent,
)

# ----------------------------------------------------------------- fixtures


def place(state, rid, floor, zone_name, status=ResponderStatus.OK, dx=0, dy=0):
    z = resolve_zone(state.building, zone_name, floor)
    assert z is not None, zone_name
    r = state.responders[rid]
    r.cell = Cell(floor=floor, x=z.center.x + dx, y=z.center.y + dy)
    r.zone = z.name
    r.status = status


@pytest.fixture
def deployed(state):
    """Mid-incident positions: E1 on 3, L2 on 4, R3 on 5 in stairwell B."""
    place(state, "E1-1", 3, "east corridor 3")
    place(state, "E1-2", 3, "unit 302")
    place(state, "L2-1", 4, "west corridor 4")
    place(state, "R3-1", 5, "stairwell B", status=ResponderStatus.IN_DANGER, dy=1)
    place(state, "R3-2", 5, "stairwell B", status=ResponderStatus.IN_DANGER)
    return state


def triage(**kw) -> TriageResult:
    base = dict(report_id="rpt_test", tag=Tag.STATUS, priority=2, summary="test")
    base.update(kw)
    return TriageResult(**base)


def mayday_delta(state) -> StateDelta:
    hz = Hazard(id="haz_b5", kind="ceiling collapse", cell=resolve_zone(state.building, "stairwell B", 5).center, zone="stairwell B", severity=5)
    state.hazards[hz.id] = hz
    tr = triage(
        report_id="rpt_mayday",
        responder_id="R3-2",
        tag=Tag.DANGER,
        priority=5,
        summary="Mayday: ceiling collapse stairwell B floor 5, Rescue 3-1 pinned",
        floor=5,
        zone="stairwell B",
        responder_status=ResponderStatus.IN_DANGER,
        hazards=["ceiling collapse"],
        needs=["RIT"],
        mayday=True,
    )
    return StateDelta(version=7, triage=tr, changed_responders=["R3-2", "R3-1"], changed_hazards=[hz.id])


def victim_delta(state) -> tuple[StateDelta, VictimEstimate]:
    z = resolve_zone(state.building, "unit 302", 3)
    v = VictimEstimate(id="vic_302", cell=z.center, zone="unit 302", probability=0.95, status=VictimStatus.CONFIRMED, condition="adult male, unconscious")
    state.victims[v.id] = v
    tr = triage(
        report_id="rpt_302",
        responder_id="E1-2",
        tag=Tag.VICTIM_FOUND,
        priority=4,
        summary="Confirmed victim in 302, adult male unconscious",
        floor=3,
        zone="unit 302",
        victim_count=1,
        victim_condition="adult male, unconscious",
        victim_certainty="confirmed",
    )
    return StateDelta(version=6, triage=tr, changed_victims=[v.id], changed_responders=["E1-2"]), v


def by_rid(decision):
    return {b.responder_id: b for b in decision.briefings}


# ------------------------------------------------------------------ (a) mayday


async def test_mayday_briefs_floor_neighbours_and_acks_caller(deployed):
    d = await Briefer().decide(mayday_delta(deployed), deployed, [])
    b = by_rid(d)
    assert d.model == "mock"
    assert len(d.briefings) == len({x.responder_id for x in d.briefings}), "max one briefing per responder"
    for x in d.briefings:
        assert words(x.text) <= 25, x.text
    # caller gets a short acknowledgement only
    assert "copies your mayday" in b["R3-2"].text.lower()
    assert words(b["R3-2"].text) <= 12
    # floor +-1 and crewmate get critical briefings with the exact location
    for rid in ("L2-1", "R3-1"):
        assert b[rid].urgency == Urgency.CRITICAL
        assert "stairwell b" in b[rid].text.lower()
        assert "floor 5" in b[rid].text
        assert b[rid].show_cell is not None and b[rid].show_cell.floor == 5
    assert b["L2-1"].text.startswith("Ladder 2:")
    assert "do not use stairwell b" in b["L2-1"].text.lower()
    # assignment: nearest crew not on the mayday unit -> the mayday responder
    asg = [a for a in d.assignments if a.target_kind == "responder"]
    assert asg and asg[0].target_id in ("R3-1", "R3-2")
    assert asg[0].responder_id not in ("R3-1", "R3-2")
    assert asg[0].responder_id == "L2-1"
    assert d.commander_note and "MAYDAY" in d.commander_note


# -------------------------------------------------------- (b) confirmed victim


async def test_confirmed_victim_briefs_nearest_other_not_reporter(deployed):
    delta, v = victim_delta(deployed)
    d = await Briefer().decide(delta, deployed, [])
    b = by_rid(d)
    assert "E1-2" not in b, "reporter must not be briefed about their own report"
    assert "E1-1" in b and "302" in b["E1-1"].text and b["E1-1"].urgency == Urgency.HIGH
    assert b["E1-1"].text.startswith("Engine 1-1:")
    assert b["E1-1"].show_cell == v.cell
    for x in d.briefings:
        assert words(x.text) <= 25
    asg = [a for a in d.assignments if a.target_kind == "victim"]
    assert asg and asg[0].target_id == "vic_302"
    assert asg[0].responder_id in ("E1-2", "E1-1")


async def test_suspected_victim_is_normal_urgency(deployed):
    z = resolve_zone(deployed.building, "unit 504", 5)
    v = VictimEstimate(id="vic_504", cell=z.center, zone="unit 504", probability=0.6, status=VictimStatus.SUSPECTED)
    deployed.victims[v.id] = v
    place(deployed, "R3-1", 5, "stairwell B")
    place(deployed, "R3-2", 5, "stairwell B")
    tr = triage(report_id="rpt_504", responder_id="R3-1", tag=Tag.VICTIM_FOUND, priority=3, floor=5, zone="unit 504", victim_certainty="suspected")
    d = RuleBriefer().decide(StateDelta(version=3, triage=tr, changed_victims=[v.id]), deployed)
    b = by_rid(d)
    assert "R3-1" not in b
    assert "R3-2" in b and "504" in b["R3-2"].text and b["R3-2"].urgency == Urgency.NORMAL
    assert not d.assignments, "suspected victims do not get assignments"


# ------------------------------------------------------------ (c) nothing relevant


async def test_routine_status_produces_no_briefings(deployed):
    tr = triage(report_id="rpt_status", responder_id="E1-1", tag=Tag.STATUS, priority=1, floor=3, zone="east corridor 3", summary="Engine 1 advancing on 3")
    d = await Briefer().decide(StateDelta(version=2, triage=tr, changed_responders=["E1-1"]), deployed, [])
    assert d.briefings == []
    assert d.assignments == []


async def test_im_ok_touch_produces_no_briefings(deployed):
    t = TouchInput(responder_id="L2-1", action="im_ok")
    d = await Briefer().decide(StateDelta(version=2, touch=t, changed_responders=["L2-1"]), deployed, [])
    assert d.briefings == []


# ------------------------------------------------------------ (d) repeats


async def test_recent_briefings_suppress_exact_repeats(deployed):
    delta = mayday_delta(deployed)
    first = await Briefer().decide(delta, deployed, [])
    assert first.briefings
    second = await Briefer().decide(delta, deployed, first.briefings)
    assert second.briefings == []


# --------------------------------------------------------- other rules


def test_blocked_stair_briefs_only_those_whose_egress_uses_it(deployed):
    place(deployed, "R3-1", 5, "stairwell A")
    place(deployed, "R3-2", 5, "stairwell A")
    tr = triage(report_id="rpt_blocked", responder_id="R3-1", tag=Tag.STATUS, floor=5, zone="stairwell A", hazards=["stairwell B blocked"])
    d = RuleBriefer().decide(StateDelta(version=9, triage=tr), deployed)
    b = by_rid(d)
    assert "L2-1" in b and "stairwell b" in b["L2-1"].text.lower() and "stairwell a" in b["L2-1"].text.lower()
    assert "E1-1" not in b, "Engine 1 uses stairwell A, not affected"
    assert "R3-1" not in b


def test_low_air_briefs_partner_only(deployed):
    tr = triage(report_id="rpt_air", responder_id="E1-1", tag=Tag.DANGER, priority=4, floor=3, zone="east corridor 3", hazards=["low air"], needs=["relief crew"])
    d = RuleBriefer().decide(StateDelta(version=10, triage=tr), deployed)
    b = by_rid(d)
    assert "E1-2" in b and "low air" in b["E1-2"].text.lower() and b["E1-2"].urgency == Urgency.HIGH
    assert "E1-1" not in b


def test_touch_mark_victim_and_camera_detection(deployed):
    cell = Cell(floor=4, x=18, y=11)
    t = TouchInput(responder_id="L2-1", action="mark_victim", cell=cell)
    v = VictimEstimate(id="vic_touch", cell=cell, zone="unit 404", probability=0.9, status=VictimStatus.CONFIRMED, source="touch")
    deployed.victims[v.id] = v
    d = RuleBriefer().decide(StateDelta(version=11, touch=t, changed_victims=[v.id]), deployed)
    assert "L2-1" not in by_rid(d) and d.briefings
    assert any(a.target_id == "vic_touch" for a in d.assignments)

    det = Detection(label="person", score=0.8, x0=0.1, y0=0.1, x1=0.5, y1=0.9)
    ev = WorldEvent(kind="photo", responder_id="E1-1", text="helmet cam: 1 person")
    v2 = VictimEstimate(id="vic_cam", cell=deployed.responders["E1-1"].cell, probability=0.82, status=VictimStatus.SUSPECTED, source="camera")
    deployed.victims[v2.id] = v2
    d2 = RuleBriefer().decide(StateDelta(version=12, detections=[det], changed_victims=[v2.id], new_events=[ev]), deployed)
    assert "E1-1" not in by_rid(d2) and "E1-2" in by_rid(d2)


def test_callsigns_and_word_guard(deployed):
    roster = list(deployed.responders.values())
    assert callsign(deployed.responders["L2-1"], roster) == "Ladder 2"
    assert callsign(deployed.responders["E1-2"], roster) == "Engine 1-2"
    assert words("Ladder 2: mayday on floor 5") == 6


# ------------------------------------------------- live-path post-processing


def test_to_decision_enforces_hard_rules(deployed):
    delta, v = victim_delta(deployed)
    long_text = "Engine 1-1: " + " ".join(["word"] * 40)
    out = BrieferOut(
        briefings=[
            BriefingOut(responder_id="GHOST-9", text="nobody home"),
            BriefingOut(responder_id="E1-2", text="Engine 1-2: you found a victim"),  # self-briefing
            BriefingOut(responder_id="E1-1", text=long_text, urgency="normal", show_floor=3, show_x=19, show_y=2),
            BriefingOut(responder_id="E1-1", text="Engine 1-1: confirmed victim unit 302", urgency="high"),
            BriefingOut(responder_id="L2-1", text="Ladder 2: FYI victim on 3", urgency="low", show_floor=3, show_x=None, show_y=2),
        ],
        assignments=[
            AssignmentOut(responder_id="E1-1", target_kind="victim", target_id="vic_302", reason="nearest"),
            AssignmentOut(responder_id="E1-1", target_kind="victim", target_id="vic_nope", reason="bad id"),
            AssignmentOut(responder_id="NOPE", target_kind="victim", target_id="vic_302", reason="bad responder"),
        ],
        commander_note="  note  ",
    )
    d = to_decision(out, deployed, delta, recent=[])
    b = by_rid(d)
    assert set(b) == {"E1-1", "L2-1"}
    assert b["E1-1"].urgency == Urgency.HIGH, "most urgent kept when deduping"
    assert b["L2-1"].show_cell is None, "partial show cell dropped"
    assert all(words(x.text) <= 25 for x in d.briefings)
    assert [a.target_id for a in d.assignments] == ["vic_302"]
    assert d.commander_note == "note"


def test_to_decision_injects_mayday_ack_when_model_forgets(deployed):
    delta = mayday_delta(deployed)
    out = BrieferOut(briefings=[BriefingOut(responder_id="L2-1", text="Ladder 2: mayday floor 5 stairwell B", urgency="critical")])
    d = to_decision(out, deployed, delta)
    b = by_rid(d)
    assert "R3-2" in b and "copies your mayday" in b["R3-2"].text.lower() and b["R3-2"].urgency == Urgency.CRITICAL


def test_to_decision_replaces_long_caller_briefing_with_ack(deployed):
    delta = mayday_delta(deployed)
    chatty = "Rescue 3-2: we hear you, ceiling collapse, stay calm, RIT is coming, keep talking, conserve air, we are on the way"
    out = BrieferOut(briefings=[BriefingOut(responder_id="R3-2", text=chatty, urgency="critical")])
    d = to_decision(out, deployed, delta)
    b = by_rid(d)
    assert list(b) == ["R3-2"] and b["R3-2"].text == "Rescue 3-2: Command copies your mayday, RIT is coming."


def test_blocked_stair_alias_in_hazard_text(deployed):
    """'stair B blocked' reported from stairwell A must flag stairwell B, not A."""
    place(deployed, "R3-1", 5, "stairwell A")
    place(deployed, "R3-2", 5, "stairwell A")
    tr = triage(report_id="rpt_alias", responder_id="R3-1", tag=Tag.STATUS, floor=5, zone="stairwell A", hazards=["stair B blocked"])
    d = RuleBriefer().decide(StateDelta(version=13, triage=tr), deployed)
    b = by_rid(d)
    assert "L2-1" in b and "do not use stairwell b" in b["L2-1"].text.lower()
    assert "E1-1" not in b and "R3-2" not in b


def test_to_decision_truncates_overlong_text(deployed):
    delta, _ = victim_delta(deployed)
    out = BrieferOut(briefings=[BriefingOut(responder_id="E1-1", text=" ".join(str(i) for i in range(60)))])
    d = to_decision(out, deployed, delta)
    assert words(d.briefings[0].text) == 25


def test_prompt_contains_state_and_delta(deployed):
    delta = mayday_delta(deployed)
    text = build_user_prompt(delta, deployed, [])
    for rid in deployed.responders:
        assert rid in text
    assert "haz_b5" in text and "mayday=YES" in text and "RECENT BRIEFINGS: none" in text
    assert "Ladder 2" in compact_state(deployed)


async def test_spark_briefer_raises_mockmode_in_mock(deployed, settings):
    from fireline.meta import MockMode

    with pytest.raises(MockMode):
        await SparkBriefer(settings).decide(mayday_delta(deployed), deployed, [])


async def test_briefer_falls_back_when_live_raises(deployed, settings, monkeypatch):
    """Any exception from the live path degrades to rules with model='mock-fallback'."""
    b = Briefer(settings)
    monkeypatch.setattr(b.settings, "force_mock", False)
    monkeypatch.setattr(b.settings, "api_key", "fake")

    async def boom(*a, **k):
        raise RuntimeError("model said nonsense")

    monkeypatch.setattr(b.spark, "decide", boom)
    d = await b.decide(mayday_delta(deployed), deployed, [])
    assert d.model == "mock-fallback" and d.briefings


# ----------------------------------------------------------------- live


@pytest.mark.live
async def test_live_mayday_briefing(deployed):
    """Prints what the real Muse Spark says for the mayday scenario."""
    from fireline.config import Settings

    settings = Settings()
    settings.force_mock = False  # conftest forces FIRELINE_MOCK=1; this test is opt-in via the live marker
    assert not settings.mock, "MODEL_API_KEY required"
    delta = mayday_delta(deployed)
    d = await SparkBriefer(settings).decide(delta, deployed, [])
    print("\nLIVE briefer decision:", d.model_dump_json(indent=2))
    assert d.briefings
    for x in d.briefings:
        assert words(x.text) <= 25
