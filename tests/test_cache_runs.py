import asyncio
import json

import pytest

from server import cache
from server.models import Triage


def _write(p, recs):
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


def test_list_promote_newest(tmp_path):
    a = tmp_path / "run_20261104_100000.jsonl"
    b = tmp_path / "run_20261104_110000.jsonl"
    _write(a, [{"t": 1.0, "type": "event", "payload": {}}, {"t": 12.5, "method": "POST", "path": "/x"}])
    _write(b, [{"t": 3.0, "type": "card", "payload": {}}])
    import os
    os.utime(a, (1, 1))
    assert cache.newest_run(tmp_path) == b
    runs = cache.list_runs(tmp_path)
    assert [r["file"] for r in runs] == [b.name, a.name] and runs[1]["t_max"] == 12.5 and runs[1]["size"] > 0
    dst = cache.promote(a.name, tmp_path)
    assert dst.name == "best.jsonl" and dst.read_text(encoding="utf-8") == a.read_text(encoding="utf-8")
    assert cache.list_runs(tmp_path)[0]["best"]
    for bad in ("../x.jsonl", "best.jsonl", "run_x.txt", "..\run_a.jsonl"):
        with pytest.raises(ValueError):
            cache.promote(bad, tmp_path)
    with pytest.raises(FileNotFoundError):
        cache.promote("run_missing.jsonl", tmp_path)


def test_triage_memo(tmp_path, monkeypatch):
    from server import triage as tri_mod

    monkeypatch.setenv("EARSHOT_MEMO", "1")
    monkeypatch.setattr(cache, "MEMO_PATH", tmp_path / "memo.jsonl")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_memo", None)
    calls = []

    class FakeSpark:
        async def acomplete_json(self, system, user, model, schema, schema_name=None):
            calls.append(user)
            return Triage(tag="DANGER", evidence_span="x"), 1234, {"prompt_tokens": 10}

    monkeypatch.setattr(tri_mod, "_spark", lambda: FakeSpark())
    t1, ms1, u1 = asyncio.run(tri_mod.triage("x 인화물질", "ko", "TAC"))
    t2, ms2, u2 = asyncio.run(tri_mod.triage("x 인화물질", "ko", "TAC"))
    assert len(calls) == 1 and t1.tag == t2.tag == "DANGER" and ms1 == ms2 == 1234
    assert "memo" not in u1 and u2["memo"] is True
    asyncio.run(tri_mod.triage("x 인화물질", "ko", "CMD"))
    assert len(calls) == 2


def test_recorder_stays_open_for_grace_period(tmp_path):
    from server.main import Runtime

    async def run():
        rt = Runtime()
        rt.recorder = cache.RunRecorder(tmp_path / "run_x.jsonl")
        rec = rt.recorder
        rt.retire_recorder(0.2)
        rec.record_rest(170.0, "POST", "/api/cards/card_0004/ack")   # late ack still recorded
        assert rt.recorder is rec and not rec._f.closed
        await asyncio.sleep(0.35)
        assert rec._f.closed and rt.recorder is None

    asyncio.run(run())
    assert "card_0004/ack" in (tmp_path / "run_x.jsonl").read_text(encoding="utf-8")


def test_restart_cancels_inflight_run_tasks_and_agent():
    from server.main import Runtime

    class _Agent:
        cancelled = False

        def cancel_all(self):
            self.cancelled = True

    async def go():
        rt = Runtime()
        agent = _Agent()
        rt.agent = agent
        slow = rt.spawn(asyncio.sleep(30))
        svc = rt.spawn_service(asyncio.sleep(30))
        await rt.cancel_run_tasks()
        assert slow.cancelled() and agent.cancelled and rt.agent is None
        assert not svc.done()  # clock loop / recorder retirement survive
        svc.cancel()

    asyncio.run(go())


def test_recorder_uses_player_clock():
    from server.main import Runtime
    from server.models import WsMessage

    class _Rec:
        def __init__(self):
            self.ts = []

        def record_ws(self, t, msg):
            self.ts.append(t)

    class _Player:
        start_wall = 1.0

        def t(self):
            return 78.0

    async def go():
        rt = Runtime()
        rt.recorder, rt.player = _Rec(), _Player()
        rt.world.set_t(77.0)  # 1 Hz tick lags
        await rt.broadcast(WsMessage(type="audio_cue", payload={"t": 78.0}))
        assert rt.recorder.ts == [78.0]

    asyncio.run(go())
