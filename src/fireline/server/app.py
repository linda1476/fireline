"""FastAPI server: every route in docs/CONTRACT.md plus the two static UIs.

    fireline-server                      # or: python -m fireline.server.app
    uvicorn fireline.server.app:app --host 0.0.0.0 --port 8000

Routes: GET / -> /command, GET /command, GET /responder/{id}, /static/*, /samples/{name},
GET /api/state, /api/scenario, /api/health, POST /api/report, /api/report/audio (multipart),
/api/touch, /api/photo, /api/ack, /api/assignment, /api/demo/run, /api/demo/reset,
/api/mic/start, /api/mic/stop, WS /ws.
"""

from __future__ import annotations

import logging
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from fireline.config import OUT_DIR, Settings, get_settings
from fireline.models import PhotoInput, RadioReport, TouchInput, WsMessage, new_id
from fireline.scenario import Scenario, load_scenario
from fireline.server.hub import Hub, message
from fireline.server.pipeline import REPLAY_MAX_AGE_S, Pipeline
from fireline.vision import SAMPLE_DIR, SAMPLE_NAMES

log = logging.getLogger("fireline.server")

STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOAD_DIR = OUT_DIR / "uploads"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ReportIn(BaseModel):
    responder_id: Optional[str] = None
    text: str = Field(..., min_length=1)
    source: Literal["mic", "file", "text", "scripted"] = "text"
    speaker_label: Optional[str] = None


class AckIn(BaseModel):
    report_id: str


class AssignmentIn(BaseModel):
    assignment_id: str
    accepted: bool


class DemoRunIn(BaseModel):
    mode: Literal["text", "audio"] = "text"
    speed: float = Field(1.0, gt=0, le=1000)


class MicStartIn(BaseModel):
    responder_id: Optional[str] = None


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(scenario: Scenario | None = None, settings: Settings | None = None,
               pipeline: Pipeline | None = None) -> FastAPI:
    """Build the app around one :class:`Pipeline` (tests pass their own for isolation)."""
    settings = settings or get_settings()
    scenario = scenario or load_scenario()
    pipe = pipeline or Pipeline(scenario, settings, Hub())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("Fireline server up: mock=%s spark=%s asr=%s sam=%s",
                 settings.mock, settings.spark_model, settings.asr_model, settings.sam_model)
        yield
        await pipe.close()

    app = FastAPI(title="Fireline", version="0.1.0", lifespan=lifespan)
    app.state.pipeline = pipe
    app.state.scenario = scenario
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # ---------------------------------------------------------------- pages
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/command")

    @app.get("/command", include_in_schema=False)
    async def command_page():
        return FileResponse(STATIC_DIR / "command.html", media_type="text/html")

    @app.get("/command.css", include_in_schema=False)
    async def command_css():
        return FileResponse(STATIC_DIR / "command.css", media_type="text/css")

    @app.get("/command.js", include_in_schema=False)
    async def command_js():
        return FileResponse(STATIC_DIR / "command.js", media_type="application/javascript")

    @app.get("/responder/{responder_id}", include_in_schema=False)
    async def responder_page(responder_id: str):
        return FileResponse(STATIC_DIR / "responder.html", media_type="text/html")

    @app.get("/samples/{name}", include_in_schema=False)
    async def sample_image(name: str):
        if name not in SAMPLE_NAMES:
            raise HTTPException(404, f"unknown sample {name!r}; one of {list(SAMPLE_NAMES)}")
        path = SAMPLE_DIR / name
        if not path.is_file():
            raise HTTPException(404, f"sample {name} not generated (python -m fireline.vision)")
        return FileResponse(path, media_type="image/jpeg")

    # ---------------------------------------------------------------- state
    @app.get("/api/state")
    async def api_state() -> dict:
        return pipe.snapshot()

    @app.get("/api/scenario")
    async def api_scenario() -> dict:
        return {
            "incident_name": scenario.incident_name,
            "responders": [r.model_dump(mode="json") for r in scenario.responders],
            "building": scenario.building.model_dump(mode="json"),
            "script": [{"t": ln.t, "responder_id": ln.responder_id, "text": ln.text} for ln in scenario.script],
        }

    @app.get("/api/health")
    async def api_health() -> dict:
        return pipe.health()

    @app.get("/api/recent")
    async def api_recent() -> dict:
        """Briefings / assignments are not in WorldState; UIs can replay them after a reload."""
        return {
            "briefings": [b.model_dump(mode="json") for b in pipe.recent],
            "assignments": [a.model_dump(mode="json") for a in pipe.assignments.values()],
        }

    # ---------------------------------------------------------------- inputs
    @app.post("/api/report")
    async def api_report(body: ReportIn) -> dict:
        report = RadioReport(responder_id=body.responder_id, transcript=body.text.strip(),
                             source=body.source, speaker_label=body.speaker_label)
        out = await pipe.handle_report(report)
        return out.model_dump(mode="json")

    @app.post("/api/report/audio")
    async def api_report_audio(audio: UploadFile = File(...), responder_id: Optional[str] = Form(None)) -> dict:
        # Keep the client's basename (per-upload folder) so demo WAVs still map to script lines in mock mode.
        folder = UPLOAD_DIR / new_id("upl")
        folder.mkdir(parents=True, exist_ok=True)
        name = Path(audio.filename or "upload.wav").name or "upload.wav"
        path = folder / name
        path.write_bytes(await audio.read())
        out = await pipe.handle_audio_file(path, responder_id or None)
        return out.model_dump(mode="json")

    @app.post("/api/touch")
    async def api_touch(touch: TouchInput) -> dict:
        out = await pipe.handle_touch(touch)
        return out.model_dump(mode="json")

    @app.post("/api/photo")
    async def api_photo(photo: PhotoInput) -> dict:
        out = await pipe.handle_photo(photo)
        return out.model_dump(mode="json")

    # ---------------------------------------------------------------- commander
    @app.post("/api/ack")
    async def api_ack(body: AckIn) -> dict:
        return {"ok": await pipe.ack(body.report_id), "report_id": body.report_id}

    @app.post("/api/assignment")
    async def api_assignment(body: AssignmentIn) -> dict:
        ok = await pipe.decide_assignment(body.assignment_id, body.accepted)
        if not ok:
            raise HTTPException(404, f"unknown assignment {body.assignment_id}")
        return {"ok": True, "assignment_id": body.assignment_id, "accepted": body.accepted}

    # ---------------------------------------------------------------- demo
    @app.post("/api/demo/run")
    async def api_demo_run(body: DemoRunIn | None = None) -> dict:
        body = body or DemoRunIn()
        pipe.start_demo(body.mode, body.speed)
        return {"started": True, "mode": body.mode, "speed": body.speed, "lines": len(scenario.script)}

    @app.post("/api/demo/reset")
    async def api_demo_reset() -> dict:
        await pipe.reset()
        return {"ok": True, "version": pipe.state.version}

    # ---------------------------------------------------------------- mic
    @app.post("/api/mic/start")
    async def api_mic_start(body: MicStartIn | None = None) -> dict:
        body = body or MicStartIn()
        try:
            return await pipe.start_mic(body.responder_id)
        except Exception as e:  # noqa: BLE001 - sounddevice / websocket failures -> 503, server keeps running
            log.exception("mic start failed")
            raise HTTPException(503, f"mic start failed: {type(e).__name__}: {e}") from e

    @app.post("/api/mic/stop")
    async def api_mic_stop() -> dict:
        return {"ok": True, "stopped": await pipe.stop_mic()}

    # ---------------------------------------------------------------- websocket
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        hub = pipe.hub
        await hub.connect(ws)
        try:
            await hub.send_state(ws)
            for b in pipe.recent_briefings(max_age_s=REPLAY_MAX_AGE_S):  # fresh ones only: pages speak them
                await hub.send(ws, message("briefing", b))
            for a in pipe.pending_assignments():
                await hub.send(ws, message("assignment", a))
            while True:
                raw = await ws.receive_json()
                await _handle_client_message(pipe, ws, raw)
        except WebSocketDisconnect:
            pass
        except Exception as e:  # noqa: BLE001
            log.debug("ws loop ended: %r", e)
        finally:
            hub.disconnect(ws)

    # Absolute asset paths used by responder.html (/static/responder.css, /static/responder.js).
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


async def _handle_client_message(pipe: Pipeline, ws: WebSocket, raw: Any) -> None:
    """Client -> server frames: only ``{"type": "touch", "payload": TouchInput}`` is meaningful."""
    try:
        msg = WsMessage.model_validate(raw)
    except ValidationError as e:
        await pipe.hub.send(ws, message("error", {"message": f"bad message: {e.errors()[0].get('msg', e)}"}))
        return
    if msg.type != "touch":
        return
    try:
        touch = TouchInput.model_validate(msg.payload)
    except ValidationError as e:
        await pipe.hub.send(ws, message("error", {"message": f"bad touch: {e.errors()[0].get('msg', e)}"}))
        return
    await pipe.handle_touch(touch)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = create_app()


def lan_urls(port: int) -> list[str]:
    """http://<ip>:<port> for every non-loopback IPv4 this host has (best effort)."""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except socket.gaierror:
        pass
    return [f"http://{ip}:{port}" for ip in ips]


def main() -> int:
    """``fireline-server``: uvicorn on FIRELINE_HOST:FIRELINE_PORT (default 0.0.0.0:8000)."""
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    mode = "MOCK (no MODEL_API_KEY)" if settings.mock else f"LIVE ({settings.spark_model})"
    print(f"Fireline server — {mode}")
    print(f"  command dashboard : http://localhost:{settings.port}/command")
    print(f"  responder display : http://localhost:{settings.port}/responder/L2-1")
    for url in lan_urls(settings.port):
        print(f"  LAN               : {url}/command   {url}/responder/<id>")
    uvicorn.run("fireline.server.app:app", host=settings.host, port=settings.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
