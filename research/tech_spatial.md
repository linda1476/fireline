# Technical Papers B: Spatial State, Localisation, Perception, Hands-free UX

Stream: TECHNICAL PAPERS B. Compiled 2026-11-04 for the Meta Global AI Developer Hackathon 2026 (firefighter indoor-outdoor coordination system).

**Evidence labels used below**
- **[V]**: verified from the primary page I opened during this session.
- **[S]**: taken from a search-result snippet or summary. I did not open the full text, so check it before quoting on stage.
- **[Vendor]**: a vendor or press claim with no independent test data.
- **[Inference]**: my own reasoning, not a sourced fact.

---

## 0. TL;DR

1. **Nobody has solved infrastructure-free 1 m 3D firefighter tracking in public.** NIST/PSCR spent about $8M on the FRST Challenge. The Phase 5 live test ran 23–27 Oct 2023, and no per-team accuracy results were published. We are **not** a localisation system. We fuse coarse, zone-level position from voice and touch, and we have to present it that way.
2. **The world-model maths we need is old and simple.** It is a log-odds occupancy/belief grid, Bayesian search-theory updates (POC×(1−POD) then renormalise), decay toward the prior per cell, and Dempster–Shafer reliability discounting for conflicting human reports. Each one fits in under 50 lines of Python.
3. **Perception in smoke is thermal-first, and SAM has a measured thermal domain gap.** Lidar and visible cameras fail in dense smoke. In the demo, sam-3.1 should only run on visible-light or drone/helmet frames ("person", "door", "window"). It should not be presented as "seeing through smoke".
4. **The firefighters' own survey argues against heavy AR.** In NIST SP 1286pt3 (n=7,182 survey), fewer than 10% of firefighters chose AR, smart glasses or VR as useful. The things they ask for are reliability, simplicity, big glove-friendly buttons and less cognitive overload. Our "clip-on display" should be presented as an **audio-first radio accessory with one-touch glove targets**, not as AR.

---

## 1. Firefighter indoor localisation and tracking

### 1.1 Why GPS fails indoors (and why z matters)
- GPS works only partly indoors. Kjærgaard et al. ("Indoor Positioning Using GPS Revisited") report RMS 2D error below 5 m in wooden buildings and below 10 m in most brick/concrete buildings, using high-sensitivity receivers. Phone receivers did worse. The causes are low SNR, multipath and poor geometry. [S] https://archive.cs.helsinki.fi/www.cs.helsinki.fi/node/7537.html
- GNSS indoor fading depends on the dielectric properties of building materials, including reinforced concrete (Inside GNSS column series). [S] https://insidegnss.com/gnss-indoors-fighting-the-fading-part-2/
- Floor level (z-axis) is the open problem. The NIST 2015 Location-Based Services R&D Roadmap (TN 1883) says limiting location to "general proximity" stops responders from finding assets by z-axis, and it notes the US had no indoor position standards. [S] https://www.nist.gov/node/392426 and https://www.route-fifty.com/digital-government/2015/05/nist-maps-the-future-of-location-services-in-public-safety/286931
- **May 2026:** NIST PSCR opened a **Z-Axis Test Facility**. It sits in a 4-storey stairwell (450 m³, about 15 m vertical) with 50 OptiTrack cameras giving sub-cm ground truth. It follows ISO/IEC 18305 and is meant to feed revisions to an international standard. [V] https://www.nist.gov/news-events/news/2026/05/z-axis-test-facility-improving-indoor-localization-public-safety
- From the radio side: NIST's fire-service interviews include a survey quote that 800 MHz radios "DO NOT WORK ON INTERIOR INCIDENTS". Half of firefighter respondents had channel issues at least "sometimes", and 75% had coverage or price problems with radios. [V] https://doi.org/10.6028/NIST.SP.1286pt3 (PDF: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf)

### 1.2 Programmes (NIST / DHS / NASA)
| Programme | What | Key numbers | Status |
|---|---|---|---|
| **NIST PSCR FRST Challenge / FR3D** (run by IU CTIL, now RedLab) | Track responders in x, y, z with **no pre-deployed infrastructure** | Target **<1 m 3D**. The 1 m figure comes from a 2016 stakeholder group. $8M cooperative agreement; up to $5.6M in prizes over 5 phases | Phase 5 live test **23–27 Oct 2023**, Muscatatuck Urban Training Center. Winners: Ascent Integrated Tech $507.5k, Adapti Trace $507.5k, BC Sysnav $307.5k, Ravenswood $307.5k, Epic Blue $107.5k, CHARLI $22.05k. **No per-team accuracy published on the page.** [V] https://ctil.iu.edu/projects/frst-challenge/index.html |
| FRST coverage (Firehouse, 8 Feb 2024) | Winning approaches were "physical sensing" (inertial and similar) and "sensor fusion" (optical plus physical). Earlier phases also tried cellular, Wi-Fi, UWB, mesh, camera and lidar | Six finalists shared $1.9M | [V] https://www.firehouse.com/tech-comm/article/53082666/technological-innovations-to-track-firefighters-at-different-elevations |
| **DHS S&T + NASA JPL POINTER** | Magnetoquasistatic (MQS) fields from a truck-side transmitter, with a receiver on the firefighter. MQS is not blocked by building materials | Accuracy claims **conflict**: "a few inches" (JPL 2021) vs "<1 m in 3D" in a 3-level structure (NASA) | Commercialisation dates of 2017 and 2022 in the sources have passed, and I found no field data. [S] https://www.jpl.nasa.gov/news/pointer-seeing-through-walls-to-help-locate-firefighters, https://www.dhs.gov/science-and-technology/st-pointer-pinpoints-first-responder-locations |
| **NIST PSIAP: CMU (Rowe et al.)** infrastructure-free system | 3–4 perimeter beacons (GPS + LoRa + UWB + barometer). Wearables carry IMU + UWB. Firefighters enter in pairs. UWB ranges between peers correct IMU drift ("SLAM-inspired"). Positions go out over LoRa to the safety-chief display | UWB ranging ~10 cm. The team's earlier system averaged 31 cm (2015 MS indoor competition). **No full-system result** | Summary dated Jul 2019. [V] https://www.nist.gov/communications-technology-laboratory-ctl/pscr/infrastructure-free-localization-system-firefighters |
| **TRX Systems NEON** (NIST PSIAP funded) | Fuses inertial data, Wi-Fi/RF constraints and inferred building features (stairs, elevators, entrances) for map-matching. UWB/BLE beacons and NextNav z are optional | 8-month 24/7 trial with Arlington County FD. **No accuracy published** | [S] https://www.gpsworld.com/trx-awarded-nist-funding-for-neon-personnel-tracker/, https://www.nist.gov/document/firstresponder3dmappingandlocationpdf |

### 1.3 Technique-level accuracy numbers
| Technique | Number | Caveat | Source |
|---|---|---|---|
| Foot-mounted INS + ZUPT (OpenShoe) | **±0.2–1% of distance** on paths under 100 m, depending on path shape | Short trajectories only | [S] Nilsson et al. 2012, https://typeset.io/pdf/foot-mounted-ins-for-everybody-an-open-source-embedded-564ttxqg1i.pdf |
| OpenShoe-derived Osmium MIMU22BTP, long walks | **<4% relative error in 95%** of cases | Tails grow with duration | [S] (via same search; secondary) |
| ZUPT limits | ZUPT resets velocity, but **heading drift remains**. Body-worn PDR fails on irregular USAR gaits (crawling, side-stepping) | Crawling is common in fires | [S] https://scitepress.org/Papers/2013/42724/pdf/index.html, https://researchgate.net/profile/Stephane-Beauregard-3/publication/224699307 |
| Sysnav magneto-inertial (ankle-worn, sends x, y, z at 1 Hz over BLE to a phone) | "<1% of distance travelled" | **[Vendor]**, and the figure is for the soldier product | https://redlab.iu.edu/projects/frst-challenge/frst-challenge-competitors/bc-sysnav.html, https://shephardmedia.com/news/landwarfareintl/sysnav-unveils-gps-independent-soldier-tracking-system/ |
| UWB ad-hoc AoA + two-way ranging (TU Dortmund, WiMob 2020) | ~30 cm position, ~20° direction, in the lab | Lab only | [S] https://cni.etit.tu-dortmund.de/storages/cni-etit/r/Research/Publications/2020/Tiemann_WiMob/Tiemann_WiMob_10_2020.pdf |
| UWB "Bring Your Own Positioning System" (VTC 2023) | 95th-percentile 2D **40 cm at ≤6 m** with no obstructions; **1.2 m at ≤12 m with obstructions** | Short range only | [S] https://cni.etit.tu-dortmund.de/storages/cni-etit/r/Research/Publications/2023/Schmickmann_2023_VTCSpring/Schmickmann_2023_VTC.pdf |
| BLE beacons + phone | ~**<1.5 m in ~90%** in the best case. Composite RSS on phones inflates variance | Needs **pre-installed** beacons, so the FRST rules exclude it | [S] https://dspace.kmitl.ac.th/items/c5e5662b-8278-41ad-b06d-34548c7ecd58/full |
| Lidar-inertial in smoke | FAST-LIO2 **APE 12.8 m** (failed) vs radar-fused **~0.6 m** | Outdoor smoke test | [S] AF-RLIO, https://arxiv.org/pdf/2507.18317 |
| Lidar/camera SLAM vs radar | Lidar and camera SLAM "tend to fail" in smoke, dust or fog, so radar SLAM is proposed | | [S] https://www.sim.informatik.tu-darmstadt.de/publ/download/2021_torchalla_ssrr_radar_slam.pdf |

### 1.4 How commercial systems estimate position without infrastructure
**[Inference, consistent with the sources above]**
1. Dead-reckon from a foot or ankle IMU (step detection, ZUPT, heading).
2. Set the start position from GPS or a beacon at the entry point (CMU beacons, TRX).
3. Add z from a barometer, with differential pressure against an outdoor reference.
4. Bound drift with peer-to-peer UWB ranges, inferred landmarks (stairs = z change, corridors = straight segments, doors) and map-matching to a floor plan if one exists (TRX, Sysnav).
5. Send a low rate (~1 Hz) upstream over LoRa or phone.

### 1.5 Borrowable in 17h
- **Do not build PDR.** Simulate responder tracks as waypoints on a floor plan. Add an explicit **uncertainty radius that grows with time since the last fix**: `σ(t) = σ0 + k·d_walked`, with k ≈ 0.01–0.04 taken from the OpenShoe 0.2–1% / 4% figures. Snap it back down when a "fix" arrives: a voice landmark ("at stairwell B, floor 2"), a touch confirmation, or passing a door.
- **Landmark snapping (map-matching lite).** Voice mentions of named features ("stairwell B", "Charlie side", "room 204") resolve to a polygon on the plan, and the position is set to its centroid with a radius equal to the room size. muse-spark structured output can extract `{floor, zone_id, landmark, confidence}`.
- **Z as a discrete floor label**, not metres. This matches what the NIST roadmap calls the gap.

### 1.6 Do NOT claim
- Sub-metre tracking, any z accuracy in metres, or "works without infrastructure like FRST". Funded teams were still being tested in late 2023 and published no per-team accuracy.
- That our system localises firefighters. It **records and fuses reported** positions at room or zone granularity.
- POINTER-style "through-wall" accuracy. Its own sources disagree.

---

## 2. "World model" / common operating picture (COP)

### 2.1 What exists
- **Fire COP motivation:** situational awareness on fire scenes is built from verbal updates, radio transmissions and siloed software tools (paper on a DC fire department COP). [S] https://s3.amazonaws.com/amz.xcdsystem.com/44ECEE4F-033C-295C-BAE73278B7F9CA1D_abstract_File20450/PaperStage3FinalEdits_25427_0829111322.pdf
- **EU FASTER project SO8:** a portable COP that extends indoors, showing people's locations and sensor inputs and providing navigation. [S] https://www.faster-project.eu/project/so8-portable-common-operational-picture-for-maximizing-situational-awareness/
- **Fire system with voice + BIM + inertial positioning + multi-user sharing.** I only saw the catalogue entry, but it is the closest precedent to our pillar 3. [S] https://peeref.com/works/24500770
- **Digital twin survey of Irish firefighters (Osadcha et al.):** current systems give fragmented information. The authors call for **information prioritisation** and **federated** rather than centralised data. [S] https://ec-3.org/?p=15567
- **Victim-location maps in USAR robotics:**
  - Kenn & Pfeil (RoboCup 2005) put sound-source estimates into a probabilistic occupancy grid. [S] https://researchr.org/publication/KennP05
  - The MDPI Remote Sensing 2019 paper (11(22):2704) fuses vision, thermal and wireless victim maps with Bayesian fusion and uses the result to choose where to explore next. [S] https://dx.doi.org/10.3390/rs11222704
  - Bayesian map priors help indoor occupancy mapping in time-critical SAR (Georgiou et al., IJRR 2017). [S] https://eprints.whiterose.ac.uk/id/eprint/111297/1/map_priors_ijrr.pdf
- **Standards for indoor maps:**
  - OGC IndoorGML 2.0 Part 1 (conceptual model) was published **Aug 2025**. Its scope is indoor navigation spaces. [S] https://www.ogc.org/standards/indoorgml/
  - A 2026 ISPRS paper serves IndoorGML 2.0 as **IndoorJSON**, which is going through OGC standardisation. [S] https://isprs-archives.copernicus.org/articles/L-4-W1-2026/87/2026/

### 2.2 Borrowable maths (implement directly)

**(a) Belief grid per hazard or victim layer: log-odds with clamp and decay**
- Bayesian log-odds update ([S] https://av2.readthedocs.io/en/latest/theory/occupancy-grids.html):
  `l_t(c) = l_{t-1}(c) + log(p(z|c)/(1-p(z|c))) − l_0`
  With prior p = 0.5, l_0 = 0, so this reduces to `l ← l + l_sensor`.
- **Clamp** to `[l_min, l_max]`, for example [−4, +4], so the map can still change.
- **Decay toward the prior** for cells that have not been observed. Compute it lazily from per-cell timestamps, not with a sweep over the whole map:
  `l(c, now) = l_0 + (l(c, t_last) − l_0) · exp(−(now − t_last)/τ)`
  Use a different τ per layer, for example "fire seen here" τ ≈ 2–5 min and "victim reported here" τ ≈ 10–15 min. The τ values are **[Inference]**: tunable demo parameters with no published firefighter values.
- The map-decay literature treats decay as a weighted blend between a prior map and the online map. [S] https://arxiv.org/pdf/1810.02355

**(b) Probabilistic victim location: search theory (Koopman/Stone)**
- Start with a prior distribution over rooms or cells (POA/POC). Build it from occupancy cues such as bedrooms at night or 911-caller location.
- After an **unsuccessful** search of cell s with detection probability POD_s:
  `POC'_s = POC_s · (1 − POD_s) / (1 − POC_s · POD_s)`.
  Every other cell is scaled up by `1 / (1 − POC_s · POD_s)`, so the total stays at 1.
- Koopman random-search detection probability: `POD = 1 − exp(−coverage)`, where coverage = sweep width × track length / area.
- On a **positive** report ("victim found, room 204"), collapse that cell to "confirmed" and take that victim out of the search distribution.
- Sources: [S] https://www.alpine-rescue.org/system/production/article/documents/file/003/984/214988d41790b814ee835976ba4085d3059b903080dc8c1e293045bf6b444606/20-MRA-Search.pdf ; https://en.wikipedia.org/wiki/Bayesian_search_theory. These are secondary. The primary sources are Koopman, *Search and Screening* (1956), and Stone, *Theory of Optimal Search*.
- A "searched" mark from a touch interaction maps directly to a POD (for example primary search 0.7, secondary 0.9). Those POD values are **[Inference]** demo parameters.

**(c) Conflict resolution between reports: Dempster–Shafer discounting**
- Each report is a mass function m over a frame such as {victim, no-victim}, with Θ = "unknown".
- Discount it by the source reliability α:
  `m'(A) = α·m(A)` for A ≠ Θ, and `m'(Θ) = 1 − α + α·m(Θ)`.
- Combine reports with Dempster's rule. **Compute the conflict mass K** and **raise any high-K disagreement to the commander** instead of silently fusing it. Dempster's rule behaves badly under high conflict, and identifying the false source is still an open problem.
- Human-report reliability is "often unknown beforehand". Proposed workarounds are consensus-based credibility (Wickramarathne/Premaratne/Murthi) and distance-to-other-sources.
- Sources: [S] https://scholarship.miami.edu/esploro/outputs/bookChapter/Consensus-Based-Credibility-Estimation-of-Soft-Evidence/991031600301002976 ; https://sas-space.sas.ac.uk/1063/1/S_Hartmann_Dempster-Shafer.pdf
- A simpler alternative for 17h: a weighted log-odds sum. Weight = reliability (first-hand visual > heard > relayed), multiplied by ASR confidence, multiplied by recency.

**(d) Indoor ↔ outdoor alignment (floor plan → geo)**
- **Helmert/similarity** (translation + rotation + uniform scale) needs **2 control points**. **Affine (Polynomial-1)** needs **3** and also absorbs shear. Use thin-plate spline only when the plan is distorted. [S] https://docs.qgis.org/testing/en/docs/user_manual/managing_data_source/georeferencer.html. QGIS doc pages disagree on the minimum GCP counts, so check before stating them.
- Demo recipe:
  1. Pick 2–3 building corners on the floor-plan image and on the outdoor map (OSM).
  2. Solve the 2D similarity or affine transform by least squares.
  3. Draw outdoor apparatus and crews in lat/lon and indoor crews in plan coordinates, all on one canvas.
- Use `floor` as a discrete layer and keep it out of the transform.

### 2.3 Do NOT claim
- That the "world model" is a learned physics model. Ours is an **explicit, auditable probabilistic state** that the LLM writes to through typed events. The auditability is a selling point.
- Calibrated probabilities. POD, τ and α are hand-set demo parameters. Say so.

---

## 3. Perception in smoke

### 3.1 Evidence
- **Thermal + deep learning for people in heavy smoke** (Tsai, Liao & Yuan, *Sensors* 2022, 22(14):5351): uses a thermal camera, follows NFPA 1801, and notes that public thermal datasets are scarce. [S] https://www.mdpi.com/1424-8220/22/14/5351. PMC and MDPI both blocked fetching, so I could not verify the numbers.
- **Ground-robot victim detection (Gelfert, MTU, 2022–23):**
  - Low-res thermal: average detection above 75% in real time in **dense smoke**. A hand/body-part model reached >90%.
  - Optical camera: only **0.6–0.9 detection in *light* smoke**.
  - [S] https://sword.mtu.ie/dptelecengcp/2 ; https://sword.cit.ie/dptelecengart/4
- **IR + radar fusion on a Raspberry Pi 4** (Kulhandjian et al., RadarConf 2023): **98% validation** accuracy, a validation figure and not field accuracy. [S] https://zimmer.fresnostate.edu/~hkulhandjian/papers/Kulhandjian_Human_Detection_RardarConf_2023.pdf
- **SAM on thermal has a domain gap:**
  - Caltech Aerial RGB-Thermal (arXiv 2403.08997): every RGB variant beat thermal by ≥0.13 mIoU, and SAM **over-segments** thermal. The person class was too degenerate to report. [S] https://arxiv.org/pdf/2403.08997
  - IRSAM (ECCV 2024) names a "notable domain gap" between natural and IR images. [S] https://mlanthology.org/eccv/2024/zhang2024eccv-irsam
- **SAM 3 / 3.1 (Meta):**
  - Open-vocabulary detection, segmentation and tracking of **all instances** of a short **noun-phrase** concept in images and video. 848M params.
  - SA-Co/Gold cgF1 54.1 vs OWLv2 24.6. LVIS zero-shot mask AP 48.8 (the paper; Ultralytics docs say 47.0).
  - SAM 3.1 (27 Mar 2026) adds "Object Multiplex" shared-memory multi-object tracking, described as "significantly faster". No numbers given.
  - [V] https://cdn.jsdelivr.net/gh/facebookresearch/sam3@main/README.md ; [S] https://arxiv.org/abs/2511.16719
- **Commercial thermal edge-enhancement (Qwake C-THRU):**
  - DHS/NUSTL operational field assessment report dated 14 May 2024, with **8 firefighter evaluators**. Reported: improved situational awareness and navigation, but weight-balance and fit issues. About 4 lb added to a ~4 lb helmet (department quote).
  - "2× faster through smoke" is **[Vendor]**.
  - DHS then planned standardised testing with 80 departments.
  - [V] https://www.usfa.fema.gov/blog/dhs-release-field-assessment-report-on-c-thru/ ; [S] https://fireandsafetyjournalamericas.com/dhs-assesses-qwake-technologies-c-thru-device-at-san-diego-fire-rescue-training-center/ ; https://www.almanacnews.com/public-safety/2024/12/25/menlo-park-fire-will-be-the-first-to-use-new-ar-tool/
- **Survey context:** thermal imaging cameras are used by more than 80% of firefighter respondents, but only 30% rank them in their top-5 most useful devices. [V] NIST SP 1286pt3.

### 3.2 Borrowable in 17h
- **sam-3.1 on drone, exterior or helmet RGB frames** with text prompts "person", "window", "door", "ladder". Turn the masks into (a) a **POC boost** for the cell a detection projects to and (b) a thumbnail on the commander view. Run it on **pre-recorded** frames, since a live phone camera adds risk.
- Exterior size-up use case: segment windows/openings and people on the façade, then map them to the floor plan through the façade-to-plan alignment from 2.2(d). This is realistic: exterior visibility is better than interior.
- Treat any detection as **evidence** (likelihood ratio ~2–4 into the log-odds), never as ground truth.

### 3.3 Do NOT claim
- "SAM sees victims through smoke". Visible and lidar sensing degrade badly in smoke, and SAM on thermal has a measured domain gap.
- Detection accuracy numbers for our pipeline. We have no evaluation set.
- That this is an "image analyzer". That is a disqualified category. Perception is one evidence source feeding the agentic state engine.

---

## 4. Hands-free interaction for firefighters

### 4.1 What firefighters say they want (NIST SP 1286pt3, *Voices of First Responders: Fire Service*, 2023) [V]
- Method: 193 interviews (all disciplines) followed by a 7,182-respondent national survey.
- **Guideline 2, Reduce unintended consequences:** technology can cause "distraction, loss of situational awareness, cognitive overload, and over-reliance".
- **Guideline 6, Require usable technology ("Fisher-Price").** One firefighter wants big buttons because of gloves. Another says that under stress they need something simple.
- **Futuristic tech is mostly unwanted:** AR, robots, smart glasses, VR and self-driving vehicles were each selected as useful by **<10% of FF**. Only single sign-on was chosen by more than 50%.
- **Existing tech they lack but want:** this list includes a **work-issued wireless earpiece** and a thermal imaging camera.
- **Information overload at command:** one interviewee describes carrying two 800 MHz radios, a VHF radio and two phones, and being unable to process all the information when someone is talking. This is direct support for pillar 1 (triage).
- **Radio ergonomics:** the volume-feedback problem with an officer standing next to you, and cords that cross the chest and can melt.
- Source: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf

### 4.2 HUD / AR evidence
- **Zhang et al., CHI 2024** (arXiv 2403.04660): 26 first responders tried a HoloLens 2 with overview, directional, highlighting and labelling cues. Firefighters preferred **bold, high-contrast** cues for smoke. Concerns included limited field of view blocking peripheral vision, trust, privacy and integration with existing gear. [S] https://arxiv.org/abs/2403.04660
- **Feder et al., *Frontiers in VR*, Nov 2024:** a VR smoke study with non-firefighters. A handheld thermal camera led to **faster detection** of the fire source. A helmet heat display gave numerically faster and more accurate localisation after detection. [S] https://www.frontiersin.org/journals/virtual-reality/articles/10.3389/frvir.2024.1252351/full
- **C-THRU** (see 3.1): weight and balance are the main field complaint.
- **Loughborough thesis (Rahubadde Kankanamge):** goal-directed information analysis for IC, sector commander, BA entry-control officer and BA wearer roles. The mock-up presentation methods were confirmed useful. [S] https://dspace.lboro.ac.uk/dspace-jspui/handle/2134/7648
- **Waring et al. 2024** (*Cognition, Technology & Work*): use of risk information depends on relevance, structure and quality, and information needs differ by organisational level. [S] https://link.springer.com/content/pdf/10.1007/s10111-024-00764-8.pdf

### 4.3 Bone conduction and voice under stress
- **Bone conduction:** I found **no controlled intelligibility study with SCBA**. Only vendor material exists:
  - 3M Vision C5 in-mask Bluetooth with optional bone-conduction receive: https://www.3m.com/3M/en_US/fire-safety-and-first-responders-us/vision-c5/
  - INVISIO jaw-bone pickup: https://www.criticalcommunicationsreview.com/ccr/company/8481/invisio-communications
  - An anecdotal head-contact-mic demo near 110 dB: https://police1.com/police-products/communications/articles/hear-it-with-your-bones-tactical-headsets-for-clear-communications-RyhmQBYVPFNtoStY
  - All [Vendor].
- **ASR on real firefighter radio:** the PRONTO German TETRA corpus (LREC 2012) reports WER that is near-useless with no adaptation and **45.2% WER** after in-domain adaptation. Distortion, noise and multiple speakers are the cited causes. [S] https://preview.aclanthology.org/menus/L12-1005/
- **ASR through masks:** the only study I found is a 1983 US Army aviator study (50-word vocabulary). A mask with an internal mic performed about as well as a boom mic. [S] https://ui.adsabs.harvard.edu/abs/1983hel..rept.....M/abstract
- I found nothing on PASS-alarm interference with ASR.

### 4.4 Borrowable in 17h
- **Audio-first brief and display-second.** Briefs should be ≤2 sentences and **only on change** (new danger in your zone, mayday, victim confirmed nearby). Anything else waits for a pull. This applies Guideline 2.
- **One-touch glove targets:** 3–4 full-width buttons at most (MAYDAY / VICTIM HERE / SEARCHED / NEED HELP). Use hold-to-confirm against accidental presses and high contrast, matching the bold-cue preference in CHI 2024.
- **Explicit ASR confidence.** Low-confidence transcripts go to a "needs confirm" queue on the commander's screen. Use keyword biasing in muse-voice-transcribe (call signs, "mayday", "Division 2", "Charlie side").
- **Present the clip-on display as a radio accessory** and avoid "AR" framing. This matches what firefighters say they want.

### 4.5 Do NOT claim
- Field-validated intelligibility of bone conduction with SCBA, or our ASR accuracy on real fireground audio. Published fireground ASR WER was about 45% in 2012, and our demo audio is clean or synthetic.
- That firefighters want AR glasses. The largest survey says the opposite.

---

## 5. Implications for our product

1. **Pitch position as "reported and fused" rather than "tracked".** The state engine stores a zone/room-level position with an uncertainty radius that grows with time since the last fix (k ≈ 1–4% of distance, based on PDR literature) and shrinks on voice landmarks or touch fixes. State plainly that infrastructure-free 1 m tracking is an open NIST challenge (FRST 2023) and that a tracker could plug in later.
2. **Implement three small, explainable update rules in the world model:**
   - (i) a log-odds hazard/victim grid with clamp and timestamp-based decay toward the prior;
   - (ii) a search-theory POC update with renormalisation when a crew marks a room "searched";
   - (iii) reliability-discounted fusion of voice reports, with a **conflict alarm** on high K.
   These give the 20% Technical Depth criterion something concrete. Show the formulas in the README.
3. **Use muse-spark as the event extractor and arbiter, not as the state.** Structured-output JSON events (`{type, floor, zone_id, landmark, victim_count, reliability, asr_conf}`) feed the deterministic engine. The agent's tools are `update_belief`, `mark_searched`, `flag_conflict` and `brief_crew(member, msg)`. This is the agentic story for the $5K bonus.
4. **Show the conflict-resolution moment in the demo video.** Two crews report contradictory things about the same room, and the system raises it to the IC instead of silently averaging. This dramatises the Mungyeong/Pyeongtaek information-sharing failure.
5. **Use sam-3.1 for exterior size-up evidence on pre-recorded RGB frames** (person/window/door). Map it onto the floor plan and treat it as a likelihood boost. Do not claim it sees in smoke, and frame it as an evidence source, not an image analyzer.
6. **Align indoor and outdoor with a 2–3 point similarity/affine transform** against OSM, with floors as discrete layers. It is cheap, visual and correct.
7. **Design the responder view around NIST SP 1286pt3:** audio-first, glove-sized one-touch buttons, briefs only on change, no AR language. Quote the "<10% want AR/smart glasses" finding to show user research.
8. **Show ASR uncertainty.** Display confidence and keep a "confirm" queue. Cite fireground ASR difficulty (PRONTO WER ~45%) as the reason the human stays in the loop. Do not claim fireground-accurate transcription.
9. **Be explicit about the demo parameters** (POD, τ, α, likelihood ratios) as tunable assumptions. Graders and firefighters will respect honesty more than invented precision.
