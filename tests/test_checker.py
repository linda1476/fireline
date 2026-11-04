import sys

sys.stdout.reconfigure(encoding="utf-8")

from server.agent import MemoryWorld, RelevanceAgent, demo_state
from server.checker import check, count_sentences, open_unescalated_maydays, related_zones
from server.models import Card


def st():
    return demo_state()


def brief(uid="kim", prio="P1", text="3층 인화물질 확인, 연소 확대 우려.", ev="evt_0004"):
    return {"unit_id": uid, "text": text, "priority": prio, "reason": "sector", "evidence_event_id": ev}


def test_related_zones_vertical_and_children():
    s = st()
    rel = related_zones("3F", s)
    assert "2F-E" in rel and "2F-E-STORE" in rel and "1F-W" not in rel
    assert {"2F-E-OFFICE", "2F-E-STORE"} <= related_zones("2F-E", s)
    assert "2F-E" in related_zones("2F-E-STORE", s)


def test_zone_containment():
    s = st()
    assert check("send_brief", brief("kim"), s, 35, {}) == (True, None)
    ok, err = check("send_brief", brief("park"), s, 35, {})
    assert not ok and "invariant 1" in err
    # P0 is not a sector bypass on a DANGER event (invariant 1: P0 only for MAYDAY-class evidence)
    ok, err = check("send_brief", brief("park", "P0"), s, 35, {})
    assert not ok and "P0 is only for crew safety" in err
    assert not check("send_brief", brief("ic", "P0"), s, 35, {})[0]


def test_assignment_counts():
    s = st()
    s.units["park"].assignment = "2F-E"
    assert check("send_brief", brief("park"), s, 35, {})[0]


def test_rate_limit():
    s = st()
    ok, err = check("send_brief", brief("kim"), s, 35, {"kim": 30})
    assert not ok and "invariant 2" in err
    assert check("send_brief", brief("kim"), s, 35, {"kim": 10})[0]
    # P0 on a MAYDAY event is exempt from sector + rate limit
    from server.agent import demo_state_mayday
    m = demo_state_mayday()
    assert check("send_brief", brief("park", "P0", "2층 동쪽 창고 대원 고립 상황. 퇴로 확인.", "evt_0009"), m, 95,
                 {"park": 90})[0]


def test_assignment_free_text_leading_zone_counts():
    s = st()
    s.units["park"].zone_id = "OUT-FRONT"
    s.units["park"].assignment = "2F-E 우선탐색"      # roster-style free text
    assert check("send_brief", brief("park"), s, 35, {})[0]


def test_related_zones_includes_siblings():
    s = st()
    assert "2F-E-OFFICE" in related_zones("2F-E-STORE", s)


def test_request_missing_field_only_to_distressed_on_mayday():
    from server.agent import demo_state_mayday
    m = demo_state_mayday()
    ok, err = check("request_missing_field", {"unit_id": "park", "field": "air", "evidence_event_id": "evt_0009"}, m, 95)
    assert not ok and "member in distress" in err
    assert check("request_missing_field", {"unit_id": "kim", "field": "needs", "evidence_event_id": "evt_0009"}, m, 95)[0]
    ok, err = check("request_missing_field", {"unit_id": "kim", "field": "air", "evidence_event_id": "evt_0004"}, m, 95)
    assert not ok and "MAYDAY" in err


def test_text_limits():
    s = st()
    assert not check("send_brief", brief(text="가" * 141), s, 35, {})[0]
    ok, err = check("send_brief", brief(text="하나. 둘. 셋."), s, 35, {})
    assert not ok and "sentences" in err
    assert count_sentences("3층 인화물질 확인. 퇴로 유지.") == 2


def test_evidence():
    s = st()
    ok, err = check("send_brief", brief(ev="evt_9999"), s, 35, {})
    assert not ok and "invariant 6" in err
    assert check("hold", {"unit_id": "park", "event_id": "evt_0004", "reason": "not your sector"}, s, 35, {})[0]
    assert not check("hold", {"unit_id": "park", "event_id": "nope", "reason": "x"}, s, 35, {})[0]
    assert check("ping_unit", {"unit_id": "park"}, s, 35, {})[0]
    assert check("get_unit_state", {"unit_id": "kim"}, s, 35, {})[0]
    assert not check("get_unit_state", {"unit_id": "ghost"}, s, 35, {})[0]


def test_propose_order():
    s = st()
    a = {"kind": "WITHDRAW", "units": ["kim"], "text": "철수", "rationale": "r", "evidence_event_id": "evt_0004"}
    assert check("propose_order", a, s, 35, {})[0]
    assert not check("propose_order", {**a, "kind": "FIRE_EVERYONE"}, s, 35, {})[0]


def test_invariant5_auto_escalate():
    s = st()
    s.cards.append(Card(id="card_0002", kind="MAYDAY", title="긴급탈출", event_ids=["evt_0004"], priority=0, created_t=34))
    assert len(open_unescalated_maydays(s)) == 1
    w = MemoryWorld(s)
    RelevanceAgent(w, spark=None)._ensure_mayday_escalated() if False else None
    a = RelevanceAgent(w, spark=None)
    a._wake_id, a._reason = "w", "test"
    a._ensure_mayday_escalated()
    assert s.cards[-1].escalation_level == 1 and not open_unescalated_maydays(s)


def test_agent_execute_reject_counts():
    s = st()
    w = MemoryWorld(s)
    a = RelevanceAgent(w, spark=None)
    a._wake_id, a._reason, a._decided = "w", "test", set()
    r = a.execute("send_brief", brief("park"))
    assert r["ok"] is False and s.counters.checker_rejections == 1
    r = a.execute("send_brief", brief("kim"))
    assert r["ok"] and s.briefs[-1].unit_id == "kim" and s.units["kim"].heard_count == 1
    r = a.execute("send_brief", brief("kim"))  # same unit + same evidence event: duplicate, no second push
    assert r["ok"] and r["deduped"] and s.units["kim"].heard_count == 1 and s.counters.checker_rejections == 1
    kinds = [t.kind for t in s.trace]
    assert kinds[:3] == ["tool_call", "checker", "tool_call"] and "delivery" in kinds
