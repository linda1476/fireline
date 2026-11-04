# Product spec: COMMANDER-FIRST angle

Compiled 2026-11-04 (KST) from every file in `D:\meta\research\`, plus three new checks: NIMS span of control, a sweep for incumbent IC tools, and NFPA 1561 mayday duties.
Tags: **[V]** means verified in a research file or in this pass. **[S]** means secondary. **[I]** means our inference.

## 0. Angle

We design for the incident commander (IC) at the moment of a mayday. The IC holds several radios, is often keyed up on one channel, and is the single point where a distress call either gets answered or gets lost. Project Mayday's position data supports this framing. The first-call miss rate is **26%** when the IC works from the back of a vehicle with a portable radio, **<5.2%** inside a vehicle, and **<1.8%** on a headset [V] (https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/). **Our thesis is that software can give every IC the headset advantage.** All three committed pillars still ship, but each one serves the IC. Pillar 1 is the IC's acknowledgement queue. Pillar 2 delivers what the IC approves to the earpieces. Pillar 3 is the accountability board the IC glances at.

---

## 1. ADD from hackathon winners

| Winner move | Evidence | What we add |
|---|---|---|
| Severity-sorted queue with a human final say | DispatchAI won the Grand Prize, 1st of 293 (https://github.com/IdkwhatImD0ing/DispatchAI) | An **ack queue** sorted by SOP 107 priority. Nothing leaves it without an IC tap |
| Approval gate | Argus: "nothing moves until the commander clicks Dispatch" (https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41). Alert X won 1st with approval before briefing (https://community.ibm.com/community/user/blogs/jennifer-judge/2025/11/13/october-hackathon-winners) | Every agent action is a *proposal card* (approve, edit or reject) |
| Evidence-linked output | Acuífero·Vigía won with "auditable reasoning trails" (https://blog.google/innovation-and-ai/technology/developers-tools/winning-entries-gemma-4-good-challenge/) | Each card carries the verbatim evidence span, the channel, the turn time and a replay button |
| Before/after numbers on screen | LabTwin went from 54 to 88. Argus macro-F1 went from 24 to 46 (https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/67) | An eval table: mayday recall and tag accuracy, clean vs degraded, keyword biasing on vs off |
| Scripted replay plus live run | FireSight "Standby Mode" (https://github.com/Youngtak-Jo/FireSight-Google-Deepmind-Hackathon-) | One-click Bridgeport-pattern scenario plus a labelled live mic run |
| Domain anchor | Prometeo had a veteran firefighter on the team (https://techcrunch.com/2019/10/12/ai-based-firefighter-safety-startup-prometeo-wins-ibm-call-for-code-challenge/) | Korean SOP 109 vocabulary (긴급탈출 ×3) and the Bucheon 2026 timeline as the hook |

## 2. ADD from papers

- **Event trace plus time-bounded rules as the "world model".** An ATC runtime-monitoring paper reached F1 0.85 on real traffic and explains each violation with its evidence (https://arxiv.org/abs/2608.25926). We use five rules, and each alert cites the transmissions behind it.
- **Roster biasing plus post-ASR snapping.** In ATC, callsign accuracy rose from 35.2% to 88.9%, mostly from cheap NER plus edit-distance matching (https://arxiv.org/html/2202.03725). We pass `keywords` at the handshake and run rapidfuzz snapping to the roster afterwards. We keep both the raw and the snapped value.
- **VAD and minimum-duration gate.** About 1% of Whisper clips contained hallucinated phrases, and pauses made it more likely (https://arxiv.org/html/2402.08021v2). Squelch tails and dead keys never reach the classifier.
- **Explicit "unknown".** Telling a model it may answer "unknown" reduced hallucination and omission (https://www.nature.com/articles/s41746-025-01670-7). Every schema field is nullable, and a missing 어디에/Location produces a "location unclear – ask" prompt.
- **Over-escalation is expected.** LLM triagers over-score lower acuity (https://arxiv.org/abs/2408.07531). We accept over-triage but cap what is visible (see §3) and show confidence.
- **Synthetic eval recipe.** SeaAlert ran synthetic distress messages through TTS, simulated VHF noise and ASR, then classified them, including codeword-masked variants (https://arxiv.org/abs/2604.14163). We use the 20 protocol-accurate lines in gap_3 and the tested ffmpeg AMR-NB chain.

## 3. REVERSE an incumbent assumption: "more data and more screens for command"

Incumbents add feeds for command. Tablet Command offers PAR timers. FLORIAN shows "a single customizable screen". Motorola Assist and Prepared transcribe *every* channel for dispatch. SDI/Motorola APAA (Nov 2023) adds a mayday button and motion alarms but does not read what crews say (https://www.firerescue1.com/application-turns-radio-into-a-fireground-accountability-tool-and-more). Practitioners push back. Crouse writes that each new display "take[s] their eyes off something else", and command software is used by only 15% of surveyed firefighters (https://www.firerescue1.com/technology/from-skepticism-to-standard-how-firefighters-adopt-new-technology). A NIST IC quote asks to "consolidate it down" (https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf). FEMA puts a supervisor's manageable span of control at 3–7, optimally 5 (https://emilms.fema.gov/_is0200c/groups/53.html).

**Inverted feature: an attention budget.** The dashboard never shows more than **5 open cards**, borrowing FEMA's span number as a design constant [I]. Routine traffic is collapsed into channel lanes and is never shown as cards. The headline metric is *what the IC did not have to hear*: "142 transmissions, 9 cards, 2 maydays, 0 unacked". A second reversal follows. The IC does not *pull* a PAR, which in the Palisades fire added traffic to an already congested channel (https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire). Instead, every transmission silently counts as a "last heard" check-in.

## 4. REVERSE a hackathon pattern: "transcribe the caller, build a big shared picture"

The 2026 lookalikes all centre a maximal shared picture fed by the *911 caller*: FireflAI, FireSight, Firewatch and ResQueue (hackathons_other.md §1). Firewatch is the exception, since it ingests radio. We do the opposite in two ways. We listen to **the crew's radio** (hackathons_google.md §3.3), and **the AI stays silent except when one of five rules fires**. There is no 3D view and no chat panel. The reason is that the failure in Bridgeport, Bucheon and Jecheon was never a missing map. The right message did not reach the right person in time (Bridgeport F2010-18, https://stacks.cdc.gov/view/cdc/163519; Jecheon, https://www.newsis.com/view/NISX20180111_0000200732).

## 5. SUBTRACT: what we will not build or claim

- A 3D twin, drones, PDR or any localisation accuracy. FRST published no per-team accuracy (https://ctil.iu.edu/projects/frst-challenge/index.html). Positions are *reported zones*.
- AR framing. Fewer than 10% of firefighters chose AR or smart glasses as useful (NIST SP 1286pt3).
- SAM "seeing through smoke", given the measured thermal domain gap (https://arxiv.org/pdf/2403.08997). SAM is only a stretch feature, on one pre-recorded exterior frame.
- Any WER or accuracy figure for Muse models beyond our own synthetic eval. Any offline claim (we are API-only).
- An ASR confidence display. **muse-voice-transcribe returns no confidence and no word timestamps** (https://dev.meta.ai/docs/speech-to-text). Uncertainty is an `asr_uncertain` field that Spark emits.
- Chat or Q&A (this reads as "basic RAG"), auto-dispatch, medical or vital-sign language, war language, and bone-conduction intelligibility claims.
- The statistics "54% missed", "USFA EFO 82.6%" and "36.5%" (gap_2.md says to drop all three).

---

## 6. PRODUCT

**Name candidates:** **FirstCall**, our pick, because it targets "missed on the first call". **LastHeard**. **Headset**.

**One-liner:** FirstCall listens to every fireground channel so the incident commander doesn't have to. Meta's Muse models turn crew radio into a short, acknowledged queue of mayday, danger and victim cards with last-heard timers, and nothing reaches a firefighter's earpiece until the IC approves it.

### Three differentiators, each tied to a sourced pain point

1. **No mayday unacknowledged, across channels.**
   - Pain point: 35.6% of maydays are missed on the first call (>9,000 maydays) (https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/). At Bridgeport, the IC "had to monitor two different radio channels" and a second mayday was needed (https://stacks.cdc.gov/view/cdc/163519).
   - Feature: one queue across channels with semantic detection. Triggers are 긴급탈출 ×3, 메이데이, 맨다운, Mayday and codeword-masked distress.
   - Escalation: if no ack arrives within 10 s, the card pulses and an audible tone sounds.
2. **Radio silence becomes a signal.**
   - Pain point: Bucheon had no radio reports from 09:12 to 09:35, and it took 26 minutes from recognising the isolation to finding the firefighter (https://khan.co.kr/article/202610231144001; https://www.hankookilbo.com/news/article/A2026101912160005075). In Project Mayday data, 68% of COs lacked accountability in hand at the time of a mayday (https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/).
   - Feature: a per-unit "last heard" timer and zone, derived from voice.
   - Rule: SOP 109 §1.1 treats a unit that fails to answer 3 calls as being in 긴급탈출 (https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf). We automate it.
3. **Hazard reports that should change a decision get forced in front of the IC, then gated to crews.**
   - Pain point: at Bucheon, flammables were reported at 08:48 and an offensive strategy was announced at 08:52 (Kyunghyang). At Wando, hazard information did not reach crews, and the NFA committed to real-time delivery of hazard and tactical information (https://www.etoday.co.kr/news/view/2600005).
   - Feature: a conflict rule ("DANGER in zone X after OFFENSIVE declared → confirm strategy?").
   - Delivery: approved briefs go only to crews in the matching zone.

### Feature list, ranked MVP-first (solo + AI agents, budget ~8 h)

| # | Feature | Hours | Cumulative |
|---|---|---|---|
| 1 | **Scenario replay ingest.** Two simulated channels (A = command, B = tactical) built from gap_3 lines, TTS output through the ffmpeg AMR-NB degradation, upsampled to 16 kHz, streamed at 1× per channel to the realtime WebSocket | 1.25 | 1.25 |
| 2 | **Triage extractor.** Spark json_schema event, verbatim `evidence_span` check, rapidfuzz roster/zone snap, VAD/min-length gate | 1.25 | 2.5 |
| 3 | **State engine with 5 rules.** Unacked mayday 10 s. Unit silent N min or 3 unanswered calls. Low air with no exit. DANGER after OFFENSIVE. Victim with no assignment. Each alert cites its evidence | 1.0 | 3.5 |
| 4 | **IC dashboard** (React Router + shadcn). Max 5 cards, ACK/approve/edit, channel lanes, accountability strip (unit · last heard · zone · status), "suppressed N" counter | 1.5 | 5.0 (demoable loop) |
| 5 | **Mayday agent.** On a 긴급탈출 card, Spark proposes the SOP 109 checklist: a 무선 침묵 broadcast, prompts for missing 누가/무엇을/어디에/필요한 것, the RIT assignment and an air-check prompt. The IC approves each item | 0.75 | 5.75 |
| 6 | **Responder phone view.** Shows only approved briefs, via browser TTS labelled "non-Meta", with 3 glove buttons (MAYDAY / VICTIM HERE / SEARCHED, hold to confirm) that feed events | 0.75 | 6.5 |
| 7 | **Eval script and table.** 20 lines × clean/degraded × biasing on/off. Metrics: mayday recall, tag accuracy, unit/floor exact match, card latency | 0.75 | 7.25 |
| 8 | **Record/replay cache** for a deterministic demo mode, plus labels marking live vs replay | 0.25 | 7.5 |
| S1 | Stretch: 2D floor-zone grid with a search-theory POC update on SEARCHED | 0.5 | — |
| S2 | Stretch: sam-3.1 "person"/"window" on one pre-recorded exterior frame → evidence pin | 0.5 | — |

### How each Meta model is used

| Model | Exact use | Constraints we design around |
|---|---|---|
| **muse-voice-transcribe-1.0** | One realtime WebSocket per channel (`wss://api.meta.ai/v1/asr/realtime`), `PCM_16KHZ`, `ENDPOINTING` mode, CUMULATIVE partials shown live in the lane, and `final` triggering triage. `keywords` = the 58 SOP/LUNAR terms from gap_3 plus the live roster. `languageBias: ["Korean","English"]` | No 8 kHz input, so we resample. Pacing is enforced, so we stream at 1× (otherwise the socket closes with 1008). Keywords are fixed per session, so a roster change means a reconnect. No confidence values come back. We attribute speakers by channel plus self-ID, not by diarization (https://dev.meta.ai/docs/api-reference/voice/schemas) |
| **muse-spark-1.3: triage** | Chat Completions, `response_format: json_schema`, `reasoning_effort: "low"`. Schema: `tag` enum `MAYDAY\|DANGER\|VICTIM_FOUND\|HELP_NEEDED\|ROUTINE`; `speaker_unit`; `addressee`; `zone{floor,sector,raw}`; `distress{who,what,where,needs,air}` (SOP 109 + LUNAR); `strategy_declared`; `asr_uncertain`; `confidence`; `evidence_span`. Optional fields are written as `anyOf[{type},{type:"null"}]` and every key is listed in `required`. The prompt carries the SOP 107 priority order, codeword-masked few-shots ("출구를 못 찾겠다", "we can't find the way out"), and the rule "unsure → DANGER, confidence <0.6" | Nullable support is undocumented, so we test it in the first hour. The backend drops any `evidence_span` that is not verbatim (https://dev.meta.ai/docs/structured-output) |
| **muse-spark-1.3: agent** | Responses API with tools `propose_broadcast`, `request_missing_field(unit, field)`, `propose_rit(unit)`, `propose_brief(unit, text, why)` and `flag_conflict(evidence_ids)`. `tool_choice: "auto"` with parallel calls. `reasoning.summary` is shown as the "why" on each proposal. Briefs are ≤2 sentences and carry "why you're hearing this" | `tool_choice` accepts only `auto`. Tools write *proposals* only, never state (https://dev.meta.ai/docs/tool-calling) |
| **sam-3.1** (stretch) | One noun phrase per request on a pre-recorded exterior RGB frame. Boxes become a labelled evidence pin | Never used in smoke or on thermal |
| muse-image-1.0 | Not used, to avoid a decorative use | — |

### Demo: 8 beats in 3:00

| Time | What the judge sees |
|---|---|
| 0:00–0:15 | My face and voice. The Bucheon timeline on screen: 08:48 flammables → 08:52 offensive → 09:12–09:35 silence. Then "35.6% of maydays missed on the first call" |
| 0:15–0:35 | Two channel lanes play degraded audio at the same time, with a visible clock. The IC is keyed on Channel A. The raw transcript scrolls in the background |
| 0:35–1:00 | On Channel B: "긴급탈출 ×3…". The MAYDAY card jumps to the top with a latency badge (for example "3.1 s after key-up"), the evidence span highlighted and a replay button. The SOP 109 fields are filled, and 필요한 것 shows as missing |
| 1:00–1:25 | The 10 s timer runs out, so the card pulses and a tone sounds. The IC taps ACK. The agent proposes a 무선 침묵 broadcast, a RIT assignment and an air-check prompt. The IC approves two and edits one |
| 1:25–1:50 | Split screen: the RIT member's phone hears the brief (TTS, labelled). Another crew's phone shows "filtered: 14 suppressed". The crew taps VICTIM HERE and the board updates |
| 1:50–2:15 | The Bucheon pattern: a DANGER "flammables" card arrives after OFFENSIVE was declared, and a conflict card asks "confirm strategy?". A unit with 3 unanswered calls turns red |
| 2:15–2:40 | Pipeline panel (which Meta model does what). Eval table: mayday recall, tag accuracy, biasing on vs off. The "142 transmissions → 9 cards" counter |
| 2:40–3:00 | Limits: synthetic plus one CC BY clip, simulated hardware, reported zones only, decision support only. Close: "Every mayday, heard on the first call." |

### Honest limits

- The eval audio is synthetic TTS plus codec degradation. The only real clip is Palisades (CC BY 3.0 US; check the licence before pushing). Real SCBA/fireground WER is unknown, and published figures are about 45–51% (https://preview.aclanthology.org/menus/L12-1005/; https://arxiv.org/html/2409.10858).
- Speaker attribution in the demo comes for free because each channel is its own stream. Real PTT attribution is inference.
- Positions are voice- and touch-reported zones. POD, τ and timer thresholds are hand-set.
- The product is cloud-dependent and inherits LTE weakness. The earpiece and display are simulated, and TTS is non-Meta.
- It is not certified. The IC decides.

### Risks

1. **This angle sits in the most crowded lane.** FireflAI, FireSight, Firewatch and ResQueue all centre an IC dashboard. *Mitigation:* lead with what we hide (attention budget) and with crew-radio input, not the board.
2. **Live ASR on degraded Korean audio may miss 긴급탈출.** *Mitigation:* run the eval in hour 2, use keywords, use semantic triage, and keep a replay cache.
3. **Unknown Spark latency** could push cards past 5 s. *Mitigation:* `low` effort, and measure it on screen.
4. **Over-escalation floods the 5-card budget.** *Mitigation:* collapse duplicates, and route low-confidence ROUTINE to the lanes.
5. **Overbuild.** *Mitigation:* stretch items are attempted only after 7.5 h.

### Evidence we cite in the video and README

- "Failure to effectively monitor and respond to Mayday transmissions" (NIOSH F2010-18): https://stacks.cdc.gov/view/cdc/163519
- 35.6% missed on the first call; IC position 26% / <5.2% / <1.8%: https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/
- "현장 활동 정보 공유가 미흡" (Mungyeong, 소방청 2024-03-13): https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810
- Bucheon radio timeline: https://khan.co.kr/article/202610231144001 · Wando real-time info pledge: https://www.etoday.co.kr/news/view/2600005
- SOP 109 긴급탈출 ×3 and the three-unanswered-calls rule: Daegu SOP PDF (above)
- "consolidate it down", and <10% of firefighters want AR (NIST SP 1286pt3): https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf
- Korean AI covers citizen calls, not fireground radio: https://www.gnmaeil.com/news/articleView.html?idxno=597905 · MSIT/MOIS radio-summary R&D: https://www.news1.kr/it-science/general-science/6259675
- Communication factor in 858 of 4,814 near-miss reports: https://pubmed.ncbi.nlm.nih.gov/25816170

---

## 7. Implications for our product

1. Make the **ack queue with a 5-card attention budget** the hero, and use "transmissions in → cards out" as the headline metric.
2. Pitch it as giving every IC the **headset advantage** (26% → <1.8%). This is the strongest single design argument.
3. Use **긴급탈출 ×3 (SOP 109) as the primary Korean trigger** and structure the card by 누가/무엇을/어디에/필요한 것. Use LUNAR plus the emergency for English.
4. Ship the **5 time-bounded rules** with evidence citations as the "world model". The probabilistic grid is a stretch.
5. Every agent action is a **proposal the IC approves**. Pillar 2 delivers only approved briefs, filtered by zone.
6. Run the **degraded-audio eval by hour 2**. If mayday recall on degraded Korean audio is poor, fall back to the clean English hero scenario and say so.
7. **Design around the ASR gaps:** resample to 16 kHz, stream at 1×, and generate uncertainty from Spark. Never show an ASR confidence value we don't have.
8. Use **35.6%** everywhere. Use 79 s only with "Firehouse 2019". Never use 54% or 82.6%.
9. Keep the pitch **anti-surveillance**: "the IC never misses your mayday", not crew tracking (https://pmc.ncbi.nlm.nih.gov/articles/PMC12673935/).
