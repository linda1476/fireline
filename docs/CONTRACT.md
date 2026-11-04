# Fireline module contract

Everything below is binding for every module. Types live in `src/fireline/models.py`.
Settings in `src/fireline/config.py` (`get_settings().mock` → never touch the network).
Meta clients in `src/fireline/meta/` raise `MockMode` when mock; the calling module must
catch it and use its own deterministic stand-in.

## Package layout and ownership

```
src/fireline/
  models.py, config.py, scenario.py, meta/*      # shared (done)
  triage/      __init__.py, extract.py, mock.py, queue.py   # triage owner
  worldmodel/  __init__.py, state.py, spatial.py             # world-model owner
  briefer/     __init__.py, agent.py, mock.py                # briefer owner
  vision/      __init__.py, helmetcam.py                     # vision owner
  server/      __init__.py, app.py, hub.py, pipeline.py      # integration owner
  server/static/command.html (+ command.js/.css)             # command-UI owner
  server/static/responder.html (+ responder.js/.css)         # responder-UI owner
  demo.py                                                    # integration owner
scripts/  make_demo_audio.ps1, smoke_meta.py                 # integration / shared
tests/    conftest.py (shared), test_<module>.py             # each owner writes its own
data/     scenario.json (shared), audio/*.wav (generated), helmetcam/*.jpg (vision owner)
```

## Python module APIs

### triage
```python
from fireline.triage import Triager, PriorityQueue
t = Triager(settings=None)                      # picks Spark or mock automatically
result: TriageResult = await t.triage(report: RadioReport, building: Building, roster: list[Responder])
#   - fills tag/priority/summary/floor/zone/responder_status/victim_*/hazards/needs/mayday
#   - zone MUST be an exact Building zone name or None (resolve aliases; validate; else None)
#   - responder_id: keep report.responder_id if set, else infer from call sign in transcript
#   - model = settings.spark_model or "mock"; latency_ms measured
q = PriorityQueue(); q.push(QueueItem); q.items() -> list[QueueItem] sorted by score desc
#   score = priority*10 + (20 if mayday) + recency bonus; acknowledged items sink
```
Mock rules (keyword based) must pass `tests/test_triage.py` on every `scenario.script` and
`triage_eval_extra` line's `expect_*` keys.

### worldmodel
```python
from fireline.worldmodel import WorldModel
wm = WorldModel(scenario.initial_state())
delta: StateDelta = wm.apply_triage(result: TriageResult, report: RadioReport)
delta: StateDelta = wm.apply_touch(touch: TouchInput)
delta: StateDelta = wm.apply_detections(responder_id: str, detections: list[Detection], photo_id: str)
wm.state -> WorldState (version increments on every apply; queue kept sorted; events appended)
wm.snapshot() -> dict (json-safe, WorldState.model_dump(mode="json"))
wm.nearby_responders(cell: Cell, max_cells=8) -> list[Responder]
wm.resolve_zone(name: str|None, floor: int|None) -> Cell|None     # zone centre; floor-aware
wm.ack(report_id); wm.set_assignment(victim_id, responder_id)
```
Rules: responder moves to the report's zone when the report is a position update;
status from responder_status (mayday → InDanger); victims: suspected p≈0.6, confirmed
p≈0.95, merge with existing victim on same floor+zone (take max p, sum sources, keep
max count); extracted → status extracted, p stays; hazards from `hazards` list, placed
in the report zone; touch mark_victim → confirmed p=0.9 at tapped cell, source touch;
camera detections → suspected p=0.5+0.4*score at responder's current cell, count =
len(detections), source camera; `need_help` → NeedsHelp; `im_ok`/`clear_danger` → OK;
`victim_out` → nearest victim extracted. All of this is pure Python, no LLM.

### briefer
```python
from fireline.briefer import Briefer
b = Briefer(settings=None)
decision: BrieferDecision = await b.decide(delta: StateDelta, state: WorldState, recent: list[Briefing])
#   - decides, per responder, whether to interrupt them and with what (<= 25 words)
#   - never briefs the responder about their own report (except confirmation of mayday receipt)
#   - mayday → brief everyone on that floor ±1 and the nearest crew with the location
#   - victim confirmed/suspected → brief the nearest non-busy responder with the zone
#   - hazard (blocked stair, collapse) → brief anyone whose egress runs through it
#   - may propose Assignment(s) for the commander (nearest responder → victim/mayday)
#   - uses Spark structured output; mock = rule-based, same shape; latency measured
```

### vision
```python
from fireline.vision import HelmetCam
hc = HelmetCam(settings=None)
dets, latency_ms, raw = await hc.find_people(photo: PhotoInput)   # SAM 3.1 prompt "person"
#   mock: returns 1 detection for sample images whose filename contains "victim", else []
data/helmetcam/*.jpg: 3 synthetic sample frames (Pillow-drawn smoky room with/without a
figure) + a README on how to use a real photo.
```

## HTTP + WebSocket API (server owner implements; UI owners consume)

Base: `http://<host>:8000`. All JSON. Static UIs: `GET /command`, `GET /responder/{responder_id}`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/state` | – | `WorldState` JSON |
| GET | `/api/scenario` | – | `{responders:[...], building:{...}, script:[{t,responder_id,text}]}` |
| POST | `/api/report` | `{responder_id?: str, text: str, source?: "text"}` | `{report, triage, delta}` |
| POST | `/api/report/audio` | multipart `audio` (WAV 16k mono s16), `responder_id?` | `{report, triage, delta, transcript}` |
| POST | `/api/touch` | `TouchInput` JSON | `{delta}` |
| POST | `/api/photo` | `{responder_id, image_b64, mime}` | `{detections, delta, latency_ms}` |
| POST | `/api/ack` | `{report_id}` | `{ok}` |
| POST | `/api/assignment` | `{assignment_id, accepted: bool}` | `{ok}` |
| POST | `/api/demo/run` | `{mode: "text"\|"audio", speed?: float}` | `{started: true}` (runs scripted scenario in background, paced by `t`/speed) |
| POST | `/api/demo/reset` | – | `{ok}` (reload scenario initial state) |
| POST | `/api/mic/start` | `{responder_id?: str}` | `{session_id}` (PC mic → realtime ASR; final turns → triage) |
| POST | `/api/mic/stop` | – | `{ok}` |
| GET | `/api/health` | – | `{mock: bool, models: {...}, version}` |
| WS | `/ws` | – | server → client `WsMessage` stream; client → server `{"type":"touch","payload":TouchInput}` |

WS message types (`WsMessage.type`): on connect the server sends `state` (full snapshot).
Then `delta`, `transcript` `{text, final, speaker, responder_id}`, `briefing` (`Briefing`),
`assignment` (`Assignment`), `event` (`WorldEvent`). Every `delta` is followed by a fresh
`state` snapshot (simplest for UIs: re-render from `state`, animate from `delta`).

Pipeline per report (server/pipeline.py): RadioReport → Triager → WorldModel.apply_triage →
broadcast delta+state → Briefer.decide → broadcast briefing(s)/assignment(s) → events.

## UI contract

- **Command dashboard** (`/command`, desktop 1440×900): left = priority queue (cards:
  tag colour, priority, summary, responder, zone, age, ACK button); centre = map with
  floor tabs 1–5 + "Site" (outdoor); SVG grid drawn from `building.zones`
  (rooms/corridors/stairs coloured by kind), responders as labelled dots with status
  colour, victims as pulsing markers sized by probability, hazards as warning icons;
  right = live transcript feed, briefing log, assignment proposals (accept/decline),
  responder roster with air/status. Top bar: incident name, clock, DEMO (text/audio)
  buttons, MIC button, model badges (live/mock). Dark theme. No framework; vanilla JS.
- **Responder clip display** (`/responder/{id}`, render at 360×640): huge status
  banner; latest briefing text (auto-spoken with `speechSynthesis`, with a one-time
  "Enable audio" tap); mini-map of their current floor with their dot + nearby
  victims/hazards; four thumb-size buttons: MARK VICTIM (tap map cell, then confirm),
  NEED HELP, VICTIM OUT, I'M OK; HELMET CAM button (file input → base64 → POST
  /api/photo). High-contrast, glove-friendly (min 64px targets).

## Testing
`uv run pytest` must pass in mock mode. Each owner adds `tests/test_<module>.py`.
Live checks: `uv run python scripts/smoke_meta.py` (needs MODEL_API_KEY).
