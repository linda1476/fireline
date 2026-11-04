# Technical Papers A: Communications & Command

Stream: speech recognition on emergency radio, LLM/NLP for incident comms, IC decision support, agentic info triage.
Compiled 2026-11-04 for the Meta Global AI Developer Hackathon (deadline 5 Nov 2026 11:00 KST).

Labels used below:
- **[verified]**: read on the primary page (arXiv abstract/HTML, HF card, etc.).
- **[snippet]**: the number reached us only through a search-result snippet or secondary source. Treat as unverified.
- **[inference]**: our own reasoning, not a source claim.

---

## 0. Corrections and caveats for other streams

- **Bridgeport 2010 report number.** Coverage points to NIOSH FACE **F2010-18** ("A Career Lieutenant and Career Fire Fighter Found Unresponsive at Residential Structure Fire – Connecticut"). It is *not* F2010-04. Fire was 24 Jul 2010; LODDs Lt. Steve Velasquez and FF Michael Baik. [verified via secondary article: https://www.firefighternation.com/fire-leadership/federal-investigation-finds-mayday-failures-in-fatal-bridgeport-fire-2/ ; the CDC PDF URL we tried 404'd]
- There is no published WER or eval for Meta's `muse-voice-transcribe-1.0` on radio audio that we found. Do not claim one. Measure our own (Section 5).

---

## 1. Speech recognition on emergency radio / PTT / noisy tactical audio

### 1.1 Police radio ASR (Srivastava et al., SLT 2024), the best public analog to fire radio
- Source: arXiv:2409.10858, submitted 17 Sep 2024. https://arxiv.org/abs/2409.10858 , full results: https://arxiv.org/html/2409.10858 [verified]
- **Data:** 62,080 manually transcribed police radio transmissions, 46.2 h (Chicago-area). Train/dev/test 44,664 / 8,714 / 8,702. Corpus and annotation pipeline released publicly.
- **Utterances are tiny:** 96.5% of training utterances are 10 s or shorter. The mean is about 2.7 s [inference: 46.2 h / 62,080]. Many are handshake/call-sign exchanges.
- **WER (dev):**
  - Whisper large-v2 zero-shot 57.4%; Whisper large-v3 51.4% (test 50.8%)
  - Parakeet TDT 1.2B 48.2%
  - NeMo Conformer-CTC 616M: 53.8% zero-shot, then **27.0%** after fine-tuning (test 27.3%)
  - Best custom SSL model (HuBERT+WavLM Conformer) about 40%
  - **Human inter-annotator WER: median 25.9% (professionals), 28.9% (others).** So fine-tuned ASR reaches roughly human level, and *humans are also bad* at this audio.
- **Failure modes:** digits and code words. Examples: "two"→"twenty", "three"→"thirty", "six"→"sixty", "four"→"for", and the code word "robert"→"roberts". About 13% of utterances contain a segment that humans also marked unintelligible.
- **Borrow:** unit IDs, floor numbers and addresses are the highest-risk tokens. Bias for them and verify them (see 1.3). Expect short, clipped transmissions, not paragraphs.

### 1.2 Firefighter / SAR-specific corpora
- **RescueSpeech** (German SAR, Sagar et al., Jun 2023, arXiv:2306.04054). Real speech from simulated rescue exercises, noisy and reverberant, emotional. The authors say state of the art is "still far from reaching an acceptable level". Data, recipes and models are public. **German only, so not usable for our EN/KO eval.** https://arxiv.org/abs/2306.04054 [verified abstract; WER figures ~23% best / ~45% Whisper are snippet]
- **Firefighter TETRA broadcast channel** (LREC 2012, German exercise corpus). Reports WER 45.2% and argues that keyword extraction needs a strong recognizer underneath. https://aclanthology.org/L12-1005/ [snippet]
- **ASR on public-safety dispatch channels** for interstate incident detection, keyword flagging ("fire", "crash"). Smart Cities (MDPI) 8(5):157, 2025. https://www.mdpi.com/2624-6511/8/5/157 [snippet; page 403'd]
- **No English fire-radio corpus with WER results was found.** Closest open raw audio: Broadcastify's Jan 2025 LA fires archive (LA County Fire dispatch plus Palisades/Eaton command channels, daily tar.gz, described as freely available for community analysis). https://www.broadcastify.com/events/2025-01-lafire/ [snippet; page 405'd. Check terms before redistributing clips.]

### 1.3 Contextual / keyword biasing (strongest borrowable trick)
- **ATC callsign biasing** (Nigmatulina et al., Idiap, Feb 2022, arXiv:2202.03725). Callsigns of aircraft currently on radar are used to (a) rescore ASR lattices and (b) "NLP-boost": NER extracts the callsign, then a weighted Levenshtein re-ranks it against the live callsign list. Callsign accuracy: NATS **35.2% → 88.9%**, LiveATC 42.8 → 88.5, Vienna 48.4 → 84.3. Most of the gain comes from the cheap **post-ASR roster matching**, not from lattice rescoring. https://arxiv.org/html/2202.03725 [verified]
- **Direct analog for us [inference]:** (1) pass the live roster (unit/crew names, "Engine 3", "Rescue 1", Korean call signs), floor/sector names and "mayday/긴급탈출/고립" into muse-voice-transcribe keyword biasing; (2) after transcription, snap any extracted unit or location to the nearest roster/map entity by edit distance, and keep the raw string for audit. This is cheap and defensible "technical depth".
- ATC benchmark context: ATCO2 corpus (4 h gold transcripts with callsign/command/value NER), arXiv:2211.04054 https://arxiv.org/html/2211.04054 ; ATC radio WER of about 5–10% after accent/noise fine-tuning, arXiv:2502.20311 https://arxiv.org/html/2502.20311v1 [snippet]. ATC is much cleaner and more scripted than fireground traffic.

### 1.4 ASR hallucination on silence and noise
- **"Careless Whisper"** (Koenecke et al., ACM FAccT 2024, arXiv:2402.08021). About **1% of 13,140 clips** contained entire hallucinated phrases. 38% of those hallucinations were harmful (violence, false authority). They were more likely with longer non-vocal durations and pauses. https://arxiv.org/html/2402.08021v2 [verified via abstract and Cornell coverage https://news.cornell.edu/stories/2024/06/ai-speech-text-can-hallucinate-violent-language]
- **Borrow [inference]:** radio has squelch tails, dead keys and open-mic noise. Gate with VAD and a minimum-speech-duration check before any transcript reaches the classifier. Never let an empty or noise-only transmission get a "Danger" tag. Show the audio clip next to every AI tag so a human can replay it.

### 1.5 Speech quality, masks, codecs
- **Mission-critical voice + ASR robot** (Janak, …, Jennings, Schulzrinne, arXiv:2509.13724, Sep 2025, motivated by NIST PSCR). Testbed emulating MCV systems. An ASR "robot" stands in for human listeners, scored with a Levenshtein-based QoE metric. **Humans beat every ASR configuration. The codec significantly affects both humans and ASR.** https://arxiv.org/abs/2509.13724 [verified]
- SCBA masks degrade intelligibility and quality (USFA Voice Radio Communications Guide, https://www.usfa.fema.gov/downloads/pdf/publications/voice_radio_communications_guide_for_the_fire_service.pdf ). NIST AMR-codec fireground tests found the worst case was chainsaw noise plus mask (https://www.nist.gov/system/files/documents/2016/08/31/13-493_1.pdf). [snippet]

### 1.6 Keyword spotting for "mayday"
- No deployed or evaluated mayday detector was found in the literature. A patent cites an industry KWS benchmark of about **70% detection at 5 false alarms/keyword/hour** (https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11295739). [snippet] That FA rate would be unacceptable for a mayday alarm without a human confirm step [inference].
- **Codeword masking matters:** distressed firefighters often do not say "mayday" ("we're trapped on the rear stairs"; see Bridgeport). SeaAlert (Section 2.2) explicitly tests distress messages with the codeword removed or replaced, and found transformer classifiers degrade more gracefully than lexical baselines. **So use LLM semantic classification, with the keyword as a booster, not a gate.**

### 1.7 Speaker attribution on shared channels
- No PTT-specific diarization paper was found (general diarization: RadioTalk corpus https://arxiv.org/pdf/1907.07073).
- [inference] PTT is half-duplex, so overlap is rare and each key-up is one speaker. Attribute speakers by **channel + key-up event + self-identification in the utterance** ("Command, Engine 3…"), extracted by the LLM and snapped to the roster. Use the diarization from muse-voice-transcribe only within a single long transmission. In the simulated demo, each simulated radio is its own stream, so attribution is free. Say so honestly.

### 1.8 Latency
- 3GPP TS 22.179 MCPTT KPIs: access time <300 ms (95%; 99% for emergency/imminent-peril calls), **mouth-to-ear <300 ms (95%)**, end-to-end access <1000 ms. https://itecspec.com/3gpp/22.179/s/6.15.3.1 [snippet via spec mirror]. A blog citing NIST IR 8328 claims P25 Phase 2 mouth-to-ear is about 602 ms (https://lteps.blogspot.com/2016/04/mcptt-latency-requirements.html). [snippet, unverified]
- **These are voice-transport specs, not AI-tagging specs.** No published latency requirement for AI triage of radio exists that we found. [inference] Proposed target: **priority tag visible to the IC within one transmission turn (≤3–5 s after key-down release)**. Voice relay is never blocked by the AI: the AI annotates in parallel and never sits inline.

---

## 2. LLM / NLP for incident communications

### 2.1 Emergency-call triage and structured extraction
- **LLM-based real-time speech reconstruction and call prioritization** (Venkateshperumal et al., arXiv:2412.16176, Dec 2024). Twilio + AssemblyAI transcription + RAG over past transcripts, filling gaps in incomplete speech and prioritizing by severity. Evaluated only with BLEU/ROUGE and "high precision" with no field-level numbers. This is **an example of weak evaluation to avoid copying.** https://arxiv.org/abs/2412.16176 [verified abstract]. Journal version: "LLM-Augmented VoIP for Emergency Call Triage", severity 1–4. https://www.sciencedirect.com/science/article/pii/S3050644125000106 [snippet]
- **LLM-Assisted Crisis Management** (Otal & Canbaz, arXiv:2402.10908, Jan 2024). Llama 2 classifies emergencies from posts and 911 descriptions, gives telecommunicator guidance, and notifies agencies. Abstract reports no metrics. https://arxiv.org/abs/2402.10908 [verified]
- **SeaAlert** (Atia, Aperstein, Apartsin, arXiv:2604.14163, Mar 2026, v2 Jul 2026). This is **the closest methodological template to ours.** LLM-generated maritime distress messages (including variants with the distress codeword omitted or replaced) → TTS → **simulated VHF radio noise** → ASR → severity classification + LLM field extraction. Findings: transformer classifiers degrade more gracefully than lexical ones under ASR noise and codeword masking, and LLM extraction beats regex on noisy fields. Their eval uses fuzzy match (partial-ratio ≥70) against stored generation metadata. [inference] That threshold can hide wrong floor numbers, so use exact match for floor/unit. https://arxiv.org/abs/2604.14163 [verified abstract; extraction-eval detail via snippet]
- **"Unknown" reduces hallucination:** in clinical summarization, telling the model to output "unknown" when information is missing significantly reduced hallucination and omission (npj Digital Medicine 2025). https://www.nature.com/articles/s41746-025-01670-7 [snippet]. See also arXiv:2504.19061 https://arxiv.org/pdf/2504.19061 .
- **LingVarBench** (arXiv:2508.15801): entity extraction from phone transcripts degrades with disfluency, interruption and overlap, all typical of fireground radio. https://arxiv.org/abs/2508.15801 [snippet]

### 2.2 Radio traffic → event trace → rule checks (ATC, 2026)
- **Formal runtime monitoring of spoken ATC procedures** (Luvini, Longo, Armando, Russo, arXiv:2608.25926, 26 Aug 2026). Radio speech → entity-linked events → merged with surveillance into a timestamped trace → ICAO obligations as **time-bounded temporal formulas** → explainable violations listing breached obligation + supporting observations. **F1 0.85** vs blind human annotation on real traffic. Correct verdict on all 1,495 synthetic situations. It re-identified the deviations documented in 2 real accident reports. https://arxiv.org/abs/2608.25926 [verified abstract]
- **SCOPE** readback monitoring: 91.05% accuracy / 91.01% F1 with an untrained local Qwen3-14B, 4-shot, intent+slot extraction incl. callsigns. https://arxiv.org/html/2605.29543v1 [snippet]
- **Borrow [inference]:** this is exactly the "world-model harness" pattern. Each transmission becomes a typed event `{t, unit, location, status, tag, evidence_span}`. The state engine evaluates time-bounded rules ("unit inside IDLH with no transmission for 5 min → prompt IC for PAR"; "mayday not acknowledged within 10 s → escalate") and every alert cites the evidence transmissions. It is explainable, deterministic, and easy to show in a demo.

### 2.3 Priority ranking and over-escalation
- **KTAS multi-agent ED triage** (Han & Choi, arXiv:2408.07531, Aug 2024). Agents are Triage Nurse, Emergency Physician, Pharmacist and ED Coordinator. It is accurate on KTAS 1–2 but tends to **overestimate urgency for levels 3–5** (snippet). https://arxiv.org/abs/2408.07531 . Medical domain, so cite only as evidence that *LLM triagers over-escalate*. Do not position our product as medical.
- **DispatchMAS** (Li, Fan et al., arXiv:2510.21228, Oct 2025). AutoGen caller-agent + dispatcher-agent simulation grounded in a taxonomy (32 chief complaints, 6-phase protocol) and a "fact commons" to curb misinformation. 4 physicians rated 100 cases (Gwet AC1 >0.70): 94% correct agent contact, 91% guidance provided. https://arxiv.org/abs/2510.21228 [verified]. **Borrow:** use agent-vs-agent simulation to *generate test traffic* (a "firefighter actor" agent produces radio lines from a scripted ground truth), then score our triage against that ground truth.
- **Seoul AI 119 Call Bot** pilot (since Mar 2025): 11,434 reports in 4 months, with **dual human monitoring** of the AI in real time. No accuracy published. https://english.seoul.go.kr/ai-to-handle-119-emergency-calls-and-secure-golden-time-the-first-of-its-kind-in-korea/ [snippet]. This is a useful Korean HITL precedent for the pitch.

---

## 3. Decision support for incident command

### 3.1 Radio overload and missed maydays (problem evidence)
- **Bridgeport, CT (24 Jul 2010, NIOSH F2010-18).** The IC monitored two channels on two handhelds, so transmissions on one channel were "missed or unanswered". The mayday ("we're trapped on the rear stairs") was not acknowledged. A possible mayday was not confirmed with dispatch. Mayday procedures had never been tested. Both victims had depleted air. https://www.firefighternation.com/fire-leadership/federal-investigation-finds-mayday-failures-in-fatal-bridgeport-fire-2/ , https://www.statter911.com/2011/06/30/niosh-says-bridgeport-fd-failed-to-respond-to-mayday-calls-in-double-lodds-many-failures-cited-in-deaths-of-lt-steve-velasquez-ff-michael-baik/ [secondary; primary PDF not retrieved]
- **Project Mayday:** about **36% (35.6%) of maydays missed on the first call** by fireground or dispatch. An earlier interim figure was 54%. Dataset said to be 18,697 mayday events over 6 years. https://fireengineeringtraining.com/courses/mayday-operations/ , https://www.firehouse.com/safety-health/article/21040224/billygoldfeder [snippet, secondary; original at projectmayday.net not reached]
- **USFA EFO study:** 82.6% of surveyed commanders reported having missed a message. The hypothesis was that sensory overload causes missed messages. https://apps.usfa.fema.gov/pdf/efop/efo49798.pdf [snippet]
- **USFA fireground radio report:** channel overwhelmed by traffic cited as a major contributing factor in LODDs, with distress messages lost under routine traffic. https://apps.usfa.fema.gov/pdf/efop/tr_96cv.pdf [snippet]
- NIOSH F2001-18 (NJ, 2001) recommends separate tactical and command channels and a PASS activation after "Mayday". https://stacks.cdc.gov/view/cdc/163876 [verified]. Multi-channel ops fix congestion but create the Bridgeport two-channel IC problem. [inference] A channel-agnostic AI listener that merges all channels into one prioritized queue addresses both.

### 3.2 Situation awareness and cognitive load
- **Endsley (1995)** SA model: L1 perception → L2 comprehension → L3 projection. Workload is a task/system factor that degrades SA, mostly at very high levels. https://journals.sagepub.com/doi/abs/10.1518/001872095779049499 [snippet]
- **Goal-directed task analysis of firefighter SA requirements** for fire and non-fire emergencies (Applied Ergonomics, 2023). https://www.sciencedirect.com/science/article/abs/pii/S0003687023001746 [snippet; 403]. Use GDTA vocabulary when designing what each role sees.
- **Unified-command SA experiment** (preliminary): interdependence between commanders under growing cognitive load. https://www.researchgate.net/publication/380186630_Unified_command_Preliminary_findings_from_a_situation_awareness_experiment [snippet]
- [inference] Map our UI to Endsley: L1 = transcribed and tagged transmissions; L2 = state engine (who is where, in what status); L3 = predicted victim locations and "time since last contact" timers. Ask the LLM only to *propose* L2/L3 changes. Never let it overwrite state silently.

### 3.3 PAR / accountability automation
- Products already auto-prompt the IC to run PAR at intervals (Versaterm, https://www.versaterm.com/resource/the-3-areas-accountability-technology-tracks-to-improve-responder-safety/). In MSA's system a firefighter must be on SCBA telemetry to appear (https://www.fireapparatusmagazine.com/fire-technology-innovation/firefighter-accountability-and-tracking-technology/). [snippet]
- **LocATER** (NSF-funded research): ties localization to PAR checks so firefighters can answer PAR without radio traffic. https://par.nsf.gov/servlets/purl/10060216 [snippet]
- NIST: indoor location is a recognized gap, with a 1 m accuracy need stated by stakeholders in 2016. Inertial-only positioning drifts. NIST SP 1191 Smart Fire Fighting roadmap lists location/accountability as priorities. https://www.criticalcomms.com.au/content/research/news/nist-research-into-indoor-tracking-for-first-responders-1245810308 , https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.1191.pdf [snippet]
- [inference] **Voice-derived PAR** is our niche: infer "last heard / last known location / status" per unit from radio content, and let the earpiece agent run a one-touch PAR ("tap to confirm") to cut radio roll-call traffic.

---

## 4. Agentic / multi-agent designs: who-needs-to-know-what, push vs pull, alarm fatigue

- **NIST PSCR "Voices of First Responders"** (NISTIR 8245, 2019): firefighters report sensory overload while doing the primary task, and want key data (air, location, thermal) on a mask HUD. NISTIR 8216 warns that new tech must not distract from the primary task. https://nvlpubs.nist.gov/nistpubs/ir/2019/NIST.IR.8245.pdf , https://nvlpubs.nist.gov/nistpubs/ir/2018/NIST.IR.8216.pdf [snippet]
- **PNNL-25158 "Attention and Situational Awareness in First Responder Operations":** responders fear overload, especially when **command pushes feeds** to them. Wearables pull attention away from immediate context, at a cost to task performance. https://www.pnnl.gov/sites/default/files/media/file/RTA_Situational_Awareness.pdf [snippet; PDF not parsed]
- **Alert fatigue:** more public-health messages lower correct recall of any given message, so limit redundant and conflicting messages (BMC Health Serv Res 2013). https://pmc.ncbi.nlm.nih.gov/articles/PMC3751004/ . Over-alerting leads people to opt out (Albany, 2025). https://scholarsarchive.library.albany.edu/cgi/viewcontent.cgi?article=1019&context=ehc_fac_scholar [snippet]
- **Availability-aware notification routing** for wearables: HeadRoom (arXiv:2607.08083) https://arxiv.org/pdf/2607.08083 ; urgency classifier for MR notifications, PersoNo (arXiv:2508.19622) https://arxiv.org/pdf/2508.19622 [snippet]
- **HITL precedent for VLM agents in ICS:** a UAV triage paper routes a VLM coordinator into the ICS as decision support for the Operations Section Chief, not as a controller (arXiv:2607.27597). https://arxiv.org/html/2607.27597v1 [snippet]
- No study directly comparing push vs pull for firefighters was found.
- [inference] **Design rule:** *push* (audio interrupt in the earpiece) only for life-safety items relevant to that responder: mayday on their floor or sector, an evacuation order, a hazard on their path, or a victim near them. Everything else is *pull* (glance or tap on the clip display). Rate-limit pushes (e.g., at most 1 per 20 s unless the item is a mayday or evac) and collapse duplicates. Each push carries why-you're-hearing-this (sector match). The relevance filter is an agent with tools `get_unit_state(unit)`, `get_sector_events(sector, since)`, `send_brief(unit, text, priority)`. The demo's Best Agentic Use-Case angle is per-responder relevance filtering + IC acknowledgment loop, not a chatbot.

---

## 5. What to borrow in 17 hours (concrete)

**Schema (muse-spark-1.3 JSON-schema output), one transmission → one event:**
```
{ "speaker_unit": "<roster id or 'unknown'>",
  "addressee": "<roster id | 'command' | 'all' | 'unknown'>",
  "tag": "DANGER | VICTIM_FOUND | HELP_NEEDED | ROUTINE",
  "is_mayday": bool, "mayday_evidence": "<verbatim span or ''>",
  "location": { "building":"...|unknown", "floor": int|null, "sector":"...|unknown", "raw":"<verbatim>" },
  "status_change": "entering|exiting|low_air|trapped|lost|ok|none",
  "victims": [{ "count": int|null, "location_raw": "...", "condition":"unknown|..." }],
  "needs_ack": bool, "confidence": 0-1, "evidence_span": "<verbatim quote>" }
```
- An explicit `unknown`/`null` is allowed for every field (clinical "unknown" finding). `evidence_span` must be a verbatim substring, and the backend checks this and drops non-matching spans [inference: a cheap hallucination guard].
- Post-process: snap `speaker_unit` and `location` to the roster and map by edit distance (ATC NLP-boost pattern). Store both raw and snapped values.
- Prompting: few-shot with *codeword-masked* distress examples ("we can't find the way out, low air", "출구를 못 찾겠다"). Instruct: "if unsure between DANGER and ROUTINE, choose DANGER and set confidence <0.6". Over-triage is the cheap error here, but surface confidence so the IC is not flooded (KTAS over-escalation precedent).
- ASR: keyword biasing list = roster call signs + "mayday", "PAR", "evacuate", floor names, Korean equivalents. VAD/min-duration gate before transcription (Careless Whisper).

**Quick eval (SeaAlert + DispatchMAS recipe), about 1–2 h of work:**
1. Write a ground-truth scenario script (based on Bridgeport/Pyeongtaek timelines) with 60–100 transmissions labelled for tag, unit, floor and mayday. Include about 20% codeword-masked distress lines and some digit-heavy lines ("Engine 2 on 3rd floor" vs "23").
2. Use muse-spark to paraphrase into radio style, then TTS (any) → add band-pass (300–3400 Hz) + noise/clipping to simulate radio → muse-voice-transcribe (with and without keyword biasing) → classifier.
3. Report: mayday recall (target 100%), DANGER precision/recall, floor/unit **exact-match** accuracy, and the biasing on/off delta. One table in the README is cheap and scores Technical Depth and Use of Meta AI.
4. Optional real-audio sanity check: the released police-radio corpus (arXiv:2409.10858) for WER on short transmissions; spikecodes/911-call-transcripts (518 rows, MIT, **empty README so provenance unknown**, text only) for extraction smoke tests. https://huggingface.co/datasets/spikecodes/911-call-transcripts

**Rules engine (ATC runtime-monitoring pattern):** about 5 time-bounded rules over the event trace: unacked mayday (10 s), no contact from a unit in IDLH (N min), low-air reported with no exit reported, victim reported with no assignment, PAR interval elapsed. Every alert lists its evidence transmissions.

## 6. What to avoid
- Claiming WER or accuracy numbers for Muse models that we did not measure.
- BLEU/ROUGE-only evaluation (2412.16176); fuzzy-match location scoring.
- Training or evaluating on the Kaggle synthetic Qwen 911 set (https://www.kaggle.com/datasets/jacopoferretti/police-emergency-calls-llm-synthetic), or RescueSpeech for EN/KO. AI Hub 위급상황 음성/음향 data forbids redistribution of re-processed data without NIA consultation (https://www.data.go.kr/data/15146382/fileData.do), so do not ship it in the public repo.
- Letting the LLM sit inline in the voice path, auto-dispatching, or silently mutating the map.
- Medical framing (triage of patients). Keep the tags operational (Danger / Victim Found / Help Needed).
- Keyword-only mayday detection (codeword masking; KWS false-alarm rates).

---

## 7. Implications for our product

1. **Problem framing is well sourced:** about 36% of maydays missed on the first call (Project Mayday, secondary), 82.6% of commanders admit missed messages (USFA EFO), and Bridgeport's two-channel IC missed an unacknowledged mayday. Pillar 1 should be pitched as "**no transmission goes unread**": a channel-agnostic AI listener merging all channels into one prioritized, acknowledged queue.
2. **Expect bad ASR and design for it.** Real radio gives about 50% WER zero-shot and about 27% fine-tuned, roughly the human level (police corpus). Show the raw clip + transcript + evidence span for every tag, and treat the transcript as a hint, not truth.
3. **Keyword biasing + roster snapping is our cheapest technical-depth win.** The ATC analog lifted callsign accuracy from 35% to 89%. Use muse-voice-transcribe keyword biasing with the live roster and floor names, then edit-distance snap in the backend. Show a before/after metric.
4. **Mayday detection must be semantic, not lexical.** Firefighters often don't say the codeword. Use muse-spark classification with codeword-masked few-shots, keep the keyword as a booster, and run an unacked-mayday timer that escalates until the IC acknowledges.
5. **Structured output with explicit "unknown" and verbatim evidence spans** is the hallucination guard. Never invent a floor. Snap to the map, or leave it unknown and flag "location unclear – ask".
6. **The world-model harness = event trace + time-bounded rules** (ATC runtime-monitoring pattern, F1 0.85). This gives explainable alerts and voice-derived PAR ("Rescue 1: last heard 4:12 ago, 3F east"), which is novel and demoable.
7. **Responder earpiece agent: push only life-safety items relevant to that responder,** rate-limited and deduplicated. Everything else is pull on the clip display (NIST PSCR overload findings, PNNL "command pushes feeds" concern). This per-responder relevance filtering is our Best-Agentic-Use-Case story.
8. **Human-in-the-loop is mandatory and a selling point:** the IC acknowledges, accepts or edits AI tags. The Seoul 119 AI bot runs with dual human monitoring, a Korean precedent. Accept over-triage but show confidence (LLM triagers over-escalate).
9. **Latency claim:** the AI annotates in parallel to voice (MCPTT 300 ms mouth-to-ear is for voice, untouched). Target a tag within one transmission turn (≤3–5 s). Measure and show it in the video.
10. **Ship a small eval table** (synthetic radio-degraded scenario: mayday recall, tag P/R, floor exact match, biasing on/off). It addresses Technical Depth (20%) and Use of Meta tooling (25%) directly.
