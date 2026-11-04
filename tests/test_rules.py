from server import rules
from server.config import Settings
from server.models import Card, Event, State, Triage, Unit, Victims

TH = Settings()


def _state() -> State:
    st = State(scenario_id="t")
    st.units["park"] = Unit(id="park", callsign="누리", name="박준", status="OK", interior=True,
                            last_heard_t=68.0, zone_id="1F-W")
    return st


def _run_r2(st: State, t_from: int, t_to: int):
    """Fake 1 Hz clock; applies Ping / RuleCard like World does."""
    pings, cards = [], []
    for t in range(t_from, t_to + 1):
        for a in rules.evaluate(st, float(t), TH):
            if isinstance(a, rules.Ping):
                st.units[a.unit_id].unanswered_pings += 1
                pings.append(t)
            elif isinstance(a, rules.RuleCard):
                st.cards.append(Card(id=f"c{t}", kind="RULE", rule_id="R2", priority=0, title=a.title,
                                     unit_id=a.unit_id, created_t=t))
                cards.append(t)
    return pings, cards


def test_r2_ping_cadence_l07():
    st = _state()
    pings, cards = _run_r2(st, 0, 200)
    assert pings == [128, 136, 144]
    assert cards == [144]


def test_r2_reset_on_transmit():
    st = _state()
    _run_r2(st, 0, 150)
    # L13 at 155: World resolves the card and resets counters
    st.cards[0].state = "resolved"
    st.units["park"].last_heard_t = 155.0
    st.units["park"].unanswered_pings = 0
    pings, cards = _run_r2(st, 151, 230)
    assert pings == [215, 223] and cards == []


def test_r2_skips_exterior_and_open_mayday():
    st = _state()
    st.units["park"].interior = False
    assert _run_r2(st, 0, 200) == ([], [])
    st = _state()
    st.cards.append(Card(id="m", kind="MAYDAY", priority=0, title="x", unit_id="park", created_t=0))
    assert [a for a in rules.r2(st, 200.0, TH)] == []


def test_r1_levels():
    st = State(scenario_id="t")
    st.cards.append(Card(id="m", kind="MAYDAY", priority=0, title="x", created_t=78))
    assert rules.r1(st, 87.0, TH) == []
    a = rules.r1(st, 88.0, TH)
    assert a == [rules.Escalate("m", 1, "R1")]
    st.cards[0].escalation_level, st.cards[0].state = 1, "escalated"
    assert rules.r1(st, 97.0, TH) == []
    assert rules.r1(st, 98.0, TH) == [rules.Escalate("m", 2, "R1")]
    st.cards[0].state = "acked"
    assert rules.r1(st, 200.0, TH) == []


def test_r3_on_danger_offensive():
    st = State(scenario_id="t", strategy="OFFENSIVE")
    ev = Event(id="e1", transmission_id="tx", t=34, channel="TAC", text="x",
               triage=Triage(tag="DANGER", hazard_terms=["인화물질"]))
    st.cards.append(Card(id="c1", kind="DANGER", priority=1, title="d", event_ids=["e1"], created_t=34))
    acts = rules.r3_on_event(ev, st)
    assert len(acts) == 1 and acts[0].kind == "CONFIRM_STRATEGY" and acts[0].card_id == "c1"
    st.strategy = "DEFENSIVE"
    assert rules.r3_on_event(ev, st) == []


def test_r4_assign_after_30s_unless_extracting():
    st = State(scenario_id="t")
    st.units["rit"] = Unit(id="rit", callsign="RIT", role="RIT")
    st.events.append(Event(id="e1", transmission_id="tx", t=56, channel="PTT", text="x",
                           triage=Triage(tag="VICTIM_FOUND", victims=Victims(count=1, state="FOUND"))))
    st.cards.append(Card(id="v", kind="VICTIM_FOUND", priority=2, title="v", event_ids=["e1"], created_t=56))
    assert rules.r4(st, 85.0, TH) == []
    a = rules.r4(st, 86.0, TH)
    assert len(a) == 1 and a[0].kind == "ASSIGN" and a[0].units == ["rit"]
    st.events[0].triage.victims.state = "EXTRACTING"
    assert rules.r4(st, 90.0, TH) == []


def test_r5_help_needed_60s():
    st = State(scenario_id="t")
    st.cards.append(Card(id="h", kind="HELP_NEEDED", priority=3, title="h", unit_id="kim", created_t=10))
    assert rules.r5(st, 69.0, TH) == []
    assert rules.r5(st, 70.0, TH) == [rules.Escalate("h", 1, "R5")]
