# Earshot build contract

Everything every module and screen agrees on. Spec: `research/PRODUCT_SPEC.md`. Data model: `server/models.py`
(the wire format is `model_dump(mode="json")` of those classes; field names are final). Measured API facts:
`research/smoke_b1.md` (read it before touching asr/triage/agent).

## Layout

```
server/
  config.py          Settings (API key from .env, thresholds, paths), load_keywords()
  models.py          pydantic models + TRIAGE_SCHEMA (strict JSON schema for Spark)
  meta/spark.py      SparkClient: acomplete_json(system, user, Triage, TRIAGE_SCHEMA) → (Triage, ms, usage); .async_client for Responses
  meta/asr.py        ASRClient.transcribe_file(wav, keywords=None|[]), RealtimeTranscriber(connect/stream_pcm/close), read_pcm, silence
  scenario.py        ScenarioPlayer: loads data/scenario_hanbit.yaml; replay clock; streams per-channel PCM at 1x into asr; emits audio_cue; schedules ptt/agent lines
  gate.py            should_triage(text) → bool  (drops empty / <2 tokens / squelch-only finals)
  triage.py          triage(text, lang, channel) → (Triage, ms, usage); prompt + 6 few-shots (NOT eval lines)
  verify.py          verify(triage, text) → (evidence_verified, triage'); snap_unit(raw, roster, lang) → unit_id|None; snap_zone(raw, floor, zones) → zone_id|None
  world.py           World: state, ids, append-only log, apply_event(), 1 Hz tick → rules, WS broadcast via a callback
  rules.py           R1..R5 over World (pure functions on state + t; return actions)
  agent.py           RelevanceAgent: wake(reason, snapshot) → tool calls via Spark Responses API, ≤3 rounds, 8 s timeout
  checker.py         check(tool_name, args, world) → (ok, error)  (6 invariants)
  router_fallback.py route(event, world) → briefs by zone match, text = triage.crew_brief
  cache.py           record/replay JSONL of every Meta call keyed by sha256(kind + canonical input)
  main.py            FastAPI app: REST below, WS /ws, static /samples → data/audio
eval/run_eval.py     batch eval → eval/results.json + eval/results.md
scripts/make_audio.py  raw recordings → clean 16k WAV → radio (AMR-NB) WAV; TTS fallback (Heami/Zira)
data/                scenario_hanbit.yaml, eval_lines.yaml, roster.json, zones.json, keywords.json, audio/{raw,clean,radio}, cache/
web/                 Vite + React 19 + react-router 8 (SPA) + Tailwind v4 + shadcn/ui (base-ui)
```

Run: `uv run uvicorn server.main:app --port 8000 --reload` and `cd web && npm run dev` (proxy /api, /samples, /ws → 8000).

## Pipeline per transmission

```
PCM frames (1x) ─► RealtimeTranscriber (ENDPOINTING, per channel) ─► transcript partials → WS "transmission"
                                                                   └► speechComplete(turnId) → text_final
text_final ─► gate.should_triage ─► triage.triage (Spark strict JSON) ─► verify (evidence, snap unit/zone)
           ─► Event ─► world.apply_event: units/zones/strategy/cards(dedupe, ≤5 open) → WS "event","card","unit","zone"
           ─► agent.wake (non-ROUTINE) ‖ router_fallback (timeout / agent cut) ─► briefs → WS "brief","trace"
world.tick (1 Hz) ─► rules R1..R5 ─► escalations / pings / RULE cards / proposals → WS
```

Measured facts that shape this (research/smoke_b1.md): strict `anyOf`-null works (no sentinels); triage uses
`reasoning_effort="minimal"` (3–7 s), agent uses `"low"`; Korean needs `languageBias:["Korean"]` + keywords ON;
ENDPOINTING emits `speechComplete` ~0.6 s after speech ends but **splits one transmission into several turns at pauses
≥ ~0.86 s** → `scenario.py` merges turns: in REPLAY/LIVE-replay the clip window is known, so a Transmission = all turns
whose speech lies in `[t_keyup, t_keyup + clip_duration + 0.5]`, finalised at the first `speechComplete` after the clip
ends (or `turn_merge_gap_s` = 1.5 s after the last one); for live mic (stretch) use the 1.5 s gap only. PTT: one
realtime socket per hold, `mode: PUSH_TO_TALK`, `{"type":"endStream"}` on release is the only end-of-turn message
(final arrives ~0.25 s later). Responses agent: `previous_response_id` works; the model does NOT retry on a tool
error by itself → the orchestrator must send the `function_call_output` error and explicitly ask for a corrected call.
Korean matching downstream: strip spaces, map Hangul numerals (일층→1층), tolerate doubled words (긴급탈출탈출).
Console: set `sys.stdout.reconfigure(encoding="utf-8")` in every entry point (Windows cp949 crashes on Korean).

Latency fields (ms, all measured, shown on the card badge): `asr_ms` = end of speech → final (realtime) or request RTT
(file); `triage_ms` = Spark RTT; `total_ms` = key-up → Event.

**LIVE vs REPLAY (cache.py).** LIVE calls Meta and `cache.py` records every outbound WS message (`{t, type, payload}`)
plus every REST action (`{t, method, path, body}`) of the run to `data/cache/run_<timestamp>.jsonl`; `POST
/api/scenario/start {mode:"REPLAY", run:"<file or 'best'>"}` re-emits that log at 1× (audio_cue included, so the lanes,
cards, briefs and latency badges are exactly the recorded live run; REST actions during REPLAY are ignored and the
recorded ones are shown as toasts). `data/cache/best.jsonl` is the run used in the video. Separately, `cache.py` also
offers an input-hash memo (`sha256(kind + canonical input)`) for `transcribe_file` and `triage` so eval/CLI re-runs
are cheap during development (`EARSHOT_MEMO=1`); it never applies to the agent. Nothing is ever silently faked: a
REPLAY with no run file raises.

**Triage prompt must-haves (smoke_b1.md):** `needs` and `air` are verbatim from the transcript or null (never
"구조 요청" / "rescue" / "low"); TRAPPED and LOST are equivalent downstream; any transmission that is part of an ongoing
긴급탈출/mayday (declaration, IC broadcast, IC instructions to the trapped member, acknowledgement) is MAYDAY; 옥상/roof →
`floor: null` with `zone_hint: "옥상"`; the 6 few-shots must not reuse any scenario or eval line (data/*.yaml).

**heard N of M.** `unit.total_count` += 1 for every transmission NOT from that unit, plus every rule firing addressed
to it; `unit.heard_count` += 1 per Brief(push) to it; `counters.held` = Σ(total − heard) over crew units. So "Park: heard
2 of 13" and "held 18" come from the same counters.

**Language.** Every ASR call passes `lang` (`transcribe_file(..., lang=)`, `connect(lang=)`), which selects
`languageBias` and `load_keywords(lang)`. The eval has 14 English lines.

## Cards

- Card from Event when `tag != ROUTINE`. `kind = tag`. `priority = TAG_PRIORITY[tag]`.
- Dedupe: same `unit_id` + same `zone_id` (or either null) + same kind within `dedupe_window_s` (30 s) → merge:
  append event_id, fill missing `fields`, recompute `missing_fields`, keep the earliest `created_t`.
  HELP_NEEDED from a unit with an open MAYDAY card merges into that MAYDAY card (fills `needs`).
- `fields` for MAYDAY = SOP 109: `who` (speaker_unit raw or unit callsign+name), `what` (DISTRESS_WHAT_KO), `where`
  (zone label or where_raw), `needs`, `air`. `missing_fields` = those that are null (air optional: list it but do not
  count it for completeness). VICTIM_FOUND fields: `count`, `where`, `state`. DANGER: `where`, `terms`.
- At most `max_open_cards` (5) in state `open|escalated`; others wait in priority order, `counters.cards_queued`.
- `POST /api/cards/{id}/ack` → state `acked`, `acked_t`. `resolve` → `resolved`, note.
- RULE cards: `rule_id` set, `kind=RULE`, `priority` = 0 for R2 (treated as MAYDAY), title in ko + title_en.

## Rules (rules.py; thresholds from Settings, "demo timescale")

| id | condition (evaluated at tick t) | action |
|---|---|---|
| R1 | card.kind in (MAYDAY, RULE-R2) & state open & t − created_t ≥ 10 → level 1; ≥ 20 → level 2 | card.state=escalated, escalation_level, WS "escalation" {card_id, level}; tone on UI |
| R2 | unit.interior & status IN & no open MAYDAY card for unit & t − last_heard_t ≥ 60 | ping_unit every 8 s (WS "ping", trace); unit.unanswered_pings++ ; at 3 → RULE card "3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1)" priority 0 |
| R3 | Event tag DANGER while state.strategy == OFFENSIVE | Proposal CONFIRM_STRATEGY (source rule) linked to the DANGER card |
| R4 | VICTIM_FOUND card, victims.state != EXTRACTING, no unit assigned within 30 s | Proposal ASSIGN |
| R5 | unit.status LOW_AIR or HELP_NEEDED card without EXITING event from that unit within 60 s | escalate card (level 1) |

Any transmission from a unit resets `last_heard_t`, `unanswered_pings=0`, and resolves an open R2 card for that unit
with note "found OK". A crew ack (`POST /api/crew/{unit}/ack`) does the same.

## Relevance agent (agent.py) and checker

Wake reasons: `event:<id>` (non-ROUTINE), `rule:<R>:<unit>`, `button:<unit>:<kind>`, `proposal_approved:<id>`.
Input: compact snapshot (units, zones with hazards, open cards, last 3 briefs per unit, the triggering event incl.
`crew_brief`). Responses API, tools below, ≤3 rounds via `previous_response_id` + `function_call_output`, wall timeout
`agent_timeout_s` → `router_fallback`. Every tool result is `{"ok": true, ...}` or `{"ok": false, "error": "..."}` (checker).

| tool | args | effect |
|---|---|---|
| get_unit_state | unit_id | read |
| send_brief | unit_id, text, priority P0/P1/P2, reason, evidence_event_id | Brief(push) → WS "brief"; unit.heard_count++ |
| hold | unit_id, event_id, reason | Brief(hold) → counters.held++ |
| request_missing_field | unit_id, field who/what/where/needs/air | WS "ask" {unit_id, field, text}; Brief(push, P0) |
| escalate_to_ic | event_id, reason | card.escalation_level = max(1, ·), WS "escalation" |
| propose_order | kind, units[], text, rationale, evidence_event_id | Proposal(pending) → WS "proposal" |
| ping_unit | unit_id | WS "ping"; unanswered_pings++ |

Checker invariants (reject → `{"ok":false,"error"}` and the agent retries): (1) send_brief target in/entering/assigned
to the event zone (or its parent/children) unless priority P0; (2) ≤1 non-P0 push per unit per 20 s; (3) text ≤ 2
sentences and ≤ 140 chars; (4) propose_order only creates a Proposal; (5) every MAYDAY card has an ack or a pending
escalation (checked on wake end; else auto escalate_to_ic); (6) every tool call cites an existing evidence_event_id
(get_unit_state/ping_unit exempt). Trace: `wake` → `reasoning` (summary if returned) → `tool_call` → `checker` →
`delivery`, all WS "trace". `counters.checker_rejections++` on reject.

## Briefs on the crew screen

`Brief.text` is ≤2 sentences in `lang`. The crew UI shows: line 1 tag chip (from the evidence event's tag or RULE),
line 2 = text, line 3 = action hint (derived: MAYDAY/P0 → "확인 버튼" etc.), small line "why: {reason}". The browser
speaks `text` with `speechSynthesis` (`ko-KR`/`en-US`), labelled "TTS: browser (non-Meta)". `heard N of M` =
`unit.heard_count / unit.total_count`.

## REST (all JSON; FastAPI under /api)

| method path | body → response |
|---|---|
| POST /api/scenario/start | {mode: LIVE/REPLAY, scenario: "hanbit", lang: ko/en, audio: "radio"/"clean"} → State |
| POST /api/scenario/stop · /reset | → State |
| GET /api/state | → State |
| POST /api/cards/{id}/ack · /resolve | → Card |
| POST /api/proposals/{id}/approve · /reject | → Proposal (approve → P0 brief to `units` and world effects: RADIO_SILENCE flag, RIT_DEPLOY sets rit.zone, WITHDRAW sets all IN→EXITING, CONFIRM_STRATEGY sets strategy, ASSIGN sets assignment) |
| PATCH /api/proposals/{id} | {text} → Proposal (state edited, still pending) |
| POST /api/crew/{unit}/button | {kind: EVACUATE/VICTIM_HERE/SEARCH_DONE/NEED_HELP} → Event (synthetic transcript per kind; EVACUATE → MAYDAY card, VICTIM_HERE → VICTIM_FOUND at unit zone, SEARCH_DONE → zone.search_state=searched, NEED_HELP → HELP_NEEDED) |
| POST /api/crew/{unit}/ptt | {clip_id: "L06"} → Transmission (PUSH_TO_TALK realtime session on the clip's clean/radio WAV, then the normal pipeline, channel PTT) |
| POST /api/crew/{unit}/ack | {} → Unit (answers a ping) |
| GET /api/eval/results | → eval/results.json |
| GET /api/scenario/lines | → scenario lines (for the launcher & subtitles) |
| GET /samples/{clean|radio}/{id}.wav | static audio |

## WebSocket `/ws` (server → client only; one socket per screen; all screens receive everything)

`{"type": T, "payload": P}` with T/P:
`snapshot` State · `clock` {t, running, mode} (1 Hz) · `transmission` Transmission (re-sent on every partial, same id) ·
`event` Event · `card` Card (re-sent on every change) · `proposal` Proposal · `brief` Brief · `unit` Unit · `zone` Zone ·
`trace` TraceEntry · `counters` Counters · `audio_cue` {channel, line_id, audio_url, t} (UI plays the clip on the lane) ·
`escalation` {card_id, level} · `ping` {unit_id, n, t, ping_id} · `ask` {unit_id, field, text} · `strategy` {strategy, event_id}.
Client → server: nothing (use REST). Reconnect: client re-requests GET /api/state.

## Frontend routes (web/src)

`/` launcher · `/command` IC dashboard · `/crew/:unitId` phone frame 390×844 · `/demo` split (CommandView 60% + CrewView kim + CrewView park) · `/eval`.
Shared: `src/lib/ws.ts` (one WS + state store), `src/lib/api.ts`, `src/lib/types.ts` (mirror of models.py), shadcn components in `src/components/ui`.
Mode badge (LIVE / REPLAY) visible on every screen. Thresholds shown with the label "demo timescale".

## Eval (eval/run_eval.py)

Set: 12 scenario audio lines + 24 eval lines = 36 (labels in the YAML files). Conditions: {clean, radio} × {keywords on, off}
via `ASRClient.transcribe_file` then `triage.triage` + `verify`. Metrics per PRODUCT_SPEC §9: MAYDAY recall/FP, 5-way
accuracy + macro-F1, critical-term hit rate, unit/floor exact match (raw vs snapped), codeword-masked recall (x/4),
evidence-span verbatim rate, Spark latency p50/p95. Writes `eval/results.json` (served at /api/eval/results) and
`eval/results.md`. GATE: radio-KO MAYDAY recall < 0.8 → hero run uses clean audio (or EN), and the README says so.

## Conventions

- ids: `tx_000N`, `evt_000N`, `card_000N`, `prop_000N`, `brief_000N`, `tr_000N` (World counters).
- Never log or print the API key. Never pass max_tokens < 3000 to Spark. Always `reasoning_effort` from Settings.
- Korean on screen for fire terms (긴급탈출, 구조대상자, 우선탐색); English UI chrome; `label_en`/`text_en` for subtitles.
- Every number shown as latency is measured in that run; nothing hard-coded.
