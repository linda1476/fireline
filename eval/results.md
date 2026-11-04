# Earshot eval

Synthetic, tts_heami 24, tts_zira 12 + AMR-NB codec degradation, n = 5 per condition. Ran 2026-11-04T18:52:39+0900; Spark `muse-spark-1.3` (reasoning_effort=minimal), ASR `muse-voice-transcribe-1.0`. No WER claim for Muse in general.

**Partial run** (only=L08,K07,K10,M01,E07, conditions=['clean_kw']).

| metric | clean_kw |
|---|---|
| n | 5 |
| errors | 0 |
| MAYDAY recall | 1.00 |
| MAYDAY FP | 0 |
| 5-way acc | 1.00 |
| macro-F1 | 1.00 |
| critical-term hit | 1.00 |
| unit raw | 1.00 |
| unit snapped | 1.00 |
| floor | 1.00 |
| codeword-masked | 2/2 |
| evidence verbatim | 1.00 |
| Spark p50 ms | 4144 |
| Spark p95 ms | 5673 |
| ASR p50 ms | 3319 |
| ASR p95 ms | 4249 |

- **clean_kw**: MAYDAY 5/5 (missed –; FP –); critical terms 3/3 {'긴급탈출': '1/1', '맨다운': '1/1', 'Mayday': '1/1'}; codeword-masked 2/2 (set ['L08', 'M01'], hit ['L08', 'M01'])

## Per line

| id | cond | transcript | pred | expected | unit raw→snapped | floor | evidence | Spark ms |
|---|---|---|---|---|---|---|---|---|
| L08 | clean_kw | 지휘대장 한빛구조대 김하늘 천장 무너져서 출구를 못 찾겠다 이층 동쪽 창고 쪽 공기 얼마 안 남았다.. | MAYDAY ok | MAYDAY | 한빛구조대 김하늘→kim (exp kim) | 2/2 | ok | 4144 |
| K07 | clean_kw | 긴급탈출. 긴급탈출. 긴급탈출. 여기 한빛구조대 소방장 김하늘. 대원고립. 천장 붕괴로 퇴로 차단. 2층 동쪽 끝 창고 선반… | MAYDAY ok | MAYDAY | 한빛구조대 소방장 김하늘→kim (exp kim) | 2/2 | ok | 5674 |
| K10 | clean_kw | 상황실, 여기 누리 구조대. 맨다운 발생. 맨다운 발생. 1층 후면 출입구 안쪽 3미터, 대원 한원 한 명 쓰러짐. 고급대 … | MAYDAY ok | MAYDAY | 누리 구조대→– | 1/1 | ok | 5667 |
| M01 | clean_kw | 지휘대장 여기 누리센터 박준 연기 때문에 앞이 안 보이고 돌아갈 길을 잃었다. 1층 서측 어디쯤 발리와 달라 | MAYDAY ok | MAYDAY | 누리센터 박준→park (exp park) | 1/1 | ok | 3956 |
| E07 | clean_kw | Mayday, Mayday, Mayday. | MAYDAY ok | MAYDAY | →– | – | ok | 3472 |

GATE: radio_kw MAYDAY recall = n/a (radio_kw not run) → hero audio: clean
