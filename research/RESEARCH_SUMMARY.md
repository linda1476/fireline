# Why Earshot: research digest

One page of the strongest sourced facts across all research streams, for the README's "why" section. Compiled 2026-11-04.
Tags: **[V]** checked against a primary or first-party page; **[S]** secondary or press only.

## 1. Maydays get missed, and where the IC stands matters
- **35.6% of firefighter maydays are missed on the first call.** The figure covers more than 9,000 maydays listened to, out of a 6-year database of 13,183 (9,052 career, 4,131 volunteer) with audio for 99.6% (Project Mayday, Fire Engineering, 2021-07-01) [V]. https://www.fireengineering.com/fdic-coverage/firefighter-communication-and-maydays/
- **The first-call miss rate depends on the IC's position** (same source) [V]:
  - 26% at the back of a vehicle with a portable radio
  - <5.2% inside a vehicle
  - <1.8% on a headset

  The listening conditions are what change the outcome.
- **Bridgeport CT, 2010 (NIOSH F2010-18): 2 firefighter deaths.**
  - The first contributing factor was "Failure to effectively monitor and respond to Mayday transmissions" [V].
  - The IC monitored two channels on two handhelds. A firefighter had to send a second mayday because the first was not acknowledged [V, PDF].
  - https://stacks.cdc.gov/view/cdc/163519
- **Communication is a contributing factor in 858 of 4,814 US near-miss reports (≈1 in 5)** (Taylor & Lacovara 2015, Table 1) [V]. https://pubmed.ncbi.nlm.nih.gov/25816170

## 2. In Korea, the information existed but did not reach the crew
- **Bucheon, 16 Oct 2026, 1 firefighter death.**
  - Flammables were reported around 08:48, and an offensive strategy was declared around 08:52 [V]. Isolation was reported around 09:09, and the firefighter was found around 09:35 (Kyunghyang, 2026-10-23). https://khan.co.kr/article/202610231144001
  - It took 26 minutes from recognising the isolation to finding him, and the RIT was ordered only at 09:20 (Hankook Ilbo, 2026-10-20) [V]. https://www.hankookilbo.com/news/article/A2026101912160005075
- **Mungyeong 2024, 2 firefighter deaths.** The official joint investigation found "현장 활동 정보 공유가 미흡" (on-scene information sharing was inadequate) (소방청, 2024-03-13) [V]. https://www.korea.kr/briefing/policyBriefingView.do?newsId=156619810
- **Wando 2026.** Hazard (urethane) information did not reach the dispatched crews, and the NFA pledged to deliver hazard and tactical information in real time [V in research stream]. https://www.etoday.co.kr/news/view/2600005
- **Pyeongtaek 2022, 3 firefighter deaths.** Last radio contact was around 09:30 (press only) [S]. https://www.nocutnews.co.kr/news/5686698
- **The protocol already exists.** SOP 109 defines the distress call as "긴급탈출" ×3, with the fields 누가/무엇을/어디에/필요한 것. A crew that fails to answer **three calls** is treated as 긴급탈출 (§1.1). SOP 107 sets the priority order: crew safety > victims > key scene factors > strategy [V]. [SOP PDF](https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf)

## 3. Today's AI listens to the caller, not the crew
- In Korea, AI-119 deployments cover **citizen calls**. Examples are Daejeon's ASR (90.3%) and Gyeongnam's LLM call summaries; neither covers fireground radio [V]. https://www.gnmaeil.com/news/articleView.html?idxno=597905
- US incumbents (Prepared, Motorola Assist, RapidSOS) transcribe for the **911/PSAP desk** (services_global stream) [V in research].
- In Aug 2026 the Korean government opened an R&D call (900M KRW) for an AI radio-summary smartwatch, which signals demand [V in research]. https://www.news1.kr/it-science/general-science/6259675

## 4. Firefighters want less glass and better audio
- Fewer than 10% of firefighters picked AR or smart glasses as useful. They asked for a work-issued wireless earpiece, and an IC asked to "consolidate it down" (NIST SP 1286pt3) [V]. https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1286pt3.pdf
- FEMA puts a supervisor's manageable span of control at 3–7, optimally 5 [V]. https://emilms.fema.gov/_is0200c/groups/53.html
- 68% of company officers lacked accountability in hand at the time of a mayday [V in research]. https://www.fireengineering.com/firefighting/the-success-of-a-good-accountability-system/

## 5. Why the method is sound
- **Event trace plus time-bounded rules:** applied to ATC radio, this gives explainable alerts at F1 0.85 [V abstract]. https://arxiv.org/abs/2608.25926
- **Roster biasing plus edit-distance snapping:** this raised ATC callsign accuracy from 35.2% to 88.9% [V]. https://arxiv.org/html/2202.03725
- **Semantic (not keyword) distress detection** holds up when the codeword is masked (SeaAlert) [V abstract]. https://arxiv.org/abs/2604.14163
- **Radio audio is hard to transcribe:** police radio scored about 51% WER zero-shot [V]. https://arxiv.org/html/2409.10858 This is why every card carries a verbatim evidence span plus replayable audio, and why a human acknowledges it.

## 6. Platform facts that shaped the design (dev.meta.ai, checked 2026-11-04)
- **muse-voice-transcribe** [V]:
  - Realtime WebSocket input is 16/24 kHz PCM only, so 8 kHz radio audio must be upsampled.
  - Audio must be streamed at about real time.
  - `keywords` and `languageBias` are fixed for the session.
  - No confidence scores and no word timestamps are returned.
  - It supports 25 languages, including Korean, with code-switching.
- **muse-spark-1.3** [V]:
  - Strict JSON-schema output: root object, `additionalProperties:false`, every key required, `anyOf` allowed below the root.
  - `tool_choice` accepts only `"auto"`; parallel tool calls are on by default.
  - The Responses API is recommended for agents, with `previous_response_id` continuity.
- **No TTS on the Model API**, so the earpiece voice is browser TTS, labelled non-Meta [V]. https://dev.meta.ai/docs/models

**Numbers we do not use**, because they are unverified or misattributed (see gap_2): "54% of maydays missed", "36.5%", "USFA EFO 82.6%", and any Korean "% of deaths caused by radio failure".
