# Smoke tests B1: Meta Model API (Earshot), 2026-11-04

Scripts: `D:\meta\scripts\smoke\` (`t1_structured.py`, `t1b_minimal.py`, `t2_file_asr.py`, `t3_realtime.py`, `t4_responses.py`, `make_audio.py`, `_common.py`).
Raw outputs (UTF-8 JSON): `D:\meta\scripts\smoke\out\t1.json`, `t1b.json`, `t2.json`, `t3_all.json`, `t4.json`. (The `.log` files from the first runs are cp949-mangled. Use the JSON, or run with `PYTHONIOENCODING=utf-8`.)
Audio: `D:\meta\scripts\smoke\audio\` (`i_kimhaneul.wav` 18.8 s, `ii_nuri.wav` 11.95 s, `radio_16k.wav` 19.1 s, all SAPI "Microsoft Heami Desktop", 16 kHz mono s16).

Windows gotcha: Python's stdout defaults to cp949 here, so printing Korean or an em dash crashes `print`. Set `PYTHONIOENCODING=utf-8` in every run config.

---

## TEST 1: Spark strict structured output with nullable fields

**Verdict: PASS.** `strict:true` accepts the full schema, including `anyOf:[X,null]` and nullable nested objects. All 3 inputs came back correct, and `distress` is a real JSON `null` on (a) and (c). `reasoning_effort="minimal"` is accepted and is about 2x faster with the same tags.

- The server really validates the schema. It is not silently ignored. A probe with `required:["tag"]` was rejected in 0.5 s with:
  `400 - 'required' is required to be supplied and to be an array including every key in properties. Missing 'addressee'.`
  No need for the no-strict or sentinel fallback.
- `evidence_span` was a verbatim substring in 10/10 calls. `finish_reason=stop` in every call. With max_tokens=4000 there was no truncation.

| call | latency | completion / reasoning tok | tag | key fields |
|---|---|---|---|---|
| a / low | 9.00 s | 1023 / 852 | ROUTINE | distress=null, victims=null, status ENTERING, floor 1 |
| a / low #2 | 8.35 s | 1000 / 825 | ROUTINE | same |
| a / minimal | 3.19 s | 391 / 221 | ROUTINE | same (from t1b) |
| b / low | 15.01 s | 1856 / 1584 | MAYDAY | what TRAPPED, floor 2, needs "구조 요청" (invented-ish), status TRAPPED |
| b / low #2 | 17.50 s | 1862 / 1607 | MAYDAY | what LOST, floor 2, **needs null**, air "공기 얼마 안 남았다" |
| b / minimal | 6.11 s | 621 / 361 | MAYDAY | what TRAPPED, floor 2, needs "rescue", air "low" (English paraphrase) |
| b / minimal #2 | 7.23 s | 956 / 684 | MAYDAY | (t1b) evidence verbatim |
| c / low | 7.64 s | 948 / 743 | VICTIM_FOUND | victims {count 1, EXTRACTING}, floor 2, distress=null |
| c / minimal | 3.32 s | 424 / 223 | VICTIM_FOUND | (t1b) |

Raw (a, low):
```json
{"addressee":"지휘대장","asr_uncertain":false,"confidence":0.96,"crew_brief":"박준 대원이 1층 서측으로 진입하여 인명검색을 시작함.","distress":null,"evidence_span":"1층 서측 진입, 인명검색 시작","hazard_terms":[],"location":{"floor":1,"raw":"1층 서측","zone_hint":"서측"},"needs_ack":false,"speaker_unit":"누리119안전센터 소방교 박준","status_change":"ENTERING","strategy_declared":"NONE","tag":"ROUTINE","uncertain_reason":null,"victims":null}
```
Raw (b, low #2):
```json
{"addressee":"지휘대장","asr_uncertain":false,"confidence":0.93,"crew_brief":"한빛구조대 김하늘이 2층 동쪽 창고 쪽에서 천장 붕괴로 출구를 찾지 못하고 공기가 거의 남지 않았다고 보고함. 즉시 구조가 필요하다.","distress":{"air":"공기 얼마 안 남았다","needs":null,"what":"LOST","where_raw":"2층 동쪽 창고 쪽","who":"한빛구조대 김하늘"},"evidence_span":"천장 무너져서 출구를 못 찾겠다","hazard_terms":["천장 무너져"],"location":{"floor":2,"raw":"2층 동쪽 창고 쪽","zone_hint":"동쪽 창고 쪽"},"needs_ack":true,"speaker_unit":"한빛구조대 김하늘","status_change":"TRAPPED","strategy_declared":"NONE","tag":"MAYDAY","uncertain_reason":null,"victims":null}
```
Raw (c, low):
```json
{"addressee":"Command","confidence":0.96,"distress":null,"evidence_span":"victim found, second floor Bravo-Charlie corner bedroom, unconscious adult","location":{"floor":2,"raw":"second floor Bravo-Charlie corner bedroom","zone_hint":"Bravo-Charlie corner bedroom"},"speaker_unit":"Truck 5","status_change":"NONE","tag":"VICTIM_FOUND","victims":{"count":1,"state":"EXTRACTING","where_raw":"second floor Bravo-Charlie corner bedroom"}, "...":"..."}
```
Observations:
- `needs` / `air` drift: the model sometimes fills `needs` with an inferred value ("구조 요청" / "rescue") instead of null. At `minimal` it also paraphrased `air` into English ("low"). If verbatim matters, tighten the prompt ("needs/air: verbatim from transcript or null").
- `what` flips between TRAPPED and LOST on (b). Both are acceptable, so treat them as equivalent downstream.
- Prompt caching works (`cached_tokens: 753` on repeat calls), but it did not reduce latency noticeably.
- The no-strict variant was not run because strict passed.

## TEST 2: File ASR, Korean, keywords on/off

**Verdict: PASS.** Keywords make Korean critical terms come out as single canonical tokens (긴급탈출, 대원고립, 공기잔량, 김하늘, 한빛구조대) and fix the misrecognitions. The no-keyword runs produce 김한을, 공기 기절량, and on radio audio 긴급 발출/파출. Latency is about 3–4 s for 12–19 s of audio. There were no errors.

| run | latency | audioDurationMs | transcript |
|---|---|---|---|
| (i) kw ON, [Korean] | 4.23 | 18880 | 긴급탈출 긴급탈출 긴급탈출 여기 한빛구조대 소방장 김하늘 대원고립 천장 붕괴로 퇴로 차단 2층 동쪽 끝 창고 선반 옆 공기잔량 절반 이하 사다리와 공기용기 필요 |
| (i) kw OFF, [Korean] | 3.93 | 18880 | 긴급 탈출. 긴급 탈출. 긴급 탈출. 여기 여기 한빛 구조대 소방장 **김한을** 대원 고립 천장 붕괴로 퇴로 퇴로 차단 2층 동쪽 끝 창고 선반 옆 **공기 기절량** 절반 이하 사다리와 공기용기 필요 |
| (ii) kw ON, [Korean] | 2.96 | 12000 | 상황실, 여기 누리구조대. 맨다운 발생, 맨다운 발생. 일층 후면 출입구 안쪽 삼 미터, 대원 한 한 명 쓰러짐, |
| (ii) kw OFF, [Korean] | 3.16 | 12000 | 상황실 여기 누리 구조대 맨다운 발생 맨다운 발생 1층 후면 출입구 안쪽 3미터 대원 한 명 쓰러짐 |
| (i) kw ON, [Korean, English] | 3.64 | 18880 | 긴급탈출긴급탈출 긴급탈출 긴급탈출 … 2층 2층 동쪽 끝 창고 선반반 옆 공기잔량 … (stutter/duplication artifacts) |
| (i) `keywords: []` (empty) | 3.77 | 18880 | accepted, no error; same as kw OFF (긴급 탈출 …, 공기 기절량) |
| (i) no languageBias, kw ON | 3.66 | 18880 | accepted; Korean detected; 긴급탈출 ×3 OK, minor dup "대원고립고립" |
| (i) no languageBias, no kw | 3.75 | 18880 | accepted; 긴급 탈출 … 공기 잔량 … "사다리와다리와" |
| **radio (i) kw ON** | 3.31 | 19120 | **긴급탈출** 긴급탈출탈출 **긴급탈출** … 김하늘 대원고립 … 이층 동쪽 끝 … 공기잔량 절반 이하 … |
| radio (i) kw OFF | 3.75 | 19120 | 긴급 **발출**, 긴급 **파출**, 긴급 **발출**, … 김한을 … 퇴로로 … 공기 공기잘량 … |

- **긴급탈출 survives the radio degradation (AMR-NB 7.95k, 300–3400 Hz band-pass, squelch tail) only with keywords ON.** With keywords OFF it becomes 긴급 발출/파출, which would miss a naive keyword match.
- Side effects of keywords ON: punctuation mostly disappears, numerals sometimes come out as Hangul words (일층, 삼 미터, 이층), and there are occasional stutter duplications (긴급탈출탈출, 한 한 명). Normalise numerals (일/이/삼 → 1/2/3) before floor parsing, and match codewords by substring or with fuzzy matching.
- `["Korean","English"]` was slightly worse: more duplication artifacts. Use `["Korean"]` alone.
- Omitting `languageBias` works. Language auto-detect handled Korean fine.
- `turns` was always an empty list in PUSH_TO_TALK file mode.

## TEST 3: Realtime WS, ENDPOINTING + PUSH_TO_TALK, Korean

**Verdict: PASS, with a caveat.** ENDPOINTING splits on any pause longer than about 0.7–0.85 s, so it gave **7 turns, not 2** (one per sentence-level pause). speechComplete arrives about **0.36–0.85 s (median ~0.57 s)** after the speech ends. Partials are cumulative. The 1x pacing loop got no pacing errors. Both sessions closed cleanly with code 1000, "No more transcript segments".

ENDPOINTING (stream 35.68 s: 1 s silence + (i) + 2 s silence + (ii) + 2 s silence; t = wall seconds since first audio frame):

| turnId | speechComplete t | transcript | speech end in stream | delay |
|---|---|---|---|---|
| 0 | 5.995 | 긴급탈출 긴급 탈출 긴급 탈출 | 5.14 | 0.85 s |
| 1 | 9.100 | 여기 한빛구조대 소방장 김하늘 | 8.36 | 0.74 s |
| 2 | 12.730 | 대원고립 천장 붕괴로 퇴로 차단 | 12.16 | 0.57 s |
| 3 | 19.610 | 2층 동쪽 끝 창고 선반 옆 공기잔량 절반 이하 사다리와 공기용기 필요 | 19.06 | 0.55 s |
| 4 | 25.025 | 상황실 여기 누리구조대 | 24.21 | 0.82 s |
| 5 | 28.074 | 맨다운 발생 맨다운 발생 | 27.72 | 0.36 s |
| 6 | 33.521 | 1층 후면 출입구 안쪽 3미터 대원 한 명 쓰러짐 | 32.98 | 0.54 s |
| - | 35.985 | `transcript{"", final:true}` after endStream (35.68) then close 1000 | | |

- **Endpointing threshold, measured from the WAV pause lengths:** pauses of 860–900 ms split a turn. Pauses of 540–630 ms did not. The threshold is somewhere around 0.65–0.85 s. A real transmission (one PTT press) will therefore produce several turns. The build must **merge turns into one transmission**, for example by concatenating speechComplete events whose gap is under about 1.5 s, or by using squelch/PTT boundaries.
- In ENDPOINTING, `speechEnd` and `speechComplete` arrive in the same instant. No per-turn `transcript{final:true}` is sent; speechComplete *is* the final. Each turn's partials restart from empty, so partials are cumulative within the turn only. A turn's audio is not re-sent after its speechComplete.
- Realtime transcripts match the file endpoint with keywords ON: same canonical tokens (긴급탈출, 대원고립, 공기잔량, 누리구조대, 맨다운). One difference is "긴급 탈출" spaced on the 2nd and 3rd repetitions, so match codewords with spaces removed. Realtime gave Arabic numerals (2층, 1층, 3미터).
- First partial arrives about 0.7–1.2 s after speech onset. Partials then update every 0.3–1.1 s.

PUSH_TO_TALK (0.5 s silence + (ii) + 0.5 s silence; endStream sent at t=12.891):
- Partials are cumulative across the whole utterance. No speechStart/speechEnd/speechComplete events in PTT.
- **The final arrives after endStream:** `transcript{final:true}` at t=13.139, which is **0.25 s after endStream** and 1.46 s after the speech ended. Close 1000 follows at 13.161. Final text: "상황실 여기 누리구조대 맨다운 발생 맨다운 발생 일층 후면 출입구 안쪽 삼 미터 대원 한 명 쓰러짐".
- The last partial (t=12.239) already had the full text before endStream was sent.

What the docs say about client control messages (dev.meta.ai/docs/speech-to-text and api-reference/voice/schemas):
- Speech-to-text page: "Drain queued audio, send `{"type": "endStream"}`, and send nothing more"; "`realtime` has no client-side turn commit."
- Schemas page: "`PUSH_TO_TALK` is single-turn and the client delimits the turn by ending the stream." The only client JSON messages are the handshake and `endStream`. There is **no** end-of-turn, commit or flush message.
- Other documented details: the handshake must arrive within 10 s of connecting. `emitAudioProgress` defaults to true. `mode` defaults to PUSH_TO_TALK. `partialMode` is CUMULATIVE or DELTA. "Do not send audio more than five seconds ahead of processing." The server also rejects streams that "remain slower than real time"; during silence, keep sending PCM silence.

## TEST 4: Responses API agent loop with tools

**Verdict: PASS.** The model calls `send_brief` for kim with priority P0. A reasoning item with a concise summary is returned. `previous_response_id` works with no error. After a `function_call_output` error, the model adapts by replying with a message rather than retrying blindly. Streaming works.

Call 1 (two runs: 3.61 s and 4.06 s; usage 668 in / 450 out / 287 reasoning). Output items in order:
1. `reasoning`, summary: "Mapping the affected sector to unit kim and preparing send_brief parameters for a P0 danger alert." (`content` and `encrypted_content` were empty)
2. `message` with `phase:"commentary"`: "Routing danger alert to the east crew." (a preamble message before the tool call)
3. `function_call send_brief` `{"priority":"P0","reason":"unit in affected sector 2F-E under 3F flammables danger","text":"DANGER: 3F flammables above your position 2F-E","unit_id":"kim"}`

Call 2 used `previous_response_id` plus the `function_call_output` `{"ok":false,"error":"rate limit: unit kim briefed 5 s ago"}`. Latency 10.34 s, 849 in (625 cached), 623 out (520 reasoning).
- Reasoning summary (2 parts): "Handling a rate-limit error and deciding to retry or redirect…", "Evaluating retry timing and duplicate-send risk…"
- The model **did not re-call the tool**. It answered: "Radio to **kim @ 2F-E** blocked — rate limit: unit briefed 5s ago. DANGER pending … Will re-brief kim immediately when limit clears. No brief sent to other sectors." The server carried the earlier context, so `previous_response_id` works.
- Caveat: "will re-brief when limit clears" is only a promise. The orchestrator must do the retry; the model will not.

`stream=True`: first event after 0.65 s, total 3.36 s. Distinct event types:
`response.created, response.in_progress, response.output_item.added (x3), response.output_item.done (x3), response.content_part.added, response.output_text.delta, response.output_text.done, response.content_part.done, response.function_call_arguments.delta (x4), response.function_call_arguments.done, response.completed`.
No `response.reasoning_summary_*` delta events were seen. The reasoning summary only arrives inside `output_item.added/done`.

---

## Decisions for the build

1. **Nullable strategy:** use `anyOf:[X,{type:null}]` with `strict:true`, including nullable nested objects. The API validates the schema strictly and rejects it if `required` does not list every key. No sentinel fallback is needed. Tighten the prompt so `needs`/`air` are verbatim or null, because the model sometimes infers them.
2. **reasoning_effort:** use `minimal` for the per-transmission triage call: 3.2–7.2 s vs 7.6–17.5 s at `low`, the same tags and floors, 220–680 reasoning tokens. Keep `low` (with max_tokens 4000) only for the agent and Responses loop. Every call returned `finish_reason=stop`.
3. **Keywords:** always ON for Korean. They are what make 긴급탈출, 대원고립/공기잔량 and unit names come out as canonical tokens, and they are the only reason 긴급탈출 survives AMR radio degradation (OFF gives 긴급 발출/파출). Use `languageBias:["Korean"]` alone, because adding English increased stutter artifacts. An empty keyword list and an omitted languageBias are both accepted. Downstream, strip spaces before codeword matching, map Hangul numerals to digits (일층→1층), and tolerate stutter duplicates.
4. **Realtime ENDPOINTING latency:** speechComplete arrives about **0.36–0.85 s (median ~0.57 s)** after speech ends. First partial comes about 0.7–1.2 s after speech onset. Turns split on pauses of roughly 0.7–0.85 s or more, so one radio call produced 3–4 turns. **Merge consecutive turns (gap < ~1.5 s) into one transmission** before triage, or run triage on each turn and fold the results. Pacing at 1x with 80 ms frames caused no errors.
5. **PTT end-of-turn:** the only control message is `{"type":"endStream"}`; the docs say "`realtime` has no client-side turn commit". The final `transcript{final:true}` arrived 0.25 s after endStream, then the socket closed (1000). One PTT press therefore needs one WebSocket session: open on key-down, send endStream on key-up, read the final. ENDPOINTING works in a single long-lived session.
6. **Responses API tool loop:** viable. Tool calls work (about 3.6–4 s), a reasoning summary is returned, `previous_response_id` works, and streaming works. Expect a `message` item with `phase:"commentary"` before the function_call. After a tool error the model explains instead of retrying, so retry and backoff policy belongs in the orchestrator. Reasoning summaries are not streamed as deltas.
