# Commercial Services A: Global Incumbents and Pain Points

Stream: commercial services (global incumbents). Compiled 2026-11-04 for the Meta Global AI Developer Hackathon 2026 entry (firefighter indoor/outdoor coordination system).
Tags used below: **[V]** = verified from the cited source (often a vendor's own claim, flagged as such); **[I]** = our inference.

---

## 0. TL;DR

- **Today, AI radio transcription is sold to the 911 center (PSAP), not used on the fireground.** Prepared (now Axon), Motorola Assist, Carbyne (now Axon) and RapidSOS Harmony all sell to dispatchers. None we found filters intel per responder or pushes triaged intel back to interior crews. That is the gap we can fill. [V/I]
- **The core failure is still voice.** Project Mayday found 36% of maydays were missed on the first call and acknowledgement took about 79 seconds on average. 47% of callers cited too much radio traffic (Firehouse, 2019). At NIOSH Bridgeport (F2010-18), the IC was working two channels on two handhelds. [V]
- **The fire service's own design research favours audio and consolidation over new screens.** NIST's fire volume (SP 1286pt3, Jan 2023) found that fewer than 10% of firefighters chose smart glasses, AR or VR as useful. A work-issued wireless earpiece was on their list of wanted existing tech. An IC quote asks to "consolidate it down". [V]
- **Precise indoor location is still unsolved** after 15+ years of programmes: GLANSER about 3 m, Q-Track 45 cm only with pre-calibration, POINTER still not visibly fielded. Responders themselves say room-level is the goal. Our demo must not claim sensor-grade localisation. [V]

---

## 1. Radio / push-to-talk layer

### Motorola Solutions: APX NEXT, SVX, Assist, ViQi, Dispatcher Assist Suite
- **What it does.** APX NEXT is a P25 LMR + LTE smart radio. ViQi is an on-radio voice assistant for radio controls. SVX (launched Apr 2025) combines a remote speaker mic and body cam with voice isolation. **Assist** is a cloud AI platform for transcription, translation and summaries. [V] [Motorola press release, Apr 2025](https://www.motorolasolutions.com/newsroom/press-releases/motorola-solutions-launches-svx-and-assist.html), [BusinessWire](https://www.businesswire.com/news/home/20250418359204/en)
- APX NEXT XE for fire was launched in Sep 2020 as a "purpose-built" fire radio. [V] [BusinessWire 2020](https://www.businesswire.com/news/home/20200923005544/en)
- The Dispatcher Assist Suite advertises "transcribe field unit radio traffic" and 911-call summaries. Its page gives **no accuracy metrics, no mayday/keyword detection and no fireground-specific features.** [V] [Motorola Dispatcher Assist](https://www.motorolasolutions.com/en_us/ai/assist-dispatcher-suite.html)
- **Who buys.** Agencies with P25 systems: public-safety radio is the anchor purchase and AI is upsold on top. [I]
- **Limits the vendor admits or press reports.** Assist transcription is **cloud-based and needs LTE**, and coverage frames it as a 911-center feature ([Urgent Comms](https://urgentcomm.com/devices/motorola-solutions-unveils-combo-rsm-and-body-cam-with-multiple-ai-capabilities); [Verdict](https://www.verdict.co.uk/motorola-ai-emergency-svx/)). A Motorola executive said industry transcription had been about 70–80% accurate and that Assist reaches "well over 90%". This is a **vendor claim, not fire-specific and not independently tested**. [V-vendor] [Gazette coverage](https://gazette.com/?p=1458539)
- **Pain points (primary evidence).** NIST survey: **1 in 2 firefighters had channel issues** with their radios at least "sometimes", and **75% had coverage and price problems**. One respondent wrote that 800 MHz radios "DO NOT WORK ON INTERIOR INCIDENTS". [V] [NIST SP 1286pt3, Jan 2023](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf). New radios add channels that "may just cause frustration" (same source). In other words, the LTE-dependent AI layer is weakest exactly where interior crews operate. [I]

### FirstNet (AT&T) push-to-talk
- **What it does.** Band-14 LTE network with mission-critical PTT. FirstNet itself positions it as a **complement to LMR, not a replacement**, for redundancy and in-building use where broadband works. [V] [FirstNet fire blog](https://firstnet.gov/newsroom/blog/game-changing-benefits-push-talk-fire-service); [FirstNet for Fire 2022 PDF](https://www.firstnet.gov/sites/default/files/FirstNet%20for%20Fire%20Service%202022.pdf)
- **Adoption.** Over 7 million connections reported in 2025. [V] [Wireless Estimator 2025](https://wirelessestimator.com/articles/2025/firstnet-surpasses-7-million-connections-expands-nations-largest-coverage-footprint-for-first-responders/)
- **Pain points.** AT&T has itself argued that in-building coverage requirements for FirstNet should mirror the fire-code requirements for LMR, which concedes that in-building broadband coverage is not guaranteed. [V] [Urgent Comms, Mar 2022](https://urgentcomm.com/2022/03/23/att-calls-for-lmr-like-hardening-coverage-for-firstnet-in-building-systems/)
- Infrastructure burns too. In the Palisades fire (Jan 2025), radio and cell sites serving the area burned, and the Green Mountain repeater was shut down. [V] [LAist summary of LAFD AAR, Oct 2025](https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire)

### Zello
- **What it does.** Smartphone PTT app. Enterprise tier made **free for first responders** in 2019, extended globally in 2020. Zello says fire departments showed the most interest. [V-vendor] [BusinessWire 2019](https://businesswire.com/news/home/20190812005412/en/Zello-Enterprise-Grade-Push-to-Talk-Service-Free-Responders); [Zello program update](https://blog.zello.com/zello-for-first-responders-program-update)
- **Pain points / positioning.** Mostly volunteer and disaster coordination. No fireground-grade evidence found. Our read: it shows crews will adopt free phone-based voice tools, but it does not address interior reliability. [I]

---

## 2. PSAP / dispatch AI (transcription, summarisation, triage)

### Prepared (Prepared 911): now Axon
- **What it does.** Assistive AI for 911: live call transcription and translation, AI summaries, **radio channel monitoring**, protocol adherence. Its blog says it transcribes radio traffic in real time and **flags keywords like "mayday"** for the dispatcher. [V-vendor] [Prepared blog](https://www.prepared911.com/blog/how-are-911-centers-using-ai-powered-technology); [Baltimore selection, Jan 2025](https://www.businesswire.com/news/home/20250122406178/en)
- **Adoption.** Claims more than 1,000 agencies across 49 states. **Axon acquired the remaining stake on 1 Oct 2025** for about $728M incremental consideration (per aggregator citing the 10-K; figures vary). [V/secondary] [VectorShift deal summary](https://vectorshift.ai/research/deals/axon-enterprise-invictus-apps-prepared-2025)
- **Pain point it addresses.** Dispatcher workload and staffing. [V] [Prepared blog on staffing](https://www.prepared911.com/blog/assistive-ai-for-911-staffing-call-volume)
- **What it does not do (inferred).** Its outputs are dispatcher-facing. We found no evidence of per-firefighter audio briefings or interior-crew delivery. [I]

### Carbyne APEX: now Axon
- **What it does.** Cloud-native NG911 call handling with AI transcription, two-way translation in 37+ languages (counts vary by source), caller live video and "Responder Connect". [V-vendor] [Carbyne AI page](https://carbyne.com/solutions/ai-that-works-for-you)
- **Adoption.** Customers include Atlanta and Orange County Fire Rescue. Axon announced the acquisition on 4 Nov 2025 ($625M); it reportedly closed in Q1 2026. [V/secondary] [Security Journal Americas](https://securityjournalamericas.com/axon-agreement-to-acquire-carbyne/)
- **Implication.** Axon now owns "call to closure" at the PSAP and is moving toward the field. Incumbents are consolidating fast, but around the call center. [I]

### RapidSOS Harmony
- **What it does.** "AI copilot for 911" (May 2024) that integrates with CAD and field-responder apps. Live call summary and transcript sharing across jurisdictions. Delivered via the AT&T ESInet as of Apr 2026. Claims connection to about 1M field responders. [V-vendor] [RapidSOS Harmony launch](https://rapidsos.com/rapidsos-introduces-harmony-the-first-ai-copilot-for-911/); [Urgent Comms May 2024](https://urgentcomm.com/2024/05/22/rapidsos-unveils-innovations-in-new-offerings-for-911-public-safety/)
- **Pain point.** The data travels with the 911 call, not with fireground radio. [I]

### Delphini (Smart Response Technologies): niche "radio intelligence" startup
- **What it does.** Live radio-to-text with channel, unit and timestamp tags, reportedly in under 2 s. Feeds keyword alerting and after-action review. It **claims** its model handles SCBA masks, sirens and overlapping transmissions. **No accuracy figures, customers or price published.** [V-vendor] [Delphini AI transcription](https://www.smartresponsetech.com/platform/ai-transcription.html)
- The SCBA claim matters because it names the hard problem, but it is unverified.

### Hexagon HxGN OnCall Dispatch (Intergraph CAD)
- **What it does.** Police, fire and EMS CAD with "Smart Advisor" analytical agents. Integrates with RapidSOS so fire-alarm signals auto-create incidents (El Paso, 2024). Fire brigades such as Kassel (DE) and Hamburg use it. [V-vendor] [Hexagon OnCall Dispatch](https://hexagon.com/products/hxgn-oncall-dispatch); [Hexagon/RapidSOS El Paso](https://hexagon.com/company/newsroom/press-releases/2024/hexagon-rapidsos-introduce-solution-to-speed-fire-response-in-el-paso)
- **Pain point (integration silo).** CAD knows the incident and the units dispatched; it does not know who is on which floor. The fireground picture is rebuilt by voice. In the Palisades fire, Metro Fire Communications kept contacting resources directly and bypassed the incident comms plan. [V] [LAist/LAFD AAR](https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire)

### Corti / Flock
- Not researched in depth (time-box). Corti is medical-call AI, adjacent to the hackathon's medical-advice anti-project, so we should not position against it. Flock is law-enforcement ALPR/RTCC. See Gaps.

---

## 3. Fireground tracking and accountability hardware

### MSA LUNAR + FireGrid (+ G1 SCBA)
- **What it does.** Handheld thermal-imaging device that shows teammates' direction and distance and has a cloud connection to FireGrid. Pairs over Bluetooth with the G1 SCBA for air and alarm status, and with Altair gas detectors. FireGrid Map View uses device GPS for crew positions. Launched 2021. [V-vendor] [MSA LUNAR docs](https://docs.msasafety.com/lunar/en-us/Content/LUNAR/LUNAROverview.htm); [Fire Engineering launch](https://www.fireengineering.com/firefighter-training/breakthrough-technology-for-firefighter-search-and-rescue-now-a-reality-from-msa-safety/)
- **Price and adoption.** Retail about **$3.3k per unit** (list about $4.1k, undated listing). Sold through the MSA+ subscription on 36–60-month contracts. Example: Easton, PA bought one per firefighter (Jul 2022). No unit totals found. [V] [Safety Equipment Store listing](https://thesafetyequipmentstore.com/msa-10214747.html); [MSA Easton](https://blog.msafire.com/connected-firefighter-video-city-of-easton-chooses-lunar-connected-device/)
- **Pain points.** Per-firefighter hardware cost, lock-in to MSA SCBA, and GPS-based mapping that is weak indoors. [I, based on cost data and the localisation literature below]

### Dräger Bodyguard 7000 + PSS Merlin telemetry
- **What it does.** Electronic SCBA monitor showing cylinder pressure, time to whistle and auto/manual distress signals. Merlin telemetry sends status to an entry-control board **(up to 12 wearers per board)**. RFID tallies for log-on. [V-vendor] [Dräger Bodyguard 7000](https://www.draeger.com/en_me/Products/Bodyguard-7000); [Merlin product sheet](https://products.papertrail.io/downloads/draeger/Product_Sheet_Merlin.pdf)
- **Who buys.** UK and EU fire and rescue services; Dorset FRS reported improved entry control in 2013. [V] [HSM Search](https://www.hsmsearch.com/page_254510.asp). The "FireGround" brand name in the brief could not be confirmed.
- **Pain point.** Telemetry carries air status and alarms, not the content of what crews say. [I]

### 3AM Innovations: FLARE (wearable mesh) and FLORIAN (software)
- **FLARE.** Wearable mesh network that logs inside/outside position and temperature. A beta was planned for 2017. **We found no confirmed 2024–25 field deployment of FLARE.** [V] [UpstartNY 2017](https://upstartny.org/features/threeam.aspx)
- **FLORIAN.** Decision-support and personnel accountability system (PAS) with AVL, smartphone location sharing (including height), 3D maps, geofences and alerts on "a single customizable screen". **Philadelphia FD signed a 5-year deal (May 2024).** Orchard Park FD (Bills stadium) also uses it. [V-vendor] [Firehouse, May 2024](https://www.firehouse.com/tech-comm/personnel-management-software/press-release/55055205/3am-innovations-provides-essential-technology-for-essential-work-philadelphia-fire-department-selects-3am-innovations-for-pas)
- **Pain point.** Indoor accuracy figures for FLARE are unpublished. The closest research figures come from a separate NIOSH-funded "FLARE"-type grant (Q-Track): **45 cm RMS, but only after pre-calibrating the building**, which is rarely possible at real scenes. [V] [CDC Stacks 218953](https://stacks.cdc.gov/view/cdc/218953)

### Qwake Technologies C-THRU
- **What it does.** Helmet/SCBA-mounted monocular thermal AR that outlines edges in green. The IC can watch each helmet's feed. [V] [DHS S&T fact sheet, Aug 2023](https://dhs.gov/sites/default/files/2023-08/23_0814_st_real_time_indoor_vis_system_fact_sheet.pdf)
- **Price and adoption.** About **$5k per unit** (DHS); Menlo Park contract $210k for 40 firefighters; later press says $5–10k. **Still pilots:** about 10 departments, including Carmel (IN, nonprofit-funded, 2026) and Colorado Springs (May 2026). [V] [Almanac, Dec 2024](https://www.almanacnews.com/public-safety/2024/12/25/menlo-park-fire-will-be-the-first-to-use-new-ar-tool/); [Axios, May 2026](https://www.axios.com/local/colorado-springs/2026/05/29/ar-firefighter-helmets-test-colorado-spring)
- **Pain points.** Menlo Park engineering said it **adds about 4 lb to a 4 lb helmet**, and the company acknowledges bulk. [V] [Almanac](https://www.almanacnews.com/public-safety/2024/12/25/menlo-park-fire-will-be-the-first-to-use-new-ar-tool/). NIST found **fewer than 10% of firefighters** picked AR or smart glasses as useful. [V] [NIST SP 1286pt3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf)

### Indoor localisation programmes (background)
- **GLANSER** (Honeywell/TRX): design goal of **3 m**; 95% correct floor in a 2012 trial. **TRX NEON** was integrated with the Motorola APX. Facella concluded "a solution has not proven to be easy". **Note: dated Nov 2014.** [V] [FireRescue1, 2014](https://www.firerescue1.com/fire-products/communications/articles/firefighter-location-technology-whats-available-UTxxQfDihaQMVDlW)
- **POINTER** (DHS S&T / NASA JPL): magneto-quasistatic fields; press claims accuracy of centimetres to inches. Licensed via Caltech spin-out; commercial release was projected for 2022. **No 2026 fielding evidence found.** [V] [NASA JPL](https://www.nasa.gov/centers-and-facilities/jpl/pointer-seeing-through-walls-to-help-locate-firefighters/)
- **NIST** ran a first-responder tracking test at its "dots" test bed (more than 2,000 surveyed points) in May 2025, which shows the problem is still open. [V] [Critical Comms](https://www.criticalcomms.com.au/content/research/article/how-thousands-of-tiny-dots-could-save-first-responders-lives-70272490)
- A responder survey ranked location accuracy as the top requirement (90.4%) and set **room-level** as the goal. [V] [USC SeqLocal paper](https://anrg.usc.edu/www/papers/NanLi_SeqLocal.pdf)
- NIST interview quote: "why can't they find me based on my radio?" [V] [NIST SP 1286pt3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf)

---

## 4. Incident-management / alerting apps

### Tablet Command
- **What it does.** iPad incident command with CAD interface, unit tracking, configurable **PAR and work timers**, and post-incident review. [V-vendor] [tabletcommand.com](https://tabletcommand.com)
- **Price and adoption (public contracts).**
  - Penryn FPD: $1,400/yr licence, about $2.6k/yr total. [civiciq](https://civiciq.com/public-contract/fbf435a2-59e5-47f8-bd30-ab932c259daf)
  - Berkeley: $77k initial, then up to $65k/yr (2024); $135k cap (2025). [Berkeley 2024](https://berkeleyca.gov/sites/default/files/documents/2024-06-04%20Item%2024%20Contract%20%20Tablet%20Command%20for%20Mobile%20CAD%20and%20Incident%20Command.pdf), [Berkeley 2025](https://berkeleyca.gov/sites/default/files/documents/2025-11-10%20Item%2002%20Contract%20%20Tablet%20Command%20for%20Mobile%20CAD.pdf)
  - Riverside County: up to $1.85M through 2028. [rivcocob](https://media.rivcocob.org/proceeds/2023/p2023_08_29_files/03.31001.pdf)
  - LAFD adopted it department-wide after the Palisades fire. [LA City Clerk, Feb 2026](https://cityclerk.lacity.org/onlinedocs/2026/26-0662_rpt_bof_2-10-26.pdf). A ~$43.8M purchase-order ceiling reported by a search summary is **UNVERIFIED** (scanned PDF, not readable).
- **Pain points.**
  - A gear test notes that "manual data entry can be cumbersome" for users not comfortable with iPads. [V] [Firefighter Nation gear test](https://www.firefighternation.com/?p=87454)
  - In a 31-person conference survey, 20 of 31 never use the technology, yet 26 of 31 believe it improves safety, and **training was named as the barrier**. [V] [Fire Engineering](https://www.fireengineering.com/?p=260914)
  - Accountability on a tablet still depends on someone typing what radio said. [I]

### Active911
- **What it does.** Mobile alerting, radio integration, mapping and scheduling. From about **$14** (Capterra). **Zero user reviews** on Capterra and SoftwareReview, so no independent voice could be found. [V] [Capterra](https://www.capterra.com/p/196556/Active911/)

### Pathfinder
- Not located or verified within the time-box. See Gaps.

---

## 5. Peripheral: public alerting and traffic

- **Genasys Protect / EVAC (Zonehaven).** Zone-based evacuation planning and alerting for counties and fire agencies. LA County awarded a 5-year contract. Outward-facing (to the public), not crew coordination. [V-vendor] [Genasys LA County](https://genasys.com/press-releases/los-angeles-county-awards-5-year-contract-to-genasys-for-evacuation-management-solution/)
- **HAAS Alert Safety Cloud.** Responder-to-vehicle and responder-to-responder digital alerts via Waze, Apple Maps and OEM infotainment. Standard on Rosenbauer and Marion apparatus. Under $400/yr per vehicle (Iowa City). Claims 800+ agencies. The "up to 90% fewer collisions" figure cites a University of Minnesota study that we could not see linked, so treat it as **vendor-cited**. [V] [Rosenbauer/HAAS](https://www.fireapparatusmagazine.com/fire-apparatus/rosenbauer-makes-haas-alerts-safety-cloud-standard-on-custom-fire-trucks); [Gazette, Iowa City](https://www.thegazette.com/?p=403495)
- **Takeaway for us.** Cheap, subscription-based, "set and forget" safety alerting gets standard-fit adoption. That supports a low-friction delivery model. [I]

---

## 6. Cross-cutting pain points vs evidence

| Pain point hunted | Evidence | Tag |
|---|---|---|
| **Maydays / critical traffic missed** | 36% of maydays missed on first call; ~79 s average to acknowledge; 47% cite too much radio traffic (Project Mayday via [Firehouse, Feb 2019](https://www.firehouse.com/safety-health/article/21040224/close-calls-mayday-reality-check-firehouse-magazine)). Bridgeport 2010: IC on two channels and two handhelds; transmissions missed while transmitting on the other ([NIOSH F2010-18](https://stacks.cdc.gov/view/cdc/163519); [STATter911](https://www.statter911.com/2011/06/30/niosh-says-bridgeport-fd-failed-to-respond-to-mayday-calls-in-double-lodds-many-failures-cited-in-deaths-of-lt-steve-velasquez-ff-michael-baik/)). Claim that only 2 of 5 maydays reached the IC comes from a secondary training doc ([Commack FD](https://commackfd.org/wp-content/uploads/2020/10/This-week-in-training-1-6-2016.pdf)). | V (last item secondary) |
| **IC cognitive overload** | NIST IC quote: "two 800 radios, a VHF, and two cellphones… too much information… consolidate it down" ([NIST SP 1286pt3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf)). The IC focused on downed firefighters and missed other frequencies ([Fire Engineering](https://www.fireengineering.com/firefighting/fireground-radio-channel-to-switch-or-not-to-switch/)). Palisades fire: tactical channel overloaded, updates scattered across squirrel channels ([LAist](https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire)). | V |
| **Transcription accuracy on fireground audio** | **No independent fireground/SCBA WER benchmark found.** USFA: SCBA facepieces distort speech and degrade digital radio intelligibility ([USFA radio guide](https://www.usfa.fema.gov/downloads/pdf/publications/voice_radio_communications_guide_for_the_fire_service.pdf)). Mic placement relative to the SCBA voice port matters ([Firehouse](https://www.firehouse.com/technology/article/10470383/tips-for-improving-the-intelligibility-of-fireground-radio-transmissions)). Closest analogue: ATC radio ASR at about 9.8% WER after fine-tuning ([arXiv 2502.20311](https://arxiv.org/abs/2502.20311)). Vendor claims only: Motorola "well over 90%" and Delphini "SCBA-aware". | V (gap) |
| **Accountability (PAR) failures** | 68% of commanding officers lacked accountability in hand at the time of a mayday; 23% had practised mayday management (Project Mayday 2021 via [Fire Engineering, Rancourt](https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/)). A PAR works only if the firefighter can talk and the IC can hear ([Firefighter Nation](https://www.firefighternation.com/?p=86464)). In the Palisades fire, PAR/check-in calls themselves added load to the congested channel ([LAist](https://laist.com/news/climate-environment/chaos-conflict-and-drones-10-takeaways-from-lafds-report-on-the-palisades-fire)). | V |
| **Alert fatigue** | PASS alarms left on or muffled were a communication obstacle for 57% in one survey ([Fire Engineering](https://www.fireengineering.com/fdic/firefighter-communication-and-maydays/)). Heat-degraded PASS alarms went unheard in 4 NIOSH fatality cases, 2001–04 ([Fire Engineering](https://www.fireengineering.com/fire-safety/pass-alarm-signals-fail-at-high-temperatures/)). No quantified alarm-fatigue study found. | V / partly I |
| **Indoor tracking accuracy** | GLANSER 3 m (2014); Q-Track 45 cm only with pre-calibration; room-level is the stated goal; NIST still testing in 2025 (see §3). | V |
| **Cost** | "Price: too expensive" was the top problem firefighters "always" have with 9 of 10 devices, often 2:1 over other issues ([NIST SP 1286pt3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf)). Per-firefighter hardware runs about $3.3k (LUNAR) to about $5–10k (C-THRU). | V |
| **Training burden** | 20 of 31 never use tablet tech; training named as the main barrier ([Fire Engineering](https://www.fireengineering.com/?p=260914)). Only 23% of COs had practised maydays (Rancourt). | V |
| **"Another screen" rejection** | "Every time we provide something else for an IC to monitor, we take their eyes off something else." Survey: command software used 15%, GPS tracking 4%, biometric wearables 2% ([FireRescue1, Crouse, Oct 2025](https://www.firerescue1.com/technology/from-skepticism-to-standard-how-firefighters-adopt-new-technology)). NIST guideline 2 says technology should not create "cognitive overload". Guideline 6 asks for "Fisher-Price" design, big buttons, gloves; one quote reads "I don't have… the bandwidth to be looking at a lot of different things." | V |
| **Dispatch–fireground silos** | AI transcription products sell to PSAPs (Prepared, Motorola Assist, Carbyne, Harmony). In the Palisades fire, dispatch bypassed the incident comms plan (LAist). CAD knows units, not interior positions. | V + I |

---

## 7. Implications for our product

### Pain points we can credibly attack in the demo
1. **Mayday and critical-traffic surfacing for the IC.** Stream radio-style audio into muse-voice-transcribe, then use muse-spark structured output to tag each transmission (Danger / Victim Found / Help Needed / MAYDAY) and pin it to the top of the IC's view with an audible cue. Pitch it directly against "36% of maydays missed on first call, ~79 s to acknowledge" and Bridgeport's two-channel IC. Our contribution is **multi-channel consolidation**: one ranked queue across channels, which answers NIST's "consolidate it down".
2. **Fill the gap that PSAP-centric AI leaves.** Prepared, Motorola Assist, Carbyne and Harmony all serve the 911 desk. Our agent sits with the **IC and the interior crews** and pushes *filtered* intel back out per responder. Name the incumbents and say plainly "we don't replace them; we close the last 100 m".
3. **Audio-first per-firefighter briefings, with the display secondary.** NIST shows firefighters want a work-issued wireless earpiece and reject AR or smart glasses (<10%). Make the bone-conduction "brief" the hero interaction: short, prioritised, only what changes *your* task. Make the clip-on display glanceable with one big button, gloves-friendly per the "Fisher-Price" guideline.
4. **Automated PAR and accountability from voice.** Today PAR/check-in calls *add* to channel congestion (Palisades) and 68% of officers lacked accountability in hand. The world-model can infer "last heard / last location report / status" per crew from transcripts and flag silent crews. That removes PAR radio traffic instead of adding it.
5. **No new screen for the IC; it replaces paper and memory.** Answer Crouse's "another screen" critique by having the agent pre-digest (summary plus top-3 actions), so the display is something to glance at, not something to watch. Show it working through a chief's aide role.
6. **Cheap, software-only, layered on existing radio.** NIST guideline 1 ("improve current technology") and the cost data (price is the #1 complaint) favour a phone-plus-earpiece layer over $3–10k per head of hardware. That is credible for Impact scoring.
7. **Dispatch to fireground continuity.** Ingest a CAD-like incident card (address, units) as the seed state of the world model, so outside command and interior crews share one state. This targets the silo seen in the Palisades AAR.
8. **After-action timeline for free.** Timestamped, tagged transcripts give automatic incident logs, the after-action/QA value incumbents (Delphini, Prepared) sell, at no extra effort.

### What we must not pretend to solve
- **Precise indoor localisation.** Fifteen years of GLANSER, POINTER and Q-Track have not delivered field-ready sub-room accuracy without pre-calibration. Present victim and responder positions as **human-reported, touch-marked, AI-estimated zones (room or floor level) with confidence**, never as sensor fixes.
- **Transcription accuracy under SCBA and fireground noise.** No public benchmark exists. Say we use clean or simulated audio in the demo, show confidence scores, keep the human in the loop, and never auto-dismiss an unrecognised possible mayday.
- **RF coverage, interior dead zones, repeater or cell-site loss.** We depend on whatever transport exists. Our cloud model calls inherit the same LTE weakness as Motorola Assist. Mention an offline/edge path (open-weights Muse) as future work only.
- **Replacing LMR, PASS, SCBA telemetry or CAD.** We sit on top of them.
- **Life-safety certification or autonomy.** The agent recommends and the IC decides. Avoid any wording that implies medical triage of victims, which the hackathon treats as a medical-advice anti-project.
- **Wearable hardware ergonomics.** It is simulated, so claim nothing about heat, water or weight; C-THRU's +4 lb shows how hard that is.
