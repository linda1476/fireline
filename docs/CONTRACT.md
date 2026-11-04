# Earshot build contract

Everything every module and screen agrees on. Spec: `research/PRODUCT_SPEC.md`. Data model: `server/models.py`
(the wire format is `model_dump(mode="json")` of those classes; field names are final). Measured API facts:
`research/smoke_b1.md` (read it before touching asr/triage/agent).

## Layout

```
server/
  config.py          Settings (API key from .env, thresholds, paths), load_keywords(lang) (drops + logs terms > 30 chars: API 400)
  models.py          pydantic models + TRIAGE_SCHEMA (strict JSON schema for Spark)
  meta/spark.py      SparkClient: acomplete_json(system, user, Triage, TRIAGE_SCHEMA) → (Triage, ms, usage); .async_client for Responses
  meta/asr.py        ASRClient.transcribe_file(wav, keywords=None|[]), RealtimeTranscriber(connect/stream_pcm/close), read_pcm, silence
  scenario.py        ScenarioPlayer: loads data/scenario_hanbit.yaml; replay clock; streams per-channel PCM at 1x into asr; emits audio_cue; schedules ptt/agent lines
  gate.py            should_triage(text) → bool  (drops empty / <2 tokens / squelch-only finals)
  triage.py          triage(text, lang, channel) → (Triage, ms, usage); prompt + 6 few-shots (NOT eval lines); EARSHOT_MEMO=1 → cache.memo
  verify.py          verify(triage, text) → (evidence_verified, triage'); snap_unit(raw, lang="ko", roster=None) → unit_id|None;
                     snap_zone(raw_hints, floor=None, lang="ko", zones=None) → zone_id|None (floor = preference, not filter);
                     snap_event(triage, text, lang) → (verified, triage', unit_id, zone_id)
  world.py           World: state, ids, append-only log, apply_event(), 1 Hz tick → rules, WS broadcast via a callback
  rules.py           R1..R7 over World (pure functions on state + t; return actions; R6/R7 = MAYDAY safety nets)
  agent.py           RelevanceAgent: wake(reason, event) → tool calls via Spark Responses API, ≤3 rounds, agent_timeout_s (12 s)
                     → router fallback delivers, the wake continues in the background (late calls applied, deduped)
  checker.py         check(tool_name, args, state, now_t, recent_pushes) → (ok, error)  (invariants 1–4, 6, 7; 5 at wake end);
                     distressed_unit(event, state) → the unit a MAYDAY is about
  router_fallback.py route(event, world) → briefs by zone match, text = triage.crew_brief
  cache.py           RunRecorder / RunReplayer (run_<ts>.jsonl), list_runs / promote / newest_run, memo(kind, payload, compute)
  main.py            FastAPI app: REST below, WS /ws, static /samples → data/audio
eval/run_eval.py     batch eval → eval/results.json + eval/results.md
scripts/make_audio.py  raw (Gemini TTS via scripts/gemini_tts.py, or recordings) → clean 16k WAV → radio (AMR-NB) WAV; SAPI fallback (Heami/Zira)
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
world.tick (1 Hz) ─► rules R1..R7 ─► escalations / pings / RULE cards / proposals → WS
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
(file); `triage_ms` = Spark RTT; `total_ms` = key-up → Event (includes the clip's own duration); `after_speech_ms` =
end of transmission → Event (≥ 0) = `total_ms` − (`Transmission.t_end` − `t_keyup`) (`models.after_speech_ms`; clips play
at 1× even with `speed`, so the subtraction is wall-exact). It is the PRIMARY badge number ("4.3 s after end of
transmission"); `total_ms` is secondary. `Transmission.t_end` (scenario s) = key-up + clip duration (replay: WAV length;
PTT: the clip's WAV length, and after_speech_ms is measured from the wall time the last PCM frame was sent; button: = key-up; live mic: last speech end). `Card.latency_after_speech_ms` copies it
(`Card.latency_ms` stays = `total_ms`). The CLI prints it too. Runs recorded before these fields replay with 0 / null
(pydantic defaults); the recorder needs no change (it dumps the models).

**LIVE vs REPLAY (cache.py).** LIVE calls Meta and `cache.py` records every outbound WS message (`{t, type, payload}`)
plus every REST action (`{t, method, path, body}`) of the run to `data/cache/run_<timestamp>.jsonl`; `POST
/api/scenario/start {mode:"REPLAY", run:"<file or 'best'>"}` re-emits that log at 1× (audio_cue included, so the lanes,
cards, briefs and latency badges are exactly the recorded live run; REST actions during REPLAY are ignored and the
recorded ones are shown as toasts). `data/cache/best.jsonl` is the run used in the video. Separately, `cache.py` also
offers an input-hash memo (`sha256(kind + canonical input)`) for `transcribe_file` and `triage` so eval/CLI re-runs
are cheap during development (`EARSHOT_MEMO=1`, wired in `triage.triage`: key = text, lang, channel, model, effort,
prompt hash; a hit returns the original call's ms with `usage.memo = true`); it never applies to the agent. Nothing is
ever silently faked: a REPLAY with no run file raises (404). `run:"best"` with no `best.jsonl` plays the newest
`run_*.jsonl` and says so with a WS `toast` `{method:"INFO", path:"best.jsonl missing, playing newest run …"}`
(and `replay_note` in the response). The recorder stays open `RECORDER_GRACE_S` = 30 s after a LIVE run stops
(end of scenario or POST stop) so late REST acks and late agent output are still recorded.

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
- `created_t` = world clock when the card became VISIBLE (≥ Event.t: the card exists only after ASR + triage, ~10–15 s
  after key-up); `event_t` = key-up `Event.t` of the first event (null for RULE cards). R1 and the UI ack timer count
  from `created_t`; the dedupe window counts from the events' `t`. A queued card's `created_t` is bumped when promoted.
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
| R1 | card.kind in (MAYDAY, RULE-R2) & state open & t − created_t (visible time) ≥ 10 → level 1; ≥ 20 → level 2 | card.state=escalated, escalation_level, WS "escalation" {card_id, level}; tone on UI |
| R2 | unit.interior & status IN & no open MAYDAY card for unit & t − last_heard_t ≥ 60 | ping_unit every 8 s (WS "ping", trace); unit.unanswered_pings++ ; at 3 → RULE card "3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1)" priority 0 |
| R3 | Event tag DANGER while state.strategy == OFFENSIVE | Proposal CONFIRM_STRATEGY (source rule) linked to the DANGER card |
| R4 | VICTIM_FOUND card, victims.state != EXTRACTING, no unit assigned within 30 s | Proposal ASSIGN |
| R5 | unit.status LOW_AIR or HELP_NEEDED card without EXITING event from that unit within 60 s | escalate card (level 1) |
| R6 | MAYDAY card (not resolved, unit known) with a missing SOP 109 field (who/what/where/needs; air is optional and not asked) and no ask for that field sent to that unit (any source) ≥ `r6_ask_s` (6 s) after `created_t` | ask via the world (same effect as the agent tool): WS "ask" {unit_id, field, text} + Brief(push, P0, source rule, reason "SOP 109 missing field: <f>", text = `ASK_FIELD_KO[f]`); trace `tool_call` + `delivery` with `source: "rule"`, wake_reason `rule:R6:<unit>` |
| R7 | MAYDAY card (not resolved) with `fields.where` known and no standing RIT_DEPLOY proposal ≥ `r7_rit_s` (15 s) after `created_t` | Proposal RIT_DEPLOY (source rule, units [RIT], text "신속동료구조팀 <zone label> 투입 (<access>)", access = nearest outdoor: 2F-E* → 동측 창문, 1F-W → 정면 출입구) and, if none yet, RADIO_SILENCE (all CREW/RIT/EXTERIOR units except the member in distress, "전 출동대 무선 침묵, 긴급탈출 관련 교신만"). A kind the IC rejected for this card is not re-proposed. |

World notes: R2 skips a unit with any non-resolved MAYDAY/R2 card (acked counts) or status TRAPPED; R5's LOW_AIR branch
escalates only that unit's MAYDAY card (plus any HELP_NEEDED card). An Event moves its speaker to the snapped zone only
when the speaker is interior and the zone is indoor, or on EXITING; status_change from IC/Dispatch applies to the
subject unit (`_subject_unit`), never to IC/Dispatch. Acking a resolved card is a no-op; a merge regenerates the card
title. The run recorder stamps WS/REST with the player clock (`RT.now_t()`). Start / reset cancel the previous run's
in-flight tasks and the agent's late wakes; reset keeps WS broadcast for LIVE. The gate always triages codewords and
short hazard words (철수/붕괴/대피/탈출/evacuate/collapse/withdraw) and counts tokens before collapsing repeats.

Any transmission from a unit resets `last_heard_t`, `unanswered_pings=0`, and resolves an open R2 card for that unit
with note "found OK". A crew ack (`POST /api/crew/{unit}/ack`) does the same.

## Relevance agent (agent.py) and checker

Wake reasons: `event:<id>` (non-ROUTINE), `rule:<R>:<unit>`, `button:<unit>:<kind>`, `proposal_approved:<id>`.
Input (round 1, kept cheap): open cards only, units with role CREW/RIT/EXTERIOR, zones with hazards/victims (+ the event
zone), last 1 brief per unit, the triggering event incl. `crew_brief`, `related_zones` and `distressed_unit`.
Round 1 runs at `agent_round1_reasoning_effort` ("minimal") with `max_output_tokens` 4000 (a token cap never makes a short
answer faster, it only truncates). A response that is `incomplete` or carries any function_call with empty / unparseable
arguments is truncated: ALL its calls are discarded (never applied, never sent to the checker), a `reasoning` trace
`{note: "truncated, retrying with 4000"}` is written and the same round is re-issued once immediately (not chained via
`previous_response_id`); truncated again → treated as no calls (gap fill). Later rounds use `agent_reasoning_effort`
("low") and 4000. Prompt order on a MAYDAY wake: request_missing_field for each missing field (to the distressed unit) →
propose_order RIT_DEPLOY (`event.rit_access`) + RADIO_SILENCE → P0 briefs to the other interior units → escalate_to_ic;
on HELP_NEEDED that fills a MAYDAY's needs, RIT_DEPLOY if not yet proposed. Proposal dedupe: RIT_DEPLOY / RADIO_SILENCE /
WITHDRAW are one per incident (any pending/edited/approved proposal of that kind → `deduped`), other kinds per evidence
event; asking a unit for a field it was already asked (agent or R6) → `deduped`. Responses API, tools
below, ≤3 rounds via `previous_response_id` + `function_call_output`. At `agent_timeout_s` (12 s) the `router_fallback`
delivers immediately and `wake()` returns; the loop keeps running in the background (≤ 45 s) and its late calls are
applied when they pass the checker and are not duplicates (send_brief to a unit that already has a push for the same
evidence event, or hold to a unit with any brief for it → `{"ok": true, "deduped": true}`, not a rejection; a pending
proposal of the same kind for the same event is likewise reused). Late trace entries carry `late: true`.
Every tool result is `{"ok": true, ...}` or `{"ok": false, "error": "..."}` (checker).

| tool | args | effect |
|---|---|---|
| get_unit_state | unit_id | read |
| send_brief | unit_id, text, priority P0/P1/P2, reason, evidence_event_id | Brief(push) → WS "brief"; unit.heard_count++ |
| hold | unit_id, event_id, reason | Brief(hold) → counters.held++ |
| request_missing_field | unit_id, field who/what/where/needs/air | WS "ask" {unit_id, field, text}; Brief(push, P0); text = `models.ASK_FIELD_KO[field]` (who "소속과 이름을 말하십시오", what "상황(원인)을 말하십시오", where "현재 위치, 지나온 위치를 말하십시오", needs "필요한 것이 무엇입니까? 사다리, 공기용기 등", air "공기잔량을 보고하십시오"); crew UI label from `field` via `ASK_FIELD_LABEL_KO` |
| escalate_to_ic | event_id, reason | card.escalation_level = max(1, ·), WS "escalation"; only for crew-safety cards (MAYDAY / HELP_NEEDED / RULE, or a card already at escalation ≥ 1), else rejected "not a crew-safety card" |
| propose_order | kind, units[], text, rationale, evidence_event_id | Proposal(pending) → WS "proposal" |
| ping_unit | unit_id | WS "ping"; unanswered_pings++ |

Checker invariants (reject → `{"ok":false,"error"}` and the agent retries): (1) send_brief target in/entering/assigned
to the event zone (its parent/children/siblings, vertical neighbours; a free-text assignment counts by its leading
zone id, "2F-E 우선탐색" → 2F-E) unless priority P0, and P0 only on MAYDAY-class evidence (tag MAYDAY, a distress
block, or a MAYDAY / R2 card); request_missing_field only on a MAYDAY-class event and only to the distressed unit; (2) ≤1 non-P0 push per unit per 20 s; (3) text ≤ 2
sentences and ≤ 140 chars; (4) propose_order only creates a Proposal; (5) every MAYDAY card has an ack or a pending
escalation (checked on wake end; else auto escalate_to_ic); (6) every tool call cites an existing evidence_event_id (get_unit_state/ping_unit exempt); (7) send_brief to the
unit a MAYDAY is about (`checker.distressed_unit`: the MAYDAY/R2 card's `unit_id`, else `distress.who` snapped with
`snap_unit`, else a crew speaker) whose text restates their own distress (긴급탈출/mayday/cause terms/their name) is
rejected; that unit gets `request_missing_field`, and a P0 "구조대 투입 중, 위치 유지." brief only when the IC approves
RIT_DEPLOY (`world.decide_proposal`). The router fallback holds that unit on a MAYDAY instead of pushing it the P0. The router also applies (2) and (3)
(hold "rate limited (20 s)"; template text if crew_brief breaks (3)), and runs as a gap fill after every agent wake
that ends on its own, for crew units the agent left undecided (trace `fallback` reason "agent gap fill"). Text-only
model messages are traced as `reasoning` (`from: "message"`). Trace: `wake` → `reasoning` (summary if returned) → `tool_call` → `checker` →
`delivery`, all WS "trace". `counters.checker_rejections++` on reject.

## Briefs on the crew screen

`Brief.text` is ≤2 sentences in `lang`. The crew UI shows: line 1 tag chip (from the evidence event's tag or RULE),
line 2 = text, line 3 = action hint (derived: MAYDAY/P0 → "확인 버튼" etc.), small line "why: {reason}". The browser
speaks `text` with `speechSynthesis` (`ko-KR`/`en-US`), labelled "TTS: browser (non-Meta)". `heard N of M` =
`unit.heard_count / unit.total_count`.

## REST (all JSON; FastAPI under /api)

| method path | body → response |
|---|---|
| POST /api/scenario/start | {mode: LIVE/REPLAY, scenario: "hanbit", lang: ko/en, audio: "radio"/"clean", speed?: number (LIVE: compresses the silence between clips, ScenarioPlayer), run?: file or "best" (REPLAY)} → State |
| GET /api/runs | → [{file, size, t_max, mtime, best}] (data/cache run_*.jsonl + best.jsonl, newest first) |
| POST /api/runs/{file}/promote | copies data/cache/{file} (run_*.jsonl) → best.jsonl → {promoted, best, size, t_max} |
| POST /api/scenario/stop · /reset | → State |
| GET /api/state | → State |
| POST /api/cards/{id}/ack · /resolve | → Card |
| POST /api/proposals/{id}/approve · /reject | → Proposal (approve → P0 brief to `units` and world effects: RADIO_SILENCE flag, RIT_DEPLOY sets rit.zone, WITHDRAW sets all IN→OUT (interior false, assignment "EXITING (withdraw)"), CONFIRM_STRATEGY sets strategy, ASSIGN sets assignment) |
| PATCH /api/proposals/{id} | {text} → Proposal (state edited, still pending) |
| POST /api/crew/{unit}/button | {kind: EVACUATE/VICTIM_HERE/SEARCH_DONE/NEED_HELP} → Event (synthetic transcript per kind; EVACUATE → MAYDAY card, VICTIM_HERE → VICTIM_FOUND at unit zone, SEARCH_DONE → zone.search_state=searched, NEED_HELP → HELP_NEEDED) |
| POST /api/crew/{unit}/ptt | {clip_id: "L06"} → Transmission (PUSH_TO_TALK realtime session on the clip's clean/radio WAV, then the normal pipeline, channel PTT) |
| POST /api/crew/{unit}/ack | {} → Unit (answers a ping) |
| GET /api/eval/results | → eval/results.json |
| GET /api/scenario/lines | → scenario lines (for the launcher & subtitles) |
| GET /samples/{clean|radio}/{id}.wav | static audio |

## WebSocket `/ws` (server → client only; one socket per screen; all screens receive everything)

`{"type": T, "payload": P}` with T/P:
`snapshot` State · `clock` {t, running, mode} (1 Hz; `running` is true from the moment POST /api/scenario/start returns —
the player / replayer set it in `start()` — until stop or the end of the run) · `transmission` Transmission (re-sent on every partial, same id) ·
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
- Never log or print the API key. Never pass max_tokens < 3000 to Spark (agent round 1 included: 4000 at "minimal").
  Always `reasoning_effort` from Settings.
- ASR keywords ≤ 30 characters each (`load_keywords` drops and logs longer ones; the API answers 400).
- Korean on screen for fire terms (긴급탈출, 구조대상자, 우선탐색); English UI chrome; `label_en`/`text_en` for subtitles.
- Every number shown as latency is measured in that run; nothing hard-coded.
