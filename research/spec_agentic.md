# Product spec: agent-first fireground radio coordinator

Synthesis of every file in `D:\meta\research\` (tech_comms, tech_spatial, hackathons_google, hackathons_other, services_global, services_korea, gap_1-3). Written 2026-11-04 KST, about 17 h before the deadline. Angle: **AGENT-FIRST**. The agent trace is the hero, aimed at Technical depth (20%) and Best Agentic Use-Case ($5K, "strongest agent autonomy and multi-step workflows", wiki paraphrase [S]: https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md).

Tags: **[V]** verified in the research files from a primary page. **[S]** secondary or snippet only. **[I]** our inference.

**Thesis.** Fireground deaths keep coming back to information that existed but never reached the right person. Examples are a mayday nobody acknowledged, flammables reported four minutes before an offensive order, and a trapped crew whose silence nobody noticed. We build an agent that listens to every crew channel and decides on its own **who needs to hear what, and when**. It checks its own world model against deterministic rules, and it leaves every *order* to the incident commander (IC).

---

## 1. ADD from hackathon and competition winners

| Winning move | Source | What we add |
|---|---|---|
| Severity-sorted queue with the human making the final call (Grand Prize, 1st of 293) | DispatchAI, https://github.com/IdkwhatImD0ing/DispatchAI | One ranked queue across all channels. The IC acknowledges each card. |
| "Nothing moves until the commander clicks Dispatch". Findings are linked to video timestamps. | Argus, https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41 | **Orders** go through an approval gate. Each card links to its radio clip and turn timestamp. |
| "AI proposes, a local checker decides, a person approves". One critique round cut errors from 16 to 0. | SpatialTwin, https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/77 | A deterministic **invariant checker** rejects agent tool calls that break rules, and the agent retries. |
| Judges praised "auditable reasoning trails" (Global Resilience Prize) | Acuífero·Vigía, https://blog.google/innovation-and-ai/technology/developers-tools/winning-entries-gemma-4-good-challenge/ | A live **agent trace panel**: reasoning summary, then tool calls, then checker verdict, then delivery. |
| Grand prize for a hands-free copilot built for a user whose hands are busy | ORION, https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge | An earpiece-first responder view. |
| Scripted scenario run through live inference, plus a labeled cached replay | FireSight README, https://github.com/Youngtak-Jo/FireSight-Google-Deepmind-Hackathon- ; LabTwin 1st place, https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/67 | "Standby → Scenario" button. Both a LIVE mode and a REPLAY mode are labeled on screen. |
| Before/after numbers on screen | LabTwin 54→88; Argus macro-F1 24→46 (same gallery) | A small eval table: distress recall, tag precision/recall, and floor exact-match with biasing on vs off. |
| Sponsor model is load-bearing and named per function | Geo-ML (Best Llama API Usage), https://ai.meta.com/blog/llamacon-hackathon/ | An architecture slide with one row per Meta model. |

## 2. ADD from papers

- **Radio → event trace → time-bounded rules → explainable alerts.** This is the pattern from ATC runtime monitoring (F1 0.85 on real traffic, Aug 2026) and it becomes our world-model harness. Every alert lists the transmissions that triggered it. https://arxiv.org/abs/2608.25926 [V abstract]
- **Roster snapping after ASR.** In ATC, callsign accuracy went from 35.2% to 88.9%, and most of the gain came from cheap entity extraction plus edit-distance matching against the live roster. We snap unit, floor and sector to the roster and floor plan, and keep the raw string. https://arxiv.org/html/2202.03725 [V]
- **Codeword-masked distress.** Firefighters often skip the codeword (Bridgeport: "trapped on the rear stairs"). SeaAlert shows that semantic classifiers degrade gracefully when the codeword is masked. So the keyword is a booster, never a gate. https://arxiv.org/abs/2604.14163 [V abstract]
- **An explicit "unknown" value for every field** reduced hallucination and omission in clinical summarisation. https://www.nature.com/articles/s41746-025-01670-7 [S]
- **Agent-vs-agent traffic generation for eval.** DispatchMAS used caller and dispatcher agents with a fact commons. We use a "crew actor" agent that writes radio lines from a ground-truth script. https://arxiv.org/abs/2510.21228 [V]
- **Self-verification with external tools.** CRITIC: the LLM revises its output after feedback from tools. https://arxiv.org/abs/2305.11738 [V]. Chain-of-Verification: separate verification questions reduce hallucination. https://arxiv.org/abs/2309.11495 [V]. We use the CRITIC shape, but the critic is our **deterministic checker**, not a second LLM call in the hot path.
- **Search-theory belief update** for victim cells: POC' = POC(1-POD)/(1-POC·POD), then renormalise. https://en.wikipedia.org/wiki/Bayesian_search_theory [S]. **Dempster-Shafer conflict mass K** escalates contradictory reports to the IC instead of averaging them. https://scholarship.miami.edu/esploro/outputs/bookChapter/Consensus-Based-Credibility-Estimation-of-Soft-Evidence/991031600301002976 [S]
- **LLM triagers over-escalate** (KTAS multi-agent study). We accept over-triage but show confidence, and the push rate limit protects the crews. https://arxiv.org/abs/2408.07531 [S]

## 3. REVERSE an incumbent assumption: "push everything to everyone" becomes "suppress by default"

Incumbents add channels, screens and feeds. Prepared flags "mayday" for the *dispatcher* (https://www.prepared911.com/blog/how-are-911-centers-using-ai-powered-technology). Every AI transcription product we found sells to the PSAP (services_global §2). Firefighters say the opposite. PNNL reports that responders fear **command pushing feeds** to them (https://www.pnnl.gov/sites/default/files/media/file/RTA_Situational_Awareness.pdf [S]). An IC in NIST SP 1286pt3 asks to "consolidate it down" (https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf [V]).

**Inverted feature: the Relevance Agent.** Its default action is *silence*. It pushes audio to a responder only when an event passes three checks:
1. It is a life-safety item.
2. It matches that responder's floor, sector or assignment.
3. It is not a duplicate within the rate window (at most 1 push per 20 s, except distress or evacuation).

Every push carries a "why you're hearing this" line, for example "sector match: 2F east". The trace panel also shows what the agent **chose not to send**. That suppression count is the agentic proof. It is a decision, not a display.

## 4. REVERSE a hackathon pattern: "transcribe the caller, make the IC dashboard the hero" becomes "transcribe the crew, make the agent trace the hero"

Every voice analog transcribes civilians: FireSight (911 caller), NagarDrishti (drivers), SafeCall (119 callers), Acuífero (volunteers) (hackathons_google §3.3). The 2026 lookalikes (FireflAI, FireSight, Firewatch, ResQueue) all centre a commander dashboard or a 3D view (hackathons_other §2). We listen to **responder-to-responder radio**. Korean AI-119 deployments also cover only citizen calls (Daejeon at 90.3% ASR, Gyeongnam LLM summaries; https://www.gnmaeil.com/news/articleView.html?idxno=597905 [V]). Our hero shot is a split screen: the agent trace in the middle, the IC queue on the left and the responder earpiece on the right. The reason is that judges have already seen incident dashboards. They have not seen an agent decide who hears a mayday.

## 5. SUBTRACT: what we deliberately do not build or claim

- **No 3D digital twin, drone integration or building reconstruction.** That is FireflAI and FireSight territory, a big time sink, and it would make us look like a copy. A 2D floor plan with zones is enough.
- **No localisation claim.** FRST published no per-team accuracy (https://ctil.iu.edu/projects/frst-challenge/index.html [V]), and Korea's crew-tracking R&D runs until 2027 (https://www.hellodd.com/news/articleView.html?idxno=110313 [V]). Positions are *reported* zones with an uncertainty ring.
- **No chat or Q&A surface.** That would read as basic RAG, which is an anti-project. Every model output is a typed event or a tool call.
- **No evacuation-route drawing.** At least four prior entries already do this.
- **No offline claim.** We are API-only.
- **No AR framing.** Fewer than 10% of firefighters picked AR or smart glasses as useful (NIST SP 1286pt3 [V]).
- **No casualty-condition fields beyond "status unknown / conscious / unconscious as reported".** This avoids the medical anti-project. No military or "tactical ops" language either.
- **No SAM video pipeline and no muse-image.** At most one stretch-goal SAM call on a pre-recorded exterior RGB frame, because SAM has a thermal domain gap (https://arxiv.org/pdf/2403.08997 [S]).
- **No WER claims for Muse models, and no "bone conduction works under SCBA" claim.** No benchmark exists for either.

---

## 6. THE PRODUCT

### Name candidates
1. **Earshot.** "No transmission falls out of earshot." Short, memorable, and not tactical.
2. **Readback.** Named after 복명복창 / ATC readback, the acknowledgement loop at the core of the product.
3. **Echo119.** Korean-first; it echoes the right message to the right firefighter.

### One-liner
**Earshot is an AI agent that listens to every fireground radio channel, decides on its own which firefighter needs to hear what, verifies its own picture of the scene, and escalates any mayday or silence that goes unanswered. The agent decides who hears what; the commander decides who does what.**

### Three differentiators (each tied to a sourced pain point)
1. **A distress call can't sit unacknowledged.** Project Mayday found that 35.6% of maydays are missed on the first call, across more than 9,000 maydays (https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/ [V]). At Bridgeport (NIOSH F2010-18), the IC was monitoring two channels and the first mayday "was not acknowledged" (https://stacks.cdc.gov/view/cdc/163519 [V]). The agent merges every channel into one queue and treats 긴급탈출×3 / mayday / 맨다운, including codeword-free distress, as a first-class unacknowledged state. It re-briefs and escalates on a timer.
2. **Hazard intel is routed to the crews it affects, not broadcast to everyone.** Bucheon 2026: flammables were reported at 08:48 and an offensive strategy was announced at 08:52 (https://khan.co.kr/article/202610231144001 [V]). At Wando the urethane information never reached the crews, and the NFA promised real-time delivery of that kind of information (https://www.etoday.co.kr/news/view/2600005 [V]). The Relevance Agent turns a hazard report into sector-matched earpiece briefs and a Danger card the IC must acknowledge.
3. **Accountability from voice, with no new hardware.** At Bucheon there were no radio reports from about 09:12 to 09:35 (same Kyunghyang source). Pyeongtaek's last contact was around 09:30 (press only, https://www.nocutnews.co.kr/news/5686698 [S]). 68% of commanding officers lacked accountability in hand at the time of a mayday (https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/ [V]). SOP 109 §1.1 says that 3 unanswered calls count as a 긴급탈출 situation (Daegu SOP PDF [V]). The world model keeps "last heard" per responder, runs the 3-call check on its own, and sends a one-tap PAR to the earpiece instead of adding roll-call traffic.

### Architecture (one paragraph)
Simulated radios (one stream per channel, Korean and English) feed muse-voice-transcribe, which emits final turns. muse-spark runs a **Triage call** that turns each turn into a typed Event. A **deterministic verifier** checks that the evidence span is a verbatim substring and snaps entities to the roster. The **World-Model Engine** appends the event to its trace, updates beliefs and evaluates time-bounded rules. Rule firings and new events wake the **Coordinator Agent** (muse-spark, Responses API, tools). The Agent's tool calls pass through the **Invariant Checker**, which accepts them or returns an error the agent must fix, CRITIC-style. Accepted actions go to the IC queue (orders wait for approval) and to the responder earpieces (information is delivered on its own). Responder taps return as events.

### Ranked feature list (MVP first; ~8 h solo plus coding agents)

| # | Feature | Hours |
|---|---|---|
| 1 | **Scenario replay harness**: scripted two-channel Bridgeport/Bucheon-style scenario (KO+EN lines adapted from gap_3 §4), TTS'd, degraded with ffmpeg AMR-NB, resampled to 16 kHz, streamed at 1×. Cached-response REPLAY mode plus a LIVE toggle, both labeled. | 1.0 |
| 2 | **ASR streaming**: WebSocket client, 58-term keyword list plus roster, `languageBias:["Korean","English"]`, final turns with startMs/endMs | 1.0 |
| 3 | **Triage call**: strict JSON schema, verbatim evidence check, roster/floor snapping, SOP 107 priority order (distress > Danger > Victim Found > Help Needed > Routine) | 1.0 |
| 4 | **World-Model Engine**: responder table (zone, last-heard, status, ack state), victim zone beliefs (POC update on "searched"), 5 time-bounded rules (unacked distress 10 s; 3 unanswered calls; silent in IDLH N min; low-air without an exit report; victim reported without an assignment), conflict K | 1.5 |
| 5 | **Coordinator Agent loop**: 6 tools, the Invariant Checker, the trace panel streaming reasoning summaries | 1.5 |
| 6 | **Two views**: IC console (ranked queue with ack/approve, zone map, trace) and phone-sized responder "clip-on" view (3 glove-sized buttons: DISTRESS / VICTIM HERE / SEARCHED, plus browser-TTS briefs) | 1.5 |
| 7 | *Stretch:* eval table (20-40 synthetic lines, clean vs degraded, biasing on/off) | 0.5 |
| 8 | *Stretch:* one sam-3.1 call on a pre-recorded exterior frame ("person" / "window") as a likelihood boost into a zone belief | 0.5 |

### How each Meta model is used

**muse-voice-transcribe-1.0 (ASR)**
- Realtime WebSocket `wss://api.meta.ai/v1/asr/realtime`, with auth in the first frame.
- `PCM_16KHZ` s16le mono. There is no 8 kHz option, so we resample client-side.
- `PUSH_TO_TALK` mode, with one socket per simulated channel, so speaker attribution = channel + call-sign self-ID. DIARIZATION mode is only for the long command-post mic.
- `keywords` = gap_3's 58 terms plus the scenario roster (fixed at handshake; reconnect if the roster changes). Partials are CUMULATIVE.
- No confidence field exists, so uncertainty comes from Spark. Audio must be paced in real time, otherwise the socket closes with 1008.
- Source: https://dev.meta.ai/docs/speech-to-text and https://dev.meta.ai/docs/api-reference/voice/schemas [V]

**muse-spark-1.3, call A (Triage)**
- Chat Completions with `response_format` json_schema (strict). `reasoning_effort:"low"`.
- Strict-mode rules: `additionalProperties:false`, every key required, nullable via `anyOf:[{type:X},{type:"null"}]` (undocumented, **test once**).
- Schema: `{speaker_unit, addressee, tag: enum[DISTRESS,DANGER,VICTIM_FOUND,HELP_NEEDED,ROUTINE], distress_fields:{who, what_cause: enum[대원고립,대원추락,대원부상,대원실종,붕괴위험,가스누출,low_air,lost,unknown], where_raw, needs}, location:{floor:int|null, zone_raw, landmark|null}, status_change: enum, victims:[{count|null, where_raw}], asr_uncertain: bool, needs_ack: bool, confidence: number, evidence_span: string}`.
- Prompt: few-shot with codeword-masked distress lines ("출구를 못 찾겠다", "we can't find the way out"), plus the instruction "if unsure between DANGER and ROUTINE choose DANGER with confidence <0.6; never invent a floor; use null".
- Sources: https://dev.meta.ai/docs/structured-output ; https://dev.meta.ai/docs/reasoning [V]

**muse-spark-1.3, call B (Coordinator Agent)**
- Responses API with `previous_response_id` for continuity, `parallel_tool_calls:true`, `tool_choice:"auto"` (the only value allowed), `reasoning.summary:"concise"` streamed to the trace panel, `reasoning_effort:"low"` per event and `"medium"` for a 30 s periodic sweep.
- Tools (6):
  - `update_responder_state(unit, zone, status, evidence_ids)`
  - `mark_victim_estimate(zone, delta, evidence_ids)`
  - `flag_conflict(zone, event_ids, question_for_ic)`
  - `propose_assignment(unit, task, rationale)` → goes to the IC approval queue only
  - `brief_responder(unit, text≤2 sentences, priority, why)` → checker enforces sector match and rate limit
  - `escalate_unacked(event_id, level)`
- Sources: https://dev.meta.ai/docs/tool-calling [V]

**Invariant Checker (deterministic, not a Meta model, shown in the trace)**
- Rejects a brief to a responder whose zone does not match.
- Rejects any order that has not been approved.
- Rejects a victim update that has no evidence ID.
- Requires that every DISTRESS event has either an acknowledgement or a pending escalation.
- Rejections return to the agent as tool errors. The visible fix-and-retry is the "self-verifying" beat.

**sam-3.1 (stretch)**
- One Responses call per noun phrase on a pre-recorded RGB exterior frame. Detections become evidence (likelihood ×2-3), never ground truth.
- Source: https://dev.meta.ai/docs/sam/overview [V]

**Not Meta**
- Earpiece speech uses browser `speechSynthesis`, labeled "TTS: browser (non-Meta)". The Model API has no TTS (https://dev.meta.ai/docs/models [V]).
- Scenario audio TTS and ffmpeg degradation are disclosed in the README.

### Demo: 7 beats, 3:00

| Time | What the judge sees |
|---|---|
| 0:00-0:20 | **Hook**, in the builder's own voice. Text on screen: "Bucheon, 16 Oct 2026: flammables reported 08:48, offensive at 08:52, no radio reports 09:12-09:35." Then "35.6% of maydays are missed on the first call" (Project Mayday). Line: "AI today listens to 911 callers. Ours listens to the crew." |
| 0:20-0:55 | **Overload.** Two channels play overlapping degraded radio (KO+EN). Left: the raw transcript scrolls. Centre: the ranked queue fills, with a per-card latency stopwatch. A Danger card ("인화물질 확인, 2층") pins to the top. |
| 0:55-1:30 | **Agent decides who hears what.** The trace panel streams the reasoning summary, then `brief_responder(구조대2, …, why:"sector 2F")`, then the checker shows ✓. The responder phone plays the brief with "why you're hearing this". Counter: "Suppressed for Engine 21: 7 transmissions (not in sector)." |
| 1:30-2:05 | **Distress with no codeword.** "출구를 못 찾겠다, 공기 얼마 안 남았다" on channel B while the IC is transmitting on A. The DISTRESS card fills the SOP 109 fields and shows the missing "needs" field. The agent asks the crew for it. There is no IC ack for 10 s, so `escalate_unacked` turns the console red. The agent `propose_assignment(RIT → 2F east)`; the **commander taps Approve**; briefs go out. |
| 2:05-2:30 | **Self-verification moment.** Two crews disagree about the 2F east room. Conflict K is high, so `flag_conflict` raises the question to the IC. Then the agent tries to brief a responder in the wrong sector: the checker rejects it, and the agent retries with the correct unit. Separately, Engine 21 has missed 3 calls (SOP 109 §1.1): the rule fires, and a one-tap PAR goes to its earpiece. The responder taps SEARCHED, and the victim belief map updates on the IC side. |
| 2:30-2:50 | **Architecture slide**: three Meta model rows, tool list, checker, plus a non-Meta disclosure (browser TTS). The eval table, if built. |
| 2:50-3:00 | **Limits**: synthetic and degraded audio; decision support, not certified; positions are reported, not tracked; the commander decides orders. |

### Honest limits
- All scenario audio is synthetic TTS with simulated degradation. The only real clip that can go in the repo, Palisades (CC BY 3.0 US, "Audio Provided by Broadcastify"), still needs its licence checked in a browser (gap_3 §1).
- No WER is claimed. Published fireground ASR is about 45% WER (2012, German), and zero-shot Whisper on police radio is about 51%.
- POD, τ, reliability α and the rate limits are hand-set demo parameters.
- Hardware is simulated, and nothing is claimed about bone conduction under SCBA.
- The system is cloud-dependent. Indoor LTE gaps apply (Motorola Assist has the same limitation).

### Risks
1. **Live-API latency or failure during the recorded run.** Spark has no published latency, and ASR enforces real-time pacing. Mitigation: record from REPLAY mode with cached Spark responses, labeled "replay of a live run", and keep one 20 s truly live segment.
2. **The agent reads as a thin wrapper.** Mitigation: the trace panel shows tool calls, checker rejections and the suppression count. Every output is a state change.
3. **Solo 8 h scope.** Features 1-6 are the whole MVP. Cut SAM and eval first, then the map belief layer, before cutting the trace.
4. **Rubric weights are secondary-sourced** (gap_1 B1). Pass/fail gates matter more: Meta models are on every core path, and there are no medical or war elements.
5. **The nullable-schema pattern is undocumented.** Test the `anyOf`-null pattern in the first 15 minutes, with plain sentinel strings ("unknown") as the fallback.
6. **Strict JSON plus Korean output** may fail validation on enums. Keep enums ASCII and put Korean only in free-text fields.

### Evidence to cite in the video and README
- 35.6% of maydays missed on first call, more than 9,000 maydays (Project Mayday, 2021): https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/ . The first-call miss rate is 26% when the IC works from the back of a vehicle with a portable radio and <1.8% on a headset (same source). Use "79 s average to acknowledge" only as "reported by Firehouse, 2019". **Do not use 54%, 36.5% or USFA EFO 82.6%** (gap_2 §c).
- NIOSH F2010-18 Bridgeport: two channels, an unacknowledged mayday, Recommendation #1: https://stacks.cdc.gov/view/cdc/163519
- Bucheon 2026 transcript timeline: https://khan.co.kr/article/202610231144001 . 26 minutes from recognising the isolation to finding the firefighter: https://www.hankookilbo.com/news/article/A2026101912160005075
- Mungyeong 2024, "현장 활동 정보 공유가 미흡": https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810
- Wando 2026, NFA promises real-time hazard information to crews: https://www.etoday.co.kr/news/view/2600005
- SOP 109 긴급탈출 ×3 and the 누가/무엇을/어디에/필요한 것 fields: https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf
- NIST SP 1286pt3: <10% want AR, an earpiece is wanted, "consolidate it down": https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf
- Korean government demand: the 900M KRW AI radio-summary smartwatch R&D call: https://www.news1.kr/it-science/general-science/6259675
- Method papers: ATC runtime monitoring https://arxiv.org/abs/2608.25926 ; ATC roster biasing https://arxiv.org/html/2202.03725 ; SeaAlert https://arxiv.org/abs/2604.14163 ; CRITIC https://arxiv.org/abs/2305.11738

---

## Implications for our product
1. **Frame autonomy as autonomy over information, not over orders.** Routing, dedupe, rate limiting, re-briefing and escalation are autonomous; assignments wait for IC approval. This wins the Agentic prize without breaking the HITL pattern judges now expect.
2. **The trace panel is the hero UI element.** Show reasoning summaries, tool calls, checker verdicts and the suppression count live.
3. **Verification is deterministic and visible.** The evidence-span check, roster snapping, conflict K and invariant rejections are cheap and explainable, and they rebut "LLM hallucination" objections.
4. **Treat SOP 109 as the schema.** Use 긴급탈출×3 with 메이데이 and 맨다운 as aliases, have the agent prompt for missing "needs", and make the 3-unanswered-calls rule a timer. Korean judges and firefighters will recognise it.
5. **Lead with crew radio, not the 911 caller.** That is the open lane in every comparable project and every Korean deployment.
6. **Subtract aggressively.** No 3D, no tracking claims, no chat, no evacuation routes, no AR. The two-screen split plus the trace is enough.
7. **Build REPLAY first, then LIVE.** Real-time ASR pacing and unknown Spark latency make a cached, labeled replay the safe recording path.
8. **Use one statistic everywhere: 35.6%.** Footnote the year and n, and use Bridgeport, Bucheon and Wando as cases.
9. **If time remains, ship an eval table.** Distress recall and floor exact-match with biasing on vs off, on degraded synthetic audio, is the cheapest technical-depth number.
