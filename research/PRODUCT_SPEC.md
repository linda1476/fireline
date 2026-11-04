# EARSHOT: final product spec (build-ready)

Judge and synthesiser pass, 2026-11-04 ~18:00 KST. Deadline 2026-11-05 11:00 KST.
Inputs: `spec_commander.md`, `spec_crew.md`, `spec_agentic.md`, plus all nine research files in `D:\meta\research\`.
Re-verified in this pass (WebFetch, 2026-11-04):
- dev.meta.ai speech-to-text, structured-output and tool-calling pages
- Kyunghyang (Bucheon timeline) and Hankook Ilbo (26 min; RIT ordered 09:20)
- Fire Engineering / Project Mayday (35.6%; IC-position miss rates)
- NIOSH F2010-18 landing page

Tags: **[V]** checked against a primary page, **[S]** secondary, **[I]** our inference or design choice.

> **Correction to all three candidate specs.** Kyunghyang (2026-10-23) shows the isolation itself was reported over radio at about 09:09, and the gap with no radio reports ran from about 09:12 to 09:35 [V]. So Bucheon is **not** a case of "silence nobody noticed". The accurate Bucheon hook has two parts:
> - The flammables report at 08:48 did not change the offensive declaration at 08:52.
> - It took 26 minutes from recognising the isolation (09:09) to finding the firefighter (09:35), and the RIT was ordered only at 09:20 (Hankook Ilbo 2026-10-20 [V]).
>
> The "silent crew" story should rest on two other sources: SOP 109 §1.1 (three unanswered calls) and Pyeongtaek 2022 (last contact around 09:30, press only [S]).

---

## 1. Scoring the three candidates

Each criterion is scored 0–10. *Feasibility* means building it in about 8 h solo with AI coding agents, plus about 3 h of video. The task requires an eval we can quote tonight, so an eval listed as a "stretch" goal costs points.

| Criterion | Commander-first ("FirstCall") | **Crew-first ("Earshot")** | Agent-first ("Earshot" + trace) |
|---|---|---|---|
| Impact (sourced pain → believable benefit) | 8: the headset argument (26% → <1.8%) is the best single design argument | 8: hazard intel that never reached crews (Bucheon, Wando, Mungyeong) plus the mayday queue | 7: same pains, but framed around the agent rather than the person |
| Meta tooling (creative, beyond basic) | 6: ASR + Spark triage + proposals; nothing Meta on the crew side | 8: ASR on both sides (channel listener + crew PTT), strict schema, Responses agent with parallel tools + reasoning summary | 8: same as crew, plus `previous_response_id` continuity |
| Demo (a tired judge remembers it) | 6: the clearest story, but it sits in the crowded IC-dashboard lane (FireflAI, FireSight, Firewatch, ResQueue) | **9**: "Kim hears one sentence, Park hears nothing", with a split screen and a 20 s viral cut | 7: the trace panel impresses engineers but is hard to read in 3 min, and the beats are crammed |
| Technical depth | 7: five rules with evidence, eval included | 7: rules + agent + eval | **9**: invariant checker, CRITIC-style retry, POC grid, conflict K |
| Feasibility (8 h + 3 h video) | **8**: the demoable loop lands at 5 h and the eval is inside 7.25 h | 6: exactly 8.0 h with no slack, two UIs plus an agent | 4: the MVP takes 8 h *without* the eval; world model + agent alone is 3 h |
| Honesty (no overclaims) | 9 | 8: Bucheon "silence" framing needs fixing (see above) | 8: same Bucheon framing; eval only as a stretch |
| **Total /60** | **44** | **46** | **43** |

**Winner: crew-first (Earshot).** Its demo shot is the only one of the three that no 2026 look-alike has, and the crowded-lane problem is the commander spec's own Risk #1. The scores sit within 3 points, so I fix crew-first's weak spot, feasibility, by taking the commander spec's build discipline and cut lines. I also make the agent trace a cuttable tab rather than the hero.

### What we graft, and why

| From | Idea grafted | Why |
|---|---|---|
| Commander | **Attention budget of at most 5 open cards** (FEMA span 3–7, optimum 5); headline counter "transmissions in → cards out" | The inverse of "more screens"; also answers the NIST "consolidate it down" quote |
| Commander | **The headset-advantage pitch** (IC at the back of a vehicle 26%, headset <1.8%) | Strongest causal argument that software can help |
| Commander | **DANGER-after-OFFENSIVE conflict rule** → "Confirm strategy?" card | Encodes the Bucheon 08:48 → 08:52 failure directly |
| Commander | **Hour-2 eval gate**: if degraded-Korean MAYDAY recall is poor, switch the hero run to clean audio or English and say so | Protects the demo from the biggest unknown |
| Commander | Record/replay cache with LIVE/REPLAY labels | Deterministic recording |
| Agent-first | **Invariant checker** (about 5 if-statements) that rejects agent tool calls, with the agent retrying | Cheap technical depth; rebuts "the LLM hallucinates" |
| Agent-first | **Trace tab** (reasoning summary → tool call → checker verdict → delivery) | Agentic-prize proof; first item to cut |
| Agent-first | "**Autonomy over information, not over orders**" framing; ASCII-only enums; test `anyOf`-null in the first 15 min | Correct HITL framing plus two build-risk fixes |
| Agent-first | `crew_brief` text produced inside the triage call (our addition, so the deterministic fallback router still speaks Meta-written text) | Makes cutting the agent safe |
| Left out (stretch only) | POC/Bayesian grid, Dempster-Shafer conflict K, SAM 3.1, Palisades clip, live mic | Time; Palisades licence not verified first-hand |

---

## 2. Product

**Name:** **Earshot**

**One-liner:** Earshot listens to every fireground radio channel so no mayday goes unheard. Meta's Muse models turn crew radio into a short, must-acknowledge queue for the incident commander, plus a two-sentence earpiece brief that goes only to the firefighters it affects.

**Tagline for the video:** *"The agent decides who hears what. The commander decides who does what."*

**How it maps onto the three committed pillars:**
- Pillar 1 (voice triage for command) is the IC ack queue.
- Pillar 2 (hands-free audio + clip-on display) is the crew view, driven by the relevance agent.
- Pillar 3 (world-model harness) is the state engine: event trace, units, zones and 5 time-bounded rules, shown on an indoor floor grid and an outdoor site plan.

All three pillars survive every cut line in §8.

### Three differentiators, each against a sourced pain

1. **No distress call sits unacknowledged, across channels, codeword or not.**
   - **Pain:**
     - 35.6% of maydays are missed on the first call, across more than 9,000 maydays (13,183 in the database) (Project Mayday, Fire Engineering, 2021-07-01 [V]). The miss rate is 26% when the IC works from the back of a vehicle with a portable radio and <1.8% on a headset [V].
     - At Bridgeport (NIOSH F2010-18), the first contributing factor was "Failure to effectively monitor and respond to Mayday transmissions" [V]. The IC was monitoring two channels on two handhelds [V, PDF p.32 via gap_2].
   - **Feature:**
     - One queue across 지휘망 and 작전망.
     - Spark detects distress semantically: 긴급탈출 ×3 (SOP 109), 메이데이, 맨다운, Mayday, and codeword-free lines such as "출구를 못 찾겠다".
     - The card fills SOP 109's 누가/무엇을/어디에/필요한 것 and escalates if it is not acked within 10 s.
2. **A per-responder relevance agent decides push / hold / suppress, and says why.**
   - **Pain:**
     - Bucheon 2026: flammables were reported at 08:48 and an offensive strategy was declared at 08:52 (Kyunghyang 2026-10-23 [V]).
     - After Wando, the NFA promised real-time delivery of hazard information to crews (Etoday [V in research]).
     - The Mungyeong 2024 official finding was "현장 활동 정보 공유가 미흡" (korea.kr [V]).
     - Firefighters reject more glass: fewer than 10% want AR or smart glasses, and they ask for a wireless earpiece (NIST SP 1286pt3 [V]).
   - **Feature:**
     - A hazard reported in sector X becomes a brief of at most 2 sentences, sent only to units in or entering X. Each brief carries a "why you hear this" line.
     - Everything else is held, and the hold is visible ("Park: heard 2 of 13").
     - A DANGER report after an OFFENSIVE declaration raises a "Confirm strategy?" card for the IC.
3. **Accountability from voice, with no new hardware.**
   - **Pain:**
     - Bucheon: 26 minutes from recognising the isolation to finding the firefighter, with the RIT ordered 11 minutes after the isolation (Hankook Ilbo 2026-10-20 [V]).
     - 68% of COs lacked accountability in hand at the time of a mayday (Fire Engineering [V in research]).
     - SOP 109 §1.1: a crew in the hazard zone that fails to answer three calls is treated as 긴급탈출 [V].
   - **Feature:**
     - Each unit has a "last heard" timer and a reported zone.
     - The agent pings a silent interior unit's earpiece; three unanswered pings raise an SOP 109 §1.1 card.
     - Replies take one gloved hold (4 buttons) or a PTT utterance transcribed by Meta ASR.

### What we do NOT build or claim (subtract list, merged from all three)

- No 3D twin, drones, evacuation-route drawing, or localisation accuracy. Positions are **reported zones**.
- No AR framing.
- No chat or Q&A (it reads as basic RAG).
- Nothing medical. 구조대상자 means location and status as reported, nothing else.
- No war or "tactical ops" language.
- No offline claim; the product is API-only.
- No WER claim for Muse beyond our own synthetic eval.
- No ASR confidence display, because the API returns none [V]. Uncertainty comes from Spark's `asr_uncertain` field.
- No bone-conduction or heat claims; the hardware is simulated.
- Statistics we never use: 54%, 36.5%, USFA EFO 82.6% (gap_2). Note that tech_comms.md still lists 82.6%; ignore it.
- Do not frame Bucheon as "unnoticed silence".

---

## 3. User roles and screens

**Roles:**
- **IC / 지휘대장** works at the command dashboard.
- **Crew member** wears a simulated clip display and earpiece: FF Kim (한빛구조대, 2F east), FF Park (누리119안전센터, 1F west), and the RIT (동부구조대).
- **Presenter** uses the scenario launcher.

**Stack:**
- Vite + React 19 + **React Router v7 in SPA (library) mode**.
- TailwindCSS + shadcn/ui.
- One WebSocket to the backend.

| Route | Screen | Contents | shadcn/ui components |
|---|---|---|---|
| `/` | Scenario launcher | Scenario picker; mode toggle `LIVE` / `REPLAY` (shown as a big label on every screen); "Standby → Run"; links to the views | `Card`, `ToggleGroup`, `Button`, `Badge`, `Separator` |
| `/command` | **IC dashboard** | **Top bar:** incident clock, mode badge, counters `transmissions 13 → cards 5 · held 18 · unacked 0` (values computed live; these are illustrative). **Left:** two channel lanes (지휘망 / 작전망) with live CUMULATIVE partials and finals, each with a replay ▶. **Centre:** card queue, **max 5 open** (MAYDAY > DANGER > VICTIM_FOUND > HELP_NEEDED; ROUTINE never becomes a card; overflow shows "+N queued"). Each card shows the tag, the SOP 109 fields with missing ones highlighted, the verbatim evidence span, channel and turn time, a latency badge ("3.4 s after key-up"), an ack-timer bar, and **ACK** / **Approve** / **Edit** / **Reject** on proposals. **Bottom:** accountability strip (unit · last heard · reported zone · status · unanswered pings). **Right:** tabs `Map` (indoor floor grid 1F/2F/3F/roof + outdoor site SVG with entry points, command post, RIT staging and the **SOP 205 1.5× building-height collapse ring**) and `Trace` (agent reasoning summary → tool calls → checker ✓/✗ → delivered/held) | `Card`, `Badge`, `Button`, `Progress` (ack timer), `Dialog` (edit proposal), `Tabs`, `ScrollArea`, `Table` (accountability), `Tooltip` (evidence), `Collapsible` (trace rows), `Alert` (escalation), `Sonner` toasts + WebAudio tone |
| `/crew/:unitId` | **Responder clip display** (390×844 phone frame) | **Header:** unit, reported zone, earpiece icon (speaking or idle), `heard N of M`. **Three lines:** (1) tag chip, (2) what changed, (3) what to do, plus a small "why you hear this" line. **Four full-width hold-to-confirm buttons** (800 ms): **긴급탈출** · **구조대상자 여기** · **검색완료** · **지원요청**. **TALK** (hold = PTT). Ack chip "확인" for pings. Footer label: "Simulated clip-on display · TTS: browser (non-Meta)" | `Button` + custom `HoldButton` (built on `Progress`), `Badge`, `Card`, `Alert` |
| `/demo` | **Split for the video** | `CommandView` (left 60%) + `CrewView unit=kim` + `CrewView unit=park` (right), rendered as components (no iframes) on one WS | Same components; `ResizablePanelGroup` optional |
| `/eval` | Eval results | Table from `eval/results.json`: per-condition metrics, per-line confusion, latency p50/p95 | `Table`, `Badge`, `Tabs` |

Earpiece audio uses `window.speechSynthesis` (`ko-KR` / `en-US`), with a persistent on-screen label saying it is non-Meta. The Meta Model API has no TTS [V, gap_1].

---

## 4. Backend services and data model

**FastAPI (Python 3.11):** `httpx`, `websockets`, `openai` SDK (base_url = Meta Model API), `rapidfuzz`, `pydantic`, `numpy`/`soundfile`, ffmpeg on PATH (AMR-NB build verified in gap_3).

```
server/
  main.py         FastAPI app; WS /ws?role=command|crew&unit=…; REST below
  scenario.py     loads scenario YAML; replay clock; streams each channel's WAV in 80 ms frames at 1×; emits audio_cue to UI
  asr.py          RealtimeASR (one WS per channel, ENDPOINTING), PTTASR (crew hold), FileASR (POST /v1/asr/transcribe for eval)
  gate.py         drops empty / <2-token / squelch-only finals before Spark (Whisper-hallucination lesson, arXiv 2402.08021)
  triage.py       Spark Chat Completions, strict json_schema → Event
  verify.py       evidence_span must be a normalised substring of the transcript (else blank + asr_uncertain=true); rapidfuzz snap unit/zone to roster.json/zones.json (keep raw + snapped)
  world.py        in-memory state + append-only event log; 1 Hz rule tick; emits diffs on WS
  rules.py        R1–R5 (below)
  agent.py        Relevance agent (Spark Responses API, tools, ≤3 tool rounds per wake)
  checker.py      invariant checker for agent tool calls
  router_fallback.py  deterministic zone-match router (used if the agent is cut or times out at 8 s)
  cache.py        JSONL record of every Meta request/response keyed by sha256(input); REPLAY reads it
  eval/run_eval.py  batch eval → eval/results.json + results.md
data/
  scenario_hanbit.yaml  roster.json  zones.json  keywords.json (58 gap_3 terms + roster)  audio/{clean,radio}/*.wav
```

**REST:**
- `POST /scenario/start {mode}`
- `POST /cards/{id}/ack`
- `POST /proposals/{id}/{approve|reject}`, `PATCH /proposals/{id}`
- `POST /crew/{unit}/button {kind}`
- `POST /crew/{unit}/ptt {clip_id}` (MVP: pre-recorded clip) or `WS /crew/{unit}/ptt` (stretch: live mic PCM)
- `GET /state`
- `GET /eval/results`

**Data model (pydantic; in memory, plus a JSONL log for after-action replay):**

```
Unit        {id, callsign, name, crew, channel, assignment, zone_id, status: IN|OUT|TRAPPED|LOW_AIR|OK|UNKNOWN,
             last_heard_at, unanswered_pings, heard_count, total_count}
Zone        {id e.g. "2F-E", floor, label_ko, label_en, kind: indoor|outdoor, polygon, hazards[], victim_reports[], search_state: none|primary|cross|searched}
Transmission{id, channel: CMD|TAC|PTT, turn_id, t_keyup, t_final, text_partial, text_final, audio_url, source: replay|live|ptt}
Event       {id, transmission_id, <triage fields §5.2>, speaker_unit_snapped, zone_id_snapped, latency_ms{asr,triage}}
Card        {id, kind: MAYDAY|DANGER|VICTIM_FOUND|HELP_NEEDED|RULE, event_ids[], rule_id?, priority, state: open|escalated|acked|resolved,
             created_at, acked_at, escalation_level, missing_fields[]}
Proposal    {id, card_id, kind: RADIO_SILENCE|RIT_DEPLOY|WITHDRAW|CONFIRM_STRATEGY|ASSIGN, units[], text, rationale, state: pending|approved|edited|rejected}
Brief       {id, unit_id, decision: push|hold, text, priority, reason, evidence_event_id, created_at, spoken_at}
TraceEntry  {id, ts, wake_reason, kind: reasoning|tool_call|checker|delivery, payload}
```

**Rules (time-bounded, evidence-citing; thresholds are hand-set and labelled "demo timescale" on screen):**

| ID | Rule | Fires | Source |
|---|---|---|---|
| R1 | MAYDAY card not acked within 10 s | Escalate (card pulses + tone); level 2 at 20 s | NIOSH F2010-18 rec. #1 |
| R2 | Unit with status IN and **no open MAYDAY card** not heard for 60 s (demo) | Agent pings its earpiece; **3 unanswered pings** (8 s apart) → MAYDAY card "3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1)" | SOP 109 §1.1 |
| R3 | DANGER in a zone while strategy = OFFENSIVE | CONFIRM_STRATEGY proposal to the IC + sector briefs | Bucheon 08:48 → 08:52 |
| R4 | VICTIM_FOUND with no unit assigned or extracting within 30 s | ASSIGN proposal | SOP 203 |
| R5 | LOW_AIR / HELP_NEEDED with no exit report within 60 s | Escalate to the IC | SOP 109 air check |

Every transmission silently counts as a "last heard" check-in, so the IC never has to pull a PAR. The Palisades AAR notes PAR traffic congesting the channel (LAist [V in research]: https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire).

**Invariant checker (rejections go back to the agent as `{"ok":false,"error":…}`, and the agent retries):**
1. `send_brief` target must be in or entering the event's zone, or assigned to it, **unless** priority = P0 (distress / evacuation / radio silence).
2. Rate limit: at most 1 non-P0 push per unit per 20 s.
3. Text is at most 2 sentences / 140 characters.
4. `propose_order` can only create a Proposal; nothing is sent until the IC approves.
5. Every MAYDAY card must have an ack or a pending escalation.
6. Every tool call must cite an existing `evidence_event_id`.

---

## 5. Exact Meta model usage (per call)

Latency for all Muse models is **unpublished** [V, gap_1]. Every number below is a *target* that we **measure and show on screen**, never a claim.

### 5.1 `muse-voice-transcribe-1.0`: channel listener (realtime)

| | |
|---|---|
| Endpoint | `wss://api.meta.ai/v1/asr/realtime`; auth in the first JSON frame [V] |
| Input | Two sockets (CMD, TAC), `PCM_16KHZ` s16le mono. Radio audio is AMR-NB 8 kHz decoded and upsampled to 16 kHz, because there is no 8 kHz enum [V]. Sent in 80 ms frames at **1× real time, including silence**; the server rejects streams that are too fast or too slow, with a 5 s backlog cap [V] |
| Config | `mode: ENDPOINTING` (server segments turns on a continuous channel); `partialMode: CUMULATIVE`; `keywords` = 58 SOP/LUNAR terms + roster callsigns + zone names (fixed at handshake [V]); `languageBias: ["Korean","English"]` |
| Output used | `transcript` partials (shown in the lane) → `final` / `speechComplete` per `turnId` → triage. Turn-level timestamps only; no confidence [V] |
| Streaming | Yes |
| Target latency | Final ≤1.5 s after key-up (measured) |

### 5.2 `muse-spark-1.3`: triage extractor (one call per final turn)

- **API:** Chat Completions, `response_format: {type:"json_schema", json_schema:{name:"radio_event", strict:true, schema}}`, `reasoning_effort:"low"` (eval also tries `"minimal"`; pick the faster one if accuracy holds). Non-streaming. Always pass `model:"muse-spark-1.3"`.
- **Strict subset [V]:** root object; `additionalProperties:false` everywhere; `required` = all keys; `anyOf` allowed below the root; no `oneOf`/`allOf`.
- **Nullable:** written as `anyOf:[{type:X},{type:"null"}]`. This is **undocumented**, so test it in the first 15 minutes. Fallback is sentinel strings `"UNKNOWN"` / `-1`.
- **Enums:** ASCII only; Korean appears only in free-text fields.

```jsonc
{
 "tag":            enum["MAYDAY","DANGER","VICTIM_FOUND","HELP_NEEDED","ROUTINE"],
 "speaker_unit":   string|null,          // raw self-ID, snapped later
 "addressee":      string|null,
 "location":       {"floor": integer|null, "zone_hint": string|null, "raw": string|null},
 "distress":       {"who": string|null,
                    "what": enum["TRAPPED","FALL","INJURY","MISSING","COLLAPSE","GAS","LOW_AIR","LOST","OTHER","UNKNOWN"],
                    "where_raw": string|null, "needs": string|null, "air": string|null} | null,
 "victims":        {"count": integer|null, "where_raw": string|null,
                    "state": enum["REPORTED","FOUND","EXTRACTING","UNKNOWN"]} | null,
 "hazard_terms":   [string],
 "status_change":  enum["ENTERING","EXITING","LOW_AIR","TRAPPED","OK","NONE"],
 "strategy_declared": enum["OFFENSIVE","DEFENSIVE","NONE"],
 "needs_ack":      boolean,
 "confidence":     number,               // 0–1, model self-report, shown as-is
 "asr_uncertain":  boolean,
 "uncertain_reason": string|null,
 "evidence_span":  string,               // verbatim substring; verify.py blanks it if not found
 "crew_brief":     string|null           // ≤2 sentences, same language as input; used by the fallback router
}
```

The TRAPPED…GAS values map to SOP 109's 대원고립/대원추락/대원부상/대원실종/붕괴위험/가스누출 in the UI.

**Prompt:**
- SOP 107 priority order (대원안전 > 구조대상자 > 주요요소 > 전략 → MAYDAY > DANGER > VICTIM_FOUND > HELP_NEEDED > ROUTINE).
- SOP 109 fields.
- Few-shots: 6 lines, including 2 codeword-masked distress lines ("출구를 못 찾겠다", "we can't find the way out"). These must **not** be in the eval set.
- Rules: "If unsure between DANGER and ROUTINE choose DANGER with confidence <0.6. Never invent a floor; use null. Victims: location and status as reported only; no medical content."

**Target latency:** ≤3 s per call; key-up → card on screen ≤5 s (measured; the badge shows it).

### 5.3 `muse-spark-1.3`: relevance agent (wakes on each non-ROUTINE event, each rule firing, and each crew button)

- **API:** Responses API, `tools=[…]`, `tool_choice:"auto"` (the only allowed value [V]), `parallel_tool_calls:true` (default [V]), `reasoning:{effort:"low", summary:"concise"}` (the summary is not guaranteed; fall back to the tool's `reason`), `stream:true` so the trace tab fills live.
- **Loop:** within one wake, use `previous_response_id` + `function_call_output` [V], with at most 3 rounds. Each wake starts fresh, with a compact world snapshot (units, zones, open cards, last 3 briefs per unit) as input.

**Tools:**

| Tool | Args | Effect |
|---|---|---|
| `get_unit_state` | `unit_id` | Read-only |
| `send_brief` | `unit_id, text, priority: P0\|P1\|P2, reason, evidence_event_id` | Push to earpiece (checker 1–3, 6) |
| `hold` | `unit_id, event_id, reason` | Logged suppression; increments "held" |
| `request_missing_field` | `unit_id, field: who\|what\|where\|needs\|air` | Earpiece question (SOP 109 §1.5.1 style) |
| `escalate_to_ic` | `event_id, reason` | Card escalation |
| `propose_order` | `kind: RADIO_SILENCE\|RIT_DEPLOY\|WITHDRAW\|CONFIRM_STRATEGY\|ASSIGN, units[], text, rationale` | IC approval queue only |
| `ping_unit` | `unit_id` | Earpiece check-in; counts toward R2 |

**Target latency:** first tool call ≤6 s. It never blocks the card: the card comes from triage plus rules. On a timeout of 8 s, `router_fallback.py` delivers `crew_brief` by zone match.

### 5.4 `muse-voice-transcribe-1.0`: crew PTT (crew side)
- The **TALK** hold opens a realtime socket in `mode: PUSH_TO_TALK` with the same keywords.
- MVP: the hold plays a pre-recorded labelled clip into the socket at 1×. Stretch: live mic through an AudioWorklet at 16 kHz.
- **Check in block 1:** the exact end-of-turn client message for PUSH_TO_TALK in the realtime API reference.
- The final goes to triage, then the Event, then the world (e.g., a VICTIM pin).

### 5.5 `muse-voice-transcribe-1.0`: eval (file endpoint)
- `POST /v1/asr/transcribe`, WAV 16 kHz mono, `keywords` on or off. There is no pacing requirement, so 100+ clips run in minutes [V gap_1: 10 min / 32 MB cap].

### 5.6 Stretch only
- `sam-3.1` on one pre-recorded **exterior RGB** frame, noun phrases "person" and "window", one per request [V]. Each detection becomes an evidence pin on the outdoor site plan, labelled as such.
- Never used on smoke or thermal frames; never "sees through smoke".
- muse-image is not used.

---

## 6. Scripted demo scenario: "한빛 도장공장" (synthetic, modelled on the Bucheon/Bridgeport patterns)

**Building:** 3-storey steel-frame paint factory (fictional).
- Zones: `1F-W`, `1F-E`, `2F-E`, `2F-E-OFFICE`, `2F-E-STORE`, `2F-STAIR` (정면 계단), `3F`, `ROOF`.
- Outdoor: 정면 출입구, 동측 창문, 지휘소 (front gate), RIT staging, collapse ring at 1.5 × 12 m.

**Units:**
- 지휘대장 (IC, CMD channel)
- 한빛119안전센터 팀장 (exterior/3F recon)
- **한빛구조대 소방장 김하늘** ("Kim", 2F east)
- **누리119안전센터 소방교 박준** ("Park", 1F west)
- 동부구조대 (RIT)

**Channels:** CMD = 지휘망, TAC = 작전망. Audio is recorded in the builder's own voice (one or two speakers), then degraded with the gap_3 ffmpeg AMR-NB chain. Fallback is any TTS, disclosed. The video shows English subtitles.

| # | t | Ch | Speaker | Line (KO; EN subtitle in video) | Expected tag | Expected world / agent effect |
|---|---|---|---|---|---|---|
| L1 | 0:00 | CMD | 지휘대장 | 전 출동대, 여기 지휘대장. 지휘권 선언, 지휘위치 정문 앞. 3층 도장공장 화재, **공격전략**. 한빛구조대 2층 동측 우선탐색, 누리센터 1층 서측 인명검색. | ROUTINE (`strategy_declared=OFFENSIVE`) | Strategy = OFFENSIVE; assignments set; no card |
| L2 | 0:12 | TAC | 김하늘 | 지휘대장, 여기 한빛구조대 소방장 김하늘. 정면 출입구로 3명 진입, 2층 동측 우선탐색 실시. | ROUTINE (`ENTERING`) | Kim → 2F-E, last heard reset; held for Park |
| L3 | 0:22 | TAC | 박준 | 지휘대장, 여기 누리119안전센터 소방교 박준. 1층 서측 진입, 인명검색 시작. | ROUTINE (`ENTERING`) | Park → 1F-W, status IN |
| L4 | 0:34 | TAC | 한빛센터 팀장 | 지휘대장, 여기 한빛119안전센터 팀장. 정면에서 3층 창문으로 확인, 도장공장 신나 드럼 다수, **인화물질** 확인. 2층 동측 천장으로 연소 확대 우려. | DANGER (speaker is exterior: status OUT, so R2 never applies to him) | DANGER card. **R3** → CONFIRM_STRATEGY proposal. Agent: `send_brief(kim, "2층 동측 위 3층 인화물질 확인, 연소 확대 우려. 퇴로는 정면 계단 유지.", P1, "sector 2F-E")`; `hold(park, "1F-W not affected")` |
| L5 | 0:46 | CMD | 지휘대장 | 상황실, 여기 지휘대장. 대응 1단계 발령 요청, 펌프차 2대 추가. | ROUTINE | Held for all crews |
| L6 | 0:56 | PTT | 김하늘 (holds **구조대상자 여기** + TALK) | 2층 계단 우측 사무실 구조대상자 1명, 정면 계단으로 구출 중. | VICTIM_FOUND (`EXTRACTING`) | Pin at 2F-E-OFFICE; card (no R4, since extracting); brief to the outdoor crew at 정면 출입구 |
| L7 | 1:08 | TAC | 박준 | 지휘대장, 여기 누리센터 박준. 1층 서측 검색 중, 이상 없음. | ROUTINE (`OK`) | Held for Kim; **Park is last heard here (1:08)**, so R2 fires at about 2:08 |
| L8 | 1:18 | TAC | 김하늘 | 지휘대장… 한빛구조대 김하늘… 천장 무너져서 **출구를 못 찾겠다**. 2층 동쪽 창고 쪽. 공기 얼마 안 남았다. | **MAYDAY** (no codeword; `what=TRAPPED`, `where=2F-E-STORE`, `needs=null`) | MAYDAY card on top, `필요한 것` missing. Agent: `request_missing_field(kim, needs)` + `escalate_to_ic` |
| L9 | 1:18 (overlaps L8) | CMD | 지휘대장 | 상황실, 여기 지휘대장. 추가 펌프차 정문 쪽으로 배치 바람. | ROUTINE | The Bridgeport overlap: IC talking on CMD while L8 lands on TAC |
| L10 | 1:32 | TAC | 김하늘 | 사다리랑 공기용기 필요. 동측 창문 쪽으로 이동 중. | HELP_NEEDED (merged into the MAYDAY card's `needs`) | Card complete. R1: no ack for 10 s, so it escalates (pulse + tone). IC taps ACK. Agent: `propose_order(RADIO_SILENCE, all)` + `propose_order(RIT_DEPLOY, 동부구조대, "2F-E 동측 창문")`. IC approves both; P0 brief to all earpieces |
| L11 | 1:50 | CMD | 지휘대장 | 전 출동대 **무선 침묵**. **긴급탈출** 발생, 한빛구조대 김하늘, 2층 동쪽 창고. 요청 자원 사다리, 공기용기. 신속동료구조팀 동측 창문 투입. | MAYDAY (command broadcast, SOP 109 §2) | Deduplicated into the existing card; RIT unit → 2F-E |
| L12 | 2:05–2:30 | (agent) | — | R2: Park not heard for 60 s (demo timescale), so `ping_unit(park)` ×3, 8 s apart, all unanswered | RULE → MAYDAY | Card "누리센터 박준: 3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1) · last heard 1:08 · 1F-W" + evidence clips |
| L13 | 2:35 | TAC | 박준 | 지휘대장, 여기 누리센터 박준. 1층 서측, 통신 불량 구역이었음, 이상 없음. | ROUTINE (`OK`) | Card auto-resolves to "found OK", kept in the log. Shows the false alarm is honest and cheap |
| (EN mode) | | | | Same script in English, built from gap_3 E1–E10 | | Fallback if the KO eval gate fails |

**Expected end state:** about 13 transmissions, 4–5 cards, 0 unacked. Kim heard 4 of 13, Park heard 2 of 13. The counters are computed live, not hard-coded.

---

## 7. Three-minute video beat sheet

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:15 | **Hook** (own voice, black screen, text) | "Bucheon, 16 Oct 2026. 08:48 a crew reports flammables. 08:52 offensive declared. 09:09 a firefighter isolated. 09:35 found. RIT ordered 09:20." (Kyunghyang; Hankook). Then "35.6% of maydays missed on the first call (Project Mayday, >9,000)" |
| 0:15–0:30 | **Open lane** | "AI in 119 today listens to citizens. Earshot listens to the crew." `/demo` split. Label: "Synthetic scenario · radio replayed · every model call live" (or "replay of a recorded live run") |
| 0:30–0:55 | **Filter** (the money shot) | L1–L5 on two lanes with partials streaming. DANGER card + "Confirm strategy?" proposal. **Kim's earpiece speaks one sentence ("why: sector 2F-E"); Park's shows "held · not your sector".** Counter `heard 2 of 5` |
| 0:55–1:10 | **One-touch victim** | Kim holds 구조대상자 여기 + TALK. Meta PTT transcript, then a pin on the floor grid, then an outdoor-crew brief |
| 1:10–1:50 | **Distress with no codeword** | L8 lands on TAC *while the IC talks on CMD*. Card in N s (latency badge). 필요한 것 is missing, so the agent asks Kim and Kim answers. 10 s unacked, so the card pulses and a tone sounds. IC ACK. Agent proposes 무선 침묵 + RIT; **the commander taps Approve**; every earpiece speaks |
| 1:50–2:15 | **Silence → SOP 109 §1.1** | Park's last-heard timer turns red. Three pings visible in the trace. Card "3회 무응답". Park answers (radio fault), the card resolves. "False alarms are cheap; missed maydays are not." |
| 2:15–2:40 | **Under the hood** | Pipeline diagram naming each Meta model. Trace tab: one **checker rejection → agent retry** (a brief aimed at the wrong sector). **Eval table** (§9 numbers, measured tonight) |
| 2:40–3:00 | **Limits + close** | "Simulated hardware · synthetic audio · reported zones, not tracking · decision support, IC decides · earpiece TTS is non-Meta." Close: "**The agent decides who hears what. The commander decides who does what.**" |

**Most Viral cut (20 s, 9:16):**
- Left: chaotic two-channel waveform and audio.
- Right: Kim's phone speaking one calm sentence, while Park's shows "held".
- End card: "35.6% of maydays are missed. Earshot."

---

## 8. MVP build plan (2-hour blocks; each ends demoable)

Time starts about 18:30 KST. Build runs to about 02:30, video to about 05:30, then buffer and sleep, and submission by 10:00 (1 h before the deadline).

| Block | Build | Exit criterion |
|---|---|---|
| **B1 · 0–2 h · Spine** | **First 15 min:** smoke-test Spark strict schema with `anyOf`-null; FileASR with `keywords`; realtime WS handshake. Write `scenario_hanbit.yaml`, roster, zones, keywords. Record L1–L13 + 24 eval lines (own voice, about 20 min) → ffmpeg AMR chain. Then `asr.py` (realtime ENDPOINTING + file), `gate.py`, `triage.py`, `verify.py` | CLI replays the scenario and prints tagged Events with latencies |
| **B2 · 2–4 h · Eval + world** | `run_eval.py` (§9) → `results.json`. **GATE:** if degraded-KO MAYDAY recall is below 0.8, switch the hero run to clean audio or EN mode and say so in the video. Then `world.py` + `rules.py` R1–R5 + `cache.py` + FastAPI WS bus | Eval numbers in hand; rules fire in CLI logs |
| **B3 · 4–6 h · Two screens** | Vite + RR7 + shadcn scaffold. `/command` (lanes, ≤5-card queue with ack timer, accountability strip, Map tab: indoor grid + outdoor SVG with collapse ring). `/crew/:unitId` (3 lines, 4 HoldButtons, TTS, heard N of M). `/demo` split. `router_fallback.py` (zone match + `crew_brief`) | **End-to-end demo loop works without the agent**: all three pillars visible |
| **B4 · 6–8 h · Agent + polish** | `agent.py` (Responses API, 7 tools) + `checker.py` + Trace tab. Crew PTT path (pre-recorded clip). `/eval` page. Run the full scenario LIVE 2–3 times; keep the best run as the REPLAY cache | Final recorded run in the cache |
| **V · 8–11 h · Video + repo** | OBS capture of `/demo` (REPLAY + one 20 s truly LIVE segment, labelled); voiceover; EN subtitles; edit. README (why, architecture, Meta-model table, eval, limits, citations, non-Meta disclosure, MIT licence); push the public repo; X post for Most Viral | Submitted |

**Cut lines (in order, if behind):**
1. SAM, Palisades, live mic: already stretch. Replace the `/eval` page with the table in the README (the eval *run* stays).
2. Trace tab: show tool calls as card footers instead.
3. Relevance agent: `router_fallback.py` stays, and the briefs are still Spark-written via `crew_brief`. Say "rule-routed" honestly. The Best Agentic claim then rests on the ack-escalate loop + the missing-field ask, which can be a single Spark call.
4. R4/R5: keep R1–R3.
5. Outdoor SVG detail: a static site image with 3 labels, but **never remove the outdoor view** (Pillar 3 says indoor + outdoor).

**Never cut:** the eval, the MAYDAY ack-escalate loop, the crew view with the 4 buttons, the accountability strip.

---

## 9. Evaluation we run tonight (and quote)

**Set (fixed before any prompt tuning; few-shot lines excluded):**
- gap_3 K1–K10 + E1–E10.
- 4 codeword-masked distress lines (2 KO, 2 EN, new wording).
- 13 scenario lines.
- N = 37 utterances, about 11 of them MAYDAY-positive.
- Labels are written in `eval/labels.csv` before the first run.

**Conditions:** {clean, AMR-NB degraded} × {keywords on, off} via the FileASR endpoint, followed by triage. That is 148 ASR calls and 148 Spark calls, roughly 15 minutes and cents in cost.

**Metrics:**
1. **MAYDAY recall** and MAYDAY false positives (headline; report n).
2. **5-way tag accuracy** and macro-F1.
3. **Critical-term hit rate:** does the transcript contain 긴급탈출 / 맨다운 / 메이데이 / Mayday / 인화물질? Keywords on vs off; this is the biasing before/after number.
4. **Unit and floor exact match**, raw vs roster-snapped (the ATC-paper analog).
5. **Codeword-masked recall** (x/4).
6. **Evidence-span verbatim rate** (before verify.py blanks bad spans).
7. **Latency:** realtime key-up → final, final → card, and key-up → card, as p50/p95 over 3 live scenario runs.
8. **Attention:** transmissions in → cards out; per-crew heard N of M; checker rejections per run.

**How we report it:** a table in the README and on `/eval`, with "synthetic, own-voice + codec degradation, n = 37" stated next to every number. No WER claim for Muse in general.

---

## 10. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Degraded Korean ASR misses distress, or Spark is slow** (both unmeasured) | Hour-2 eval gate (B2); semantic triage, not lexical; keywords; `reasoning_effort` low/minimal; latency shown, not claimed; EN-mode fallback |
| 2 | **8 h scope overrun** (two UIs + agent) | Each block ends demoable; the agent is the last build block and has a deterministic fallback; cut list in §8 |
| 3 | Realtime WS pacing / handshake friction | 80 ms frames at 1× including silence; if stuck for more than 40 min, use FileASR per transmission at key-up (still Meta ASR, labelled "per-transmission") |
| 4 | Undocumented `anyOf`-null in strict mode | Test in the first 15 min; fall back to sentinel strings |
| 5 | Live demo fails while recording | REPLAY cache of a real live run, labelled; one 20 s truly live segment |
| 6 | Over-triage floods the 5-card budget (LLM triagers over-escalate, arXiv 2408.07531) | Deduplicate by unit + zone + 30 s window; ROUTINE never becomes a card; confidence shown |
| 7 | "Crew-side Meta looks thin" (TTS is non-Meta) | PTT transcribe on the crew side + agent decisions in the trace; non-Meta label on screen |
| 8 | Judges read it as "surveillance" | Pitch "the IC never misses your 긴급탈출", not tracking; positions are self-reported |
| 9 | Rubric weights are secondary-sourced | The pass/fail gates matter more: Meta models are on every core path; no medical or war content |
| 10 | Crowded fire-tech lane (FireflAI, FireSight, Firewatch, ResQueue) | Lead with crew radio + per-responder suppression, which no reviewed project does |

---

## 11. Citation list (README and video)

**Problem (US):**
- Project Mayday, 35.6% missed on first call; IC position 26% / <5.2% / <1.8% (Fire Engineering, 2021-07-01): https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/
- NIOSH F2010-18 (Bridgeport CT, 2010; report 2011-06-01): https://stacks.cdc.gov/view/cdc/163519 · PDF https://stacks.cdc.gov/view/cdc/163519/cdc_163519_DS1.pdf
- NFFNMRS: communication in 858 of 4,814 near-miss reports (Taylor & Lacovara 2015): https://pubmed.ncbi.nlm.nih.gov/25816170
- 68% of COs without accountability in hand at mayday: https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/
- NIST SP 1286pt3 (<10% want AR; earpiece wanted; "consolidate it down"): https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf
- FEMA span of control 3–7: https://emilms.fema.gov/_is0200c/groups/53.html
- Command software used by 15% of surveyed firefighters: https://www.firerescue1.com/technology/from-skepticism-to-standard-how-firefighters-adopt-new-technology

**Problem (Korea):**
- Bucheon 2026 radio timeline (Kyunghyang, 2026-10-23): https://khan.co.kr/article/202610231144001
- Bucheon 26 min, RIT 09:20 (Hankook Ilbo, 2026-10-20): https://www.hankookilbo.com/news/article/A2026101912160005075
- Mungyeong 2024 official finding (소방청, 2024-03-13): https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810
- Wando 2026, NFA real-time hazard-info pledge: https://www.etoday.co.kr/news/view/2600005
- Pyeongtaek 2022, last contact ~09:30 (press): https://www.nocutnews.co.kr/news/5686698
- 재난현장 표준작전절차 (SOP 107 / 109 / 205), Daegu print: https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf
- Korean AI-119 covers citizen calls only: https://www.gnmaeil.com/news/articleView.html?idxno=597905 · https://www.cctoday.co.kr/news/articleView.html?idxno=2225697
- MSIT/MOIS AI radio-summary R&D call (Aug 2026): https://www.news1.kr/it-science/general-science/6259675

**Method:**
- ATC runtime monitoring (event trace + rules, F1 0.85): https://arxiv.org/abs/2608.25926
- ATC roster biasing 35.2% → 88.9%: https://arxiv.org/html/2202.03725
- SeaAlert (codeword-masked distress): https://arxiv.org/abs/2604.14163
- Whisper hallucination on pauses: https://arxiv.org/html/2402.08021v2
- Police-radio ASR ~51% WER zero-shot: https://arxiv.org/html/2409.10858
- LLM triage over-escalation: https://arxiv.org/abs/2408.07531
- CRITIC: https://arxiv.org/abs/2305.11738

**Platform:**
- https://dev.meta.ai/docs/speech-to-text
- https://dev.meta.ai/docs/api-reference/voice/schemas
- https://dev.meta.ai/docs/structured-output
- https://dev.meta.ai/docs/tool-calling
- https://dev.meta.ai/docs/reasoning
- https://dev.meta.ai/docs/models

**Precedent:**
- DispatchAI: https://github.com/IdkwhatImD0ing/DispatchAI
- Argus: https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41
- ORION: https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge

---

## 12. Implications for our product

1. **Ship Earshot (crew-first)** with the commander spec's build discipline. The hero shot is "Kim hears one sentence, Park hears nothing".
2. **Fix the Bucheon framing everywhere:** 08:48 → 08:52 (hazard did not change the strategy) and 09:09 → 09:35 (26 min; RIT at 09:20). Not "unnoticed silence".
3. **Use one tag enum everywhere:** `MAYDAY | DANGER | VICTIM_FOUND | HELP_NEEDED | ROUTINE`. MAYDAY tops the committed set per SOP 107 대원안전.
4. **긴급탈출 (SOP 109) is the on-screen Korean hero term**; detection is semantic, so codeword-free distress still fires.
5. **Cards come from triage plus rules; the agent only routes information.** Orders always wait for the IC tap.
6. **The eval is not optional:** run it in B2, gate the hero language on it, and quote only measured numbers with n.
7. **Every Meta model has a visible job:** ASR on both channel and crew sides with keywords and code-switching; Spark strict schema; a Spark Responses agent with parallel tools and a reasoning summary. The non-Meta TTS is labelled.
8. **Keep both indoor and outdoor views alive under every cut**, or Pillar 3 looks dropped.
9. **35.6% is the only US statistic on the title card;** never 54%, 36.5% or 82.6%.
