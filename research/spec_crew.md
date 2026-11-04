# Product Spec: CREW-FIRST angle

Synthesis of all nine research files in `D:\meta\research\` (tech_comms, tech_spatial, hackathons_google, hackathons_other, services_global, services_korea, gap_1, gap_2, gap_3). Written 2026-11-04 KST, about 17 h before the deadline.
Labels: **[V]** verified in the stream's primary source; **[S]** secondary or snippet; **[I]** our inference or design choice.

**How this spec resolves the angle.** The brief says "the clip display is the hero". The evidence says firefighters reject new glass: fewer than 10% chose AR or smart glasses as useful, and they asked for a work-issued wireless earpiece instead (NIST SP 1286pt3 [V], https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf). So the hero is the **decision**: what this one firefighter hears now, what is held back, and what they can say back with one gloved touch. The display is a radio accessory with three lines of text and four buttons. It never carries the AR label.

---

## 1. ADD (from hackathon and competition winners)

| Winner move | Evidence | What we add |
|---|---|---|
| Hands-free copilot for a busy-handed user | ORION, Gemini Live Agent grand prize (https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge) [V] | "ORION for the fireground": the user is the firefighter inside. |
| Severity queue, human has the final say | DispatchAI, Grand Prize, 1st of 293 (https://github.com/IdkwhatImD0ing/DispatchAI) [S] | Compact IC queue; distress stays open until acknowledged. |
| Approval gate, evidence on every output | Argus, SpatialTwin (https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41) [V] | Orders need IC approval. Each brief carries an evidence span, replayable audio and a live/replayed/synthetic label. |
| Numbers on screen | Argon SF winner 54→88; Argus F1 24→46 (https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/67) [V] | Eval table plus a latency clock. |
| Voice-to-structure for crews | FireForm, 1st at UN Reboot the Earth (https://news.ucsc.edu/2025/11/ai-solutions-wildfire-mitigation-reboot-the-earth-hackathon/) [V] | A spoken distress call becomes an SOP 109 card. |
| One real artefact, labelled | Firewatch's Palisades audio, CC BY 3.0 (https://github.com/Anastassy/fire-incident-copilot) [V] | 206 s Palisades sanity check, "Audio Provided by Broadcastify"; verify the licence in a browser first. |
| Scripted scenario, live inference | FireSight "Standby Mode"; LabTwin cached replay [V] | Replayed radio, live model calls, labelled fixture fallback. |

## 2. ADD (from papers)

- **Roster snapping.** In ATC, post-ASR named-entity recognition plus edit-distance matching against the live callsign list raised callsign accuracy from 35.2% to 88.9% (https://arxiv.org/html/2202.03725) [V]. We do the same with unit names, floors and zones. We store both the raw string and the snapped one.
- **Semantic distress detection with codeword-masked examples.** In SeaAlert, transformer and LLM classifiers held up better than lexical methods when the distress codeword was removed (https://arxiv.org/abs/2604.14163) [V]. At Bridgeport the distress call was "trapped on the rear stairs", with no codeword. So the keyword boosts detection but does not gate it.
- **Explicit `unknown` and a verbatim evidence span.** Forcing "unknown" cut hallucination in clinical summaries (https://www.nature.com/articles/s41746-025-01670-7) [S]. The backend drops any span that is not a substring of the transcript [I].
- **VAD gate.** About 1% of Whisper clips contained hallucinated phrases, more often after pauses or non-speech (https://arxiv.org/html/2402.08021v2) [V]. Squelch tails and dead keys never reach the classifier.
- **Event trace plus time-bounded rules.** ATC runtime monitoring reached F1 0.85 on real traffic (https://arxiv.org/abs/2608.25926) [V]. Our rules: a mayday not acknowledged within 10 s escalates; three unanswered calls are treated as 긴급탈출 (SOP 109 §1.1); a hazard reported in a sector is pushed to every unit in that sector; a silent unit inside escalates to the IC.
- **SOP 107 priority order as the ranking.** The order is 대원안전 > 구조대상자 > 주요요소 > 전략 (https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf) [V]. We map it to MAYDAY > DANGER > VICTIM_FOUND > HELP_NEEDED > ROUTINE.
- **Push/pull rule.** Responders fear command pushing feeds (PNNL-25158 [S]). Push only life-safety items for your own sector, at most one per 20 s except distress and evacuation; everything else is pull [I].
- **Eval recipe.** Synthetic lines → TTS → AMR degradation → ASR → classifier, as in SeaAlert and DispatchMAS (https://arxiv.org/abs/2510.21228) [V]. Score floor and unit by exact match.

## 3. REVERSE (incumbent assumption)

**Incumbent assumption: AI radio transcription serves the dispatcher.**
- Prepared flags "mayday" for 911 dispatchers. Prepared and Carbyne were bought by Axon.
- Motorola Assist is cloud transcription aimed at the PSAP.
- RapidSOS Harmony travels with the 911 call.
- Sources: https://www.prepared911.com/blog/how-are-911-centers-using-ai-powered-technology ; https://securityjournalamericas.com/axon-agreement-to-acquire-carbyne/ [V].
- Korean AI 119 pilots are all on the citizen-call side, for example Daejeon at 90.3% ASR (https://www.cctoday.co.kr/news/articleView.html?idxno=2225697) [V].

**Inverted:** the AI listens *on behalf of the firefighter inside* and speaks to them only when something changes their next move. Why it matters: at Wando 2026, urethane-foam information never reached the dispatched crews (https://www.etoday.co.kr/news/view/2600005) [V], although 119현장지원시스템 had been nationwide since 2022. An app opened with gloves on, in smoke, is not delivery [I].

## 4. REVERSE (hackathon pattern)

**Pattern:** the 2026 lookalikes (FireflAI, FireSight, Firewatch, ResQueue) put the commander dashboard at the centre. They transcribe the *911 caller* and show everyone one shared picture (hackathons_other §2; hackathons_google §3.3).

**Opposite:** we centre the responder's three-line surface and crew radio, and our headline metric is **what we suppress**. For example: "Kim heard 2 of 31 transmissions, and both were about her sector."

**Reason:**
- No reviewed project triages responder-to-responder radio or filters intel per responder (open lane, [I]).
- The fire service's own research rejects more screens. Command software is used by 15% of surveyed firefighters and GPS tracking by 4% (https://www.firerescue1.com/technology/from-skepticism-to-standard-how-firefighters-adopt-new-technology) [V].
- A deliberate, explained silence is the agentic decision the Best Agentic prize rewards.

## 5. SUBTRACT

- **No 3D twin, drones or evacuation-route generator**: crowded (four or more prior entries) and a time sink.
- **No localisation accuracy claims.** FRST published no per-team accuracy (https://ctil.iu.edu/projects/frst-challenge/index.html) [V]; Korea's 2.5 m / 1 m target is R&D through 2027 (https://www.hellodd.com/news/articleView.html?idxno=110313) [V]. Positions are zone labels with an uncertainty radius that grows with time.
- **No AR language; no bone-conduction, heat or IP claims.** No SCBA study exists, and exposed mics and cords failed first in NIST heat tests (https://www.sciencedaily.com/releases/2006/09/060930094159.htm) [V].
- **No chatbot or Q&A** (reads as basic RAG). **Nothing medical**: 구조대상자 means location and status only.
- **No offline claim**, no muse-image, and SAM 3.1 only as a stretch goal.
- **No surveillance framing.** Rank-and-file firefighters oppose wearables (https://pmc.ncbi.nlm.nih.gov/articles/PMC12673935/) [V].
- **Statistics we drop:** 82.6% (USFA EFO), 54%, 36.5%, and any Korean communications-cause percentage (gap_2) [V].

---

## 6. PRODUCT

### Name candidates
1. **Earshot**: the crew hears only what is within its earshot of danger. This is the preferred name.
2. **Last Heard**: named after the accountability timer.
3. **Hoseline**: firefighters follow a hose line to the exit, as the Pyeongtaek survivors did.

### One-liner
Earshot is an AI radio partner for the firefighter inside. It listens to every channel, says only what changes your next move in two sentences or fewer, and turns one gloved hold or a spoken "긴급탈출" into a structured distress card the IC cannot miss.

### Three differentiators, each tied to a pain point
1. **A per-responder relevance agent decides push, hold or suppress.**
   - Pain: hazard information reached the system but not the crew. At Bucheon, flammables were reported at 08:48 and offence was declared at 08:52 (Kyunghyang [V]). At Mungyeong, the official finding was "현장 활동 정보 공유가 미흡" (https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810) [V].
   - Constraint: avoid overload (NIST SP 1286pt3 [V]).
2. **Distress takes one hold or one utterance and becomes an SOP 109 card with an ack-or-escalate loop.**
   - The card fills 누가 / 무엇을 / 어디에 / 필요한 것, and LUNAR for English.
   - Pain: 35.6% of maydays are missed on the first call, across more than 9,000 maydays (https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/) [V].
   - Pain: at Bridgeport the first mayday "was not acknowledged" (https://stacks.cdc.gov/view/cdc/163519) [V].
   - Pain: Korean radios are hard to use with gloves and SCBA (korea.kr [V]), and switching channels on the LTE radio takes about 8 touch steps (https://www.fpn119.co.kr/132299) [V].
3. **Voice-derived "last heard" accountability, including SOP 109 §1.1: three unanswered calls count as 긴급탈출.**
   - Pain: Bucheon had no radio reports from about 09:12 to 09:35, and it took 26 minutes from recognising the isolation to finding the firefighter (https://www.hankookilbo.com/news/article/A2026101912160005075) [S].
   - Pain: 68% of commanding officers lacked accountability in hand at the time of a mayday (https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/) [V].

### Features, ranked MVP-first (solo plus AI agents, about 8 h)

| # | Feature | h |
|---|---|---|
| 1 | Radio replay into a realtime transcribe WebSocket, one per simulated channel (지휘망 / 작전망). 16 kHz PCM paced at 80 ms frames, `keywords` and `languageBias`. Audio streams unbroken, silence included; a VAD/min-duration gate drops empty or noise-only *finals* before Spark | 1.5 |
| 2 | Spark event extractor (JSON schema), evidence-span check, roster and zone snapping | 1.0 |
| 3 | **Crew wearable view.** Phone-sized frame with three lines: tag, what changed (or "nearest reported 구조대상자: 2F 동측 사무실" when one exists), what to do. Four full-width hold-to-confirm buttons: 긴급탈출 / 구조대상자 여기 / 검색완료 / 지원요청. Earpiece output through browser TTS, labelled non-Meta | 1.5 |
| 4 | Responder relevance agent: push, hold or suppress, with a rate limit, deduplication and a "why you hear this" line | 1.0 |
| 5 | World state and rules: last-heard timers, unacked-distress escalation, three-unanswered rule, distress card that prompts for missing SOP 109 fields | 1.0 |
| 6 | Crew voice-mark: holding a button plays a labelled replayed clip through transcribe in PUSH_TO_TALK mode, then Spark, then a pin on the zone. A live mic is a stretch goal (0.5–0.75 h, taken from the IC grid) | 0.25 |
| 7 | Compact IC pane: ranked queue, Ack / Approve buttons, 2D zone grid with pins | 0.75 |
| 8 | Eval: 20 gap_3 lines (10 KO, 10 EN) plus 4 codeword-masked lines, tested clean vs AMR-degraded and biasing on vs off | 1.0 |
| | **Total** | **8.0** |
| S1 | Stretch: sam-3.1 on a pre-recorded exterior frame ("person", "window"), used as a likelihood boost for a zone | 0.75 |
| S2 | Stretch: Palisades clip as a real-audio sanity check; MMS-TTS as an open-weights Meta voice path | 0.5 |

### How each Meta model is used

**muse-voice-transcribe-1.0** (https://dev.meta.ai/docs/speech-to-text)

- *Command-side listener:* one `wss://api.meta.ai/v1/asr/realtime` session per channel; `PCM_16KHZ` (upsampled from 8 kHz), `mode: ENDPOINTING`, `partialMode: CUMULATIVE`; triage starts on `final:true`. Stream at 1× real time or the server closes with 1008.
- `keywords`: gap_3's 58-term list (긴급탈출, 맨다운, 메이데이, 대원고립, 인화물질, 공기잔량, Mayday, PAR, RIT…) plus unit names; `languageBias: ["Korean","English"]`. Both are fixed at the handshake, so a roster change means reconnecting.
- Speaker = channel + self-ID ("지휘대장, 여기 ○○구조대…") snapped to the roster; diarization letters only inside a long transmission.
- *Crew-side voice mark:* `PUSH_TO_TALK` mode keyed by the hold button, so Meta ASR also runs on the firefighter's side.

**muse-spark-1.3**, call A: event extractor
- Chat Completions, `response_format` json_schema, `strict:true`, `reasoning_effort:"low"`. Plain-object root, `additionalProperties:false`, all keys `required`; optional fields as `anyOf:[{type},{type:"null"}]` (nullable is undocumented, so test once; gap_1). Fields:
```
{ speaker_unit, channel, tag: MAYDAY|DANGER|VICTIM_FOUND|HELP_NEEDED|ROUTINE,
  distress: { who, what: 대원고립|대원추락|대원부상|대원실종|붕괴위험|가스누출|other|null, where_raw, needs, air },
  location: { floor:int|null, zone_id|null, raw }, hazard_terms:[...],
  status_change: entering|exiting|low_air|trapped|ok|none,
  needs_ack, confidence, asr_uncertain, uncertain_reason, evidence_span }
```
- Prompt: SOP 107 priority rules; few-shots K1–K10 / E1–E10 plus masked distress ("출구를 못 찾겠다, 공기 얼마 없다", "can't find the way out, low air"); "If unsure between DANGER and ROUTINE choose DANGER, confidence < 0.6. Never invent a floor; use null." ASR has no confidence field, so uncertainty is Spark's `asr_uncertain`.

**muse-spark-1.3**, call B: responder relevance agent
- Responses API, `reasoning.effort:"medium"`, `reasoning.summary:"concise"` (shown on the IC pane as "why"). Triggered by each new event or rule firing.
- Parallel tools; `tool_choice` stays "auto", the only allowed value:
  - `get_unit_state(unit)`
  - `get_sector_events(zone, since)`
  - `send_brief(unit, text≤2 sentences, priority, reason, evidence_id)`
  - `hold(unit, event_id, reason)`
  - `request_missing_field(unit, field)`
  - `escalate_to_ic(event_id)`
  - `propose_order(order, units)`, which requires IC approval
- If `reasoning.summary` does not arrive (it is not guaranteed), the "why you hear this" line falls back to `send_brief.reason`.
- Deterministic guardrails sit outside the model: the rate limit, distress always going to the IC, and orders never being auto-sent.

**sam-3.1** (stretch)
- One noun phrase per request on a pre-recorded exterior frame.
- A detection becomes evidence, raising a zone's victim log-odds by about 2–4×. It is never treated as ground truth, and it is never claimed to see through smoke.

**Non-Meta, disclosed:** the earpiece voice uses browser `speechSynthesis`. The Model API has no TTS (https://dev.meta.ai/docs/models) [V].

### Demo: 3:00, two panes (wearables on the right, IC on the left), clock on screen

| Time | What the judge sees |
|---|---|
| 0:00–0:15 | **Hook**, black screen, presenter's own voice. Bucheon timeline: "08:48 flammables reported → 08:52 offensive → 09:12–09:35 silence." Then 35.6%. |
| 0:15–0:30 | **Setup.** Label reads "Synthetic scenario modelled on Bucheon/Bridgeport; radio replayed, every model call live." Two wearables: FF Kim (2F east) and FF Park (roof). |
| 0:30–1:00 | **Filter.** Thirty transmissions roll on two channels. An adjacent crew says "2층 동측 인화물질". Kim's earpiece says "2층 동측 인화물질 보고. 퇴로는 정면 계단." Park hears nothing, and his counter reads "suppressed 9". The tag-latency clock is visible. |
| 1:00–1:20 | **One-touch victim.** Kim holds 구조대상자 여기 and says "계단 우측 사무실 1명". A pin appears on the IC grid, and the rescue crew gets a brief. |
| 1:20–1:55 | **Distress loop.** Kim: "긴급탈출 ×3, 대원고립, 2층 동쪽 창고". The card fills 누가 / 무엇을 / 어디에, and 필요한 것 shows *unknown*. The agent asks Kim through the earpiece; she answers "공기용기, 사다리". The IC has not acknowledged within 10 s, so the card escalates. The IC acks. 무선 침묵 goes to every earpiece, and the IC approves the RIT order. |
| 1:55–2:15 | **Silence pays off the hook.** Park has gone quiet. The agent calls Park through his earpiece three times and counts no PTT reply. The IC card reads "3회 무응답 = 긴급탈출 상황 (SOP 109 §1.1)" with "last heard 4:12, roof" and the evidence clips. |
| 2:15–2:40 | **Under the hood.** Pipeline diagram naming each Meta model. Eval table: distress recall, codeword-masked recall (N/4), floor/unit exact match, clean vs degraded, biasing on vs off. Only measured numbers are shown. |
| 2:40–3:00 | **Limits and close.** "Simulated hardware; decision support, not certified; positions are reported, not tracked." Final line: "The IC never misses your 긴급탈출." |

### Honest limits
- No fireground or SCBA ASR benchmark exists; real police radio scored about 51% WER zero-shot (https://arxiv.org/html/2409.10858) [V]. Our audio is synthetic and degraded, plus one real clip.
- Hardware is simulated. Positions are reported zones, not tracking. Thresholds and rate limits are hand-set.
- Cloud-dependent; inherits radio and LTE dead zones. Sits on top of LMR, PASS and CAD.
- Speaker attribution in the demo comes from channel plus self-ID snapped to the roster, with diarization letters as a tiebreaker. It is not validated on real overlapping traffic.

### Risks
1. **Crew-side Meta use could look thin.** The earpiece voice is non-Meta. Mitigation: show the Spark agent's push/hold decisions and reasoning summary, and the PTT transcribe on the crew side.
2. **The live demo could die** on WebSocket pacing (1008), latency or rate limits. Mitigation: a cached fixture mode, labelled, plus a rehearsed recording.
3. **Over-triage floods the IC** (LLM triagers over-escalate, https://arxiv.org/abs/2408.07531 [V]). Mitigation: confidence shown, deduplication, IC confirmation.
4. **Spark latency is unpublished.** Keep the extractor on low effort and measure it on screen.
5. **The Palisades licence is unverified first-hand.** Drop the clip if the Broadcastify page cannot be checked.

### Evidence to cite in the video and README (quotes under 15 words)
- Project Mayday 35.6%: https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/
- NIOSH F2010-18, "the IC had to monitor two different radio channels": https://stacks.cdc.gov/view/cdc/163519
- Bucheon 2026 timeline (Kyunghyang); Mungyeong "현장 활동 정보 공유가 미흡" (korea.kr); NFA's post-Wando promise to deliver hazard information to crews in real time (Etoday).
- SOP 109: "긴급탈출" ×3, with 누가 / 무엇을 / 어디에 / 필요한 것 (Daegu SOP PDF).
- NIST SP 1286pt3: under 10% want AR or smart glasses; a wireless earpiece is wanted.
- Korea R&D call (900M KRW, Aug 2026) for an AI radio-summary smartwatch: https://www.news1.kr/it-science/general-science/6259675
- ATC roster biasing 35.2% → 88.9% (arXiv 2202.03725).

---

## 7. Implications for our product

1. **The hero is the decision, not the glass.** The key shot is Kim hearing one sentence while Park hears nothing.
2. **Measure suppression as a feature**: report "heard N of M" per responder next to distress recall.
3. **긴급탈출 is the primary Korean trigger** (SOP 109), with 메이데이 and 맨다운 as aliases. Detection is semantic, with codeword-masked few-shots.
4. **Make Spark visibly load-bearing on the crew side.** Use the Responses API agent with parallel tools and a reasoning summary, plus PTT transcribe for crew voice marks. This answers the risk that the non-Meta TTS hides the Meta work.
5. **The ack-or-escalate loop and the three-unanswered rule** are the agentic beats for the $5K prize. Both are deterministic rules wrapped around model output.
6. **Every claim carries its source and year.** Use 35.6% everywhere and drop 82.6% and 54%.
7. **Build in the order of the table.** If hour 6 slips, cut the IC grid before the wearable view and cut SAM entirely.
8. **For Most Viral, use a 20-second split clip:** chaotic two-channel audio and waveform on one side, a single calm earpiece sentence on the other.
