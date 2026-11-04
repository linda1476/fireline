# Gap 3: Eval assets and Korean fireground radio protocol

*Research pass 2026-11-04 (KST). Tools used: WebSearch, WebFetch, GitHub API (read-only) and local PDF text extraction of fetched primary PDFs. Firecrawl was not used.*
*Verification labels: **[V]** means I read it in a primary source. **[2nd]** means a secondary or press source. **[INF]** means it is my inference and not verified.*

---

## 0. TL;DR

- **Only one real fireground audio clip can go in our public repo tonight:** the Palisades (LA County Fire, 2025-01-07) Broadcastify clip in `Anastassy/fire-incident-copilot`. It is 206 s, labelled CC BY 3.0 US, and needs the attribution "Audio Provided by Broadcastify". Two caveats. Broadcastify's own help pages returned 403/405 to my fetcher, so the licence claim rests on that repo's manifest plus a secondhand forum quote. Check it in a browser before pushing.
- **The police-radio corpus (BPC-CPD, arXiv 2409.10858)** is restricted and needs a data-use agreement sent by email. We cannot get it tonight, and it must not go in a public repo.
- **AI Hub "119 지능형 신고접수 음성 인식 데이터"** can be requested by Korean nationals only (내국인만). Third-party provision needs approval and export abroad needs a separate agreement. **No derived clips may go in a public GitHub repo.** We may publish only metrics and the required NIA attribution.
- **The official Korean term for a firefighter distress call is "긴급탈출" said three times, not "메이데이".** The source is 재난현장 표준작전절차 **SOP 109 대원 긴급탈출 절차**. The required content is **누가 / 무엇을 / 어디에 / 필요한 것**. [V]
- **Radio degradation can run tonight with the ffmpeg already installed on this machine.** That build includes `libopencore_amrnb` and `libgsm`; sox is not installed. I tested the command in §5 end to end.

---

## 1. Asset table (task deliverable a)

| # | Name | URL | Licence | Can it go in our public repo? | Duration / size |
|---|---|---|---|---|---|
| 1 | Palisades Command clip `decision-focus.mp3` (LA County Fire V-1 / Palisades Fire Command, Broadcastify feed 38651, recorded 2025-01-07 12:20:53 PST) | https://github.com/Anastassy/fire-incident-copilot/tree/main/data/demo/palisades-radio-demo (path `data/demo/palisades-radio-demo/audio/decision-focus.mp3`). Source event page: https://www.broadcastify.com/events/2025-01-lafire/ | CC BY 3.0 US. The README and `provenance/source-manifest.json` say `"license": "CC-BY-3.0-US"` and `"attribution": "Audio Provided by Broadcastify"` [V, repo]. Broadcastify's Help Center says feed archives are under a Creative Commons licence and may be rebroadcast, and a RadioReference forum post names CC BY 3.0 US [2nd]: https://support.broadcastify.com/hc/en-us/articles/204740415 and https://forums.radioreference.com/threads/boston-public-safety-response-audio-to-marathon-terrorist-attack.264950/ . Both official Broadcastify pages returned 403/405 to WebFetch, so this is **not verified first-hand**. | **Yes, conditionally.** We must credit "Audio Provided by Broadcastify", link the CC BY 3.0 US licence, and state the changes made (trimmed, mono 16 kHz, re-encoded). The **repo has no LICENSE file** (GitHub API `license: null`), so its code and transcripts are all-rights-reserved. Copy only the audio from the original Broadcastify source plus our own attribution. Do not copy their transcript JSON or code. Their README is in Russian. | 206 s (offset 04:52 to 08:18 of a 600 s excerpt); 2,473,676 bytes. The parent recording is 1,844 s, mp3, 22.05 kHz mono. The transcript is Whisper large-v3-turbo output and is **not human-checked**. |
| 2 | BPC-CPD ASR Corpus (Broadcast Police Communications, Chicago PD), released with Srivastava et al., "Speech Recognition for Analysis of Police Radio Communication", SLT 2024 (arXiv 2409.10858) | https://zenodo.org/records/15724888 (DOI 10.5281/zenodo.15724888). Paper: https://arxiv.org/abs/2409.10858 | "Outgoing Data Use Agreement: BPC-CPD Corpus". Files are **restricted**: you email a DUA plus a project description for ethics review (Belmont principles). Listed uses are replication or evaluation, education, and development without deployment [V]. The paper itself is CC BY 4.0. | **No.** It is restricted access and cannot be obtained tonight. | About 62k transmissions, about 46 h (paper). The Zenodo record shows 9.7 MB (metadata only). |
| 3 | AI Hub "위급상황 음성/음향(고도화) – 119 지능형 신고접수 음성 인식 데이터" | https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71768 | AI Hub common policy: no viewing, provision, transfer, lending or sale to unapproved third parties. Derivative outputs must state they are an NIA (한국지능정보사회진흥원) project result. Overseas parties and export abroad need a separate agreement [V]: https://www.aihub.or.kr/intrcn/guid/usagepolicy.do?currMenu=151&topMenu=105 . The dataset page says "내국인만 데이터 신청이 가능합니다" [V]. | **No, not raw or derived clips.** Allowed: a Korean national applies, downloads, and uses it locally for model development and evaluation. We may publish aggregate metrics (for example CER on N clips) with the NIA attribution line. We may not publish audio, transcripts or snippets. Note also that these are **119 citizen calls, not firefighter radio**. | 3,064 h; 158,973 calls (Seoul 66.7%, Incheon 17.9%, Gwangju 16.4%); wav + json; v1.1 opened 2024-10-30 |
| 4 | Fireground mayday audio from NIOSH, USFA or fire departments for training | None found with a stated reuse licence. Project Mayday reviewed more than 5,000 recordings; reuse terms are not stated: https://www.fireengineering.com/fdic/firefighter-communication-and-maydays/ | n/a | **No.** For anything reposted on YouTube or Firefighter Close Calls, assume all rights reserved. | n/a |
| 5 | **Fallback: TTS from US federal transcript text.** NIOSH FFFIPP report F2010-18 (Bridgeport CT, 2010-07-24; Lt. Velasquez and FF Baik; maydays not effectively answered) | Collection: https://stacks.cdc.gov/view/cdc/5991 . Summary: https://www.statter911.com/2011/06/30/niosh-says-bridgeport-fd-failed-to-respond-to-mayday-calls-in-double-lodds-many-failures-cited-in-deaths-of-lt-steve-velasquez-ff-michael-baik/ | NIOSH reports are US federal government works and generally public domain [INF]. **I did not confirm that F2010-18 contains verbatim radio transcript excerpts.** | Yes for **text we re-voice** (paraphrased or our own TTS), with a citation. | n/a |
| 6 | **Our own synthetic set** (§4 scripts, TTS, then the §5 degradation) | (ours) | Our licence (MIT / CC BY) | **Yes.** This should be the main eval set. | 20 lines × about 5 to 10 s |

**Real Korean radio text we can quote as reference, but not redistribute as audio:**
- Pyeongtaek cold-storage fire, 2022-01-06. The SBS 2022-01-18 transcript has lines such as "자원대기소 여기 송탄구조 3팀장", "송탄구조 전원 철수", "송탄구조 긴급탈출. 긴급탈출.", "맨다운 발생" [2nd]: https://news.sbs.co.kr/news/endPage.do?news_id=N1006609697
- Bucheon paint-factory fire, 2026-10-16 (1 FF LODD). The Wikitree 2026-10-27 timeline includes "서부119안전센터 팀장", "지휘단장", the inflammables note "인화물질이 있을 것으로 추정", and a request for "용기 3개가 필요" because air was running out [2nd]: https://www.wikitree.co.kr/articles/1169553 . Hankook Ilbo 2026-10-20 reports it took 26 minutes from recognising the isolation to finding the firefighter, and that the RIT order came 11 minutes after the isolation was confirmed [2nd]: https://www.hankookilbo.com/news/article/A2026101912160005075 . **This is a fresh, highly relevant pitch hook.**

---

## 2. Korean fireground radio protocol (primary source: 재난현장 표준작전절차)

**Source.** I used the Daegu Fire HQ print of the national 재난현장 표준작전절차 (SOP). The PDF was created on 2025-04-03 and has a text layer; I extracted it locally. URL: https://www.daegu.go.kr/cmsh/daegu.go.kr/119/files/%EC%9E%AC%EB%82%9C%ED%98%84%EC%9E%A5%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8.pdf . The SOP numbering is confirmed by the legal 별표 "재난현장 표준작전절차 수립운영에 관한 규정 [별표] 표준작전절차 구성체계(제7조1항 관련)" (Hancom PDF dated 2024-11-21): https://law.go.kr/LSW/flDownload.do?flSeq=145726231&flNm=%5B%EB%B3%84%ED%91%9C%5D+%ED%91%9C%EC%A4%80%EC%9E%91%EC%A0%84%EC%A0%88%EC%B0%A8+%EA%B5%AC%EC%84%B1%EC%B2%B4%EA%B3%84%28%EC%A0%9C7%EC%A1%B01%ED%95%AD+%EA%B4%80%EB%A0%A8%29&bylClsCd=200201 [V]

Relevant SOP numbers [V, 별표]:
- **SOP 101** 지휘권 확립
- **SOP 107** 무선통신
- **SOP 108** 안전관리
- **SOP 109** 대원 긴급탈출 절차
- **SOP 203** 인명구조 작전절차
- **SOP 204** 대원고립상황 대응절차
- **SOP 205** 낙하물ㆍ붕괴 위험 작전절차
- **SOP 504** 상황보고 절차
- **SSG 7** 신속동료구조팀(RIT)

### 2.1 Call signs and transmission format

- **Rule.** 소방정보통신운영관리규정 제30조 requires stations to attach their own call sign or call name (호출부호, 호출명칭) so the source is clear, to keep traffic minimal and terms concise, and to correct errors immediately [2nd, via LBOX]: https://lbox.kr/v2/statute-admin/%EC%86%8C%EB%B0%A9%EC%A0%95%EB%B3%B4%ED%86%B5%EC%8B%A0%EC%9A%B4%EC%98%81%EA%B4%80%EB%A6%AC%EA%B7%9C%EC%A0%95
- **Observed field format.** Transmissions run "[수신처], 여기 [발신 출동대·직위]". Examples are "자원대기소 여기 송탄구조 3팀장" (SBS). Units are named by station or team, such as 송탄구조, 서부119안전센터 팀장, 오정119안전센터, and 지휘단장 (Wikitree) [2nd].
- **Not verified.** Suffixes like "펌프1", "탱크1" or "구조1" are a common convention, but I found no official source for them [INF]. Use "○○119안전센터", "○○구조대", "지휘대장" or "현장지휘관", and "상황실" (119종합상황실) instead.
- **SOP 107 radio rules [V]:**
  - Priority order: ① 대원 안전 ② 구조대상자 ③ 재난현장 주요요소 ④ 전략·전술·대응활동계획.
  - Crews on task transmit only for 위치이동, 중요 정보, and 긴급탈출.
  - Required style: 명확하고 간결, 평소 음성, 중요한 내용부터, and **복명복창** for important items.
  - Channel split: **지휘망 / 작전망 / 지원망(유관기관망)**.
  - The commander keeps a 통신지원요원 in the command post. A 전진지휘소 talks to the 현장지휘소 on the 지휘망.
- **SOP 101 initial report (최초상황), sent by the 선착대장 to 상황실 and 후착대 [V]:**
  1. 도착 출동대 명칭
  2. 연소 상황, 구조대상자(사상자) 발생
  3. 건물용도·규모·건축방식
  4. 위험요소·대원안전 사항
  5. 지휘관 신분·지휘위치, which together form the **지휘권 선언**
  6. 시도 중이거나 예정인 소방활동
  7. **공격·방어·병행 전략** 선언
  8. 필요한 자원 요청

### 2.2 Distress protocol: 긴급탈출, not 메이데이 (SOP 109) [V, PDF pp. 22-23]

- **Declaration.** A firefighter who cannot get out safely transmits **"긴급탈출, 긴급탈출, 긴급탈출"** (three times). Any member who notices the situation may declare it.
- **No-response trigger.** If a crew in the hazard zone fails to answer **three radio call attempts**, that is also treated as a 긴급탈출 situation (§1.1).
- **Required content.** While holding the PTT key, the firefighter reports:
  - **누가**: 소속, 이름
  - **무엇을**: 긴급탈출 상황(원인)
  - **어디에**: 현재 위치 또는 지나온 위치 (주변에 보이는 것)
  - **필요한 것**: what is needed to get out. The SOP marks this "매우 중요".
- **Cause vocabulary (§1.2.2).** "대원추락", "대원부상", "대원실종", "대원고립", "붕괴위험", "가스누출".
- **All units (§1.2.3-1.2.4).** Stop all traffic except 긴급탈출-related messages, strategy changes and status changes. Use **one channel** for both hazard-zone work and the rescue.
- **Incident commander's steps:**
  1. Send the trapped member: 침착·호흡조절·공기잔량 확인, 무선연결 유지, and **PASS(인명구조경보기)** on (off while transmitting).
  2. Broadcast to all units the 누가·무엇을·어디에, a demand for **무선 침묵**, and the resources requested. **상황실 복명복창.**
  3. Deploy rescue quickly, in this order: the trapped member's own crew, then crews already in the hazard zone, then the **신속동료구조팀(RIT)**.
  4. Command directly, or delegate to the affected unit leader.
  5. When the rescue is complete, notify 상황실 of **비상통신 해제** and re-plan (§1.6).
- **The LUNAR equivalent** is 누가 (Unit + Name) / 무엇을 (the reason, which LUNAR lacks) / 어디에 (Location) / 필요한 것 (Resources). Air status is not a declared field. It appears only in the commander's prompt "공기잔량 확인". [V + INF mapping]
- **Isolation self-checks (SOP 204) [V].** 현 위치, 출입구 방향, 낙하물·붕괴 우려, 공기호흡기 잔압, 랜턴, 무전기 감도, and 지표물 (호스, 라이트라인, 로프). On a hose, the 수나사 (male) coupling side points toward the exit.
- **Where "메이데이" appears.** Ko-Wikipedia and the media use "메이데이" for this situation [2nd]: https://ko.wikipedia.org/wiki/%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD%EC%9D%98_%EC%86%8C%EB%B0%A9%EA%B3%B5%EB%AC%B4%EC%9B%90_%EC%88%9C%EC%A7%81_%EC%82%AC%EA%B1%B4 . Real traffic also uses **"맨다운 발생"** (Pyeongtaek, SBS). The classifier must accept 긴급탈출, 메이데이 and 맨다운 as triggers.
- **RIT rules [2nd, Hankook Ilbo 2026-10-20].** Since the SOP revision of 2024-09, on-scene members are designated RIT when isolation is a concern, and designated RIT get no other task. After the April 2026 Wando cold-storage fire, forming an RIT in advance became mandatory. In practice it is often skipped because of short staffing.

### 2.3 Victim and hazard terms

- **구조대상자** is the SOP term. SOP 101 uses "구조대상자(사상자)", and SOP 101 and SOP 109 use 사상자 [V]. **요구조자** is the common field and press term [INF; not found in the SOP text].
- **인명검색** (SOP 202 §3.4, SOP 203) [V]:
  - **우선탐색**: the first crew searches the fire floor and the floor directly above first.
  - **교차탐색**: first-in and later crews cross-check those floors.
  - Priority search spots: 막다른 통로, 엘리베이터, 화장실, 창, 출입구, 계단 [V].
- **Hazard terms [V, SOP 109/205/236/240]:**
  - 붕괴위험 / 붕괴 우려
  - 낙하물
  - 위험물, 인화성 액체·가스, 금수성물질
  - 플래시오버, 롤오버, 백드래프트
  - 화재가스발화 (FGI)
  - Withdraw (철수) beyond **1.5× the building height** when collapse is feared (SOP 205 §3.5)
  - 인화물질, as used in the Bucheon report [2nd]

### 2.4 English equivalents (one line each)

- **US mayday content (LUNAR).** Location, Unit, Name, Air supply, Resources; the IC obtains this after "Mayday" (Ames FD SOG 3.2.7, rev. 2016) [V]: https://www.cityofames.org/files/assets/city/v/1/fire/documents/sog-ada/3.2.7-mayday-procedures.pdf
- **US IC response in the same SOG [V].** Emergency radio traffic. Move everyone not involved in the rescue to a different channel. Get the LUNAR report. Rework the plan around a RIT rescue. Request an ALS ambulance. Conduct a PAR. Assemble a second RIT.
- **The NFA "Calling the MAYDAY" curriculum** uses LUNAR with "Assignment/Air" [2nd]: https://www.fireengineering.com/firefighter-training/firefighter-basics-calling-the-mayday/
- **Critique of LUNAR.** It omits the *Emergency* (the reason). FDIC 2025 proceedings, "Three Degrees of Mayday" [2nd]: https://cdn.asp.events/CLIENT_CL_US_323E7AA7_5056_B733_8303D39C538813E0/sites/fdic-international-2023/media/2025/conference-proceedings/Three-Degrees-of-Mayday.pdf . The Korean 무엇을 field covers this.
- **Plain language and call signs.** "Engine 21", "Truck 5", and "[Name] Command" are standard US usage. The USFA/IAFF *Voice Radio Communications Guide for the Fire Service* (2008) is at https://usfa.fema.gov/downloads/pdf/publications/voice_radio_communications_guide_for_the_fire_service.pdf (not opened in this pass; content claims are [INF]). "Palisades Command" is a real example in the Broadcastify feed title.
- **NFPA 1561** (Incident Management System) is commonly cited for emergency-traffic / mayday procedures; it is reportedly consolidated into NFPA 1550 in its 2024 edition. **The standard's text was not fetched**, so both points are [INF].
- **Project Mayday figure.** 36% of maydays were missed on the first call, per Project Mayday via Fire Engineering [2nd]: https://www.fireengineering.com/fdic/firefighter-communication-and-maydays/

---

## 3. Bilingual keyword-biasing list for muse-voice-transcribe (task deliverable b)

**How to use it:** pass these as keyword-biasing terms. Add each scenario's own unit names, such as "○○119안전센터", "송탄구조" and "Engine 21", at runtime.

Source keys:

| Key | Source |
|---|---|
| S101 / S107 / S109 / S202 / S204 / S205 | Daegu SOP PDF (§2) |
| SBS | Pyeongtaek transcript |
| WT | Wikitree Bucheon transcript |
| HK | Hankook Ilbo |
| AMES | Ames FD SOG 3.2.7 |
| NFA | Fire Engineering article on the NFA curriculum |
| WIKI | ko.wikipedia |
| USFA | USFA radio guide |
| INF | my inference |

### Korean (36 terms)

| # | Term | Source |
|---|---|---|
| 1 | 긴급탈출 | S109, SBS |
| 2 | 대원고립 | S109 |
| 3 | 대원추락 | S109 |
| 4 | 대원부상 | S109 |
| 5 | 대원실종 | S109 |
| 6 | 붕괴위험 | S109 |
| 7 | 가스누출 | S109 |
| 8 | 맨다운 | SBS |
| 9 | 메이데이 | WIKI |
| 10 | 무선 침묵 | S109 |
| 11 | 비상통신 해제 | S109 |
| 12 | 복명복창 | S107, S109 |
| 13 | 공기잔량 | S109 |
| 14 | 잔압 | S204 |
| 15 | 공기호흡기 | S204 |
| 16 | 용기 | WT |
| 17 | 인명구조경보기 | S109 |
| 18 | 신속동료구조팀 | S109, HK |
| 19 | 구조대상자 | S101 |
| 20 | 요구조자 | INF |
| 21 | 사상자 | S101 |
| 22 | 인명검색 | S202 |
| 23 | 우선탐색 | S202 |
| 24 | 교차탐색 | S202 |
| 25 | 지휘권 선언 | S101 |
| 26 | 선착대장 | S101 |
| 27 | 지휘대장 | S107 |
| 28 | 상황실 | S101 |
| 29 | 지휘망 | S107 |
| 30 | 작전망 | S107 |
| 31 | 전진지휘소 | S107 |
| 32 | 철수 | SBS, S205 |
| 33 | 진입 | S101, WT |
| 34 | 낙하물 | S204, S205 |
| 35 | 인화물질 | WT |
| 36 | 위험물 | S205 |

### English (22 terms)

| # | Term | Source |
|---|---|---|
| 1 | Mayday | AMES |
| 2 | emergency traffic | AMES |
| 3 | LUNAR | AMES |
| 4 | RIT / rapid intervention team | AMES |
| 5 | PAR / personnel accountability report | AMES |
| 6 | PASS | AMES |
| 7 | air supply | AMES |
| 8 | low air | INF |
| 9 | ALS ambulance | AMES |
| 10 | Command | USFA |
| 11 | Engine | USFA |
| 12 | Truck | USFA |
| 13 | Battalion | USFA |
| 14 | Division | USFA |
| 15 | primary search | INF |
| 16 | all clear | INF |
| 17 | victim found | INF |
| 18 | evacuate | INF |
| 19 | collapse | INF |
| 20 | Side Alpha / Bravo / Charlie / Delta | INF |
| 21 | defensive | INF |
| 22 | offensive | INF |

That is 58 terms in total. If a cap applies, drop the INF-sourced English terms first.

---

## 4. Synthetic but protocol-accurate transmissions (task deliverable c)

**All 20 lines are SYNTHETIC.** Names and units are fictional (○○ is a placeholder). Each Korean 긴급탈출 line carries the SOP 109 fields in order: 누가 → 무엇을 → 어디에 → 필요한 것. Each English Mayday carries the LUNAR fields. Format sources are given in §2.

### Korean (10)

| # | Tag | Transmission |
|---|---|---|
| K1 | Routine | "상황실, 여기 ○○119안전센터 팀장. 현장 도착. 지상 3층 철골조 도장공장, 2층 창문 흑연 분출. 구조대상자 미확인. 선착대장 지휘권 선언, 지휘위치 정문 앞. 공격전략. 구조대 1대 추가 요청." (follows the SOP 101 ①-⑧ order) |
| K2 | Routine | "지휘대장, 여기 ○○구조대 2팀장. 정면 출입구로 3명 진입, 발화층 2층 우선탐색 실시하겠음." |
| K3 | Victim Found | "지휘대장, 여기 ○○구조대 2팀장. 2층 계단 우측 사무실에서 구조대상자 1명 발견, 의식 없음. 정면 계단으로 구출 중. 구급대 정문 대기 바람." |
| K4 | Danger | "지휘대장, 여기 ○○119안전센터 팀장. 2층 천장 처짐, 붕괴 우려. 신나 드럼 다수, 인화물질 확인. 내부 진입 대원 위치 확인 바람." |
| K5 | Help Needed | "지휘대장, 여기 ○○119안전센터 팀장. 옥상 3명 대기 중, 옥상은 안전한데 공기 용량이 다 돼서 용기 3개 필요함." (modelled on the Bucheon 2026 traffic) |
| K6 | Danger | "전 출동대, 여기 지휘대장. 전 대원 철수, 전 대원 철수. 건물 높이 1.5배 밖으로 철수 후 단위지휘관별 인원 점검 보고." (SOP 205 §3.5, SOP 109 §1.3) |
| K7 | Mayday | "긴급탈출, 긴급탈출, 긴급탈출. 여기 ○○구조대 소방장 김○○. 대원고립, 천장 붕괴로 퇴로 차단. 2층 동쪽 끝 창고 선반 옆, 올라온 계단에서 약 15미터. 공기잔량 절반 이하, 사다리와 공기용기 필요." |
| K8 | Mayday | "전 출동대 무선 침묵. 여기 지휘대장. 긴급탈출 발생. ○○구조대 김○○ 대원, 대원고립, 2층 동쪽 끝. 요청 자원 사다리, 공기용기. 신속동료구조팀 동측 창문으로 투입." (SOP 109 §2; 상황실 then repeats it back: 복명복창) |
| K9 | Mayday | "김○○ 대원, 여기 지휘대장. 침착하게 호흡 조절하고 공기잔량 보고할 것. 무전 유지, 교신하지 않을 때 인명구조경보기 작동." (SOP 109 §1.5.1) |
| K10 | Mayday | "상황실, 여기 ○○구조대. 맨다운 발생, 맨다운 발생. 1층 후면 출입구 안쪽 3미터, 대원 1명 쓰러짐. 구급대 후면으로 요청." (the jargon comes from Pyeongtaek 2022) |

### English (10)

| # | Tag | Transmission |
|---|---|---|
| E1 | Routine | "Dispatch, Engine 21 on scene, two-story wood-frame residential, heavy smoke showing second floor Side Alpha. Engine 21 establishing Main Street Command, offensive strategy." |
| E2 | Routine | "Main Street Command, Truck 5, we're making entry Side Alpha for primary search, second floor." |
| E3 | Victim Found | "Command, Truck 5, victim found, second floor Bravo-Charlie corner bedroom, unconscious adult, removing via interior stairs. Need ALS at Side Alpha." |
| E4 | Danger | "Command, Engine 23, floor is soft over the basement, possible collapse Side Charlie. Recommend we back out." |
| E5 | Help Needed | "Command, Truck 5, crew is low on air, exiting Side Alpha. Need a relief crew to finish search on two." |
| E6 | Danger | "Emergency traffic, emergency traffic. All units evacuate the structure, exit Side Alpha. PAR to follow." |
| E7 | Mayday | "Mayday, Mayday, Mayday." |
| E8 | Mayday | "Command, Mayday. Location: second floor, Side Charlie, back bedroom by a window. Unit: Engine 21. Name: Firefighter Ortiz. Air: about 1,000 psi. Resources: I need RIT and a ladder to the Charlie-side window." (LUNAR as in AMES) |
| E9 | Mayday | "Mayday acknowledged, Engine 21. All units not involved in the rescue switch to Tac 3. RIT deploy to Side Charlie, second floor window. Dispatch, Command, give me a second alarm and an ALS ambulance." (AMES IC steps) |
| E10 | Routine | "All companies, Main Street Command, give me a PAR." |

---

## 5. Radio-degradation recipe (task deliverable d)

### A. ffmpeg only (runs tonight)

The local ffmpeg build includes `libopencore_amrnb` and `libgsm`. Check with `ffmpeg -encoders | findstr amr`. I tested the command end to end: a 2 s input gives 2.26 s of output, including a 0.25 s squelch tail.

```bash
# in.wav = clean TTS line
ffmpeg -y -i in.wav -f lavfi -t 0.25 -i "anoisesrc=c=white:a=0.3:r=16000" \
 -filter_complex "[0:a]aresample=16000,highpass=f=300,lowpass=f=3400,\
acompressor=threshold=-20dB:ratio=6:attack=5:release=50,volume=6dB,alimiter=limit=0.7,\
aformat=channel_layouts=mono[v];\
[1:a]afade=t=out:st=0.05:d=0.2,aformat=channel_layouts=mono[sq];\
[v][sq]concat=n=2:v=0:a=1[out]" \
 -map "[out]" -ar 8000 -ac 1 -c:a libopencore_amrnb -b:a 7.95k radio.amr
ffmpeg -y -i radio.amr -ar 16000 radio_16k.wav   # decode back for the ASR input
```

- **Band-pass.** `highpass` and `lowpass` at 300 and 3400 Hz give the classic telephony / LMR voice band.
- **Clipping.** `volume=6dB` into `alimiter`. For harsher distortion, raise the volume or add `acrusher=bits=8:mix=0.3`.
- **AMR-NB codec.** Valid bitrates are 4750 to 12200 bit/s, mono at 8 kHz; 7.95k is one of them. ffmpeg docs §8.9: https://ffmpeg.org/ffmpeg-codecs.html
- **GSM alternative.** `-c:a libgsm -ar 8000` (listed in the local build).
- **Squelch tail.** White-noise burst with a fade (lavfi `anoisesrc`, `afade`); ffmpeg filter documentation: https://ffmpeg.org/ffmpeg-filters.html
- **Background noise.** For fireground noise, mix at -15 dB with `amix` (for example `anoisesrc=c=brown`).

### B. sox variant (if installed)

```bash
sox in.wav -r 8000 -c 1 radio.wav highpass 300 lowpass 3400 compand 0.01,0.2 -60,-60,-30,-15,0,-6 -3 overdrive 15 gain -3
sox -n -r 8000 -c 1 squelch.wav synth 0.25 whitenoise fade 0 0.25 0.2
sox radio.wav squelch.wav radio_tail.wav
```

- Syntax for `highpass`, `lowpass`, `compand` and `overdrive [gain [colour]]` is from https://manpages.debian.org/testing/sox/sox.1.en.html [V].
- `sinc 300-3400` is a steeper alternative. The page mentions it, but I did not fetch its syntax section.
- `synth … whitenoise` comes from the sox man page: https://linux.die.net/man/1/sox [V].

### C. Codec2 (digital-radio artefacts, LGPL-2.1)

```bash
sox in.wav -r 8000 -c 1 -t s16 - | c2enc 1300 - - | c2dec 1300 - - | sox -t s16 -r 8000 -c 1 - radio_c2.wav
```

The modes in the examples are 3200 (maintained for M17), 2400, 1300 and 700C. Input is 16-bit signed linear at 8 kHz. Source: https://github.com/drowe67/codec2 [V]. Codec2 needs a build, so skip it tonight; AMR is enough.

---

## 6. Implications for our product

1. **Use 긴급탈출 as the primary Korean distress trigger**, with 메이데이 and 맨다운 as aliases. A Korean captain will mark the demo inauthentic if it shows only "메이데이". Cite **SOP 109** on screen.
2. **Make the Mayday card's structured output the SOP 109 fields** (누가 / 무엇을 / 어디에 / 필요한 것), plus air (공기잔량). For English, use LUNAR plus the emergency. Use muse-spark JSON-schema output, and have the agent **prompt for missing fields** the way the commander does in SOP 109 §1.5.1. That makes a strong agentic beat.
3. **Encode the SOP 107 priority order** (대원 안전 > 구조대상자 > 재난현장 주요요소 > 전략) directly as the triage ranking: Mayday > Danger > Victim Found > Help Needed > Routine. The SOP gives us a defensible ordering for judges.
4. **Automate the commander's 긴급탈출 checklist:**
   - broadcast 무선 침묵
   - generate the 누가·무엇을·어디에 broadcast text
   - push the RIT assignment
   - start the 공기잔량 timer
   - log 비상통신 해제

   The Bucheon 2026 case (26 minutes from recognising the isolation to finding the firefighter; RIT ordered 11 minutes after isolation was confirmed) is the impact story. A "3 unanswered calls" timer (SOP 109 §1.1) is a cheap and very credible feature.
5. **Build the eval set from synthetic TTS lines plus the §5 degradation**, plus one real CC BY clip (Palisades) for an English sanity check. Report CER/WER and tag accuracy clean versus degraded. Use no AI Hub or BPC data in the repo. If anything, mention AI Hub as "future eval with NIA approval".
6. **Before committing the Palisades clip**, open the Broadcastify licence page in a browser. Add `ATTRIBUTION.md` with "Audio Provided by Broadcastify", a CC BY 3.0 US link and a list of the changes made. Do not copy that repo's code or transcripts, because it has no LICENSE.
7. **Ship the 58-term keyword list** as a config file, plus per-incident unit names injected at runtime. Biasing toward "긴급탈출" and "맨다운" matters most, because a missed distress call is the failure our system exists to prevent. Project Mayday reports that 36% of first maydays were missed.
8. **Use SOP vocabulary in the UI:**
   - 구조대상자 rather than 요구조자
   - 우선탐색 and 교차탐색 states for the floor map
   - a collapse-zone ring at 1.5× building height (SOP 205 §3.5) on the outdoor map: a nice world-model touch
9. **Treat call signs as configurable**, using "○○119안전센터 / ○○구조대 / 지휘대장 / 상황실". Do not hard-code "펌프1"-style suffixes, because I could not verify them.
