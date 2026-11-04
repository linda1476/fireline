"""Triage module tests (mock mode). The ``live`` test needs FIRELINE_LIVE_TESTS=1 + MODEL_API_KEY."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from fireline.config import Settings
from fireline.models import QueueItem, RadioReport, Tag, TriageResult
from fireline.scenario import ScriptLine, load_scenario
from fireline.triage import (
    PriorityQueue,
    TriageExtraction,
    Triager,
    build_system_prompt,
    extraction_to_result,
    infer_responder_id,
    normalize_zone,
)

_SC = load_scenario()
_LINES: list[ScriptLine] = _SC.script + _SC.eval_extra


def _ids() -> list[str]:
    return [f"{'script' if i < len(_SC.script) else 'extra'}{i:02d}-{ln.responder_id}" for i, ln in enumerate(_LINES)]


def check_expectations(result: TriageResult, expect: dict[str, Any]) -> list[str]:
    """Return a list of human-readable failures for the expect_* keys (empty = all good)."""
    probs: list[str] = []
    if "expect_tags" in expect and result.tag.value not in expect["expect_tags"]:
        probs.append(f"tag {result.tag.value} not in {expect['expect_tags']}")
    if "expect_floor" in expect and result.floor != expect["expect_floor"]:
        probs.append(f"floor {result.floor} != {expect['expect_floor']}")
    if "expect_zone_any" in expect and result.zone not in expect["expect_zone_any"]:
        probs.append(f"zone {result.zone!r} not in {expect['expect_zone_any']}")
    if "expect_victim_certainty" in expect and result.victim_certainty != expect["expect_victim_certainty"]:
        probs.append(f"certainty {result.victim_certainty} != {expect['expect_victim_certainty']}")
    if "expect_victim_count" in expect and result.victim_count != expect["expect_victim_count"]:
        probs.append(f"victim_count {result.victim_count} != {expect['expect_victim_count']}")
    if "expect_mayday" in expect and result.mayday != expect["expect_mayday"]:
        probs.append(f"mayday {result.mayday} != {expect['expect_mayday']}")
    if "expect_priority_min" in expect and result.priority < expect["expect_priority_min"]:
        probs.append(f"priority {result.priority} < {expect['expect_priority_min']}")
    if expect.get("expect_hazard") and not result.hazards:
        probs.append("expected hazards")
    if expect.get("expect_needs") and not result.needs:
        probs.append("expected needs")
    return probs


# --------------------------------------------------------------------------- scenario


@pytest.mark.parametrize("line", _LINES, ids=_ids())
async def test_mock_matches_scenario_expectations(line: ScriptLine, scenario, settings):
    t = Triager(settings)
    report = RadioReport(responder_id=line.responder_id, transcript=line.text, source="scripted")
    result = await t.triage(report, scenario.building, scenario.responders)

    assert result.report_id == report.id
    assert result.model == "mock"
    assert result.responder_id == line.responder_id
    assert result.zone is None or result.zone in scenario.building.zone_names(), "zone must be exact or None"
    assert len(result.summary.split()) <= 15
    probs = check_expectations(result, line.expect)
    assert not probs, f"{line.text!r}: {probs}\n{result.model_dump()}"


@pytest.mark.parametrize("line", _LINES, ids=_ids())
def test_callsign_inferred_when_unattributed(line: ScriptLine, scenario, settings):
    report = RadioReport(responder_id=None, transcript=line.text)
    result = Triager(settings).triage_sync(report, scenario.building, scenario.responders)
    assert result.responder_id == line.responder_id


def test_mayday_line_shape(scenario, settings):
    line = next(ln for ln in _SC.script if "MAYDAY" in ln.text)
    result = Triager(settings).triage_sync(RadioReport(transcript=line.text), scenario.building, scenario.responders)
    assert result.mayday and result.tag == Tag.DANGER and result.priority == 5
    assert result.responder_status.value == "InDanger"
    assert result.zone == "stairwell B" and result.floor == 5
    assert "RIT" in result.needs
    assert result.summary.startswith("MAYDAY")


# --------------------------------------------------------------------------- call signs


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Engine 1-2 to Command, we're good.", "E1-2"),
        ("engine one two, we're good", "E1-2"),
        ("Engine 1 on three, heavy smoke.", "E1-1"),
        ("Command, engine one, we're in.", "E1-1"),
        ("Ladder 2, primary search on four.", "L2-1"),
        ("Rescue 3-2, fifth floor.", "R3-2"),
        ("Rescue three dash two here", "R3-2"),
        ("Rescue 3 on five via stairwell B.", "R3-1"),
        ("Rescue 3-1 to Command.", "R3-1"),
        ("Engine 1, low air alarm on 1-2.", "E1-1"),
        ("Command from Truck 9, nothing showing.", None),
        ("Engine 1-7 to Command.", None),
        ("heavy smoke on three", None),
    ],
)
def test_infer_responder_id(text, expected, scenario):
    assert infer_responder_id(text, scenario.responders) == expected


# --------------------------------------------------------------------------- normalizer


@pytest.mark.parametrize(
    "name,floor,expected",
    [
        ("unit 302", None, ("unit 302", 3)),
        ("apartment 301", None, ("unit 301", 3)),
        ("Apartment 301", 5, ("unit 301", 3)),          # room floor wins over a conflicting floor
        ("404", None, ("unit 404", 4)),
        ("three-oh-one", None, ("unit 301", 3)),
        ("fire apartment", None, ("unit 302", 3)),
        ("Stairwell b", 4, ("stairwell B", 4)),          # stairs keep the spoken floor
        ("stair A", 2, ("stairwell A", 2)),
        ("stairwell A", None, ("stairwell A", None)),   # generic stair name, floor unknown
        ("stairwell B landing", None, ("stairwell B", 5)),  # floor-specific alias
        ("third floor east hallway", None, ("east corridor 3", 3)),
        ("east corridor", 4, ("east corridor 4", 4)),
        ("4th floor west corridor", 2, ("west corridor 4", 4)),
        ("the gym", None, ("gym", 2)),
        ("Staging", 3, ("staging area", 0)),
        ("main lobby", 3, ("lobby", 1)),
        ("elevator lobby", None, ("elevator lobby 1", 1)),
        ("roof", 5, (None, 5)),
        ("null", 2, (None, 2)),
        (None, None, (None, None)),
    ],
)
def test_normalize_zone(name, floor, expected, scenario):
    assert normalize_zone(scenario.building, name, floor) == expected


# --------------------------------------------------------------------------- live post-processing (no network)


def test_extraction_schema_is_flat():
    schema = TriageExtraction.model_json_schema()
    assert "$defs" not in schema
    for name, prop in schema["properties"].items():
        types = {prop.get("type")} | {a.get("type") for a in prop.get("anyOf", [])}
        assert "object" not in types, name
        if "array" in types:
            assert prop["items"]["type"] == "string", name
        assert prop.get("description"), f"{name} needs a description"
    assert set(schema["required"]) >= {"tag", "priority", "summary"}


def test_extraction_coerces_sloppy_model_output():
    ex = TriageExtraction.model_validate(
        {
            "tag": "victim_found",
            "priority": 9,
            "summary": "a " * 30,
            "responder_callsign": None,
            "floor": "3rd",
            "zone": "Apartment 301",
            "responder_status": "in danger",
            "victim_count": "two",
            "victim_condition": "null",
            "victim_certainty": "CONFIRMED",
            "hazards": "heavy smoke, high heat",
            "needs": None,
            "mayday": "false",
            "confidence": 85,
        }
    )
    assert ex.tag == "VictimFound" and ex.priority == 5 and ex.floor == 3
    assert ex.responder_status == "InDanger" and ex.victim_count == 2
    assert ex.victim_condition is None and ex.victim_certainty == "confirmed"
    assert ex.hazards == ["heavy smoke", "high heat"] and ex.needs == []
    assert ex.mayday is False and ex.confidence == 0.85


def test_extraction_to_result_normalises(scenario):
    report = RadioReport(responder_id=None, transcript="Engine 1-2, victim in apartment 301, adult, unconscious.")
    ex = TriageExtraction(
        tag="VictimFound", priority=4, summary="word " * 20, responder_callsign="Engine 1-2",
        floor=5, zone="apartment 301", responder_status="OK", victim_count=0, victim_condition="adult, unconscious",
        victim_certainty="confirmed", hazards=[], needs=[], mayday=False, confidence=0.9,
    )
    r = extraction_to_result(ex, report, scenario.building, scenario.responders, model="muse-spark-1.3", latency_ms=321)
    assert r.zone == "unit 301" and r.floor == 3               # alias resolved, conflicting floor corrected
    assert r.responder_id == "E1-2"                            # call sign -> roster id
    assert r.victim_count == 1                                 # confirmed victim implies at least one
    assert len(r.summary.split()) == 15
    assert r.model == "muse-spark-1.3" and r.latency_ms == 321 and r.confidence == 0.9


def test_extraction_to_result_enforces_mayday_and_unknown_zone(scenario):
    report = RadioReport(responder_id="R3-2", transcript="Mayday mayday, Rescue 3-2, I'm stuck on the roof deck.")
    ex = TriageExtraction(tag="Status", priority=2, summary="stuck", zone="roof deck", floor=6, mayday=False, confidence=0.9)
    r = extraction_to_result(ex, report, scenario.building, scenario.responders, model="m", latency_ms=1)
    assert r.mayday and r.tag == Tag.DANGER and r.priority == 5 and r.responder_status.value == "InDanger"
    assert r.zone is None and r.floor == 6                    # unresolvable zone -> None, floor kept
    r2 = extraction_to_result(ex.model_copy(update={"floor": None, "zone": "stairwell A"}), RadioReport(
        responder_id="E1-1", transcript="Engine 1 on three in stairwell A."), scenario.building, scenario.responders,
        model="m", latency_ms=1)
    assert r2.zone == "stairwell A" and r2.floor == 3          # model floor null -> spoken floor backfilled
    assert r.confidence <= 0.5                                 # lowered because the zone did not resolve
    assert r.responder_id == "R3-2"                            # report attribution is kept


def test_system_prompt_mentions_building_and_roster(scenario):
    p = build_system_prompt(scenario.building, scenario.responders)
    for z in scenario.building.zones:
        assert z.name in p
    for r in scenario.responders:
        assert r.id in p and r.name in p
    assert "Engine 1-2" in p and "stairwell B landing" in p
    assert "404 -> floor 4" in p
    assert p.count("Radio:") >= 4  # few-shot examples
    for line in _LINES:  # examples are new, not the scenario script
        assert line.text not in p


# --------------------------------------------------------------------------- queue


def _item(priority: int, mayday: bool = False, age_min: float = 0.0, rid: str | None = None) -> QueueItem:
    rid = rid or f"rpt_{priority}_{mayday}_{age_min}"
    ts = (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat(timespec="milliseconds")
    report = RadioReport(id=rid, transcript="x", timestamp=ts)
    triage = TriageResult(report_id=rid, tag=Tag.STATUS, priority=priority, summary="s", mayday=mayday, timestamp=ts)
    return QueueItem(triage=triage, report=report)


def test_queue_orders_mayday_first_and_ack_sinks():
    q = PriorityQueue()
    low = q.push(_item(2, rid="low"))
    high = q.push(_item(5, rid="high"))
    mayday = q.push(_item(4, mayday=True, rid="mayday"))
    assert [it.report.id for it in q.items()] == ["mayday", "high", "low"]
    assert mayday.score == pytest.approx(4 * 10 + 25 + 10) and high.score == pytest.approx(60) and low.score == pytest.approx(30)

    assert q.ack("mayday") is True and q.ack("nope") is False
    ordered = q.items()
    assert [it.report.id for it in ordered] == ["high", "low", "mayday"]
    assert ordered[-1].acknowledged and ordered[-1].score < 0

    assert q.remove("low").report.id == "low" and q.remove("low") is None
    assert len(q) == 2 and "high" in q and "low" not in q


def test_queue_recency_and_stability():
    q = PriorityQueue()
    q.push(_item(3, age_min=0, rid="fresh"))
    q.push(_item(3, age_min=30, rid="old"))
    q.push(_item(3, age_min=0, rid="fresh2"))
    ids = [it.report.id for it in q.items()]
    assert ids == ["fresh", "fresh2", "old"]            # recency bonus, then insertion order on ties
    assert q.get("old").score == pytest.approx(30) and q.get("fresh").score == pytest.approx(40)
    q.push(_item(5, rid="fresh"))                        # re-push replaces by report id
    assert len(q) == 3 and q.items()[0].report.id == "fresh"


# --------------------------------------------------------------------------- live wiring without network


def _fake_live_settings() -> Settings:
    s = Settings()
    s.force_mock = False
    s.api_key = "test-key-not-used"
    s.spark_model = "muse-spark-test"
    return s


async def test_live_wiring_uses_spark_result(monkeypatch, scenario):
    from fireline.meta.spark import SparkClient

    captured: dict[str, Any] = {}

    async def fake_acomplete_json(self, system, user, schema, **kw):
        captured.update(system=system, user=user, schema=schema)
        return schema(tag="HelpNeeded", priority=3, summary="Ladder 2 needs water on four", responder_callsign="Ladder 2",
                      floor=None, zone="4th floor east", needs=["water supply"], confidence=0.77), 123

    monkeypatch.setattr(SparkClient, "acomplete_json", fake_acomplete_json)
    t = Triager(_fake_live_settings())
    assert t.live
    report = RadioReport(responder_id=None, transcript="Command, Ladder 2 needs water on four, the line is dry.")
    r = await t.triage(report, scenario.building, scenario.responders)
    assert captured["schema"] is TriageExtraction and "unit 404" in captured["system"] and report.transcript in captured["user"]
    assert r.model == "muse-spark-test" and r.latency_ms == 123 and r.confidence == 0.77
    assert r.tag == Tag.HELP_NEEDED and r.zone == "east corridor 4" and r.floor == 4 and r.responder_id == "L2-1"


async def test_live_wiring_falls_back_to_mock_on_api_error(monkeypatch, scenario):
    from fireline.meta import MetaAPIError
    from fireline.meta.spark import SparkClient

    async def boom(self, *a, **kw):
        raise MetaAPIError("structured output failed")

    monkeypatch.setattr(SparkClient, "acomplete_json", boom)
    t = Triager(_fake_live_settings())
    line = next(ln for ln in _SC.script if "MAYDAY" in ln.text)
    r = await t.triage(RadioReport(responder_id="R3-2", transcript=line.text), scenario.building, scenario.responders)
    assert r.model == "mock" and r.confidence <= 0.3
    assert r.mayday and r.tag == Tag.DANGER and r.zone == "stairwell B" and r.floor == 5
    assert not check_expectations(r, line.expect)


# --------------------------------------------------------------------------- live


@pytest.mark.live
async def test_live_spark_accuracy(scenario):
    """Runs every scenario line through the real model and prints an accuracy table."""
    settings = Settings()
    settings.force_mock = False
    assert settings.api_key, "MODEL_API_KEY missing"
    t = Triager(settings)
    rows: list[tuple[str, bool, list[str], TriageResult]] = []
    for line in _LINES:
        report = RadioReport(responder_id=line.responder_id, transcript=line.text, source="scripted")
        result = await t.triage(report, scenario.building, scenario.responders)
        probs = check_expectations(result, line.expect)
        rows.append((line.text, result.model != "mock", probs, result))

    print("\n{:<4} {:<5} {:<12} {:<3} {:<5} {:<18} {:<9} {:<6} {}".format("#", "live", "tag", "pri", "floor", "zone", "cert", "ms", "problems"))
    for i, (text, live, probs, r) in enumerate(rows):
        print("{:<4} {:<5} {:<12} {:<3} {:<5} {:<18} {:<9} {:<6} {}".format(
            i, "yes" if live else "MOCK", r.tag.value, r.priority, str(r.floor), str(r.zone), r.victim_certainty,
            r.latency_ms, "; ".join(probs) or "ok"))
        print("     ", text[:110])
    passed = sum(1 for _, _, probs, _ in rows if not probs)
    live_n = sum(1 for _, live, _, _ in rows if live)
    print(f"\naccuracy: {passed}/{len(rows)} lines satisfied all expectations; {live_n}/{len(rows)} answered live")
    assert live_n == len(rows), "some lines fell back to mock"
    assert passed / len(rows) >= 0.75


def test_live_marker_is_skipped_without_key():
    assert os.environ.get("FIRELINE_MOCK") == "1"
