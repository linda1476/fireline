# Earshot

**Earshot listens to every fireground radio channel so no mayday goes unheard.**
Meta's Muse models turn crew radio into a short, must-acknowledge queue for the incident commander, plus a
two-sentence earpiece brief that goes only to the firefighters it affects.

> *The agent decides who hears what. The commander decides who does what.*

Built solo in one night for the **Meta Global AI Developer Hackathon 2026** ("Build for Your World").
Everything on screen is driven by live calls to the Meta Model API; the one non-Meta component (browser TTS for the
earpiece) is labelled on screen.

## Why

- **Bucheon, 16 Oct 2026.** A crew reported flammables at 08:48; an offensive strategy was declared at 08:52. A
  firefighter was isolated at 09:09 and found at 09:35; the RIT was ordered at 09:20
  (Kyunghyang 2026-10-23, Hankook Ilbo 2026-10-20).
- **35.6 % of maydays are missed on the first call** across more than 9,000 maydays (Project Mayday, Fire Engineering
  2021). The miss rate is 26 % when the IC works from a vehicle with a portable radio, under 1.8 % on a headset.
- **Bridgeport 2010 (NIOSH F2010-18):** the first contributing factor was "failure to effectively monitor and respond
  to Mayday transmissions"; the IC was monitoring two channels on two handhelds.
- **Mungyeong 2024** official finding: "현장 활동 정보 공유가 미흡" (information sharing on scene was insufficient).
- Firefighters do not want more glass: fewer than 10 % want AR, and they ask for a wireless earpiece (NIST SP 1286pt3).

Korea's AI for 119 today listens to citizens calling in. Earshot listens to the crew.

## What it does

| Pillar | On screen | Meta model |
|---|---|---|
| 1 · Voice triage for command | One ack queue across 지휘망 + 작전망, max 5 open cards (FEMA span of control), SOP 109 fields (누가/무엇을/어디에/필요한 것) with missing ones highlighted, verbatim evidence span, latency badge, 10 s ack-escalate loop | `muse-voice-transcribe-1.0` realtime ENDPOINTING per channel with SOP keyword biasing · `muse-spark-1.3` strict JSON-schema triage |
| 2 · Hands-free crew side | 390×844 clip display: 3 lines + "why you hear this", 4 hold-to-confirm buttons (긴급탈출 · 구조대상자 여기 · 검색완료 · 지원요청), TALK = PTT | `muse-voice-transcribe-1.0` PUSH_TO_TALK per hold · `muse-spark-1.3` Responses-API relevance agent (7 tools, invariant checker) decides push / hold / ask |
| 3 · World-model harness | Units · zones · event trace · 5 time-bounded rules (R1 ack, R2 three unanswered pings = SOP 109 §1.1, R3 danger-after-offensive, R4 unassigned victim, R5 low air) · indoor floor grid + outdoor site plan with the SOP 205 1.5 H collapse ring | state engine (`server/world.py`, `server/rules.py`) |

Distress is detected **semantically**: 긴급탈출 ×3 (SOP 109), 메이데이, 맨다운, Mayday — and codeword-free lines such as
"출구를 못 찾겠다".

## Architecture

```
radio WAV (own voice → AMR-NB radio degradation)           crew phone (TALK hold)
        │ 80 ms PCM at 1×, one socket per channel                 │ one PUSH_TO_TALK socket per hold
        ▼                                                          ▼
muse-voice-transcribe-1.0 (ENDPOINTING, keywords, languageBias) ──► partials → finals (turns merged per clip)
        ▼
gate → muse-spark-1.3 (Chat Completions, strict json_schema, reasoning_effort=minimal) → verify (evidence verbatim, roster/zone snap)
        ▼
Event → World (units, zones, strategy, cards ≤ 5, dedupe) ─► rules R1–R5 (1 Hz) ─► WS → /command, /crew/:unit, /demo
        ▼
muse-spark-1.3 Responses API agent (tools: get_unit_state · send_brief · hold · request_missing_field · escalate_to_ic · propose_order · ping_unit)
        └─ invariant checker (6 rules) rejects → agent retries ─► briefs (earpiece) · proposals (IC approves) · trace tab
```

- Backend: FastAPI + websockets (`server/`), Python 3.11+, `uv`.
- Frontend: Vite + React 19 + React Router (SPA) + Tailwind v4 + shadcn/ui (`web/`).
- Data: `data/scenario_hanbit.yaml` (13-line synthetic scenario "한빛 도장공장"), `data/eval_lines.yaml`, `roster.json`,
  `zones.json`, `keywords.json` (58 SOP/LUNAR terms from 재난현장 표준작전절차 SOP 101/107/109/202/204/205 + roster + zones).

## Run it

```bash
cp .env.example .env            # MODEL_API_KEY=...
uv sync
uv run python scripts/make_audio.py      # raw recordings (or TTS fallback) → data/audio/{clean,radio}
uv run uvicorn server.main:app --port 8000
cd web && npm install && npm run dev     # http://localhost:5173
```

Routes: `/` launcher (LIVE / REPLAY) · `/command` · `/crew/kim` · `/crew/park` · `/demo` (split for the video) · `/eval`.
CLI: `uv run python -m server.cli replay --audio radio` prints every tagged event with its latencies.
Eval: `uv run python -m eval.run_eval` → `eval/results.{json,md}`.

## Evaluation (measured tonight)

_Synthetic, own-voice/TTS + AMR-NB codec degradation, n = 36 (12 scenario + 10 Korean SOP-style + 4 codeword-masked + 10 English LUNAR lines). Labels were fixed before any prompt tuning; the triage few-shots use none of these lines._

<!-- EVAL_TABLE: filled from eval/results.md -->

| condition | MAYDAY recall | MAYDAY FP | 5-way acc | macro-F1 | critical-term hit | unit match (raw → snapped) | codeword-masked | evidence verbatim | Spark p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|
| clean · keywords on | | | | | | | | | |
| clean · keywords off | | | | | | | | | |
| radio · keywords on | | | | | | | | | |
| radio · keywords off | | | | | | | | | |

Live-run latencies (key-up → card), p50 / p95 over the recorded runs: _see `docs/INTEGRATION_REPORT.md`_.

No general WER claim is made for Muse; the numbers above are this project's own synthetic set.

## Limits (stated on screen too)

- Simulated hardware: the clip display and earpiece are a phone-sized web view; earpiece audio is **browser TTS
  (non-Meta)**, labelled.
- Synthetic audio: a scripted scenario in the builder's own voice (TTS where noted in `data/audio/provenance.json`),
  degraded with an AMR-NB 7.95 kb/s radio chain. No real fireground recordings are redistributed.
- Positions are **reported zones**, not tracking. Nothing medical: 구조대상자 means location and status as reported.
- Decision support only: the agent routes information; every order is a proposal the IC approves.
- Rule thresholds (10 s / 60 s / 8 s) are **demo timescale** and labelled as such.
- The Meta ASR returns no confidence scores; uncertainty is Spark's `asr_uncertain` self-report.

## Sources

- Project Mayday, 35.6 % / IC position: https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/
- NIOSH F2010-18 (Bridgeport): https://stacks.cdc.gov/view/cdc/163519
- NIST SP 1286pt3: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf
- FEMA span of control: https://emilms.fema.gov/_is0200c/groups/53.html
- Bucheon 2026 timeline: https://khan.co.kr/article/202610231144001 · https://www.hankookilbo.com/news/article/A2026101912160005075
- Mungyeong 2024 finding: https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810
- 재난현장 표준작전절차 (SOP 107 / 109 / 205): https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/재난현장표준작전절차.pdf
- Method: ATC runtime monitoring https://arxiv.org/abs/2608.25926 · roster biasing https://arxiv.org/html/2202.03725 ·
  codeword-masked distress https://arxiv.org/abs/2604.14163 · ASR hallucination on pauses https://arxiv.org/html/2402.08021v2
  · LLM triage over-escalation https://arxiv.org/abs/2408.07531 · CRITIC https://arxiv.org/abs/2305.11738
- Meta Model API docs: https://dev.meta.ai/docs/speech-to-text · /docs/structured-output · /docs/tool-calling · /docs/reasoning

Research notes and the judged product spec are in `research/`.

## Licence

MIT. Scenario text, recordings and eval labels are the author's own work (CC BY 4.0).
