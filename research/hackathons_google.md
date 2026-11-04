# Hackathons A: emergency and responder projects in the Google / Gemini / DeepMind ecosystem (2021-2026)

Stream: comparable projects from Google-ecosystem hackathons and competitions, plus what won, what was common and what nobody built.
Compiled: 2026-11-04 (KST), about 17 hours before the Meta Global AI Developer Hackathon deadline.
Method: WebSearch/WebFetch on official Google blogs, Cerebral Valley gallery pages, Devpost, GitHub READMEs and team write-ups. Firecrawl was not used.

**How to read the evidence tags**
- **[V]** I fetched the primary page in this session and confirmed the claim there.
- **[S]** The claim comes from a search snippet or a mirror. I could not fetch the primary page.
- **[I]** My inference, not a stated fact.

---

## 1. Context: the competitions we checked

| Competition | Date | Scale / prizes | Emergency winner? | Source |
|---|---|---|---|---|
| Gemini API Developer Competition | Winners posted 21 Nov 2024 | "Thousands" of devs. Prize categories: Best Overall, Most Impactful, Most Creative, and others | **No.** Winners were accessibility and consumer apps (Jayu, Vite Vere, Gaze Link, Viddyscribe). The organizers listed disaster response as an example idea, but no disaster app won | [V] https://developers.googleblog.com/en/announcing-the-winners-of-the-gemini-api-developer-competition/ |
| Gemma 3n Impact Challenge (Kaggle) | 2025 (deadline about 6 Aug 2025) | 600+ submissions | **No.** The post mentions "crisis response" in passing but names no crisis winner. 1st place: Gemma Vision (accessibility) | [V] https://blog.google/innovation-and-ai/technology/developers-tools/developers-changing-lives-with-gemma-3n/ |
| Gemma 4 Good Challenge (Kaggle) | Post dated 24 Aug 2026 | 14 named winners | **Yes:** Acuífero·Vigía won the Global Resilience Prize | [V] https://blog.google/innovation-and-ai/technology/developers-tools/winning-entries-gemma-4-good-challenge/ |
| Gemini Live Agent Challenge (Devpost + Google Cloud) | Submissions 16 Feb-16 Mar 2026; winners posted 16 May 2026 | 11,878 participants, 1,536 projects, 151 countries, $80K | **Indirectly.** The grand prize went to a hands-free voice copilot in a safety-critical setting (ORION, surgery). One honorable mention is a hazard-reporting app | [V] https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge |
| Gemini 3 Hackathon (Devpost, Google DeepMind) | Deadline 9 Feb 2026 | $100K pool, $50K grand prize | Grand prize went to "Globot". I could not open the full list (Devpost returned 403) | [S] https://gemini3.devpost.com/updates |
| Agent Development Kit (ADK) Hackathon (Google Cloud) | Results posted 2 Sep 2025 | 10,400 participants, 477 projects | **No** among the main winners. Grand prize: SalesShortcut, a sales tool | [S] https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights |
| Cerebral Valley x Google DeepMind in-person hackathons (TED AI SF Oct 2025, Gemini 3 SF Dec 2025, Gemini 3 Seoul Feb 2026, Gemini 4 Argon SF 25 Oct 2026) | One day each | Argon SF: $7.5K / $5K / $2.5K plus $5K for Best use of Managed Agents | Many disaster entries. Their placements are **not shown** on the gallery pages (six unnamed finalists per event) | [V] https://cerebralvalley.ai/e/gemini-4-argon-sf |

Takeaway: in every large Google contest we checked, accessibility and "AI for people with X" entries won most often. Disaster response is a common **entry** topic but a rare **winner**. The exceptions won by bringing physical-world evidence (Acuífero·Vigía), a hands-free voice workflow for a safety-critical user (ORION), or a measurable simulation loop (the Argon SF winner).

---

## 2. Comparable projects (16)

### 2.1 FireSight (Youngtak-Jo): fire incident copilot for dispatchers and field crews. **Closest analog to our product.**
- Link: https://github.com/Youngtak-Jo/FireSight-Google-Deepmind-Hackathon- [V]. Video: https://youtu.be/L4dzFN3qgNM
- What it does: transcribes the live 911 call while Gemini Live suggests follow-up questions. Research subagents run in parallel (geo/routing, structure/occupancy, floor plan and photo vision, materials/hazards, weather). It builds an evidence-linked 3D scene in Three.js and gives dispatchers and field responders one shared workspace synced over WebSocket. The field side includes a "bodycam" live stream.
- Models: `gemini-4-argon` (orchestration, Search grounding, vision, 3D synthesis, Q&A), `gemini-3.8-live` (real-time voice and camera), `gemini-3.5-transcribe` (dictation). Also Google Maps Platform (Routes, Places, Weather).
- Pitch: the README's line is "something one firefighter sees" becomes "something the whole team can act on". The demo has a "Standby Mode" with two one-click scenarios: a scripted Bradbury Building fire with five trapped occupants, and a live Ferry Building run.
- Event and award: the README says "Google DeepMind hackathon" but gives no date or placement. **[I]** The model names suggest the Gemini 4 Argon era, so probably the 25 Oct 2026 SF event, but I could not find FireSight in that gallery. Award unknown.
- Gap compared with us: it transcribes the *caller* (911 intake), not responder radio. It has no mayday or priority-tag triage, no firefighter status or accountability tracking, and no wearable UX.

### 2.2 FireSight (yc-firesight): voice-driven pre-incident inspections. **Placed: 2nd, B2B track**
- Link: https://github.com/builderpepc/yc-firesight [V]. This is a **different team and a different project** from 2.1, despite the same name.
- Event: Cactus x Google DeepMind Voice Agent Hackathon at Y Combinator. No date in the README.
- What it does: inspectors speak observations hands-free. AI glasses (the README names Meta Ray-Bans) capture photos. Inspectors can ask "what's missing?" by voice and export a PDF in one tap. Routine Q&A runs locally offline, and heavier AI waits for connectivity.
- Pitch: the team claims feedback from FDNY and other departments. They stressed that offline matters because basements, elevators and electrical rooms have no signal.
- Takeaway for us: naming real fire-department users and a wearable form factor made an unglamorous workflow place. It covers pre-incident inspection, not the fireground.

### 2.3 Argus: earthquake damage picture and dispatch (Gemini 4 Argon SF, 25 Oct 2026)
- Link: https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41 [V]. Repo: github.com/icecreamlun/argus. Video: youtu.be/s9aMt3HxWhk
- What it does: a physics replay of the 1906 earthquake over a 3D model of 5,689 San Francisco buildings. Gemini reviews helicopter video, drone footage and resident reports, links each finding to a **video timestamp**, and corrects the physics model. It writes drone mission plans in about 6 s. Commanders ask in natural language for unit assignments and routes. The page says "nothing moves until the commander clicks Dispatch."
- Measured results against hidden ground truth: macro-F1 rose from 24% to 46% on observed buildings, and from 33% to 43% downtown after observing 7% of the city. It matched 77% of 198 noisy, multilingual resident reports to the correct building, with 96% correct damage reads.
- Award: none shown. The event listed six finalists but did not name them.

### 2.4 SpatialTwin: live evacuation digital twin (Gemini 4 Argon SF, 25 Oct 2026)
- Link: https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/77 [V]. Deployed at spatialtwin.alhinai.dev
- What it does: turns a posted evacuation-map photo, a PDF or a phone video into a 3D building model. Users drop a hazard and routes re-plan. Gemini managed agents stress-test the plan, and a local checker re-runs each agent claim. Judges could scan a QR code to turn their phones into live exit signs or to drop hazards.
- Pitch: "AI proposes, a local checker decides, and a person approves." Every output is labeled by source (live Gemini, saved run, local solver or simulated). Reported verification: one critique round cut map-reading errors from 16 to 0.
- Award: none shown.

### 2.5 Scailer / "first-hour": a shared view of incidents across agencies (Gemini 4 Argon SF)
- Link: https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/72 [V]. Repo: github.com/jmadeiros/first-hour
- Problem framing: highway patrol, police, traffic desks and fire crews each see only part of an incident. The page cites FHWA: secondary-crash risk rises 2.8% per minute. Model details are not given on the page. Award: none shown.

### 2.6 Horizon / "Lifeline": crisis-operations agent for building emergencies (Gemini 3 Hackathon SF, 6 Dec 2025)
- Link: https://cerebralvalley.ai/e/gemini-3-hack-sf/hackathon/gallery/60 [V]
- What it does: the operator reports a fire in a zone. Gemini 3 Pro reasons over zones, hazards and accessibility routes and re-plans. Nano Banana Pro edits the floor plan to draw hazard overlays and arrows on 2K evacuation maps.
- Pitch: speed, transparency, a long-running "marathon agent". Award: none shown, 0 votes.

### 2.7 13th Floor Fireguard.ai: resident fire alerts plus distress signal to firefighters (Google Gemini Hackathon at TED AI SF, 18 Oct 2025)
- Link: https://cerebralvalley.ai/e/2025-ted-ai-hackathon/hackathon/gallery [V] (gallery id 4)
- Replaces "archaic" alarms with alerts that tell residents which floor is burning and the best evacuation route. Trapped residents can signal firefighters. Award: none shown.
- Same event: **Guardian Agent** (gallery id 17) uses Gemini 2.5 Flash to judge in real time whether audio transcripts indicate danger. This is the closest in-ecosystem precedent for *classifying speech by danger level*.

### 2.8 SafeCall: 119/112 calls from people with dementia (Gemini 3 Seoul Hackathon, 28 Feb 2026)
- Link: https://cerebralvalley.ai/e/gemini-3-seoul-hackathon/hackathon/gallery [V] (gallery id 30)
- Gemini checks home-camera footage to judge whether a 119 call is a real emergency and shares the evidence with family. It is the only Korean 119-related entry we found. That Seoul gallery contains **no fire or firefighter projects**. Award: not shown.

### 2.9 Acuífero·Vigía: offline flood early warning. **Won: Global Resilience Prize, Gemma 4 Good (Aug 2026)**
- Link: https://blog.google/innovation-and-ai/technology/developers-tools/winning-entries-gemma-4-good-challenge/ [V]
- Fuses local telemetry, **volunteer audio reports** and river-camera feeds into flood predictions and safety instructions. Runs Gemma 4 E2B on Raspberry Pi 5 and is reportedly deployed in South America.
- Judges' praise: technical depth and "auditable reasoning trails".
- Why it matters to us: it is the nearest *winning* example of fusing field voice reports with sensors into one situational state. That is our pillar 3, at river scale.

### 2.10 KMesh: offline mesh SOS with on-device triage. **Won: Special Winner, Best Use of Gemma 4 (Google DeepMind Hyderabad Hackathon on Kaggle)**
- Link: https://dev.to/haquedot/how-we-became-google-deepmind-hackathon-special-winners-with-kmesh-2lbc [V]
- Citizens send SOS reports that hop between phones over Bluetooth or Wi-Fi Direct (seen-set plus TTL). Gemma 4 on responder phones triages and prioritizes reports. Data syncs to central command when the internet returns.
- Judges' praise is unknown. The team says they missed the top 10 and their demo went poorly; a second judge gave them five minutes. **[I]** A clear problem and a live demo shown one-on-one can still win a special prize.

### 2.11 ORION: voice-directed surgical copilot. **Won: Grand Prize, Gemini Live Agent Challenge (May 2026)**
- Link: https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge [V]
- Not an emergency project, but it is the **direct precedent for our pillar 2**: a hands-free voice agent for a user whose hands and eyes are busy in a life-critical setting. Surgeons get answers and live data "without breaking scrub". Built on the Gemini Live API, ADK and Google Cloud.
- Same contest: **drone-copilot** won the Live Agent category (voice-commanded drone inspections, confirming actions aloud). **NagarDrishti** got an honorable mention (hands-free pothole and waterlogging reports while driving, feeding a dashboard for officials). NagarDrishti is the structural twin of our pillar 1 (voice in the field leading to a triaged dashboard for command), but for civic potholes.

### 2.12 Emergent: crisis simulation for emergency managers. **Won: Google Cloud challenge at KnightHacks VIII (UCF, 2025)**
- Link: https://discuss.google.dev/t/google-cloud-ignites-agentic-ai-innovation-at-florida-s-premier-hackathons/325840 [V]
- Lets emergency managers test disaster plans in simulation. The challenge focused on ADK and A2A. The post gives no details on judging or architecture.

### 2.13 SafeGuardianAI: voice-based victim status checks for rescue teams (Gemini API Developer Competition 2024 entry)
- Link: https://ai.google.dev/competition/projects/safeguardianai [S]. The page now returns 301 to aistudio.google.com, so this is from a **search snippet only**.
- Post-disaster app: an LLM checks on victims by voice and passes status to rescue teams, with maps and case prioritization. Built on Firebase by a Swiss team. **Did not win.**

### 2.14 RescueAI and Emergify (Gemini API Developer Competition 2024 entries)
- https://ai.google.dev/competition/projects/rescueai and https://ai.google.dev/competition/projects/emergify [S]
- RescueAI: country-aware emergency calling and texting plus a Gemini chat that accepts text and images (Egypt). Emergify: first-aid steps and hospital routing. **Neither won.** Both are generic citizen SOS apps.

### 2.15 Citizen2Responder and Gemergency (Gemma 3n Impact Challenge entries, Aug 2025)
- Citizen2Responder [S, mirror]: https://kaggle-google-competition.pages.dev. A fine-tuned Gemma 3n runs on-device via llama.rn and generates reports for EMTs. Vision falls back to cloud Gemini Flash. The team admits it is not fully offline.
- Gemergency [S]: https://charming-whaley.github.io/gemergency_ios_app_code. An iOS app with step-by-step guidance for emergencies.
- Neither placed. Both sit near the excluded "medical advice" category.

### 2.16 i-RISE: disaster risk management (Google Solution Challenge 2021). **Reported Top 3**
- Source [S, not directly verified; dzup.org returned 521]: https://dzup.org/news/campus-news/up-student-developers-hailed-world-software-challenge-co-champions and https://dailyguardian.com.ph/?p=220845
- University of the Philippines team. A cloud-based local-government system: residents submit rescue requests and incident reports, and officials manage the response. It predates Gemini. It shows that citizen-reports-to-command dashboards have been a Solution Challenge pattern since 2021.

**Excluded as only adjacent:** PenguinAgent (Gemma 4 Good, 3rd; uses SAM 3 for wildlife tracking; useful only as a precedent that "SAM 3 plus LLM fusion" places). Also Sixth Sense for Security Guards (Gemma 3n, 4th; YOLO-NAS gating Gemma, 16 camera feeds).

---

## 3. Pattern analysis

### 3.1 What wins in Google-ecosystem judging
1. **A specific person with occupied hands, eyes or abilities.** Gemma Vision (blind user with a cane), ORION (surgeon in scrubs), Vite Vere, Gaze Link and Gem-Care all name a specific user whose constraint makes the AI necessary, not just convenient. Judges' language rewards "deep user empathy" (Trido, PreVillage). [V] Gemma 4 Good post; Live Agent post.
2. **A measurable before/after against ground truth.** The Argon SF 1st place (LabTwin / "polar bears") showed visual match rising from 54 to 88 and an RL agent at 1.0 success. Argus showed macro-F1 from 24 to 46. Gem-Care showed word error rate from 32.7% to 19.0%. SpatialTwin showed errors from 16 to 0. Numbers on screen beat adjectives. [V] https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/67
3. **A visible human approval gate plus a verification loop.** Argus ("nothing moves until the commander clicks Dispatch"), SpatialTwin ("a person approves anything that changes state"), LabTwin (simulate "before a real pipette moves"), Project Rosie (praised as "non-hallucinatory"). By late 2026 this is the default design pattern for safety-critical entries in this ecosystem.
4. **Evidence-linked output.** Argus ties each finding to a video timestamp. SpatialTwin labels every source as live, saved or simulated. Acuífero·Vigía was praised for "auditable reasoning trails". Judges trust outputs they can trace.
5. **Showcasing the sponsor's newest features by name.** Winners say which feature does what: Live API, managed agents, streamed thought summaries, Nano Banana map edits, MediaPipe on-device inference. Partner prizes (Unsloth, Ollama, LiteRT, Managed Agents) reward this directly.
6. **Offline/edge robustness** dominates the Kaggle Gemma tracks. Robust offline fallback is praised again and again. **We cannot credibly claim this with API-only Meta models**; see the Implications section.
7. **Demo format at Cerebral Valley events (the same organizer as our hackathon).** The gallery card shows a title, a one-liner, the repo and the video. The 1st-place LabTwin hosted demo **replays a cached run**, with live use needing a local key. FireSight's "Standby Mode" offers two scripted one-click scenarios plus one live run. A recorded or scripted scenario is accepted practice if it is labeled honestly.

### 3.2 What is common or boring (and loses)
- **Citizen SOS and first-aid apps** (RescueAI, Emergify, Gemergency, Citizen2Responder, SafeGuardianAI): many entries, none placed. They also drift toward medical advice, which is excluded for us.
- **Evacuation-route generators** (Horizon, SpatialTwin, Fireguard.ai, Safeexitplanner on Argon SF): at least four in under a year. Leading with "AI draws exit arrows on a floor plan" is now generic.
- **Disaster physics simulators** at Argon SF (Argus, StormSim, Risk Engineer Argon, Backflow): impressive but crowded, and aimed at planners rather than people on the ground.
- **Chat wrappers on emergency info.** Devpost's Gemini 3 call explicitly said "Go beyond chat wrappers" (https://x.com/devpost/status/2001779137598623900).

### 3.3 What nobody did (our open lanes)
1. **Nobody transcribed or triaged responder-to-responder fireground radio.** Every voice-triage analog transcribes *civilians*: FireSight (911 caller), NagarDrishti (drivers), SafeCall (119 callers), Acuífero·Vigía (volunteers), Guardian Agent (personal audio). No project detects maydays, tags "Victim Found" or "Help Needed" from crew radio, or handles multi-channel overload. **This is our pillar 1.**
2. **Nobody tracked firefighter status or accountability.** All projects track victims, buildings or hazards. None models "where is each crew member, when did we last hear from them, is their egress still open". That is exactly the failure in Pyeongtaek 2022 (radio contact lost, egress not found) and NIOSH Bridgeport 2010 (maydays not heard).
3. **Nobody built responder-side wearable UX for the fireground.** yc-firesight used AI glasses for *pre-incident inspections*, FireSight streams a bodycam *to* command, and ORION shows hands-free works in a safety-critical domain. No one built an earpiece briefing plus one-touch marking on a clip-on display *for the firefighter inside*.
4. **Nobody grounded the pitch in line-of-duty-death investigation reports** (NIOSH / USFA / Korea's National Fire Agency (NFA)). The closest is Scailer citing FHWA and Caltrans statistics.
5. **Nobody filtered intel per responder.** FireSight and Argus show everyone one shared picture. No one has an agent decide *what this specific firefighter needs to hear now* and suppress the rest. That is a real agentic decision, not just display.

---

## 4. Implications for our product (3-minute demo and pitch)

1. **Open with a line-of-duty-death fact, then the open lane.** For example, the Pyeongtaek 2022 lost radio contact, or the Bridgeport 2010 maydays "transmitted but not heard". Then say plainly: existing AI tools listen to 911 callers; ours listens to the crew. Every analog we found transcribes civilians.
2. **Make pillar 1 the hero shot: live radio triage with an on-screen number.** Play a scripted, overlapping two-channel radio clip (Korean plus English, to use muse-voice-transcribe's diarization and keyword biasing for terms like "mayday" and "메이데이"). Show tagged cards arriving (Danger / Victim Found / Help Needed) and **a measured result**, such as "mayday surfaced in X s, versus buried at position N in raw chatter" or tag accuracy on a 20-clip labeled set. Winners in this ecosystem show before/after numbers.
3. **Add a visible commander-approval gate.** The AI proposes a predicted victim location or a "crew 2 egress compromised" alert, and nothing reaches responders' earpieces until the commander taps Approve. Say it in one line, for example "AI proposes, the commander decides". Judges in this ecosystem now expect this pattern; Argus and SpatialTwin both used it.
4. **Link every tag to evidence.** Each priority card shows the radio-clip timestamp, the speaker (from diarization) and a source label (live or replayed). This matches the "auditable reasoning trails" praise and guards against hallucination concerns.
5. **Pillar 2 as "ORION for the fireground".** On the simulated phone-sized display, show the per-firefighter agent *filtering*: it suppresses most of the chatter, briefs only what changes that firefighter's next move by text-to-speech, and offers a single-tap "mark victim here". The Gemini Live Agent grand prize was a hands-free copilot for a user with occupied hands, and our wearable is the same pattern.
6. **Make pillar 3 the accountability board, not an evacuation map.** Lead the world-model view with **responder status**: last heard, location, air/time-in, and egress open or blocked. Victim predictions sit beside it. Evacuation-route drawing is crowded (four or more prior entries); firefighter accountability has no competitor.
7. **Name each Meta model and what it does** (this is the 25% criterion). On screen and in the README, include a one-row table: muse-voice-transcribe for streaming, diarization and keyword biasing; muse-spark-1.3 for JSON-schema triage, tool calls that update the world state, and per-responder briefing; sam-3.1 for segmenting a helmet-cam or drone frame to place a hazard or victim marker on the map. Winners here explicitly mapped features to functions.
8. **Do not claim offline.** Gemma-track winners won on offline robustness, but we are API-only with no GPU. Say this honestly: "cloud today; designed to fail degraded, with last-known state cached on device." Show latency on screen instead. A fake offline claim would undercut the auditability story.
9. **Use the demo format that already works at Cerebral Valley.** Build a "Standby, then Scenario" one-click scripted replay (as FireSight and the LabTwin 1st place did), plus 20-30 s of a clearly labeled live run. Split-screen layout: command dashboard on the left, firefighter wearable view on the right, both reacting to the same radio event within one beat. This visual sync is the single shot that proves pillar 3.
10. **Frame the agent loop for the Best Agentic Use-Case prize.** Show the loop explicitly: radio in, triage, tool call to update the world state, conflict check (for example, two crews report the same victim, so dedupe), commander approval, per-responder brief, then listen for acknowledgment and re-brief if none comes. A missing acknowledgment that triggers escalation is a striking agentic moment that no analog shows.

---

## Sources (fetched or cited)
- https://developers.googleblog.com/en/announcing-the-winners-of-the-gemini-api-developer-competition/
- https://blog.google/innovation-and-ai/technology/developers-tools/developers-changing-lives-with-gemma-3n/
- https://blog.google/innovation-and-ai/technology/developers-tools/winning-entries-gemma-4-good-challenge/
- https://cloud.google.com/blog/topics/developers-practitioners/winners-and-highlights-of-the-gemini-live-agent-challenge
- https://gemini3.devpost.com/updates
- https://x.com/devpost/status/2001779137598623900
- https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights
- https://discuss.google.dev/t/google-cloud-ignites-agentic-ai-innovation-at-florida-s-premier-hackathons/325840
- https://cerebralvalley.ai/e/gemini-4-argon-sf
- https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery
- https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/41
- https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/77
- https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/72
- https://cerebralvalley.ai/e/gemini-4-argon-sf/hackathon/gallery/67
- https://cerebralvalley.ai/e/gemini-3-hack-sf/hackathon/gallery/60
- https://cerebralvalley.ai/e/2025-ted-ai-hackathon/hackathon/gallery
- https://cerebralvalley.ai/e/gemini-3-seoul-hackathon/hackathon/gallery
- https://github.com/Youngtak-Jo/FireSight-Google-Deepmind-Hackathon-
- https://github.com/builderpepc/yc-firesight
- https://dev.to/haquedot/how-we-became-google-deepmind-hackathon-special-winners-with-kmesh-2lbc
- https://ai.google.dev/competition/projects/safeguardianai
- https://ai.google.dev/competition/projects/rescueai
- https://ai.google.dev/competition/projects/emergify
- https://kaggle-google-competition.pages.dev
- https://charming-whaley.github.io/gemergency_ios_app_code
- https://dzup.org/news/campus-news/up-student-developers-hailed-world-software-challenge-co-champions
- https://dailyguardian.com.ph/?p=220845
