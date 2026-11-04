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
