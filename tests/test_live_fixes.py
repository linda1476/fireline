"""Fixes from the first LIVE run (run_20261104_193926): truncated round 1, R6/R7 safety nets, escalate scope,
latency after speech, the SOP 109 ask text, the running flag."""

import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from server import checker, rules  # noqa: E402
from server.agent import MemoryWorld, RelevanceAgent, demo_state, demo_state_mayday  # noqa: E402
from server.config import Settings  # noqa: E402
from server.models import (ASK_FIELD_KO, Card, Distress, Event, Latency, Transmission, Triage,  # noqa: E402
                           Victims, after_speech_ms)

TH = Settings()


class _Item:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ----------------------------------------------------------------------------- A: truncated round 1
class _TruncThenOk:
    def __init__(self):
        self.calls = []

    async def create(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1:  # max_output_tokens ran out: function_call items with empty arguments
            return _Item(id="resp_trunc", status="incomplete", output=[
                _Item(type="function_call", name="request_missing_field", call_id="e1", arguments=""),
                _Item(type="function_call", name="escalate_to_ic", call_id="e2", arguments="{}"),
            ])
        return _Item(id="resp_ok", status="completed", output=[
            _Item(type="function_call", name="request_missing_field", call_id="c1", arguments=json.dumps(
                {"unit_id": "kim", "field": "needs", "evidence_event_id": "evt_0009"})),
            _Item(type="function_call", name="propose_order", call_id="c2", arguments=json.dumps(
                {"kind": "RIT_DEPLOY", "units": ["rit"], "text": "신속동료구조팀 2층 동쪽 창고 투입 (동측 창문)",
                 "rationale": "mayday", "evidence_event_id": "evt_0009"})),
        ])


def test_truncated_round_is_discarded_and_retried_at_4000():
    s = demo_state_mayday()
    resp = _TruncThenOk()
    spark = _Item(async_client=_Item(responses=resp))
    res = asyncio.run(RelevanceAgent(MemoryWorld(s), spark, Settings()).wake("event:evt_0009", s.events[-1]))
    assert not res["fallback"] and res["calls"] == 2 and res["rejections"] == 0
    assert len(resp.calls) == 2 and all(k["max_output_tokens"] == 4000 for k in resp.calls)
    assert "previous_response_id" not in resp.calls[1]          # the truncated response is never chained
    assert resp.calls[1]["input"] == resp.calls[0]["input"]
    assert any(t.kind == "reasoning" and "truncated, retrying with 4000" in (t.payload.get("note") or "")
               for t in s.trace)
    # no empty-arg call reached the checker
    assert not any(t.kind == "checker" and not t.payload.get("ok") for t in s.trace)
    assert not any(t.kind == "tool_call" and t.payload.get("args") in ({}, None) for t in s.trace)
    assert [p.kind for p in s.proposals] == ["RIT_DEPLOY"]


class _AlwaysTrunc:
    def __init__(self):
        self.n = 0

    async def create(self, **kw):
        self.n += 1
        return _Item(id=f"r{self.n}", status="incomplete",
                     output=[_Item(type="function_call", name="send_brief", call_id="x", arguments="{")])


def test_truncated_twice_falls_through_to_gap_fill():
    s = demo_state_mayday()
    resp = _AlwaysTrunc()
    res = asyncio.run(RelevanceAgent(MemoryWorld(s), _Item(async_client=_Item(responses=resp)), Settings())
                      .wake("event:evt_0009", s.events[-1]))
    assert resp.n == 2 and res["calls"] == 0 and "park" in res["gap_filled"]


# ----------------------------------------------------------------------------- E: ask text
def test_request_missing_field_asks_named_field_in_korean():
    s = demo_state_mayday()
    w = MemoryWorld(s)
    agent = RelevanceAgent(w, None, Settings())
    r = agent.execute("request_missing_field", {"unit_id": "kim", "field": "needs", "evidence_event_id": "evt_0009"})
    assert r["ok"]
    asks = [p for t, p in w.sent if t == "ask"]
    assert asks == [{"unit_id": "kim", "field": "needs", "text": "필요한 것이 무엇입니까? 사다리, 공기용기 등"}]
    b = s.briefs[-1]
    assert b.text == ASK_FIELD_KO["needs"] and b.priority == "P0" and b.reason == "SOP 109 missing field: needs"
    # a second ask of the same field is a no-op
    again = agent.execute("request_missing_field", {"unit_id": "kim", "field": "needs", "evidence_event_id": "evt_0009"})
    assert again.get("deduped") and len([x for x in w.sent if x[0] == "ask"]) == 1


# ----------------------------------------------------------------------------- C: escalate scope
def test_escalate_only_crew_safety_cards():
    s = demo_state_mayday()
    ok, err = checker.check("escalate_to_ic", {"event_id": "evt_0004", "reason": "x"}, s, s.t)
    assert not ok and "not a crew-safety card" in err                          # DANGER card
    assert checker.check("escalate_to_ic", {"event_id": "evt_0009", "reason": "x"}, s, s.t)[0]  # MAYDAY
    s.cards[0].escalation_level = 1
    assert checker.check("escalate_to_ic", {"event_id": "evt_0004", "reason": "x"}, s, s.t)[0]  # already escalated
    ev = Event(id="evt_0010", transmission_id="tx_0010", t=95, channel="TAC", text="구조대상자 구출 중",
               triage=Triage(tag="VICTIM_FOUND", victims=Victims(count=1, state="EXTRACTING")), zone_id_snapped="1F-W")
    s.events.append(ev)
    s.cards.append(Card(id="card_0003", kind="VICTIM_FOUND", title="v", event_ids=[ev.id], created_t=95))
    ok, err = checker.check("escalate_to_ic", {"event_id": "evt_0010", "reason": "x"}, s, s.t)
    assert not ok and "not a crew-safety card" in err


# ----------------------------------------------------------------------------- B: R6 / R7
def test_r6_asks_missing_field_after_6s_once():
    s = demo_state_mayday()               # card_0002 created_t 92, missing needs
    assert not [a for a in rules.evaluate(s, 97.0, TH) if isinstance(a, rules.Ask)]
    asks = [a for a in rules.evaluate(s, 98.1, TH) if isinstance(a, rules.Ask)]
    assert [(a.unit_id, a.field) for a in asks] == [("kim", "needs")]
    w = MemoryWorld(s)
    from server.agent import ask_field
    ask_field(w, "kim", "needs", "evid", source="rule")
    assert not [a for a in rules.evaluate(s, 99.0, TH) if isinstance(a, rules.Ask)]


def test_r7_proposes_rit_deploy_and_radio_silence():
    s = demo_state_mayday()
    assert not [a for a in rules.evaluate(s, 106.0, TH) if isinstance(a, rules.ProposeOrder)]
    props = [a for a in rules.evaluate(s, 107.1, TH) if isinstance(a, rules.ProposeOrder)]
    by = {p.kind: p for p in props}
    assert set(by) == {"RIT_DEPLOY", "RADIO_SILENCE"}
    assert by["RIT_DEPLOY"].units == ["rit"] and by["RIT_DEPLOY"].text == "신속동료구조팀 2층 동쪽 창고 투입 (동측 창문)"
    assert by["RADIO_SILENCE"].text == "전 출동대 무선 침묵, 긴급탈출 관련 교신만"
    assert "kim" not in by["RADIO_SILENCE"].units and "ic" not in by["RADIO_SILENCE"].units


def test_r7_skips_when_agent_already_proposed():
    s = demo_state_mayday()
    MemoryWorld(s).add_proposal(kind="RIT_DEPLOY", units=["rit"], text="x", rationale="y",
                                evidence_event_id="evt_0009", card_id="card_0002", source="agent")
    kinds = [a.kind for a in rules.evaluate(s, 120.0, TH) if isinstance(a, rules.ProposeOrder)]
    assert kinds == ["RADIO_SILENCE"]


def _world_with_mayday(sent):
    from server.world import World

    w = World("hanbit", "ko", "LIVE", Settings(), sent.append, log_path=None)
    tx = Transmission(id=w.new_id("tx"), channel="TAC", unit_id="kim", t_keyup=78, t_end=87.6, text_final="x")
    w.upsert_transmission(tx)
    ev = Event(id=w.new_id("evt"), transmission_id=tx.id, t=78, channel="TAC", text="긴급탈출 2층 동쪽 창고",
               triage=Triage(tag="MAYDAY", distress=Distress(what="TRAPPED", where_raw="2층 동쪽 창고")),
               speaker_unit_snapped="kim", zone_id_snapped="2F-E-STORE",
               latency=Latency(total_ms=14800, after_speech_ms=after_speech_ms(14800, 78, 87.6)))
    w.set_t(92)
    card = w.apply_event(ev)[0]
    return w, card


def test_world_applies_r6_r7_with_rule_source():
    sent = []
    w, card = _world_with_mayday(sent)
    assert "needs" in card.missing_fields
    w.tick(98.5)
    asks = [m.payload for m in sent if m.type == "ask"]
    assert {(a["unit_id"], a["field"]) for a in asks} >= {("kim", "needs")}
    ask_b = [b for b in w.state.briefs if b.reason == "SOP 109 missing field: needs"]
    assert len(ask_b) == 1 and ask_b[0].source == "rule" and ask_b[0].text == ASK_FIELD_KO["needs"]
    assert any(t.kind == "tool_call" and t.payload.get("source") == "rule" and t.payload.get("rule_id") == "R6"
               for t in w.state.trace)
    w.tick(99.5)
    assert len([b for b in w.state.briefs if b.reason == "SOP 109 missing field: needs"]) == 1  # once
    w.tick(107.5)
    kinds = sorted(p.kind for p in w.state.proposals if p.source == "rule")
    assert kinds == ["RADIO_SILENCE", "RIT_DEPLOY"]
    w.tick(108.5)
    assert len(w.state.proposals) == 2  # duplicates are no-ops


# ----------------------------------------------------------------------------- D: latency after speech
def test_after_speech_latency_on_card():
    assert after_speech_ms(14800, 78.0, 87.6) == 5200
    assert after_speech_ms(3000, 10.0, 20.0) == 0
    assert after_speech_ms(1200, 10.0, None) == 1200
    sent = []
    _, card = _world_with_mayday(sent)
    assert card.latency_ms == 14800 and card.latency_after_speech_ms == 5200


# ----------------------------------------------------------------------------- F: running flag
def test_player_running_when_start_returns():
    from server.scenario import ScenarioPlayer

    async def run():
        p = ScenarioPlayer("hanbit", "ko", "radio", "LIVE", asr="file", max_t=0.0)
        await p.start()
        running = p.running
        await p.stop()
        return running, p.running

    assert asyncio.run(run()) == (True, False)


def test_replayer_running_when_start_returns(tmp_path):
    from server.cache import RunReplayer

    f = tmp_path / "run_x.jsonl"
    f.write_text(json.dumps({"t": 5.0, "type": "counters", "payload": {}}) + "\n", encoding="utf-8")

    async def run():
        r = RunReplayer(str(f), lambda m: None)
        await r.start()
        running = r.running
        await r.stop()
        return running

    assert asyncio.run(run()) is True


def test_demo_state_danger_unchanged():
    assert demo_state().cards[0].kind == "DANGER"
