"""FastAPI server + pipeline tests (mock mode, no network, no uvicorn).

Each test gets its own app/pipeline through ``with TestClient(create_app())`` so the
background demo task of one test cannot leak into the next. The ``with`` is load-bearing:
it keeps one event loop alive for the whole test, which the demo task needs.
"""

from __future__ import annotations

import base64
import io
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fireline.config import get_settings
from fireline.models import RadioReport
from fireline.scenario import load_scenario
from fireline.server.app import create_app
from fireline.server.pipeline import (
    MOCK_TRANSCRIPT,
    Pipeline,
    audio_path_for,
    script_line_for_wav,
)
from fireline.vision import SAMPLE_DIR, SAMPLE_NAMES

SCENARIO = load_scenario()
SCRIPT = SCENARIO.script
MAYDAY_LINE = next(ln for ln in SCRIPT if "MAYDAY" in ln.text)
VICTIM_LINE = next(ln for ln in SCRIPT if "found one victim" in ln.text)


@pytest.fixture
def client():
    with TestClient(create_app(scenario=SCENARIO, settings=get_settings())) as c:
        yield c


def _silent_wav(path: Path, seconds: float = 0.3) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return path


def _wait_for(client: TestClient, pred, timeout: float = 20.0) -> dict:
    """Poll GET /api/state until ``pred(state)`` holds (bounded)."""
    deadline = time.time() + timeout
    state = client.get("/api/state").json()
    while not pred(state):
        assert time.time() < deadline, f"timed out; version={state['version']} queue={len(state['queue'])}"
        time.sleep(0.1)
        state = client.get("/api/state").json()
    return state


# ---------------------------------------------------------------------------
# read-only routes
# ---------------------------------------------------------------------------


def test_health_reports_mock_and_models(client):
    h = client.get("/api/health").json()
    assert h["mock"] is True
    assert h["version"] == 0
    for key in ("spark", "asr", "sam", "briefer"):
        assert h["models"][key]["live"] is False
        assert h["models"][key]["model"] == "mock"


def test_scenario_route_shape(client):
    s = client.get("/api/scenario").json()
    assert {r["id"] for r in s["responders"]} == {"E1-1", "E1-2", "L2-1", "R3-1", "R3-2"}
    assert s["building"]["name"] == SCENARIO.building.name
    assert len(s["script"]) == len(SCRIPT)
    assert set(s["script"][0]) == {"t", "responder_id", "text"}


def test_state_route_is_initial_world_state(client):
    st = client.get("/api/state").json()
    assert st["version"] == 0
    assert set(st["responders"]) == {"E1-1", "E1-2", "L2-1", "R3-1", "R3-2"}
    assert st["victims"] == {} and st["hazards"] == {} and st["queue"] == []


@pytest.mark.parametrize("path, needle", [
    ("/command", "<title>Fireline Command</title>"),
    ("/responder/L2-1", "<title>Fireline Responder</title>"),
    ("/responder/anything", "<title>Fireline Responder</title>"),
])
def test_static_pages(client, path, needle):
    r = client.get(path)
    assert r.status_code == 200
    assert needle in r.text


@pytest.mark.parametrize("path, ctype", [
    ("/command.css", "text/css"),
    ("/command.js", "javascript"),
    ("/static/responder.css", "text/css"),
    ("/static/responder.js", "javascript"),
    ("/static/command.js", "javascript"),
])
def test_static_assets_resolve(client, path, ctype):
    r = client.get(path)
    assert r.status_code == 200, path
    assert ctype in r.headers["content-type"]
    assert len(r.content) > 500


def test_root_redirects_to_command(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/command"


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_sample_images(client, name):
    r = client.get(f"/samples/{name}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    assert client.get("/samples/nope.jpg").status_code == 404


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def test_post_report_triages_and_bumps_version(client):
    r = client.post("/api/report", json={"responder_id": "E1-2", "text": VICTIM_LINE.text, "source": "text"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"report", "triage", "delta"}
    assert body["triage"]["tag"] == "VictimFound"
    assert body["triage"]["zone"] == "unit 302"
    assert body["triage"]["victim_certainty"] == "confirmed"
    assert body["report"]["responder_id"] == "E1-2"
    assert body["delta"]["version"] >= 1
    state = client.get("/api/state").json()
    assert state["version"] >= body["delta"]["version"]
    assert len(state["queue"]) == 1
    assert state["queue"][0]["report"]["id"] == body["report"]["id"]
    assert state["responders"]["E1-2"]["zone"] == "unit 302"
    assert len(state["victims"]) == 1
    # briefer ran: the nearest other responder was briefed, the reporter proposed to the victim
    assert body["briefings"] and all(b["responder_id"] != "E1-2" for b in body["briefings"])
    assert any(a["target_kind"] == "victim" for a in body["assignments"])


def test_post_report_without_responder_infers_callsign(client):
    body = client.post("/api/report", json={"text": "Ladder 2 to Command, we're on four, west side, all good."}).json()
    assert body["triage"]["responder_id"] == "L2-1"


def test_post_report_accepts_callsign_as_responder_id(client):
    body = client.post("/api/report", json={"responder_id": "Engine 1-2", "text": "Engine 1-2, we're good."}).json()
    assert body["report"]["responder_id"] == "E1-2"


def test_post_report_rejects_empty_text(client):
    assert client.post("/api/report", json={"responder_id": "E1-1", "text": ""}).status_code == 422


def test_mayday_flow(client):
    body = client.post("/api/report", json={"responder_id": "R3-2", "text": MAYDAY_LINE.text}).json()
    assert body["triage"]["mayday"] is True and body["triage"]["priority"] == 5
    state = client.get("/api/state").json()
    assert state["responders"]["R3-2"]["status"] == "InDanger"
    assert state["queue"][0]["triage"]["mayday"] is True
    # the caller gets the mayday acknowledgement, someone else is proposed as RIT
    mine = [b for b in body["briefings"] if b["responder_id"] == "R3-2"]
    assert mine and "mayday" in mine[0]["text"].lower()
    assert any(a["target_kind"] == "responder" and a["target_id"] == "R3-2" for a in body["assignments"])


def test_touch_need_help_and_im_ok(client):
    r = client.post("/api/touch", json={"responder_id": "L2-1", "action": "need_help", "cell": None})
    assert r.status_code == 200, r.text
    assert "delta" in r.json()
    assert client.get("/api/state").json()["responders"]["L2-1"]["status"] == "NeedsHelp"
    client.post("/api/touch", json={"responder_id": "L2-1", "action": "im_ok", "cell": {"floor": 0, "x": 36, "y": 9}})
    assert client.get("/api/state").json()["responders"]["L2-1"]["status"] == "OK"


def test_touch_mark_victim_creates_confirmed_victim(client):
    r = client.post("/api/touch", json={"responder_id": "E1-1", "action": "mark_victim",
                                        "cell": {"floor": 3, "x": 18, "y": 2}})
    assert r.status_code == 200
    victims = client.get("/api/state").json()["victims"]
    assert len(victims) == 1
    v = next(iter(victims.values()))
    assert v["status"] == "confirmed" and v["source"] == "touch" and v["cell"]["floor"] == 3


def test_photo_with_sample_image_mock_detection(client):
    # put E1-2 indoors first so the detection has a cell to land on
    client.post("/api/report", json={"responder_id": "E1-2", "text": "Engine 1-2 in 302, searching."})
    b64 = base64.b64encode((SAMPLE_DIR / "smoky_room_victim.jpg").read_bytes()).decode("ascii")
    r = client.post("/api/photo", json={"responder_id": "E1-2", "image_b64": b64, "mime": "image/jpeg"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"detections", "delta", "latency_ms"}
    assert len(body["detections"]) == 1
    d = body["detections"][0]
    assert d["label"] == "person" and 0 <= d["x0"] < d["x1"] <= 1 and 0 <= d["y0"] < d["y1"] <= 1
    assert body["delta"]["changed_victims"]
    assert body["raw"] == "mock"


def test_photo_without_people(client):
    b64 = base64.b64encode((SAMPLE_DIR / "corridor_clear.jpg").read_bytes()).decode("ascii")
    body = client.post("/api/photo", json={"responder_id": "L2-1", "image_b64": b64, "mime": "image/jpeg"}).json()
    assert body["detections"] == []
    assert any(ev["kind"] == "photo" for ev in body["delta"]["new_events"])


def test_photo_garbage_does_not_crash(client):
    body = client.post("/api/photo", json={"responder_id": "L2-1", "image_b64": "not-base64!!", "mime": "image/jpeg"}).json()
    assert body["detections"] == []


def test_ack(client):
    body = client.post("/api/report", json={"responder_id": "E1-1", "text": SCRIPT[0].text}).json()
    rid = body["report"]["id"]
    r = client.post("/api/ack", json={"report_id": rid})
    assert r.status_code == 200 and r.json()["ok"] is True
    q = client.get("/api/state").json()["queue"]
    assert q[0]["acknowledged"] is True and q[0]["score"] < 0
    assert client.post("/api/ack", json={"report_id": rid}).json()["ok"] is False  # already acked
    assert client.post("/api/ack", json={"report_id": "rpt_missing"}).json()["ok"] is False


def test_assignment_accept_and_decline(client):
    body = client.post("/api/report", json={"responder_id": "E1-2", "text": VICTIM_LINE.text}).json()
    asg = body["assignments"][0]
    r = client.post("/api/assignment", json={"assignment_id": asg["id"], "accepted": True})
    assert r.status_code == 200 and r.json()["ok"] is True
    state = client.get("/api/state").json()
    victim = state["victims"][asg["target_id"]]
    assert victim["assigned_responder_id"] == asg["responder_id"]
    assert any(ev["kind"] == "assignment" and "accepted" in ev["text"] for ev in state["events"])
    # the responder was briefed about the accepted assignment
    assert any(ev["kind"] == "briefing" and "assigns you" in ev["text"] for ev in state["events"])
    assert client.post("/api/assignment", json={"assignment_id": "asg_missing", "accepted": False}).status_code == 404


def test_duplicate_assignment_not_reproposed(client):
    first = client.post("/api/report", json={"responder_id": "E1-2", "text": VICTIM_LINE.text}).json()
    second = client.post("/api/report", json={"responder_id": "E1-2", "text": VICTIM_LINE.text}).json()
    assert first["assignments"] and not second["assignments"]


def test_audio_report_mock_transcript(client, tmp_path):
    wav = _silent_wav(tmp_path / "clip.wav")
    with open(wav, "rb") as f:
        r = client.post("/api/report/audio", files={"audio": ("clip.wav", f, "audio/wav")}, data={"responder_id": "E1-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"] == MOCK_TRANSCRIPT
    assert body["report"]["source"] == "file" and body["report"]["responder_id"] == "E1-1"
    assert set(body) >= {"report", "triage", "delta", "transcript"}


def test_audio_report_named_like_demo_wav_uses_script_text(client, tmp_path):
    wav = _silent_wav(tmp_path / audio_path_for(7, "R3-2").name)
    with open(wav, "rb") as f:
        body = client.post("/api/report/audio", files={"audio": (wav.name, f, "audio/wav")}).json()
    assert body["transcript"] == SCRIPT[6].text
    assert body["triage"]["mayday"] is True


def test_script_line_for_wav_naming():
    assert audio_path_for(1, "E1-1").name == "01_E1-1.wav"
    assert script_line_for_wav("data/audio/07_R3-2.wav", SCENARIO) is SCRIPT[6]
    assert script_line_for_wav("07_E1-1.wav", SCENARIO) is None      # wrong responder for that line
    assert script_line_for_wav("99_E1-1.wav", SCENARIO) is None
    assert script_line_for_wav("clip.wav", SCENARIO) is None


# ---------------------------------------------------------------------------
# demo runner, reset, websocket
# ---------------------------------------------------------------------------


def test_demo_run_text_fast_then_reset(client):
    r = client.post("/api/demo/run", json={"mode": "text", "speed": 50})
    assert r.status_code == 200 and r.json()["started"] is True
    state = _wait_for(client, lambda s: len(s["queue"]) >= len(SCRIPT), timeout=30)
    assert state["version"] >= 12
    assert len(state["queue"]) == len(SCRIPT)
    # R3-2's mayday (line 7) is resolved by line 10 ("RIT got the beam off me ... we're coming down").
    assert state["responders"]["R3-2"]["status"] == "OK"
    assert any("R3-2 status -> InDanger" in e["text"] for e in state["events"])
    assert any(v["status"] == "extracted" for v in state["victims"].values())
    assert any("blocked" in h["kind"] or "collapse" in h["kind"] for h in state["hazards"].values())
    assert client.get("/api/health").json()["models"]["spark"]["calls"] == len(SCRIPT)
    r = client.post("/api/demo/reset", json={})
    assert r.status_code == 200 and r.json()["ok"] is True
    fresh = client.get("/api/state").json()
    assert fresh["version"] == 0 and fresh["queue"] == [] and fresh["victims"] == {}


def test_demo_audio_mode_falls_back_to_text_without_wavs(client):
    client.post("/api/demo/run", json={"mode": "audio", "speed": 200})
    state = _wait_for(client, lambda s: len(s["queue"]) >= len(SCRIPT), timeout=30)
    assert {q["report"]["source"] for q in state["queue"]} <= {"scripted", "file"}


def test_ws_sends_state_first_then_report_traffic(client):
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["payload"]["version"] == 0
        client.post("/api/report", json={"responder_id": "E1-1", "text": SCRIPT[0].text})
        types = [ws.receive_json()["type"] for _ in range(4)]
        assert types[0] == "transcript"
        assert types[1] == "delta"
        assert "state" in types[2:]
        health = client.get("/api/health").json()
        assert health["clients"] == 1


def test_ws_touch_message_from_client(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state"
        ws.send_json({"type": "touch", "payload": {"responder_id": "R3-1", "action": "need_help", "cell": None}})
        msg = ws.receive_json()
        assert msg["type"] == "delta" and msg["payload"]["touch"]["action"] == "need_help"
        state = _wait_for(client, lambda s: s["responders"]["R3-1"]["status"] == "NeedsHelp", timeout=5)
        assert state["responders"]["R3-1"]["status"] == "NeedsHelp"


def test_ws_replays_pending_assignments_on_connect(client):
    body = client.post("/api/report", json={"responder_id": "E1-2", "text": VICTIM_LINE.text}).json()
    with client.websocket_connect("/ws") as ws:
        msgs = [ws.receive_json() for _ in range(1 + len(body["briefings"]) + len(body["assignments"]))]
        assert msgs[0]["type"] == "state"
        assert {m["type"] for m in msgs[1:]} <= {"briefing", "assignment"}
        assert any(m["type"] == "assignment" and m["payload"]["id"] == body["assignments"][0]["id"] for m in msgs)


def test_mic_start_in_mock_mode(client):
    r = client.post("/api/mic/start", json={"responder_id": "E1-1"})
    assert r.status_code == 200 and r.json()["session_id"] == "mock"
    assert client.post("/api/mic/stop", json={}).json()["ok"] is True


# ---------------------------------------------------------------------------
# pipeline in-process (what demo.py uses)
# ---------------------------------------------------------------------------


async def test_pipeline_run_script_without_server():
    pipe = Pipeline(SCENARIO)
    seen: list[str] = []
    pipe.hub.subscribe(lambda m: seen.append(m.type))
    outcomes = await pipe.run_script(mode="text", speed=0)
    assert len(outcomes) == len(SCRIPT)
    assert seen[0] == "transcript" and "state" in seen
    tags = [o.triage.tag.value for o in outcomes]
    assert tags[6] == "Danger" and outcomes[6].triage.mayday
    assert pipe.state.version >= len(SCRIPT)
    assert pipe.health()["models"]["briefer"]["calls"] == len(SCRIPT)
    await pipe.close()


async def test_pipeline_report_outcome_is_json_safe():
    pipe = Pipeline(SCENARIO)
    out = await pipe.handle_report(RadioReport(responder_id="L2-1", transcript=SCRIPT[1].text))
    dumped = out.model_dump(mode="json")
    assert dumped["triage"]["tag"] == "Status"
    assert isinstance(dumped["delta"]["version"], int)
