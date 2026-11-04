# Hackathons B: other hackathons and competitions (firefighter, first-responder and dispatch AI, 2022-2026)

Compiled 2026-11-04 for the Meta Global AI Developer Hackathon 2026 (solo entry, fireground coordination system).
Method: WebSearch (standard and extended) plus WebFetch of primary pages. Devpost project pages return HTTP 403 to the fetcher, so Devpost-only facts come from search-engine snippets of those pages and are marked **[snippet]**. Anything I inferred rather than read is marked **[inference]**.

---

## 0. TL;DR

- The space is getting crowded. In 2026 alone, at least four hackathon projects built nearly our exact idea: FireflAI (UC Berkeley AI Hackathon 2026), FireSight (Google DeepMind hackathon), Fire Incident Copilot / "Firewatch" (AI Tinkerers Valencia, 12 Sep 2026) and ResQueue (Cal Hacks 13.0). Each combines 911 or radio intake, a shared incident state, maps or 3D views, and agent briefings. "AI for the fire incident commander" is no longer novel by itself. What can still set us apart is the **responder-side loop**: radio-to-priority-tags, per-firefighter audio briefings, and one-touch victim marks feeding back into a shared world state, plus Korean and mayday grounding.
- The clearest relevant grand-prize winner is **DispatchAI** (UC Berkeley AI Hackathon 2024, Grand Prize, 1st of 293). It won with a live phone call, severity-sorted queue, map, human-in-the-loop "dispatcher makes the final say", and a model it fine-tuned and open-sourced itself.
- In Cerebral Valley and Meta events, **domain-expert builders** win: a lawyer won with CrossBeam, a cardiologist placed 3rd with PostVisit, and a Ugandan Ministry of Works engineer took a special prize. The Meta event's own theme text, "solve a problem you know firsthand", rewards the same thing.
- Korea validates pillar 1 directly. In Aug 2026, MSIT and MOIS funded a 900M KRW, 2-year R&D project for **an AI radio-summarisation smartwatch** for fire and police on the disaster safety network. We can cite it as "the government is funding this; we prototyped it with Meta models".

---

## 1. Project catalogue (21 entries)

| # | Project / event (date) | What it built | Tech | Emphasised strength | Result |
|---|---|---|---|---|---|
| 1 | **DispatchAI**, UC Berkeley AI Hackathon (22-23 Jun 2024) | 911 dispatcher copilot. A caller phones a Twilio number, a voice agent handles the call, the system extracts location, time and caller emotion, ranks calls by severity on a dashboard and map, and recommends actions | Next.js + Tailwind + shadcn, Leaflet, Python, Twilio, Retell, Hume EVI, fine-tuned Mistral-7B on Intel Dev Cloud | Human in the loop ("Dispatchers make the final say"); understaffing statistic ("82% of emergency call centers are understaffed"); inference cut from 2m53s to <10s; open-sourced model and dataset | **Grand Prize** (1st of 293), plus AI for Good and Best Use of Intel AI. https://github.com/IdkwhatImD0ing/DispatchAI ; https://devpost.com/software/dispatch-ai **[snippet]** |
| 2 | **FireflAI**, UC Berkeley AI Hackathon 2026 | Multi-agent tool. From a 911 call plus real-estate listing photos it builds a hazard-annotated walkable 3D model of the house. The crew dashboard shows a map, streaming agent feed, recommended path and briefing | Fetch.ai Agentverse multi-agent pipeline (acquire, curate, map, reconstruct, hazard, plan, tactical, briefing) | Pre-entry floor-plan knowledge; visible agent feed | **Winner: Best Use of Agentverse (Fetch.ai)**, a sponsor prize, not the grand prize. Next steps it lists: live 911 transcription and mid-incident sensor fusion. https://devpost.com/software/fireflai **[snippet]** |
| 3 | **FireSight**, Google DeepMind hackathon (2026) | Shared workspace for dispatcher and field responders: Gemini Live 911 intake with follow-up questions, transcription into an incident timeline, parallel research subagents, 3D fire-spread timeline, phone as an "AI bodycam" | Gemini Live / transcribe / vision, React 19, Tailwind v4, Three.js, Express + WebSocket, Google Maps | Two one-click demo scenarios: one scripted ("Bradbury Building") and one live ("Ferry Building") | No award listed. https://github.com/Youngtak-Jo/FireSight-Google-Deepmind-Hackathon- |
| 4 | **Fire Incident Copilot ("Firewatch")**, AI Tinkerers Valencia (12 Sep 2026) | Decision support. Sensor changes and **radio reports** become a source-linked briefing; the dashboard has CCTV, radio playback with transcript, and a replay clock | FastAPI + Postgres + Redis (REST/SSE/MCP), OpenAI Agents SDK, OpenRouter (Gemini flash-lite primary) | Honest scope and **cited evidence**. Unknown occupancy stays unknown; deterministic offline fixture mode; 112 tests. Uses **real Palisades radio audio (Broadcastify, CC BY 3.0)** plus synthetic building and CCTV data | No award reported. Explicitly "not certified detection, emergency dispatch or autonomous incident command". https://github.com/Anastassy/fire-incident-copilot |
| 5 | **ResQueue (Wildfire Rescue Queue)**, Cal Hacks 13.0 (2026) | Per-station rescue queue. Residents request help; agents estimate time-to-fire-arrival; residents, responders and IC share one live state | Fetch.ai uAgents (commander / hazard / news / intake), SpacetimeDB for shared state, Qwen3-VL, fire U-Net, React | Shared live state across three roles; **replays real incidents** (NASA FIRMS, NIROPS 2020 perimeters, Glass Fire 2020) next to synthetic residents | Award not stated. https://github.com/sat-malla/wildfire-rescue |
| 6 | **Firewire / "EmergencyAI"**, AWS x INRIX AI Hackathon (2024) | Devpost snippet: a mobile app tracks the name, location and audio of each first responder, and AI turns it into summaries. An SCU ACM recap calls it an emergency system that turns accident footage into action | AWS GenAI (Bedrock) **[inference]** | Responder-tracking plus summaries | **Winner**, but sources conflict: Devpost snippet says "Transportation Track 1st"; SCU ACM says "AI Track Graduate Winner". https://devpost.com/software/firewire **[snippet]** ; https://aws.scuacm.com/ |
| 7 | **Prometeo**, IBM Call for Code (Oct 2019; pre-window but the canonical firefighter win) | Wearable sensors stream to Watson, which shows commanders a green/yellow/red safety status per firefighter | IoT + Watson Studio / ML | Team included a **veteran firefighter** and an EMS nurse | **Global Grand Prize, $200K**. https://techcrunch.com/2019/10/12/ai-based-firefighter-safety-startup-prometeo-wins-ibm-call-for-code-challenge/ |
| 8 | **Alert X (Team Agents FDRK)**, IBM TechXchange hackathon, Call for Code track (Oct 2025) | Multi-agent urban crisis system: a vision agent reads the scene, a mapping agent finds nearby fire and hospital facilities, a reasoning agent scores severity and urgency, and **after user approval** a comms agent drafts the briefing to authorities | watsonx Orchestrate, Granite 3.3 Reasoning, Granite Vision / Llama vision, OpenStreetMap | Clear agent roles; human approval gate before the briefing goes out | **1st place**, $5K. https://community.ibm.com/community/user/blogs/jennifer-judge/2025/11/13/october-hackathon-winners |
| 9 | **FireForm**, UN Reboot the Earth hackathon at UCSC (7-8 Nov 2025) | Firefighters fill CAL FIRE paperwork **by speaking**; a local LLM auto-populates the forms | Local LLM on a laptop, works offline | Solved a pain point **CAL FIRE named itself**; field-deployable with no cloud | **1st place**, plus 6 months of coaching from Salesforce and UN partners. https://news.ucsc.edu/2025/11/ai-solutions-wildfire-mitigation-reboot-the-earth-hackathon/ |
| 10 | **Llama CCTV Operator** (Agajan Torayev), LlamaCon Hackathon, Meta x Cerebral Valley (May 2025) | AI control-room operator. Operators describe custom surveillance events in plain language; no fine-tuning | Llama 4 multimodal; motion check every 5 frames | Natural-language-defined detection, zero training | **3rd place** of 44 submissions ($35K pool). https://ai.meta.com/blog/llamacon-hackathon/ |
| 11 | **Geo-ML** (William Davis), LlamaCon Hackathon (May 2025) | Turns 400-page geology reports into structured data, 3D subsurface models and deposit estimates | Llama 4 Maverick, GemPy | Builder works in the domain ("I spend most of my time reading through geology documents") | **Best Llama API Usage**. https://ai.meta.com/blog/llamacon-hackathon/ |
| 12 | **OpenGlass**, first Meta Llama 3 Hackathon with Cerebral Valley (May 2024) | $20 open-source AI smart-glasses add-on that describes what the wearer sees | Llama 3 + cheap hardware | Wearable form factor; went viral (Quartz, Swarajya coverage) | **1st place**. https://ai.meta.com/blog/llama-3-hackathon-recap-cerebral-valley/ ; https://qz.com/a-group-of-hackers-built-20-open-source-smart-glasses-1851478685 |
| 13 | **Guardian**, Meta Llama Impact Hackathon London (Nov 2024) | AI **triage** assistant for NHS frontline staff: intake, real-time risk assessment, clinical agent "Atlas", multilingual | Llama 3.2 | Tied to UK government missions; public-service framing | **1st place** ($50K shared among top 3). https://about.fb.com/news/2024/11/metas-llama-impact-hackathon-pioneering-ai-solutions-for-public-good/ |
| 14 | **LLAMA First Aid / LinguaLink**, Llama Impact Hackathons Rome and SF (2024) | First-aid assistant (Rome); real-time medical translation for emergency care (SF) | Llama 3.2 | Emergency framing | **2nd place** at each. https://lablab.ai/blog/llama-impact-hack-rome-summary ; https://lablab.ai/blog/llama-impact-hackathon-sf-summary |
| 15 | **CrossBeam** (Mike Brown, lawyer), Built with Opus 4.6, Anthropic x Cerebral Valley (announced 20 Apr 2026) | California housing-permit tool: parallel sub-agents read blueprints and correction letters and produce an action plan | Claude Code, sub-agents | Domain expertise; a real city (Buena Park) considering adoption | **1st place** of 227 projects (13K applicants). https://claude.com/blog/meet-the-winners-of-our-built-with-opus-4-6-claude-code-hackathon |
| 16 | **TARA** (Kyeyune Kazibwe), same event | Turns dashcam road footage into an investment appraisal | Opus 4.6 vision | Tested on **real footage from a Ugandan road**; replaces $1-4M studies | **"Keep Thinking" prize**. Same URL as #15 |
| 17 | **NIST PSCR First Responder Smart Tracking (FRST) Challenge** (final Jan 2024) | 3D **indoor localisation** plus biometrics for firefighters in multistorey buildings, scored at NIST's "dots" indoor test bed with a 1 m target | Sensors on responder gear | Measured accuracy against ground truth | **$1.9M to 6 teams**. https://www.criticalcomms.com.au/content/industry/news/winners-announced-first-responder-smart-tracking-challenge-253687011 ; https://www.nextgov.com/emerging-tech/2026/02/when-every-second-counts-government-tech-helps-first-responders-lifesaving-missions/411391/ |
| 18 | **NIST PSCR CHARIoT Challenge** (2020) | AR interfaces for first responders fed by emulated IoT data in 4 disaster scenarios | AR + IoT emulation | Data sets later open-sourced | AR track: JANUS Research and North Star Simulations tied 1st ($25K each); BadVR 3rd. https://www.us-ignite.org/chariot-challenge/ |
| 19 | **Perimeter / WICS / KIS Fire View**, NSIN "Beat the Blaze" (2021; context) | Real-time incident info sharing between civilian and Guard responders that works with poor connectivity; live fire-perimeter maps | Mobile, drone imagery | Fire chief quote: "Fifteen minutes would be phenomenal" (vs daily updates) | 3 winners, $15K contracts each; Perimeter later raised $1.2M. https://blumcenter.berkeley.edu/students-alum-solve-wildfire-challenges/ |
| 20 | **Korea, NFA (소방청) 6th Fire-Safety Big Data and Idea Contest** (awards 14-16 Sep 2026) | 303 entries (+121% YoY). Grand prizes: "오늘의 수리" (finds unmaintained hydrants), "안심동행 119", "EV-SAFE 119". Top-excellence prize: **"FireGround-AI"** (links 119 reports, drone and thermal imaging; fire simulation) | Public fire data + AI | Data-driven fixes for current fire-service problems | 12 awards. https://www.newspim.com/news/view/20260916000535 ; https://www.safetynews.co.kr/news/articleView.html?idxno=250601 |
| 21 | **Korea, MOIS 4th Disaster-Safety Data Startup Contest** (results 30 Jul 2026) | **"트윈세이퍼" (Auto-Safer team)**: puts disaster data and real-time observations into a **digital twin**; AI predicts risk and supports response decisions and tabletop training | Digital twin + AI | Real-time + digital twin + decision support | **Grand prize** (59 entries, 10 finalists). https://newsseoul.co.kr/news/view/1065586822899753 |

Other leads checked but unconfirmed or tangential:
- **Dispatch Ops**, Mistral Worldwide Hackathon NY (Feb-Mar 2026): AI dispatch combining real-time maps with Mistral triage. Award unverified. https://twyoon.com/writings/mistral-worldwide-hackathon-2026-recap/
- **YC Voice Agents Hackathon** (Cactus x YC x DeepMind, ~Apr 2026): a YouTube video titles itself "Winning Y Combinator Hackathon with an On-Device Voice Agent in 24 Hours", built "for firefighters". The project and award are unverified. https://www.youtube.com/watch?v=KuzUJNjJvAs
- **Fire Resilience Hackathon** (mimik + Kwaai, 21 Feb-7 Mar 2025, LA): judges included a retired LA Fire captain and a fire chief; $10K; 40+ teams. Winners not published in the sources I found. https://fire-emergency-hackathon.devpost.com/ ; https://mimik.com/our-events/fire-resilience-emergency-response-disaster-recovery-hackathon-powered-by-mimik-and-kwaai-at-scale-22x
- **KTU DIGITWIN** (Dec 2022): main prize for a prototype showing which rooms people are trapped in, relayed by dispatch to firefighters. https://en.ktu.edu/news/a-team-determined-to-help-firefighters-wins-the-ktu-digital-twins-hackathon/
- **XPRIZE Wildfire** ($11M, 2026): Autonomous track 1st was Anduril, 2nd Dryad (per Forbes, 1 Nov 2026). Defence-adjacent and hardware-heavy, so not our lane. https://forbes.com/sites/cathyrubin/2026/11/01/can-ai-save-the-planet-how-nine-innovators-are-fighting-climate-change ; https://www.xprize.org/news/finals-testing-autonomous-wildfire-response
- **Korean government R&D, not a contest**: MSIT + MOIS, "재난안전통신망 연동 스마트워치 및 AI 무전요약·알림시스템", 2 years, 900M KRW, call closed 7 Sep 2026. Also monitors heart rate, skin temperature and location. https://www.news1.kr/it-science/general-science/6259675 ; https://edaily.co.kr/News/Read?mediaCodeNo=257&newsId=01439926645548304
- **경북소방본부 1st AI contest** (2026): 12 of 50 firefighter proposals selected, including "radio information analysis" (무전 정보 분석). https://www.eroun.net/news/articleView.html?idxno=92272
- **NFA "Fire AI expert pool"** (Oct 2026): 40 AI-capable firefighters selected to build AI services. https://www.mt.co.kr/policy/2026/10/14/2026101409302784902
- Not found: any **Call for Code 2022-2025** global winner, **NASA Space Apps 2023-2025** global winner or **Imagine Cup 2023-2025** winner in firefighting. Phoenix Eye (Space Apps 2023) was a wildfire-forecast *global finalist* only.

---

## 2. Patterns: winners vs also-rans in this domain

**Winners tend to:**
1. **Show one complete, working loop live**: input, AI, prioritised output, human decision. DispatchAI runs a real call through to a ranked queue and dispatcher approval. Alert X runs vision, mapping, reasoning, then a human approves before the briefing goes out. Both wins stress a human-in-the-loop gate.
2. **Have a credible domain anchor**: a firefighter on the team (Prometeo), a pain point named by the agency (FireForm and CAL FIRE), or a builder who lives the problem (CrossBeam, Geo-ML, TARA, PostVisit). The Meta event page frames "Build for Your World" as solving "a problem you know firsthand". https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md
3. **Use real artefacts somewhere in the demo**: real road dashcam footage (TARA), real Palisades radio audio (Firewatch), real 2020 fire perimeters (ResQueue). Pure synthetic worlds read as toys. **[inference from the cases above]**
4. **Make deep, visible use of the sponsor's stack**: DispatchAI took "Best Use of Intel AI" by measuring the IPEX speed-up; FireflAI won the Fetch.ai sponsor prize by making its agents visible; Geo-ML won "Best Llama API Usage". Sponsor-tool prizes go to projects where the tool is load-bearing and shown on screen.
5. **Keep the user surface narrow and finished**: one dashboard and one phone view, not five apps.

**Also-rans (FireSight, Firewatch, ResQueue, Dispatch Ops: no grand prize found)** were often technically *richer* than the winners: 3D reconstruction, many APIs, MCP, SpacetimeDB. They tend to put the commander dashboard at the centre and have diffuse stories. **[inference: the absence of an award is not proof of a loss; those results were simply not reported]**. The 2026 cluster of near-identical "fire incident copilot" builds means judges may have seen this concept before. We need a distinct hook.

**What judges and organisers praised (quotes <15 words):**
- Cerebral Valley's Ivan Porollo on Llama Impact: "demonstrate how open source AI can create positive social impact". https://about.fb.com/news/2024/11/metas-llama-impact-hackathon-pioneering-ai-solutions-for-public-good/
- UCSC OSPO on Reboot the Earth: "genuine potential to save lives and protect communities". https://news.ucsc.edu/2025/11/ai-solutions-wildfire-mitigation-reboot-the-earth-hackathon/
- Daily.co on its realtime-AI winner: "seamless combination of video, voice AI, and map navigation". https://www.daily.co/blog/open-source-realtime-ai-hackathon-winner-announcement/
- Commentary on the Opus 4.6 results: "expertise trumps coding" (Dexter Hadley, via GIGAZINE). https://gigazine.net/gsc_news/en/20260425-anthropic-hackathon/
- Judge essay (Abgar Simonean, HackerNoon, Jan 2026): "do not delegate the innovation to AI". Judges also favour the presenter's own voice and face over AI voiceover. https://hackernoon.com/from-the-judges-seat-standing-out-in-hackathons-in-the-age-of-ai

---

## 3. Common failure modes

- **Fake data with nothing real.** A demo world where every element is invented reads as a mock-up. Best practice from Firewatch and ResQueue: mix synthetic scenario data with *one* real public artefact, and label which is which. Judges tolerate mocks but punish misrepresentation: "Never pretend a broken thing works", and judges will ask you to click it (2026 guide summary). https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/ **[snippet; page 403]**
- **No real time.** "Real-time" claimed but shown as a static page. Responders care about latency ("Fifteen minutes would be phenomenal"). Show streaming transcription and tag latency on screen.
- **Scope too wide.** Teams build 3D twins, drones, sensors, bodycams and maps and lose the mental model ("overbuilt projects"). https://hackernoon.com/from-the-judges-seat-standing-out-in-hackathons-in-the-age-of-ai
- **Demo dies on stage.** API rate limits or network failures. Guides recommend cached fallbacks and an offline "demo mode" toggle; Firewatch shipped a deterministic fixture mode. https://github.com/Anastassy/fire-incident-copilot
- **Overclaiming safety outcomes.** Firewatch explicitly claims no validated reduction in casualties. Medical or safety overclaims hurt credibility, and in this hackathon medical advice is an anti-project.
- **Sponsor model used thinly.** One LLM call wrapped in UI. Prizes went to entries where the sponsor tech is load-bearing (Intel IPEX numbers, Llama API structured extraction).

---

## 4. Demo-video patterns that worked

- **Length.** Hard caps of 2-3 minutes are common, and judges may stop at the cap: "judges will be instructed to stop watching... after the first three minutes". Lead with the product, not a team intro. https://tips.hackathon.com/article/creating-the-best-demo-video-for-a-hackathon-what-to-know ; https://dev.to/jacklynbiggin/how-to-make-your-devpost-submissions-not-suck-37i0
- **Structure that recurs in winners** **[inference from DispatchAI, Alert X, FireSight, Firewatch]**:
  1. A 10-20 s hook: the real-world failure, ideally with real audio or a cited report.
  2. A live scenario run end to end with a visible clock.
  3. A human decision moment (approve, dispatch, acknowledge).
  4. A short architecture slide showing which model does what.
  5. Honest limits and next steps.
- **Live vs scripted.** The strongest pattern is a *scripted scenario driven by live model calls*. FireSight shipped one curated demo and one fully live demo; Firewatch replays recorded radio through live agents. Pre-recorded inputs with live inference is accepted practice. Never fake the inference.
- **Human presence.** Use your own voice and face rather than TTS narration (HackerNoon judge). Captions are fine for a non-native speaker.
- **Map the video to the rubric.** Name each judging criterion on screen as you hit it. https://civiso.notion.site/What-do-I-include-in-my-Devpost-Submission-Demo-c2cb13c36bae44cb8847d7f1ad403e8a

---

## 5. Implications for our product

**Do these:**
1. **Lead with the responder-side loop, which none of the 2026 lookalikes centre on.** FireflAI, FireSight, Firewatch and ResQueue centre the dispatcher or IC dashboard. Our hook: one radio burst goes to muse-voice-transcribe, then muse-spark tags it (Danger / Victim Found / Help Needed). A *different, filtered* audio brief goes to each firefighter's simulated earpiece, and a one-tap victim mark updates the commander's map. Show both screens side by side in the video.
2. **Make mayday/priority triage the money shot, with a measurable before/after.** Play 30 s of overlapping radio traffic with a buried "Mayday" or "victim found" (Bridgeport 2010: maydays not heard). Show the system surfacing it to the top within N seconds, with a timer on screen. Precedent: DispatchAI's severity-sorted queue won a grand prize.
3. **Use one real public artefact, labelled.** For example, use real fireground radio from a public, CC-licensed source (Firewatch used Broadcastify Palisades audio under CC BY 3.0), or replay the Pyeongtaek or Mungyeong timeline from official reports. Keep synthetic people and positions labelled "synthetic".
4. **Put the Korean angle on screen:** bilingual Korean/English radio and keyword biasing for Korean fireground terms (구조대상자, 탈출, 메이데이). Cite the Aug 2026 MSIT/MOIS 900M KRW "AI 무전요약 smartwatch" R&D call and NFA's 2026 fire-AI expert pool as evidence of demand. This answers "Build for Your World" more convincingly than a US-only story.
5. **Make Meta-model depth visible (25% weight).** Show a pipeline panel listing each model's job: transcribe with diarization and keyword bias, then Spark with JSON-schema tags and tool calls that mutate world state, then SAM 3.1 tagging victims or hazards in a helmet-cam or thermal frame, with optional muse-image for the floor-plan base. Prizes go to entries whose sponsor tooling is load-bearing and shown (Geo-ML, DispatchAI/Intel).
6. **Show the agent acting, not just summarising (Agentic $5K prize).** Spark calls tools (`update_victim_estimate`, `assign_team`, `push_brief(ff_id)`, `escalate_mayday`) on a shared world state, with a human-approval gate for orders. Alert X and DispatchAI both kept an approval step, and FireflAI won a sponsor prize by making its agent feed visible.
7. **Build a deterministic demo mode.** Cache replayed audio chunks and keep one live path. Rehearse a 2:50 video: hook (real failure plus citation, 15 s), live scenario (2 min), architecture plus Meta models (20 s), limits (10 s). Use your own voice.
8. **Keep honest scope language** in the README and video ("decision support; simulated hardware; not certified"), as Firewatch did. This protects the Impact score from overclaim penalties.
9. **Do one viral-friendly visual:** a split screen of chaotic radio audio with a waveform, next to a calm earpiece brief ("Team 2: victim reported 2F east, your egress is stairwell B"). OpenGlass shows that wearables plus AI travel well socially.

**Do NOT do these:**
1. **Do not build a 3D digital twin, drone integration or full building reconstruction.** That is FireflAI's and FireSight's territory, a huge time sink for a solo 17-hour build, and it would make us look like a me-too. A 2D floor-plan grid with live pins is enough.
2. **Do not make it a chatbot or Q&A over incident documents.** That reads as "basic RAG" (an anti-project), and Firewatch and FireSight already have tactical Q&A. Every AI output should be a structured state change or tag, not chat.
3. **Do not drift into medical triage or victim-health advice**, as the Llama Impact winners Guardian and First Aid did. In this hackathon it is a disqualifying anti-project. "Victim Found" means location and status only, with no clinical guidance. Also avoid defence or "tactical military" language: the XPRIZE winner was Anduril, and the war-related exclusion applies.

---

## Sources count and gaps

- About 45 distinct URLs cited above.
- **Gaps:**
  - Devpost pages (DispatchAI, FireflAI, Firewire, the UC Berkeley 2026 gallery) and the JetBrains judging blog returned 403. Their facts come from search snippets.
  - No official judge quotes exist for the firefighter-specific winners.
  - Nothing found on Call for Code 2022-25, NASA Space Apps 2023-25 global winners, Imagine Cup 2023-25, or HackMIT/PennApps winners with firefighter projects.
  - The YC voice-agent firefighter project and the Mistral "Dispatch Ops" awards are unverified.
  - The Meta event page lists indie judging as creativity, technical ambition and "whether they work". The weights in our brief (Impact 30 / Meta tooling 25 / Demo 25 / Technical depth 20) were not on that page, so verify them against the official rules. The page also shows a deadline discrepancy: "Nov 5 UTC" vs "Nov 4 9:00 PM ET".
