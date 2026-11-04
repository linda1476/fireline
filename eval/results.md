# Earshot eval

Synthetic, tts_gemini 36 + AMR-NB codec degradation, n = 36 per condition. Ran 2026-11-04T20:50:25+0900; Spark `muse-spark-1.3` (reasoning_effort=minimal), ASR `muse-voice-transcribe-1.0`. No WER claim for Muse in general.

| metric | clean_kw | clean_nokw | radio_kw | radio_nokw |
|---|---|---|---|---|
| n | 36 | 36 | 36 | 36 |
| errors | 0 | 0 | 0 | 0 |
| MAYDAY recall | 1.00 | 1.00 | 1.00 | 1.00 |
| MAYDAY FP | 1 | 0 | 1 | 0 |
| 5-way acc | 0.97 | 1.00 | 0.97 | 1.00 |
| macro-F1 | 0.95 | 1.00 | 0.95 | 1.00 |
| critical-term hit | 1.00 | 1.00 | 1.00 | 0.79 |
| unit raw | 0.79 | 0.70 | 0.79 | 0.58 |
| unit snapped | 0.88 | 0.85 | 0.88 | 0.82 |
| floor | 1.00 | 0.90 | 1.00 | 0.90 |
| codeword-masked | 5/5 | 5/5 | 5/5 | 5/5 |
| evidence verbatim | 0.97 | 1.00 | 1.00 | 1.00 |
| Spark p50 ms | 4128 | 4720 | 4098 | 4166 |
| Spark p95 ms | 6716 | 7995 | 6138 | 6492 |
| ASR p50 ms | 2800 | 2430 | 2939 | 2539 |
| ASR p95 ms | 3978 | 4003 | 4155 | 3674 |

- **clean_kw**: MAYDAY 13/13 (missed –; FP ['E05']); critical terms 14/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '2/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **clean_nokw**: MAYDAY 13/13 (missed –; FP –); critical terms 14/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '2/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **radio_kw**: MAYDAY 13/13 (missed –; FP ['E05']); critical terms 14/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '2/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **radio_nokw**: MAYDAY 13/13 (missed –; FP –); critical terms 11/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '0/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '0/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])

## Per line

| id | cond | transcript | pred | expected | unit raw→snapped | floor | evidence | Spark ms |
|---|---|---|---|---|---|---|---|---|
| L01 | clean_kw | 전 출동대 여기 지휘대장 지휘권 선언 지휘 위치 정문 앞 3층 도장공장 화재 공격 전략 한빛구조대 2층 동측 우선탐색 누리센… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | 3 | ok | 5201 |
| L02 | clean_kw | 지휘대장 여기 한빛구조대 소방장 김하늘 정면 출입구로 삼 명 진입 이 층 동측 우선탐색 실시., | ROUTINE ok | ROUTINE | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 4448 |
| L03 | clean_kw | 지휘대장, 여기 누리 119안전센터 소방교 박준, 1층 서측 진입, 인명검색 시작. | ROUTINE ok | ROUTINE | 누리 119안전센터 소방교 박준→park (exp park) | 1/1 | ok | 2458 |
| L04 | clean_kw | 지휘대장 여기 한빛119안전센터 팀장 정면에서 3층 창문으로 확인 도장공장 신나 드럼 다수 인화물질 확인 2층 동측 천장으로… | DANGER ok | DANGER | 한빛119안전센터 팀장→hanbit_center (exp hanbit_center) | 3/3 | ok | 5468 |
| L05 | clean_kw | 상황실 여기 지휘대장 대응 1단계 발령 요청 펌프차 2대 추가. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3079 |
| L06 | clean_kw | 2층 계단 우측 사무실 구조대상자 일 명 정면 계단으로 구출 중. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 3436 |
| L07 | clean_kw | 지휘대장 여기 누리센터 박준 1층 서측 검색 중 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 3155 |
| L08 | clean_kw | 지휘대장, 한빛구조대 김하늘, 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽 공기 얼마 안 남았다. | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 4109 |
| L09 | clean_kw | 상황실 여기 지휘대장 추가 펌프차 정문 쪽으로 배치 바람.. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4265 |
| L10 | clean_kw | 사다리랑 공기용기 필요. 동측 창문 쪽으로 이동 중.. | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 2403 |
| L11 | clean_kw | 전 출동대 무선 침묵 긴급탈출 발생 한빛구조대 김하늘 2층 동쪽 창고 요청자원 사다리 공기용기 신속동료구조팀 동측 창문 투입. | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 6619 |
| L13 | clean_kw | 지휘대장, 여기 누리센터 박준, 1층 서측, 통신 불량 구역이었음, 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 1937 |
| K01 | clean_kw | 상황실, 여기 한빛119안전센터 팀장, 현장 도착, 지상 3층 철골조골조 도장공장, 2층 2층 창문 흡연 분출 구조대상자 미… | ROUTINE ok | ROUTINE | 한빛119안전센터 팀장→hanbit_center (exp hanbit_center) | 3 | ok | 6481 |
| K02 | clean_kw | 지휘대장 여기 한빛구조대 2 팀장 정면 출입구로 3명 진입 발화층 2층 우선탐색 실시하겠음.. | ROUTINE ok | ROUTINE | 한빛구조대 2 팀장→kim (exp kim) | 2/2 | ok | 6171 |
| K03 | clean_kw | 지휘대장 여기 한빛구조대 2 팀장 2층 계단 우측 사무실에서 구조대상자자 1명 발견 의식 없음 정면 계단으로 구출 중 9급대… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛구조대 2 팀장→kim (exp kim) | 2/2 | ok | 3520 |
| K04 | clean_kw | 지휘대장 여기 한빛119안전센터 팀장 2층 천장 처짐 붕괴 우려 신나 신나 드럼 다수 인화물질 확인 내부 진입 대원 위치 확… | DANGER ok | DANGER | 한빛119안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 4131 |
| K05 | clean_kw | 지휘대장, 여기 누리119안전센터 팀장, 옥상 3명 3명 대기 중, 옥상은상은 안전한데 공기 용량이 다 돼서 용기 세 개 필… | HELP_NEEDED ok | HELP_NEEDED | 누리119안전센터 팀장→park (exp park) | – | ok | 4522 |
| K06 | clean_kw | 전 출동대 여기 지휘대장 전 대원 철수 전 대원 대원 철수 건물 높이 일점 오 배 밖으로 철수 후 단위 지휘관 변 인원 점검… | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 4397 |
| K07 | clean_kw | 긴급탈출, 긴급탈출, 긴급탈출, 여기 한빛구조대 소방장 김하늘, 대원고립, 천장 붕괴로 퇴로 차단, 2층 동쪽 끝 창고 선반… | MAYDAY ok | MAYDAY | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3727 |
| K08 | clean_kw | 전 출동대 무선 침묵. 여기 지휘대장 긴급탈출 발생. 한빛구조대 김하늘 대원 대원고립 2층 동쪽 끝 요청자원 사다리 공기용기… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 6384 |
| K09 | clean_kw | 김하늘 대원 여기 지휘대장 침착하게 호흡 조절하고 공기잔량 보고할 보고할 것 무전 유지 교신하지신하지 않을 때 인명구조경보기… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | x | 7006 |
| K10 | clean_kw | 상황실 여기 누리 구조대 맨다운 발생 맨다운 발생 1층 후면 출입구 안쪽 삼 미터 대원 일 명 쓰러짐 구급대 후면으로 요청. | MAYDAY ok | MAYDAY | 누리 구조대→– | 1/1 | ok | 6350 |
| M01 | clean_kw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 1층 서측 어디쯤 빨리 와달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3684 |
| M02 | clean_kw | 한빛구조대 김하늘 바닥이 꺼져서 다리가 끼었다 움직일 수가 없다 2층 동쪽 사람 보내달라 | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 2857 |
| M03 | clean_kw | Command, Truck 5, we're cut off. Fire's between us and the stairs. Se… | MAYDAY ok | MAYDAY | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3628 |
| M04 | clean_kw | Engine 21 to Command. I'm down. Something fell on me. me. I can't mov… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | – | ok | 4703 |
| E01 | clean_kw | Dispatch, engine 21 on scene. Two story wood frame residential heavy … | ROUTINE ok | ROUTINE | engine 21→en_engine21 (exp en_engine21) | 2 | ok | 4616 |
| E02 | clean_kw | Main Street Command, Truck 5 we're making entry Side Alpha for primar… | ROUTINE ok | ROUTINE | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3351 |
| E03 | clean_kw | Command, Truck 5, victim found, second floor, Bravo Charlie corner be… | VICTIM_FOUND ok | VICTIM_FOUND | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3083 |
| E04 | clean_kw | Command, Engine 23, floor is soft over the basement, possible collaps… | DANGER ok | DANGER | Engine 23→en_engine23 (exp en_engine23) | – | ok | 3612 |
| E05 | clean_kw | Command, Truck 5, crew is low on air. Exiting Side Alpha. Need a reli… | MAYDAY **x** | HELP_NEEDED | Truck 5→en_truck5 (exp en_truck5) | – | ok | 12215 |
| E06 | clean_kw | emergency traffic emergency traffic all units evacuate the structure … | DANGER ok | DANGER | →– | – | ok | 4126 |
| E07 | clean_kw | Mayday, mayday, mayday! | MAYDAY ok | MAYDAY | →– | – | ok | 4210 |
| E08 | clean_kw | Command, Mayday. Location, second floor, Side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 3763 |
| E09 | clean_kw | Mayday, acknowledged. Engine 21, all units not involved in the rescue… | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 4924 |
| E10 | clean_kw | all companies Main Street Command give me a PAR. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 3460 |
| L01 | clean_nokw | 전출동대 여기 지휘대장 지휘권 선언 지휘 위치 정문 앞무나 삼 층 도장 공장 화재 공격 전략 한빛 구조대대 이 층 동측 우선… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4922 |
| L02 | clean_nokw | 지휘대장 여기 한빛 구조대 소방장 김하늘 정면 출입구로 삼 명 진입 이층 동측 우선 탐색 실시。 | ROUTINE ok | ROUTINE | 한빛 구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 5015 |
| L03 | clean_nokw | 지휘대장, 여기 누리 119 안전센터 소방교 박준 1층 서측 진입 인명 검색 시작. | ROUTINE ok | ROUTINE | 누리 119 안전센터 소방교 박준→park (exp park) | 1/1 | ok | 3356 |
| L04 | clean_nokw | 지휘대장, 여기 한빛 일일구 일구 안전센터 팀장, 정면에서 삼 층 창문으로으로 확인, 도장 공장 신나 드럼 다수 인화물질 확… | DANGER ok | DANGER | 한빛 일일구 일구 안전센터 팀장→hanbit_center (exp hanbit_center) | 3/3 | ok | 6094 |
| L05 | clean_nokw | 상황실, 여기 지휘대장, 대응 1단계 발령 발령 요청, 펌프차 2대 추가. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4602 |
| L06 | clean_nokw | 2층 2층 계단, 우측 사무실 구조 대상자 일명 정면면 계단으로 구출 중. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 3535 |
| L07 | clean_nokw | 지휘대장, 여기 누리센터 박준, 1층 서측 검색 중, 이상 없음.! | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2226 |
| L08 | clean_nokw | 지휘대장, 한빛 구조대 김하늘 천장 무너져서 출구를 못 찾겠다. 이 층 동쪽 창고 쪽 공기 얼마 안 남았다.. | MAYDAY ok | MAYDAY | 한빛 구조대 김하늘→kim (exp kim) | –/2 | ok | 4723 |
| L09 | clean_nokw | 사항실,실 여기 지휘대장, 추가 펌프차, 정문 쪽으로 배치 바람.. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4316 |
| L10 | clean_nokw | 사다리랑 공기용기 필요 동측 창문 쪽으로 쪽으로 이동 중. | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 2708 |
| L11 | clean_nokw | 전 출동대 무선 침묵 긴급 탈출 발생 한빛 구조대 김하늘 2층 동쪽 창고 요청 자원 사다리 공기용기 신속 동료 구조팀 동측 … | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 6019 |
| L13 | clean_nokw | 지휘대장 여기 누리센터 박준 1층 서측 통신 통신 불량 구역이었음 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2407 |
| K01 | clean_nokw | 상황실 여기 한빛 119 119 안전센터 팀장 현장 도착 지상 3층 철골조 도장 공장 2층 창문 흑연 분출 구조 대상자 미 … | ROUTINE ok | ROUTINE | 한빛 119 119 안전센터 팀장→hanbit_center (exp hanbit_center) | 2 | ok | 7685 |
| K02 | clean_nokw | 지휘대장 여기 한빛 구조대 이 팀장 정면 출입구로 삼 명 진입 발화층 이 층 우선 탐색 실시하겠음. | ROUTINE ok | ROUTINE | 한빛 구조대 이 팀장→kim (exp kim) | 2/2 | ok | 5632 |
| K03 | clean_nokw | 지휘대장 여기 한빛 구조대 2팀장 이침 계단 우측 사무실에서 구조 대상자 일 명 발견의식 없음 정면 계단으로 구출 중 구급대… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛 구조대 2팀장→kim (exp kim) | 2/2 | ok | 3799 |
| K04 | clean_nokw | 지휘대장, 여기 한빛 119 안전센터 팀장 이충 천장장 처짐 붕괴 우려 신나 드럼 다수 인화 물질 확인 내부 진입 기원원 위… | DANGER ok | DANGER | 한빛 119 안전센터 팀장→hanbit_center (exp hanbit_center) | –/2 | ok | 4752 |
| K05 | clean_nokw | 지휘대장, 여기 누리 119 안전센터 팀장, 옥상상 3명 대기 중, 옥상은 안전한데 공기 용량이 용량이 다 돼서 용기 세 개… | HELP_NEEDED ok | HELP_NEEDED | 누리 119 안전센터 팀장→park (exp park) | – | ok | 9154 |
| K06 | clean_nokw | 전 출동대 출동대 여기 지휘대장 전 대원 철수 전 대원 철수 건물 건물 높이 일 정 오 배 밖으로 철수 후 단위 지휘 관변 … | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 4236 |
| K07 | clean_nokw | 긴급 탈출 긴급 탈출 긴급 탈출 여기 한빛 구조대 소방장 김하늘 대원 고림 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선반여… | MAYDAY ok | MAYDAY | 한빛 구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 5874 |
| K08 | clean_nokw | 전 출동대 무선 침묵. 여기 지휘대장, 긴급 탈출 발생. 한빛 구조대 김하늘 대원 대원원 고립 2층 동쪽 끝 요청 자원 사다… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 5464 |
| K09 | clean_nokw | 김한을 대원 여기 지휘대장 침착하게 호흡 조절하고 공기 잔량 보고할 것 무전 유지 교신하지 않을 때 인명 구조경 보기 적동 | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 5872 |
| K10 | clean_nokw | 상황실 여기 누리 구조대 맨다운 발생 맨다운 발생 일층 후면 출입구 안쪽 삼 미터 대원 일 명 쓰러짐 구급대 후면으로 요청 | MAYDAY ok | MAYDAY | 누리 구조대→– | 1/1 | ok | 5890 |
| M01 | clean_nokw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 일층 서쪽 서쪽 어디쯤 빨리 와달라! | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 4786 |
| M02 | clean_nokw | 한빛 구조대 기만을 바닥이 꺼져서 다리가 끼었다 움직일 수가 없다 없다 2층 동쪽 사람 보내달라!. | MAYDAY ok | MAYDAY | 한빛 구조대→kim (exp kim) | 2/2 | ok | 5925 |
| M03 | clean_nokw | Command, truck five, we're cut off. Fires between us and the stairs. … | MAYDAY ok | MAYDAY | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3170 |
| M04 | clean_nokw | Ancient 21 to command. command. I'm down, something fell on me, I can… | MAYDAY ok | MAYDAY | Ancient 21→– (exp en_engine21) | – | ok | 4206 |
| E01 | clean_nokw | Dispatch, Engine 21 on scene, two story wood frame residential heavy … | ROUTINE ok | ROUTINE | Engine 21→en_engine21 (exp en_engine21) | 2 | ok | 4717 |
| E02 | clean_nokw | Main Street Command, Truck Five, we're making entry side Alpha for pr… | ROUTINE ok | ROUTINE | Truck Five→en_truck5 (exp en_truck5) | 2/2 | ok | 2275 |
| E03 | clean_nokw | command truck five, victim found, second floor, Bravo Charlie corner … | VICTIM_FOUND ok | VICTIM_FOUND | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3514 |
| E04 | clean_nokw | command, Engine 23, floor is soft over the basement, possible collaps… | DANGER ok | DANGER | Engine 23→en_engine23 (exp en_engine23) | – | ok | 2023 |
| E05 | clean_nokw | command, truck five, crew is low on air, exiting side alpha, need a r… | HELP_NEEDED ok | HELP_NEEDED | truck five→en_truck5 (exp en_truck5) | 2 | ok | 8926 |
| E06 | clean_nokw | emergencyemergency traffic emergency traffic all units evacuate the s… | DANGER ok | DANGER | →– | – | ok | 3664 |
| E07 | clean_nokw | May Day, day, May day, May day. | MAYDAY ok | MAYDAY | →– | – | ok | 4826 |
| E08 | clean_nokw | command, mayday, location, second floor, side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 3979 |
| E09 | clean_nokw | Mayday acknowledged. Engine 21, all units not involved in the rescue … | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 6031 |
| E10 | clean_nokw | All companies, companies, Main Street Command, give me a par. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 2662 |
| L01 | radio_kw | 전 출동대 여기 지휘대장 지휘권권 선언 지휘 위치 정문 앞 앞 삼 층 도장공장 화재 공격 전략 한빛 구조대 이대 이 층 동측… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | 3 | ok | 5712 |
| L02 | radio_kw | 지휘대장 여기 한빛구조대 소방장 소방장 김하늘 정면 출입구로 삼 명 진입 이 층 동측 우선 탐색 실시 | ROUTINE ok | ROUTINE | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3023 |
| L03 | radio_kw | 지휘대장 여기 누리 119안전센터 소방교 박준, 1층 서측 진입, 인명검색 시작. | ROUTINE ok | ROUTINE | 누리 119안전센터 소방교 박준→park (exp park) | 1/1 | ok | 3622 |
| L04 | radio_kw | 지휘대장 여기 한빛119안전센터 팀장 정면에서 3층 창문으로 확인 도장공장 신나 드럼 다수 인화물질 확인 2층 동측 천장으로… | DANGER ok | DANGER | 한빛119안전센터 팀장→hanbit_center (exp hanbit_center) | 3/3 | ok | 5439 |
| L05 | radio_kw | 상황실 여기 지휘대장 대응 일단계 발령 요청 펌프차 2대 추가 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3638 |
| L06 | radio_kw | 2층 계단 우측 사무실 구조대상자 일명 정면 계단으로 구출 중. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 2831 |
| L07 | radio_kw | 지휘대장 여기 누리센터 박준 1층 서측 검색 중 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2789 |
| L08 | radio_kw | 지휘대장 한빛구조대 김하늘 천장 무너져서 출구를 못 찾겠다 2층 동쪽 창고 쪽 공기 얼마 안 남았다.. | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 3778 |
| L09 | radio_kw | 상황실 여기 지휘대장 추가 펌프차 정문 쪽으로 쪽으로 배치해 바람 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4443 |
| L10 | radio_kw | 사다리랑 공기용기 필요 동측 창문 쪽으로 이동 중 | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 2332 |
| L11 | radio_kw | 전 출동대 무선 침묵 긴급탈출 발생 한빛구조대 김하늘 2층 동쪽 창고 창고 요도청 대원 사다리 공기용기 신속동료구조팀 동측 … | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 5698 |
| L13 | radio_kw | 지휘대장, 여기 누리센터 박준, 1층 서측, 통신 불량 구역이었음. 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2454 |
| K01 | radio_kw | 상황실 여기 한빛 119 안전센터 팀장 현장 도착 지상 3층 철골조 도장공장 2층 창문 흑연 분출 구조대상자 미 확인 선착대… | ROUTINE ok | ROUTINE | 한빛 119 안전센터 팀장→hanbit_center (exp hanbit_center) | – | ok | 4561 |
| K02 | radio_kw | 지휘대장 여기 한빛구조대 2 팀장 정면 출입구로 삼 명 진입 발화층 이 층 우선 탐색 실시하겠음 | ROUTINE ok | ROUTINE | 한빛구조대 2 팀장→kim (exp kim) | 2/2 | ok | 4831 |
| K03 | radio_kw | 지휘대장 여기 한빛구조대 이 팀장 2층 계단 우측 사무실에서 구조대상자 일 명 발견 의식 없음 정면 계단으로 구출 중 구급대… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛구조대 이 팀장→kim (exp kim) | 2/2 | ok | 2963 |
| K04 | radio_kw | 지휘대장 여기 한빛119안전센터 팀장 2층 천장 처짐 붕괴 우려 신나 드럼 다수 인화물질 확인 내부 진입 기원 위치 확인 바람 | DANGER ok | DANGER | 한빛119안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 3651 |
| K05 | radio_kw | 지휘대장 여기 누리119안전센터 팀장 옥상 3명 대기 중 옥상은 안전한데 공기 용량이 다 돼서 용기 세 개 필요함. | HELP_NEEDED ok | HELP_NEEDED | 누리119안전센터 팀장→park (exp park) | – | ok | 4006 |
| K06 | radio_kw | 전 출동대 여기 지휘대장 전 대원 철수 전 대원 철수 건물 높이 높이 일점 오배 밖으로 철수 후 단위 지휘관 변 변 인원 점… | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 4179 |
| K07 | radio_kw | 긴급탈출 긴급탈출 긴급탈출 여기 한빛구조대 소방장 김하늘 대원고립 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선반 여 올라온… | MAYDAY ok | MAYDAY | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 6472 |
| K08 | radio_kw | 전 출동대 무선 침묵 여기 지휘대장 긴급탈출 발생 한빛구조대 김하늘 대원 대원고립 2층 동쪽 끝 요청자원 사다리 공기용기 신… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 4425 |
| K09 | radio_kw | 김하늘 대원 여기 지휘대장 침착하게 호흡 조절하고 공기잔량 보고할 것 무전 유지 교신하지 않을 때 인명구조경보기 적동 | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 5851 |
| K10 | radio_kw | 상황실 여기 누리구조대 구조대 맨다운 발생 맨다운 발생 1층 후면 출입구 안쪽 삼 미터 대원 일 명 쓰러짐 구급대 후면으로 … | MAYDAY ok | MAYDAY | 누리구조대→– | 1/1 | ok | 5762 |
| M01 | radio_kw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 1층 서쪽 어디쯤 빨리 와달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 2888 |
| M02 | radio_kw | 한빛구조대 김하늘 바닥이 꺼져서 다리가 끼었다 움직일 수가 없다 2층 동쪽 사람 보내달라 | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 3394 |
| M03 | radio_kw | Command, Truck 5, we're cut off, fire's between us and the stairs, se… | MAYDAY ok | MAYDAY | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3480 |
| M04 | radio_kw | Engine 21 to Command, I'm down something fell on me I can't move base… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | – | ok | 3726 |
| E01 | radio_kw | Dispatch, Engine 21 on scene, two story wood frame residential, heavy… | ROUTINE ok | ROUTINE | Engine 21→en_engine21 (exp en_engine21) | 2 | ok | 4911 |
| E02 | radio_kw | Main Street Command, Truck 5, we're making entry Side Alpha for prima… | ROUTINE ok | ROUTINE | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 4017 |
| E03 | radio_kw | Command, Truck 5, victim found, second floor, Bravo Charlie corner be… | VICTIM_FOUND ok | VICTIM_FOUND | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 2409 |
| E04 | radio_kw | Command, Engine 23, floor is soft over the basement. Possible collaps… | DANGER ok | DANGER | Engine 23→en_engine23 (exp en_engine23) | – | ok | 3195 |
| E05 | radio_kw | Command, Truck 5, crew is low on air, exiting Side Alpha, need a reli… | MAYDAY **x** | HELP_NEEDED | Truck 5→en_truck5 (exp en_truck5) | 2 | ok | 8791 |
| E06 | radio_kw | emergency traffic emergency traffic all units evacuate the structure … | DANGER ok | DANGER | →– | – | ok | 4348 |
| E07 | radio_kw | Mayday! Mayday! Mayday! | MAYDAY ok | MAYDAY | →– | – | ok | 6026 |
| E08 | radio_kw | Command, Mayday. Location, second floor, Side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 4566 |
| E09 | radio_kw | Mayday, acknowledged. Engine 21, all units not involved in the rescue… | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 4392 |
| E10 | radio_kw | all companies, Main Street Command, give me a PAR. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 4291 |
| L01 | radio_nokw | 전출동대 여기 지휘대장 지휘권 선언 지휘 위치 정문 앞 삼층 도장 공장 화재 공격 전략 한빛 구조대 이층 동측 우선 탐색 누… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3690 |
| L02 | radio_nokw | 지휘대장 여기 한빛 구조대 소방장 김하늘 정면 출입구로 삼 명 진입 이층 동측 우선 탐색 실시 | ROUTINE ok | ROUTINE | 한빛 구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3989 |
| L03 | radio_nokw | 지휘대장 여기 누리 일일구 안전센터 소방교 박준 일층 서측 진입 인명 검색 시작 | ROUTINE ok | ROUTINE | 누리 일일구 안전센터 소방교 박준→park (exp park) | 1/1 | ok | 3436 |
| L04 | radio_nokw | 지휘대장 여기 한빛 일일구 119 안전센터 팀장 정면에서 3층 창문으로 확인 도장 공장 신나 드럼 다수 인화 물질 확인 2층… | DANGER ok | DANGER | 한빛 일일구 119 안전센터 팀장→hanbit_center (exp hanbit_center) | 2/3 | ok | 3314 |
| L05 | radio_nokw | 상황실상황실 여기 지휘대장 대응 1단계 발령 요청 펌프차 2대 추가 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4165 |
| L06 | radio_nokw | 2층 계단 우측 사무실 구조 대상자 일 명 정면 계단으로 구출 중. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 2466 |
| L07 | radio_nokw | 지휘대장 여기 누리센터 박준준 1층 서측 검색 중 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박준준→park (exp park) | 1/1 | ok | 2957 |
| L08 | radio_nokw | 지휘대장 한빛 구조대 김하늘 천장 무너져서 출구를 못 찾겠다 이 층 동쪽 창고 쪽 공기 얼마 안 남았다. | MAYDAY ok | MAYDAY | 한빛 구조대 김하늘→kim (exp kim) | –/2 | ok | 4166 |
| L09 | radio_nokw | 상황실 여기 지휘대장 추가 펌프차 정문 정문 쪽으로 배치 바람. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3771 |
| L10 | radio_nokw | 사다리랑 공기용기 필요 동축 측면 쪽으로 이동 중 | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 2155 |
| L11 | radio_nokw | 전 출동대 무선 친목 긴급 탈출 발생 한빛 구조대 김하늘 2층 동쪽 창고 요청 자원 사다리 공기용기 신속 동료 구조팀 동측 … | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 5330 |
| L13 | radio_nokw | 지휘대장 여기 누리센터 박준 박준 일층 서측 통신 불량 구역이었음 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 3584 |
| K01 | radio_nokw | 상황실상왕실 여기 한빛 일일구 안전센터 팀장 현장 도착 지상 삼 층 철골조 도장 공장 이 층 창문 흑연 분출 분출 구조 대상… | ROUTINE ok | ROUTINE | 한빛 일일구 안전센터 팀장→hanbit_center (exp hanbit_center) | 3 | ok | 8677 |
| K02 | radio_nokw | 지휘대장, 여기 한빛 구조대 이 팀장 정면 출입구로 삼 명 진입 발화층 이 층 우선 탐색 실시하겠음 | ROUTINE ok | ROUTINE | 한빛 구조대 이 팀장→kim (exp kim) | 2/2 | ok | 4699 |
| K03 | radio_nokw | 지휘대장 여기 한빛 구조대 2 팀장 2 층 계단 우측 사무실에서 구조 대상자 일명 발견 의식 없음 정면 계단으로 구출 중 구… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛 구조대 2 팀장→kim (exp kim) | 2/2 | ok | 2815 |
| K04 | radio_nokw | 지휘대장 여기 한빛 일일구 안전센터 팀장 이층 천장 처짐 붕괴 우려 신나 드럼 다수 인화 물질 확인 내부 진입 기원 위치 확… | DANGER ok | DANGER | 한빛 일일구 안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 4755 |
| K05 | radio_nokw | 지휘대장 여기 누리 일일구 안전센터 팀장 옥상 삼 명 대기 중 옥상은 안전한데 공기 용량이 다 용량이 다 돼서 용기 세 개 … | HELP_NEEDED ok | HELP_NEEDED | 누리 일일구 안전센터 팀장→hanbit_center (exp park) | – | ok | 4699 |
| K06 | radio_nokw | 전 출동대 여기 지휘대장 전 대원 철수 전 대원 철수 건물 높이 일 정 오 배 밖으로 철수 후 단위 지휘관 변 인원 점검 보고 | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 5494 |
| K07 | radio_nokw | 긴급 탈출 긴급 탈출 긴급 탈출 여기 한빛 구조대 소방장 김하늘 대원 고립 천장 붕괴로괴로 퇴로도 차단 2층 동쪽 끝 창고 … | MAYDAY ok | MAYDAY | 한빛 구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 6331 |
| K08 | radio_nokw | 전 출동대 무선 친묵 여기 지휘대장 긴급 탈출 발생 한빛 구조대 김한을 대원 대원 고립 2층 동쪽 끝 요청 자원 사다리 공기… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 5733 |
| K09 | radio_nokw | 김한을 대원 여기 지휘대장 침착하게 호흡 조절하고 공기 잔량 보고할 것 무전 유지 교신하지 않을 때 임명 구조경 보기 적동 | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 5960 |
| K10 | radio_nokw | 상황실 여기 누리 구조대 맨다운 발생 발생 맨다운 발생 일층 후면 출입구 안쪽 삼 미터 대원 이 명 쓰러짐 구급대 후면으로 … | MAYDAY ok | MAYDAY | 누리 구조대→– | 1/1 | ok | 5739 |
| M01 | radio_nokw | 지휘대장 회장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다. 1층 서쪽 어디쯤 빨리 와달라. | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3162 |
| M02 | radio_nokw | 한빛 구조대 기만을 바닥이 꺼져서 다리가 끼었다. 움직일 수가 없다. 2층 동쪽 사람 보내달라. | MAYDAY ok | MAYDAY | 한빛 구조대→kim (exp kim) | 2/2 | ok | 5207 |
| M03 | radio_nokw | Command,Command, truck five, we're cut off, fires between us and the … | MAYDAY ok | MAYDAY | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 2939 |
| M04 | radio_nokw | Ancient 21 to command, I'm down, something fell on me, I can't move, … | MAYDAY ok | MAYDAY | Ancient 21→– (exp en_engine21) | – | ok | 4501 |
| E01 | radio_nokw | Dispatch, engine 21 on scene, two story wood frame residential, heavy… | ROUTINE ok | ROUTINE | engine 21→en_engine21 (exp en_engine21) | 2 | ok | 1997 |
| E02 | radio_nokw | Main Street Command, truck five, we're making entry side alpha for pr… | ROUTINE ok | ROUTINE | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3240 |
| E03 | radio_nokw | command truck five victim found second floor Bravo Charlie corner bed… | VICTIM_FOUND ok | VICTIM_FOUND | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 2737 |
| E04 | radio_nokw | command, engine 23, floor is soft over the basement, possible collaps… | DANGER ok | DANGER | engine 23→en_engine23 (exp en_engine23) | – | ok | 2924 |
| E05 | radio_nokw | command, truck five, crew is low on air, exiting side alpha, need a r… | HELP_NEEDED ok | HELP_NEEDED | truck five→en_truck5 (exp en_truck5) | 2 | ok | 6975 |
| E06 | radio_nokw | Emergency traffic. Emergency traffic. All units evacuate the structur… | DANGER ok | DANGER | →– | – | ok | 6296 |
| E07 | radio_nokw | Mayday, mayday, mayday. | MAYDAY ok | MAYDAY | →– | – | ok | 4605 |
| E08 | radio_nokw | command, Mayday, location second floor side Charlie back bedroom by a… | MAYDAY ok | MAYDAY | engine 21 firefighter O…→en_engine21 (exp en_engine21) | 2/2 | ok | 4833 |
| E09 | radio_nokw | Mayday acknowledged. Engine 21, 21. All units, not involved in the re… | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 5629 |
| E10 | radio_nokw | all companies, Main Street Command, give me a par. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 2606 |

GATE: radio_kw MAYDAY recall = 1.00 → hero audio: radio
