from server.config import Settings
from server.models import Distress, Event, Transmission, Triage, Victims
from server.world import World


def mkworld():
    msgs = []
    w = World("hanbit", "ko", "LIVE", Settings(), msgs.append, log_path=None)
    return w, msgs


def ev(w: World, unit, t, tag="ROUTINE", zone=None, channel="TAC", text="x", **tri):
    tx = Transmission(id=w.new_id("tx"), channel=channel, unit_id=unit, t_keyup=t, text_final=text)
    w.upsert_transmission(tx)
    e = Event(id=w.new_id("evt"), transmission_id=tx.id, t=t, channel=channel, text=text,
              triage=Triage(tag=tag, **tri), speaker_unit_snapped=unit, zone_id_snapped=zone)
    w.set_t(t)
    return w.apply_event(e)


def test_loads_roster_and_zones():
    w, _ = mkworld()
    assert set(w.state.units) == {"ic", "dispatch", "hanbit_center", "kim", "park", "rit"}
    assert "2F-E-STORE" in w.state.zones and w.state.thresholds["R2_silent_s"] == 60


def test_entering_status_and_strategy():
    w, msgs = mkworld()
    ev(w, "ic", 0, strategy_declared="OFFENSIVE", channel="CMD")
    ev(w, "kim", 12, status_change="ENTERING", zone="2F-E")
    k = w.state.units["kim"]
    assert k.status == "IN" and k.interior and k.zone_id == "2F-E" and k.last_heard_t == 12
    assert w.state.strategy == "OFFENSIVE"
    types = {m.type for m in msgs}
    assert {"transmission", "event", "unit", "strategy", "counters"} <= types


def test_mayday_sop_fields_merge_and_dedupe():
    w, _ = mkworld()
    c1 = ev(w, "kim", 78, "MAYDAY", "2F-E-STORE",
            distress=Distress(what="TRAPPED", where_raw="2층 동쪽 창고 쪽", air="공기 얼마 안 남았다"))[0]
    assert c1.kind == "MAYDAY" and c1.priority == 0
    assert c1.fields["what"] == "대원고립" and c1.fields["who"].startswith("한빛구조대")
    assert c1.missing_fields == ["needs"]
    # HELP_NEEDED from same unit merges into the MAYDAY, fills needs
    c2 = ev(w, "kim", 92, "HELP_NEEDED", "OUT-EAST", distress=Distress(needs="사다리랑 공기용기"))[0]
    assert c2.id == c1.id and c2.fields["needs"] == "사다리랑 공기용기" and c2.missing_fields == []
    # IC broadcast about kim (18 s after the last merge) dedupes into the same card
    c3 = ev(w, "ic", 110, "MAYDAY", "2F-E-STORE", channel="CMD", text="긴급탈출 발생, 한빛구조대 김하늘, 2층 동쪽 창고",
            distress=Distress(who="한빛구조대 김하늘"))[0]
    assert c3.id == c1.id and len(c3.event_ids) == 3 and c3.created_t == 78
    assert len([c for c in w.state.cards if c.kind == "MAYDAY"]) == 1


def test_dedupe_window_expires():
    w, _ = mkworld()
    a = ev(w, "hanbit_center", 34, "DANGER", "3F", hazard_terms=["인화물질"])[0]
    b = ev(w, "hanbit_center", 50, "DANGER", "3F", hazard_terms=["인화물질"])[0]
    c = ev(w, "hanbit_center", 90, "DANGER", "3F", hazard_terms=["인화물질"])[0]
    assert a.id == b.id and c.id != a.id
    assert a.fields == {"where": "3층", "terms": "인화물질"}
    assert w.state.zones["3F"].hazards


def test_max_open_cards_queue_and_promote():
    w, _ = mkworld()
    zones = ["1F-W", "1F-E", "2F-W", "2F-E", "3F", "ROOF", "OUT-FRONT"]
    for i, z in enumerate(zones):
        ev(w, "hanbit_center", 10 + i * 40, "DANGER", z, hazard_terms=[f"h{i}"])
    assert w.state.counters.cards_open == 5 and w.state.counters.cards_queued == 2
    # MAYDAY bypasses the cap
    ev(w, "kim", 400, "MAYDAY", "2F-E-STORE", distress=Distress(what="TRAPPED"))
    assert w.state.counters.cards_open == 6
    first = w.state.cards[0].id
    w.ack_card(first)
    assert w.state.counters.cards_queued == 2  # still 5 non-acked + mayday ≥ 5
    w.ack_card(w.state.cards[1].id)
    assert w.state.counters.cards_queued == 1 and w.state.counters.cards_open == 5


def test_victim_found_fields():
    w, _ = mkworld()
    c = ev(w, "kim", 56, "VICTIM_FOUND", "2F-E-OFFICE", channel="PTT",
           victims=Victims(count=1, state="EXTRACTING", where_raw="2층 계단 우측 사무실"))[0]
    assert c.fields == {"count": "1", "where": "2층 계단 우측 사무실", "state": "EXTRACTING"}
    assert w.state.zones["2F-E-OFFICE"].victim_reports[0].count == 1


def test_r3_proposal_on_danger_when_offensive():
    w, msgs = mkworld()
    ev(w, "ic", 0, strategy_declared="OFFENSIVE", channel="CMD")
    ev(w, "hanbit_center", 34, "DANGER", "3F", hazard_terms=["인화물질"])
    assert [p.kind for p in w.state.proposals] == ["CONFIRM_STRATEGY"]
    p = w.state.proposals[0]
    assert p.card_id == w.state.cards[0].id and p.source == "rule"


def test_counters_heard_n_of_m_and_brief():
    w, _ = mkworld()
    ev(w, "ic", 0, channel="CMD")
    ev(w, "kim", 12, status_change="ENTERING", zone="2F-E")
    ev(w, "park", 22, status_change="ENTERING", zone="1F-W")
    park = w.state.units["park"]
    assert park.total_count == 2 and park.heard_count == 0
    w.add_brief("park", "1층 서측 진입 확인", priority="P1", reason="test")
    assert park.heard_count == 1
    w.add_brief("kim", "hold", decision="hold", reason="irrelevant")
    # held = Σ(total − heard) over CREW: kim 2-0, park 2-1
    assert w.state.counters.held == 3 and w.state.counters.pushed == 1


def test_r2_card_then_resolve_on_transmit():
    w, msgs = mkworld()
    ev(w, "park", 22, status_change="ENTERING", zone="1F-W")
    ev(w, "park", 68, status_change="OK", zone="1F-W")
    for t in range(69, 155):
        w.tick(float(t))
    pings = [m.payload["t"] for m in msgs if m.type == "ping"]
    assert pings == [128, 136, 144]
    rc = [c for c in w.state.cards if c.kind == "RULE"]
    assert len(rc) == 1 and rc[0].created_t == 144 and rc[0].priority == 0 and rc[0].rule_id == "R2"
    # R1 escalates the R2 card too
    assert rc[0].escalation_level >= 1
    ev(w, "park", 155, status_change="OK", zone="1F-W")
    assert rc[0].state == "resolved" and rc[0].note.startswith("found OK")
    assert w.state.units["park"].unanswered_pings == 0


def test_crew_ack_resets():
    w, _ = mkworld()
    ev(w, "park", 22, status_change="ENTERING", zone="1F-W")
    for t in range(23, 100):
        w.tick(float(t))
    assert w.state.units["park"].unanswered_pings == 3
    w.crew_ack("park")
    u = w.state.units["park"]
    assert u.unanswered_pings == 0 and u.last_heard_t == 99


def test_proposal_approve_effects():
    w, _ = mkworld()
    c = ev(w, "kim", 78, "MAYDAY", "2F-E-STORE", distress=Distress(what="TRAPPED"))[0]
    p = w.add_proposal("RIT_DEPLOY", ["rit"], "신속동료구조팀 동측 창문 투입", "MAYDAY", card_id=c.id,
                       evidence_event_id=c.event_ids[0])
    w.decide_proposal(p.id, True)
    assert w.state.units["rit"].zone_id == "2F-E-STORE"
    assert any(b.unit_id == "rit" and b.priority == "P0" for b in w.state.briefs)
    p2 = w.add_proposal("RADIO_SILENCE", ["kim"], "무선 침묵", "MAYDAY")
    w.edit_proposal(p2.id, "전 출동대 무선 침묵")
    assert p2.state == "edited"
    w.decide_proposal(p2.id, False)
    assert p2.state == "rejected" and not w.flags["radio_silence"]


def test_snapshot_for_agent():
    w, _ = mkworld()
    ev(w, "kim", 78, "MAYDAY", "2F-E-STORE", distress=Distress(what="TRAPPED"))
    snap = w.snapshot_for_agent()
    assert snap["open_cards"][0]["kind"] == "MAYDAY" and len(snap["units"]) == 6
