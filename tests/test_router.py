import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")

from server.agent import MemoryWorld, RelevanceAgent, demo_state
from server.config import Settings
from server.router_fallback import route


def test_route_danger_3f():
    s = demo_state()
    w = MemoryWorld(s)
    briefs = route(s.events[0], w)
    by = {b.unit_id: b for b in briefs}
    assert by["kim"].decision == "push" and by["kim"].text.startswith("3층")
    assert by["park"].decision == "hold" and by["park"].reason == "not your sector (zone 1F-W)"
    assert "ic" not in by and "hanbit_center" not in by  # IC / speaker skipped
    assert any(t.kind == "fallback" for t in s.trace)


def test_route_mayday_all_p0_and_template():
    s = demo_state()
    ev = s.events[0]
    ev.triage.tag = "MAYDAY"
    ev.triage.crew_brief = None
    briefs = route(ev, MemoryWorld(s))
    assert all(b.decision == "push" and b.priority == "P0" for b in briefs)
    assert "긴급탈출" in briefs[0].text


def test_route_routine_noop():
    s = demo_state()
    s.events[0].triage.tag = "ROUTINE"
    assert route(s.events[0], MemoryWorld(s)) == []


class _BoomSpark:
    @property
    def async_client(self):
        raise RuntimeError("no network in tests")


class _SlowResponses:
    async def create(self, **kw):
        await asyncio.sleep(5)


class _SlowSpark:
    class async_client:  # noqa: N801
        responses = _SlowResponses()


def test_agent_error_falls_back():
    s = demo_state()
    res = asyncio.run(RelevanceAgent(MemoryWorld(s), _BoomSpark(), Settings()).wake("event:evt_0004", s.events[0]))
    assert res["fallback"] and {b.unit_id: b.decision for b in s.briefs} == {"kim": "push", "park": "hold", "rit": "hold"}
    assert s.counters.fallback_routes == 1


def test_agent_timeout_falls_back():
    s = demo_state()
    st = Settings(agent_timeout_s=0.2)
    res = asyncio.run(RelevanceAgent(MemoryWorld(s), _SlowSpark(), st).wake("event:evt_0004", s.events[0]))
    assert res["fallback_reason"] == "timeout"
    assert any(t.kind == "fallback" for t in s.trace)


def _ic_mayday_about_kim():
    """L11: IC broadcast (speaker ic) about kim; kim's MAYDAY card already holds the event."""
    from server.models import Card, Distress

    s = demo_state()
    ev = s.events[0]
    ev.triage.tag = "MAYDAY"
    ev.speaker_unit_snapped = "ic"
    ev.triage.distress = Distress(who="한빛구조대 김하늘", what="TRAPPED")
    ev.triage.crew_brief = "한빛구조대 김하늘 긴급탈출 발생, 2층 동쪽 창고."
    s.cards[0] = Card(id="card_0001", kind="MAYDAY", title="긴급탈출 · 김하늘", event_ids=[ev.id], priority=0,
                      unit_id="kim", zone_id="2F-E-STORE", created_t=34.0)
    return s, ev


def test_route_mayday_skips_distressed_unit():
    s, ev = _ic_mayday_about_kim()
    by = {b.unit_id: b for b in route(ev, MemoryWorld(s))}
    assert by["kim"].decision == "hold" and "distress" in by["kim"].reason
    assert by["park"].decision == "push" and by["park"].priority == "P0"


def test_route_mayday_distress_who_without_card():
    s, ev = _ic_mayday_about_kim()
    s.cards.clear()
    by = {b.unit_id: b for b in route(ev, MemoryWorld(s))}
    assert by["kim"].decision == "hold" and by["park"].decision == "push"


def test_checker_invariant7_rejects_own_distress_brief():
    s, ev = _ic_mayday_about_kim()
    w = MemoryWorld(s)
    agent = RelevanceAgent(w, _BoomSpark(), Settings())
    res = agent.execute("send_brief", {"unit_id": "kim", "text": "김하늘 긴급탈출 발생, 2층 동쪽 창고.", "priority": "P0",
                                       "reason": "mayday", "evidence_event_id": ev.id})
    assert not res["ok"] and "invariant 7" in res["error"] and s.counters.checker_rejections == 1
    ok = agent.execute("send_brief", {"unit_id": "park", "text": "김하늘 긴급탈출 발생, 2층 동쪽 창고.", "priority": "P0",
                                      "reason": "mayday", "evidence_event_id": ev.id})
    assert ok["ok"]
    ask = agent.execute("request_missing_field", {"unit_id": "kim", "field": "needs", "evidence_event_id": ev.id})
    assert ask["ok"]


def test_rit_deploy_approval_briefs_distressed_unit_hold_position():
    from server.models import Distress
    from server.world import World

    w = World("hanbit", "ko", "LIVE", Settings(), None, log_path=None)
    from server.models import Event, Transmission, Triage

    tx = Transmission(id=w.new_id("tx"), channel="TAC", unit_id="kim", t_keyup=78, text_final="x")
    w.upsert_transmission(tx)
    e = Event(id=w.new_id("evt"), transmission_id=tx.id, t=78, channel="TAC", text="x",
              triage=Triage(tag="MAYDAY", distress=Distress(what="TRAPPED")), speaker_unit_snapped="kim",
              zone_id_snapped="2F-E-STORE")
    w.set_t(92)
    card = w.apply_event(e)[0]
    p = w.add_proposal("RIT_DEPLOY", ["rit", "kim"], "RIT 2층 동쪽 창고 투입", "mayday", evidence_event_id=e.id,
                       card_id=card.id)
    w.decide_proposal(p.id, True)
    kim = [b for b in w.state.briefs if b.unit_id == "kim"]
    assert len(kim) == 1 and kim[0].text == "구조대 투입 중, 위치 유지." and kim[0].priority == "P0"
    assert any(b.unit_id == "rit" and b.text == "RIT 2층 동쪽 창고 투입" for b in w.state.briefs)


class _Item:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _LateResponses:
    """Answers after 0.4 s with send_brief(kim) (router already pushed it) + escalate_to_ic + propose_order."""

    def __init__(self):
        self.calls = []

    async def create(self, **kw):
        import json as _j

        self.calls.append(kw)
        await asyncio.sleep(0.4)
        out = [
            _Item(type="function_call", name="send_brief", call_id="c1", arguments=_j.dumps(
                {"unit_id": "kim", "text": "3층 인화물질 확인.", "priority": "P1", "reason": "sector",
                 "evidence_event_id": "evt_0004"})),
            _Item(type="function_call", name="propose_order", call_id="c2", arguments=_j.dumps(
                {"kind": "CONFIRM_STRATEGY", "units": ["kim"], "text": "방어전략 전환 검토", "rationale": "flammables",
                 "evidence_event_id": "evt_0004"})),
        ]
        return _Item(id="resp_1", output=out, status="completed")


class _LateSpark:
    def __init__(self):
        self.async_client = _Item(responses=_LateResponses())


def test_late_agent_calls_applied_after_fallback_without_duplicates():
    s = demo_state()
    spark = _LateSpark()
    agent = RelevanceAgent(MemoryWorld(s), spark, Settings(agent_timeout_s=0.1))

    async def run():
        res = await agent.wake("event:evt_0004", s.events[0])
        assert res["fallback_reason"] == "timeout" and res["late"]
        n_router = len(s.briefs)
        await agent.drain(5)
        return res, n_router

    res, n_router = asyncio.run(run())
    kim = [b for b in s.briefs if b.unit_id == "kim"]
    assert len(kim) == 1 and kim[0].source == "router"          # late duplicate push was dropped
    assert len(s.briefs) == n_router
    assert [p.kind for p in s.proposals] == ["CONFIRM_STRATEGY"]  # late, non-duplicate call applied
    assert any(t.payload.get("late") and t.payload.get("decision") == "duplicate" for t in s.trace)
    kw = spark.async_client.responses.calls[0]
    assert kw["max_output_tokens"] == 4000 and '"role":"IC"' not in kw["input"][1]["content"]


def test_route_rate_limits_recent_non_p0_push():
    s = demo_state()
    w = MemoryWorld(s)
    w.add_brief(unit_id="kim", decision="push", text="이전 정보.", priority="P1", reason="x",
                evidence_event_id="evt_0004", source="agent")
    s.t = 40.0
    by = {b.unit_id: b for b in route(s.events[0], w)}
    assert by["kim"].decision == "hold" and "rate limited" in by["kim"].reason


def test_route_long_crew_brief_falls_back_to_template():
    s = demo_state()
    s.events[0].triage.crew_brief = "하나. 둘. 셋."
    by = {b.unit_id: b for b in route(s.events[0], MemoryWorld(s))}
    assert by["kim"].text.startswith("위험 정보")


class _Item:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _TextOnlyResponses:
    async def create(self, **kw):
        return _Item(id="r1", status="completed",
                     output=[_Item(type="message", content=[_Item(text="I will not retry.")])])


class _TextOnlySpark:
    class async_client:  # noqa: N801
        responses = _TextOnlyResponses()


def test_agent_text_only_answer_gap_filled_and_traced():
    from server.agent import demo_state_mayday

    s = demo_state_mayday()
    res = asyncio.run(RelevanceAgent(MemoryWorld(s), _TextOnlySpark(), Settings()).wake("event:evt_0009", s.events[-1]))
    assert not res["fallback"] and set(res["gap_filled"]) >= {"park", "rit", "hanbit_center"}
    by = {b.unit_id: b for b in s.briefs}
    assert by["park"].priority == "P0" and by["park"].decision == "push"
    assert "kim" not in by  # speaker + member in distress: never briefed about own mayday
    assert any(t.kind == "reasoning" and t.payload.get("from") == "message" for t in s.trace)
    assert not any(t.kind == "fallback" for t in s.trace) and s.counters.fallback_routes == 0
    # one wake → one wake_reason across agent + router entries
    assert {t.wake_reason for t in s.trace if t.wake_id == res["wake_id"]} == {"event:evt_0009 MAYDAY"}


def test_gap_fill_skips_exterior_units_on_danger():
    s = demo_state()
    briefs = route(s.events[0], MemoryWorld(s), skip_units={"kim"}, gap_fill=True)
    assert {b.unit_id for b in briefs} == {"park"}  # rit / hanbit_center are OUT: not a gap
    assert not any(t.kind == "fallback" for t in s.trace)


def test_fallback_traced_even_when_all_units_decided():
    s = demo_state()
    assert route(s.events[0], MemoryWorld(s), skip_units={"kim", "park", "rit"}) == []
    assert any(t.kind == "fallback" for t in s.trace)
