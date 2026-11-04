# Earshot eval

Synthetic, tts_heami 24, tts_zira 12 + AMR-NB codec degradation, n = 36 per condition. Ran 2026-11-04T19:02:54+0900; Spark `muse-spark-1.3` (reasoning_effort=minimal), ASR `muse-voice-transcribe-1.0`. No WER claim for Muse in general.

| metric | clean_kw | clean_nokw | radio_kw | radio_nokw |
|---|---|---|---|---|
| n | 36 | 36 | 36 | 36 |
| errors | 0 | 0 | 0 | 0 |
| MAYDAY recall | 1.00 | 1.00 | 1.00 | 1.00 |
| MAYDAY FP | 0 | 1 | 0 | 0 |
| 5-way acc | 1.00 | 0.97 | 1.00 | 1.00 |
| macro-F1 | 1.00 | 0.95 | 1.00 | 1.00 |
| critical-term hit | 0.93 | 0.86 | 1.00 | 0.71 |
| unit raw | 0.76 | 0.64 | 0.70 | 0.52 |
| unit snapped | 0.88 | 0.85 | 0.88 | 0.79 |
| floor | 1.00 | 0.95 | 0.90 | 0.95 |
| codeword-masked | 5/5 | 5/5 | 5/5 | 5/5 |
| evidence verbatim | 1.00 | 1.00 | 1.00 | 1.00 |
| Spark p50 ms | 3684 | 3686 | 3687 | 3748 |
| Spark p95 ms | 6196 | 6703 | 6969 | 5609 |
| ASR p50 ms | 2504 | 2752 | 2382 | 2354 |
| ASR p95 ms | 3783 | 3696 | 3665 | 3340 |

- **clean_kw**: MAYDAY 13/13 (missed –; FP –); critical terms 13/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '1/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **clean_nokw**: MAYDAY 13/13 (missed –; FP ['E05']); critical terms 12/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '1/2', '신속동료구조팀': '0/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **radio_kw**: MAYDAY 13/13 (missed –; FP –); critical terms 14/14 {'인화물질': '2/2', '긴급탈출': '3/3', '무선 침묵': '2/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])
- **radio_nokw**: MAYDAY 13/13 (missed –; FP –); critical terms 10/14 {'인화물질': '2/2', '긴급탈출': '1/3', '무선 침묵': '0/2', '신속동료구조팀': '1/1', '공기잔량': '1/1', '인명구조경보기': '1/1', '맨다운': '1/1', 'Mayday': '3/3'}; codeword-masked 5/5 (set ['L08', 'M01', 'M02', 'M03', 'M04'], hit ['L08', 'M01', 'M02', 'M03', 'M04'])

## Per line

| id | cond | transcript | pred | expected | unit raw→snapped | floor | evidence | Spark ms |
|---|---|---|---|---|---|---|---|---|
| L01 | clean_kw | 전 출동대 여기 지휘대장 지휘권 선언 지휘 위치 정문 앞 3층 도장공장 화재 화재 공격 전략 한빛구조대 2층 동측 우선탐색 … | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 5939 |
| L02 | clean_kw | 지휘대장, 여기 한빛구조대 소방장 김하늘, 정면 출입구로 세 명 진입, 2층 동측 우선탐색 실시,. | ROUTINE ok | ROUTINE | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3695 |
| L03 | clean_kw | 지휘대장, 여기 누리 119안전센터 소방교 박준 1층 서측 진입 인명 검색 시작. | ROUTINE ok | ROUTINE | 누리 119안전센터 소방교 박준→park (exp park) | 1/1 | ok | 2710 |
| L04 | clean_kw | 지휘대장, 여기 한빛 119안전센터 팀장, 정면에서 3층 창문으로 확인, 도장공장 신나 드럼 다수, 인화물질 확인, 2층 동… | DANGER ok | DANGER | 한빛 119안전센터 팀장→hanbit_center (exp hanbit_center) | 3/3 | ok | 5698 |
| L05 | clean_kw | 상황실 여기 지휘대장 대응 대응 한 단계 발령 요청 펌프차 두 대 추가! | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 6009 |
| L06 | clean_kw | 2층 계단 우측 사무실 구조대상자 한 명 정면 계단으로 구출 중.. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 3148 |
| L07 | clean_kw | 지휘대장, 여기 누리센터 박준, 1층 서측 검색 중, 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 3155 |
| L08 | clean_kw | 지휘대장, 한빛구조대 김하늘, 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽 공기 얼마 안 남았다.. | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 3400 |
| L09 | clean_kw | 상황실 여기 지휘대장 추가 펌프차 정문 쪽으로 배치 바람. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3457 |
| L10 | clean_kw | 사다리랑 공기용기 필요. 동측 창문 쪽으로 이동 중. | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 2656 |
| L11 | clean_kw | 전 출동대 무선 침묵. 긴급탈출 발생. 한빛구조대 김하늘. 2층 동쪽 창고. 요청 자원 사다리. 사다리. 공기용기. 신속동료… | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 4825 |
| L13 | clean_kw | 지휘대장, 여기 누리센터 박준, 1층 서측, 통신 불량 구역이었음, 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2044 |
| K01 | clean_kw | 상황실, 여기 한빛백십구안전센터 팀장, 현장 도착. 지상 삼층 철골조 도장공장, 이층 창문 흑연 분출, 구조대상자 미 확인.… | ROUTINE ok | ROUTINE | 한빛백십구안전센터 팀장→hanbit_center (exp hanbit_center) | – | ok | 5951 |
| K02 | clean_kw | 지휘대장, 여기 한빛구조대 2 팀장 정면 출입구로 세 명 진입 발화층 2층 우선 탐색 실시하겠음 | ROUTINE ok | ROUTINE | 한빛구조대 2 팀장→kim (exp kim) | 2/2 | ok | 4010 |
| K03 | clean_kw | 지휘대장, 여기 한빛구조대 이 팀장. 2층 계단 우측 사무실에서 구조대상자 한 명 명 발견. 의식 없음. 정면 계단으로 구출… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛구조대 이 팀장→kim (exp kim) | 2/2 | ok | 2984 |
| K04 | clean_kw | 지휘대장 여기 한빛 119안전센터 팀장 2층 천장 쳐짐 붕괴 우려 신나 드럼 다수 인화물질 확인 내부 진입 대원 위치 확인 … | DANGER ok | DANGER | 한빛 119안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 3354 |
| K05 | clean_kw | 지휘대장 여기 누리 119안전센터 팀장 옥상 세 명 대기 대기 중 옥상은 안전한데 공기 용량이 다 돼서 용기 세 개 개 필요함 | HELP_NEEDED ok | HELP_NEEDED | 누리 119안전센터 팀장→park (exp park) | – | ok | 5726 |
| K06 | clean_kw | 전 출동대 여기 지휘대장 전 대원 철수 전 대원 철수 건물 높이 1.5 바퀴로 철수 후 단위 지휘관별 인원 점검 보고。 | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 3358 |
| K07 | clean_kw | 긴급탈출. 긴급탈출. 긴급탈출. 여기 한빛구조대 소방장 김하늘 대원고립 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선반 여 … | MAYDAY ok | MAYDAY | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 6357 |
| K08 | clean_kw | 전 출동대 무선선 침묵. 여기 지휘대장. 긴급탈출 발생. 한빛구조대 김하늘 대원. 대원고립. 2층 동쪽 끝 요청 자원 사다리… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 4408 |
| K09 | clean_kw | 김하늘 대원, 여기 지휘대장. 침착하게 호흡 조절하고 공기잔량 보고할 것 무전 유지. 교신하지 않을 때 인명구조경보기 작동.. | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 3520 |
| K10 | clean_kw | 상황실 여기 누리구조대 맨다운 발생 맨다운 발생 1층 후면 출입구 안쪽 삼 미터 대원 한 명 쓰러짐 고급대 후면으로 요청. | MAYDAY ok | MAYDAY | 누리구조대→– | 1/1 | ok | 5391 |
| M01 | clean_kw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 1층 서측 어디쯤 발리와 달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 4522 |
| M02 | clean_kw | 한빛구조대 김하늘 바닥이 거져서 거져서 다리가 끼었다 움직일 수가 없다 2층 동쪽 사람 보내달라. | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 4215 |
| M03 | clean_kw | Command, Truck 5, we're cut off, fires between us and the stairs. Sec… | MAYDAY ok | MAYDAY | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 1977 |
| M04 | clean_kw | Engine 21 to Command, I'm down, something fell on me. I can't move. B… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | – | ok | 4773 |
| E01 | clean_kw | dispatch Engine 21 on scene two story wood frame residential heavy sm… | ROUTINE ok | ROUTINE | Engine 21→en_engine21 (exp en_engine21) | 2 | ok | 4088 |
| E02 | clean_kw | Main Street Command, Truck 5, we're making entry Side Alpha for prima… | ROUTINE ok | ROUTINE | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3046 |
| E03 | clean_kw | Command, Truck 5, victim found, second floor Bravo Charlie corner bed… | VICTIM_FOUND ok | VICTIM_FOUND | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 2885 |
| E04 | clean_kw | Command, Engine 23, floor is soft over the basement possible collapse… | DANGER ok | DANGER | Engine 23→en_engine23 (exp en_engine23) | – | ok | 2728 |
| E05 | clean_kw | Command, Truck 5, 5, crew is low on air, exiting Side Alpha. Need a a… | HELP_NEEDED ok | HELP_NEEDED | Truck 5→en_truck5 (exp en_truck5) | 2 | ok | 7375 |
| E06 | clean_kw | emergency traffic emergency traffic all units evacuate the structure … | DANGER ok | DANGER | →– | – | ok | 3672 |
| E07 | clean_kw | Mayday, mayday, mayday, mayday. | MAYDAY ok | MAYDAY | →– | – | ok | 3600 |
| E08 | clean_kw | Command, Mayday. Location, second floor, Side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 4419 |
| E09 | clean_kw | Mayday acknowledged, Engine 21, all units not involved in the rescue … | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 6142 |
| E10 | clean_kw | all companies, Main Street Command, give me a PAR. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 1757 |
| L01 | clean_nokw | 전출동대 여기 지휘대장 지휘관 선언 지휘 위치 정문 앞 삼 층 도장 공장 화재 공격 전략 한빛 구조대 이 층 동측 우선 탐색… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | 3 | ok | 3811 |
| L02 | clean_nokw | 지휘대장, 여기 한빛 구조대 소방장 김하늘 정면 출입구로 세 명 진입 이층 동측 우선 탐색 실시. | ROUTINE ok | ROUTINE | 한빛 구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3744 |
| L03 | clean_nokw | 지휘대장 여기 누리 백십구 안전센터 소방교 박준 일층 서측 진입 인명 검색 시작. | ROUTINE ok | ROUTINE | 누리 백십구 안전센터 소방교 박준→park (exp park) | 1/1 | ok | 2325 |
| L04 | clean_nokw | 지휘대장,진비대장 여기의 한빛 백십구 안전센터 팀장 정면에서 삼 층 창문으로 확인 도장 공장 신나 드럼 다수 인화물질 확인 … | DANGER ok | DANGER | 한빛 백십구 안전센터 팀장→hanbit_center (exp hanbit_center) | 2/3 | ok | 5926 |
| L05 | clean_nokw | 상황실, 여기 지휘대장, 대응 한 단계 발령 요청, 펌프차 두 대 추가, | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 2653 |
| L06 | clean_nokw | 이층 계단 우측 사무실 구조 대상자 한 명, 정면 계단으로 구출 중. | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 2295 |
| L07 | clean_nokw | 지휘대장,진희대장 여기 누리센터 박준 1층 서측 검색 중 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2185 |
| L08 | clean_nokw | 지휘대장 한빛 구조대 김하늘 천장 무너져서 출구를 못 찾겠다 이 층 동쪽 창고 쪽 공기 얼마 안 남았다. | MAYDAY ok | MAYDAY | 한빛 구조대 김하늘→kim (exp kim) | 2/2 | ok | 6488 |
| L09 | clean_nokw | 상황실, 여기 지휘대장. 추가 펌프차 정문 쪽으로 배치 바람.. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 4580 |
| L10 | clean_nokw | 사다리란 공기용기 비력. 동측 창문 쪽으로 이동 중., | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | 사다리란→– (exp kim) | – | ok | 3327 |
| L11 | clean_nokw | 전 출동대 무선 친목 긴급 탈출 발생 한빛 구조대 구조대 김하늘 이층 동쪽쪽 창고 요청 자원 사다리 공기 용기 신속 동료 구… | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 4675 |
| L13 | clean_nokw | 지휘대장 여기 누리센터 박준 1층 서측 통신 분량 구역이었음 이상 없음. | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2687 |
| K01 | clean_nokw | 상황실 여기 한빛 119 안전센터 안전센터 팀장 현장 도착 지상 3층 철골조 도장 공장 2층 창문 흙연 분출 구조 대상자 미… | ROUTINE ok | ROUTINE | 한빛 119 안전센터 팀장→hanbit_center (exp hanbit_center) | – | ok | 7349 |
| K02 | clean_nokw | 진리대장, 여기 한빛 구조대 이 टीम장, 정면 출입구로 세 명 진입, 발화층 이 층 우선 탐색 실시하겠음. | ROUTINE ok | ROUTINE | 한빛 구조대 이 팀장→kim (exp kim) | 2/2 | ok | 3167 |
| K03 | clean_nokw | 지휘대장,진희대장 여기 한빛 구조대 이대 이 팀장 이층 계단 우측 사무실에서 구조 대상자 대상자 한 명 발견 의식식 없음 정… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛 구조대 이 팀장→kim (exp kim) | 2/2 | ok | 4530 |
| K04 | clean_nokw | 지휘대장, 여기 한빛 백십구 안전센터 팀장, 이층 천장 처짐, 붕괴 우려. 신나 드럼 다수, 인화물질 확인. 내부 진입 대원… | DANGER ok | DANGER | 한빛 백십구 안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 3241 |
| K05 | clean_nokw | 지휘대장진리대장 여기 누리 백십구 안전센터 팀장 옥상 옥상 세 명 대기 중 옥상은 안전한데 공기 용량이 다 돼서 용기 세 개… | HELP_NEEDED ok | HELP_NEEDED | 누리 백십구 안전센터 팀장→hanbit_center (exp park) | – | ok | 5320 |
| K06 | clean_nokw | 전출동대 여기 지휘대장 전대원 철수 전대원 전대원 철수 건물 건물 높이 일 평 오 밖으로 철수 후 단위 지휘관별 인원 점검 … | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 4145 |
| K07 | clean_nokw | 긴급 탈출, 긴급 탈출, 긴급 탈출 여기 한빛 구조대 소방장 기하늘 대원 고립 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선… | MAYDAY ok | MAYDAY | 한빛 구조대 소방장 기하늘→kim (exp kim) | 2/2 | ok | 4591 |
| K08 | clean_nokw | 전출동대무선침묵. 여기 지휘대장. 긴급 탈출 발생. 한빛 고조대 김한을 대원. 대원원 고립. 2층 동쪽 끝 요청 자원 사다리… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 6180 |
| K09 | clean_nokw | 김하늘 대원 여기 지휘대장 침착하게 호흡 조절하고 공기 잔량 보고할 것 무전 유지 교신하지 않을 때 인명 구조 경보기 작동. | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 5116 |
| K10 | clean_nokw | 상황실, 여기 누리구조대, 맨다운 발생, 맨다운 발생, 1층 후면 출입구 안쪽 3미터, 대원 한 명 쓰러짐, 고급대 후면으로… | MAYDAY ok | MAYDAY | 누리구조대→– | 1/1 | ok | 4666 |
| M01 | clean_nokw | 지휘대장휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 1층 서쪽 어디쯤 발리와 달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3018 |
| M02 | clean_nokw | 한빛고조대 김하늘. 바닥이 꺼져서 다리가 꼿였다. 움직일 수가 없다. 2층 동쪽. 사람 보내달라. | MAYDAY ok | MAYDAY | 한빛고조대 김하늘→kim (exp kim) | 2/2 | ok | 3346 |
| M03 | clean_nokw | Command, truck truck five, we're cut off, fires between us and the st… | MAYDAY ok | MAYDAY | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3368 |
| M04 | clean_nokw | Engine 21 to 21 to command. I'm down, something fell on me, I can't m… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | – | ok | 3608 |
| E01 | clean_nokw | dispatch, engine 21 on scene, two story wood frame residential, heavy… | ROUTINE ok | ROUTINE | engine 21→en_engine21 (exp en_engine21) | 2 | ok | 3627 |
| E02 | clean_nokw | main street command truck five we're making entry side alpha for prim… | ROUTINE ok | ROUTINE | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3574 |
| E03 | clean_nokw | command, truck five, victim found, second floor Bravo Charlie corner … | VICTIM_FOUND ok | VICTIM_FOUND | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3004 |
| E04 | clean_nokw | command, engine 23, floor is soft over the basement, possible collaps… | DANGER ok | DANGER | engine 23→en_engine23 (exp en_engine23) | – | ok | 2725 |
| E05 | clean_nokw | command, truck five, crew is low on air, exiting side alpha. Need a r… | MAYDAY **x** | HELP_NEEDED | truck five→en_truck5 (exp en_truck5) | 2 | ok | 7579 |
| E06 | clean_nokw | emergency traffic emergency traffic all all units evacuate the struct… | DANGER ok | DANGER | →– | – | ok | 4114 |
| E07 | clean_nokw | Mayday mayday mayday. | MAYDAY ok | MAYDAY | →– | – | ok | 4444 |
| E08 | clean_nokw | Command, Mayday. Location, second floor, side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 3216 |
| E09 | clean_nokw | may day acknowledged acknowledged, engine 21, all units not involved … | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 3934 |
| E10 | clean_nokw | All companies, Main Street Command, give me a PAR. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 2791 |
| L01 | radio_kw | 전 출동대, 여기 지휘대장, 지휘권 선언, 지휘 위치 정문 앞 3층 도장공장 화재, 공격 전략, 한빛구조대 2층 동측 우선탐… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | 3 | ok | 3627 |
| L02 | radio_kw | 지휘대장 여기 한빛구조대 소방장 김하늘 정면 출입구로 세 명 진입 이 층 동측 우선탐색 실시 | ROUTINE ok | ROUTINE | 한빛구조대 소방장 김하늘→kim (exp kim) | –/2 | ok | 3267 |
| L03 | radio_kw | 지휘대장 여기 누리 119안전센터 소방교 박준 1층 서측 진입 인명 검색 시작 | ROUTINE ok | ROUTINE | 누리 119안전센터 소방교 박준→park (exp park) | 1/1 | ok | 2058 |
| L04 | radio_kw | 지휘대장, 여기 한빛 119안전센터센터 팀장, 정면에서 3층 창문으로 확인, 도장공장 신나 드럼 다수, 인화물질 확인. 2층… | DANGER ok | DANGER | 한빛 119안전센터센터 팀장→hanbit_center (exp hanbit_center) | 2/3 | ok | 4093 |
| L05 | radio_kw | 상황실 여기 지휘대장 대응 한 단계 발령 요청 펌프차 두 대 추가 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3479 |
| L06 | radio_kw | 2층 계단 우측 사무실 구조대상자 안명 안명 정면 계단으로 구출출 중 | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 4173 |
| L07 | radio_kw | 지휘대장 여기 누리센터 박준 1층 서측 검색 중 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 1898 |
| L08 | radio_kw | 지휘대장 한빛구조대 김하늘 천장 무너져서 출구를 못 찾겠다 2층 동쪽 창고 쪽 공기 얼마 안 남았다 | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 3702 |
| L09 | radio_kw | 상황실, 여기 지휘대장, 추가 펌프차 정문 쪽으로 배치 바람. | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 2915 |
| L10 | radio_kw | 사다리랑 공기용기 필요 동측 창문 창문 쪽으로 진입 동중 | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 4065 |
| L11 | radio_kw | 전 출동대 무선 침묵. 긴급탈출 발생. 한빛구조대 김하늘, 2층 동쪽 창고, 요청 자원 사다리, 공기용기, 신속동료구조팀 동… | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 4746 |
| L13 | radio_kw | 지휘대장 여기 누리센터 박준 일층 서측 통신 불량 불량 구역이었음 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 3295 |
| K01 | radio_kw | 상황실, 여기 한빛 백십구 안전센터 팀장 현장 도착 지상 삼층 철골조 도장공장 이층 창문 흑연 분출 구조 대상자 미 확인 선… | ROUTINE ok | ROUTINE | 한빛 백십구 안전센터 팀장→hanbit_center (exp hanbit_center) | 2 | ok | 6953 |
| K02 | radio_kw | 지휘대장 여기 한빛구조대 이 팀장 정면 출입구로 세 명 진입 ara층 2층 우선탐색 실시하겠음 | ROUTINE ok | ROUTINE | 한빛구조대 이 팀장→kim (exp kim) | 2/2 | ok | 3237 |
| K03 | radio_kw | 지휘대장 여기 한빛구조대 이 팀장 이 층 계단 우측 사무실에서 구조대상자 한 명 발견 의식 없음 정면 계단으로 구출 중 구급… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛구조대 이 팀장→kim (exp kim) | 2/2 | ok | 2629 |
| K04 | radio_kw | 지휘대장, 여기 한빛 119안전센터센터 팀장, 2층 천장 처짐, 붕괴 우려, 신나 드럼 다수, 인화물질 확인, 내부 내부 진… | DANGER ok | DANGER | 한빛 119안전센터센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 3355 |
| K05 | radio_kw | 지휘대장, 여기 누리 119안전센터 팀장, 옥상 세 명 대기 중. 옥상은 안전한데 공기 용량이 다 돼서 용기 세 개 필요함. | HELP_NEEDED ok | HELP_NEEDED | 누리 119안전센터 팀장→park (exp park) | – | ok | 8478 |
| K06 | radio_kw | 전 출동대 여기 지휘대장 전 전 대원 철수 전 대원 철수 건물 높이 1.5m 밖으로 철수 후 단위 지휘관별 인원 점검 보고 … | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 3221 |
| K07 | radio_kw | 긴급탈출. 긴급탈출. 긴급탈출. 긴급탈출. 여기 한빛구조대 소방장 김하늘. 대원고립. 천장 붕괴로 퇴로 차단. 2층 동쪽 끝… | MAYDAY ok | MAYDAY | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 3962 |
| K08 | radio_kw | 전 출동대 무선 침묵 여기 지휘대장휘대장 긴급탈출 발생 한빛구조대 김하늘 대원 대원고립 2층 동쪽 끝 요청 자원 사다리 공기… | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | 2/2 | ok | 4861 |
| K09 | radio_kw | 김하늘 대원 여기 지휘대장 침착하게 호흡 조절하고 공기잔량 보고할 건 무전 유지 교신하지 않을 때 인명구조경보기 작동 | MAYDAY ok | MAYDAY | 지휘대장→ic (exp ic) | – | ok | 4144 |
| K10 | radio_kw | 상황실, 여기 누리구조대. 맨다운 발생, 맨다운 발생. 1층 후면 출입구구 안쪽 삼 미터, 대원 대원 한 명 쓰러짐. 고급대… | MAYDAY ok | MAYDAY | 누리구조대→– | 1/1 | ok | 5309 |
| M01 | radio_kw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다 1층 서쪽 어디쯤 알리와 달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3690 |
| M02 | radio_kw | 한빛구조대 김하늘 바닥이 꺼져서 거져서 다리가 끼었다 움직일 수가 없다 2층 동쪽 동쪽 사람 보내달라。 | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 7016 |
| M03 | radio_kw | Command, Truck 5, we're cut off. Fire's between us and the stairs. Se… | MAYDAY ok | MAYDAY | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 2852 |
| M04 | radio_kw | Engine 21 to Command, I'm down. Something Something fell on me. I can… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | – | ok | 4566 |
| E01 | radio_kw | dispatch. Engine 21 on scene. Two story wood frame residential. Heavy… | ROUTINE ok | ROUTINE | Engine 21→en_engine21 (exp en_engine21) | 2 | ok | 3684 |
| E02 | radio_kw | Main Street Command, Truck 5, we're making entry Side Alpha for prima… | ROUTINE ok | ROUTINE | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 3040 |
| E03 | radio_kw | Command, Truck 5, victim found, second floor Bravo Charlie corner bed… | VICTIM_FOUND ok | VICTIM_FOUND | Truck 5→en_truck5 (exp en_truck5) | 2/2 | ok | 2421 |
| E04 | radio_kw | Command, Engine 23, floor is soft over the basement, the basement. Po… | DANGER ok | DANGER | Engine 23→en_engine23 (exp en_engine23) | – | ok | 3289 |
| E05 | radio_kw | Command, Truck 5, 5, crew is low on air. Exiting Side Alpha. Need a r… | HELP_NEEDED ok | HELP_NEEDED | Truck 5→en_truck5 (exp en_truck5) | 2 | ok | 5135 |
| E06 | radio_kw | emergency traffic. Emergency traffic. All units evacuate the structur… | DANGER ok | DANGER | →– | – | ok | 5588 |
| E07 | radio_kw | Mayday, Mayday, Mayday | MAYDAY ok | MAYDAY | →– | – | ok | 2634 |
| E08 | radio_kw | Command, Mayday. Location, second floor, Side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | Engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 3965 |
| E09 | radio_kw | Mayday acknowledged. Engine 21. All units not involved in the rescue … | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 4645 |
| E10 | radio_kw | all companies, Main Street Command, give me a PAR. | ROUTINE ok | ROUTINE | Main Street Command→en_command (exp en_command) | – | ok | 2558 |
| L01 | radio_nokw | 전출동대 여기 지휘대장 지휘관 선언 지휘 위치 정문 앞 3층 도장공장 도장공장 화재 공격 전략 한빛고조대 2층 동측 우선 탐… | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | 3 | ok | 4256 |
| L02 | radio_nokw | 지리대장 여기 한빛 구조대 소방장 소방장 김한을 정면 출입구로 세 명 진입 이층 동측 우선 탐색 실시 | ROUTINE ok | ROUTINE | 한빛 구조대→kim (exp kim) | 2/2 | ok | 3762 |
| L03 | radio_nokw | 지휘대장, 여기 우리 백십구 안전센터 소방교 박준 일층 서측 진입 인명 검색 시작 | ROUTINE ok | ROUTINE | 백십구 안전센터 소방교 박준→park (exp park) | 1/1 | ok | 3528 |
| L04 | radio_nokw | 진리대장 여기 한빛 백십구 안전센터 팀장 정면에서 삼층 창문으로 확인 도장 공장 신나 드럼 다수 인화물질 확인 이층 동측 천… | DANGER ok | DANGER | 한빛 백십구 안전센터 팀장→hanbit_center (exp hanbit_center) | 3/3 | ok | 4593 |
| L05 | radio_nokw | 상황실 여기 지휘대장 대응 한 단계 발령 요청 펌프차 두 대 추가 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3716 |
| L06 | radio_nokw | 이층 기단 우측 사무실 구조 대상자 자녀 정면 계단으로 구출 중 | VICTIM_FOUND ok | VICTIM_FOUND | →– (exp kim) | 2/2 | ok | 2864 |
| L07 | radio_nokw | 지리대장, 여기 누리센터 박줄, 1층 서측 검색 중, 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박줄→park (exp park) | 1/1 | ok | 2580 |
| L08 | radio_nokw | 지휘대장, 한빛고조대 김하늘, 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽 공기 얼마 안 남았다. | MAYDAY ok | MAYDAY | 한빛고조대 김하늘→kim (exp kim) | 2/2 | ok | 3670 |
| L09 | radio_nokw | 상황실 여기 지휘대장 추가 펌프차 정문 쪽으로 배치 바람 | ROUTINE ok | ROUTINE | 지휘대장→ic (exp ic) | – | ok | 3457 |
| L10 | radio_nokw | 하다리란 공기용기 필요. 동측 창문 쪽으로 이동 중. | HELP_NEEDED ok | HELP_NEEDED/MAYDAY | →– (exp kim) | – | ok | 3404 |
| L11 | radio_nokw | 전 출동대 무선 친목 긴급 긴급 탈출 발생 한빛 고조대 김한을 2층 동쪽 창고 요청 자원 자원 사다리 공기 용기 신속 동요 … | MAYDAY ok | MAYDAY | →– (exp ic) | 2/2 | ok | 6588 |
| L13 | radio_nokw | 지휘대장 여기 누리센터 박준 일층 서측 통신 통신 불량 구역이었음 이상 없음 | ROUTINE ok | ROUTINE | 누리센터 박준→park (exp park) | 1/1 | ok | 2299 |
| K01 | radio_nokw | 상황실, 여기 한빛 백십구 안전센터 팀장, 현장 도착. 지상 삼층 철골조 도장 공장. 이층 창문 후견 분출. 구조 대상자 미… | ROUTINE ok | ROUTINE | 한빛 백십구 안전센터 팀장→hanbit_center (exp hanbit_center) | 2 | ok | 5538 |
| K02 | radio_nokw | 지금 이대장 여기 한빛 구조대 이 팀장 정면 출입구로 세 명 진입 바라침 이 층 우선 탐색 실시하겠음 | ROUTINE ok | ROUTINE | 한빛 구조대 이 팀장→kim (exp kim) | –/2 | ok | 4887 |
| K03 | radio_nokw | 틀기대장. 여기 한빛고조대 이 팀장. 이층 계단 우측 사무실에서 구조대 상자 한 한 명 발견. 의식 없음. 없음. 정면 계단… | VICTIM_FOUND ok | VICTIM_FOUND | 한빛고조대 이 팀장→kim (exp kim) | 2/2 | ok | 4511 |
| K04 | radio_nokw | 진리대장. 여기 한빛 119 안전센터 팀장. 이층 천장 처짐. 붕괴 우려. 신나 드럼 다수. 인화물질 확인. 내부 진입 대원… | DANGER ok | DANGER | 한빛 119 안전센터 팀장→hanbit_center (exp hanbit_center) | 2/2 | ok | 3033 |
| K05 | radio_nokw | 칠리대장, 여기 우리 백십구 안전센터센터 팀장 옥상 세 세 명 대기 중 옥상은 안전한데 공기 농량이 다 돼서 용기 세 개 필… | HELP_NEEDED ok | HELP_NEEDED | 백십구 안전센터센터 팀장→hanbit_center (exp park) | – | ok | 4362 |
| K06 | radio_nokw | 전출동대 여기 지휘대장 전 대원 철수 전 대원 철수 건물 높이 일점 오 회 밖으로 철수 후 단위 지휘관별 인원 점검 보고 | DANGER ok | DANGER | 지휘대장→ic (exp ic) | – | ok | 4369 |
| K07 | radio_nokw | 김급 발굴 긴급 발굴 긴급 발굴 여기 한빛 구조대 소방장 김한을 대원 고립 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선반 … | MAYDAY ok | MAYDAY | 한빛 구조대 소방장 김한을→kim (exp kim) | 2/2 | ok | 5246 |
| K08 | radio_nokw | 전출동대 무선 친목 여기 진리대장 긴급 파출 발생 한빛 고조대 기만을 대원 대원 고립 2층 동쪽 끝 요청 자원 사다리 공기 … | MAYDAY ok | MAYDAY | 진리대장→– (exp ic) | 2/2 | ok | 4624 |
| K09 | radio_nokw | 기만을 대원 여기 즐기대장 침착하게 호흡 조절하고 공기 잔량 보고할 건 무전 유지 교신하지 않을 때 인명 구조 경보기 작동. | MAYDAY ok | MAYDAY | 즐기대장→– (exp ic) | – | ok | 4880 |
| K10 | radio_nokw | 상황실 여기 우리 구조대 맨다운 발생 맨다운 발생 일층 후면 출입구 안쪽 삼 미터 대원 한 명 쓰러짐 구급대 후면으로 요청 | MAYDAY ok | MAYDAY | 우리 구조대→– | 1/1 | ok | 5822 |
| M01 | radio_nokw | TV 대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 보이고 돌아갈 길을 잃었다 1층 서쪽 어디쯤 알리와 달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3733 |
| M02 | radio_nokw | 한빛고조대 기만해 바닥이 거져서 다리가 기었다. 움직일 수가 없다. 이층 동쪽 사람 보내달라 | MAYDAY ok | MAYDAY | 한빛고조대 기만해→kim (exp kim) | 2/2 | ok | 4771 |
| M03 | radio_nokw | command, truck five, we're cut off, fires between us and the stairs, … | MAYDAY ok | MAYDAY | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3176 |
| M04 | radio_nokw | engine 21 to command. I'm down. down, something fell on me, I can't m… | MAYDAY ok | MAYDAY | engine 21→en_engine21 (exp en_engine21) | – | ok | 4312 |
| E01 | radio_nokw | dispatch engine twenty one on scene two story wood frame residential … | ROUTINE ok | ROUTINE | engine twenty one→en_engine21 (exp en_engine21) | 2 | ok | 3684 |
| E02 | radio_nokw | main Street Command, truck five, we're making making entry side alpha… | ROUTINE ok | ROUTINE | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 3005 |
| E03 | radio_nokw | command truck five victim found second floor Bravo Charlie corner bed… | VICTIM_FOUND ok | VICTIM_FOUND | truck five→en_truck5 (exp en_truck5) | 2/2 | ok | 2751 |
| E04 | radio_nokw | command, engine 23, floor is soft over the basement, possible collaps… | DANGER ok | DANGER | engine 23→en_engine23 (exp en_engine23) | – | ok | 2339 |
| E05 | radio_nokw | command, truck five, crew is low on air, exiting side alpha. Need a r… | HELP_NEEDED ok | HELP_NEEDED | truck five→en_truck5 (exp en_truck5) | 2 | ok | 5402 |
| E06 | radio_nokw | emergency traffic traffic, emergency traffic, all units evacuate the … | DANGER ok | DANGER | →– | – | ok | 4067 |
| E07 | radio_nokw | Mayday mayday mayday. | MAYDAY ok | MAYDAY | →– | – | ok | 3362 |
| E08 | radio_nokw | Command, mayday. Location, second floor, side Charlie, back bedroom b… | MAYDAY ok | MAYDAY | engine 21→en_engine21 (exp en_engine21) | 2/2 | ok | 3520 |
| E09 | radio_nokw | mayday acknowledged engine 21 all units not involved in the rescue sw… | MAYDAY ok | MAYDAY | →– (exp en_command) | 2 | ok | 4064 |
| E10 | radio_nokw | all companies, main street command, give me a PAR. | ROUTINE ok | ROUTINE | main street command→en_command (exp en_command) | – | ok | 1865 |

GATE: radio_kw MAYDAY recall = 1.00 → hero audio: radio
