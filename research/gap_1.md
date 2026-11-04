# Gap fill 1: Meta Model API capabilities and hackathon rules

Accessed 2026-11-04 (KST), about 17 h before the deadline. Researcher: subagent stream "GAP FILL".
Legend: **[V]** = verified on a primary or official page (dev.meta.ai docs, cerebralvalley.ai). **[S]** = secondary source only (community wiki, blog, news). **[not found]** = searched and no source states it.

Caveats:
- The official Cerebral Valley pages `/details` and `/waiver` render through JS. WebFetch only got "Loading...", so I could not read the full Official Rules text. I also tried `/details.md` and `/waiver.md`; both returned HTTP 404.
- The rubric weights come from secondary sources that claim to quote the Official Rules (posted around Oct 25). Two of those sources are independent and agree.
- The GitHub repo `meta-ai-hackathon/meta-hack` is another participant's team repo with a community wiki. It is not an official source.

---

## A. Meta Model API facts

### muse-voice-transcribe-1.0

| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 1a | Biasing parameter name | `keywords`: an array of strings, set in the handshake or request JSON | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/schemas | [V] |
| 1b | Max keyword list size / per-item length | Not documented. The schemas page gives no maxItems or maxLength. | https://dev.meta.ai/docs/api-reference/voice/schemas | [not found] |
| 1c | Boost weight? | No weight; plain phrases only. Docs say biasing "does not guarantee an exact spelling". The blog says it nudges rather than constrains. | https://dev.meta.ai/docs/api-reference/voice/schemas ; https://dev.meta.ai/resources/blog/meet-muse-voice-transcribe-streaming-speech-to-text/ (post dated 2026-09-03) | [V] |
| 1d | Free-form context biasing | No separate context param. `languageBias` takes a list of language names, not free text. | https://dev.meta.ai/docs/speech-to-text | [V] |
| 1e | Can biasing change mid-stream? | No. `keywords` and `languageBias` are fixed at session start, so a change needs a reconnect. | https://dev.meta.ai/docs/speech-to-text ; https://docs.livekit.io/reference/python/livekit/plugins/meta/index.html | [V] |
| 2a | Streaming protocol | WebSocket `wss://api.meta.ai/v1/asr/realtime`. Auth goes in the first JSON frame (`authorization.accessToken: "Bearer <key>"`), sent within 10 s; the HTTP Authorization header is ignored. The file endpoint `POST /v1/asr/transcribe` can also stream SSE (`Accept: text/event-stream`). | https://dev.meta.ai/docs/api-reference/voice/realtime ; https://dev.meta.ai/docs/api-reference/voice/transcribe | [V] |
| 2b | Audio formats / rates | Realtime: raw s16le mono PCM, `audioEncoding` = `PCM_24KHZ` (native) or `PCM_16KHZ`. File: WAV, mono 16-bit PCM at 16 or 24 kHz. | https://dev.meta.ai/docs/api-reference/voice/schemas | [V] |
| 2c | 8 kHz narrowband accepted? | No. There is no PCM_8KHZ or mu-law enum, so 8 kHz radio audio must be upsampled to 16 kHz client-side. | https://dev.meta.ai/docs/api-reference/voice/schemas | [V] (absence in enum) |
| 2d | Partial vs final | `transcript` events with `final:false/true`. `partialMode` is `CUMULATIVE` (default; replace, do not append) or `DELTA`. Modes: `PUSH_TO_TALK` (default), `ENDPOINTING`, `DIARIZATION`. In ENDPOINTING/DIARIZATION completion is a `speechComplete` per `turnId`. | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/schemas | [V] |
| 2e | Pacing constraint | You must stream in real time, including silence, and not more than 5 s ahead. Sending below real time closes the socket with code 1008. | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/realtime | [V] |
| 3a | Diarization labels | Bare letters (`A`, `B`, ...). Labels are session-scoped, not identities. One `speaker` event (field `label`) per turn, with no `turnId`, so correlate by order. Handles non-overlapping speech only; 20+ speakers. | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/schemas ; dev.meta.ai blog above | [V] |
| 3b | Timestamps | Turn-level only. The file response has `turns[]` with `turnId, startMs, endMs, transcript, speaker`. Stream events carry `audioProcessedMs`. | https://dev.meta.ai/docs/api-reference/voice/schemas | [V] |
| 3c | Word-level timestamps / confidence | Not available. There is no `confidence` field anywhere. | https://dev.meta.ai/docs/speech-to-text ; https://venturebeat.com/technology/meta-prices-muse-voice-transcribe-at-0-18-an-hour-with-real-time-diarization-for-20-speakers-a-steal-for-enterprises | [V] |
| 4a | Language auto-detect | Yes, when `languageBias` is omitted. No detected-language field is returned. | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/schemas | [V] |
| 4b | Korean + code-switching | Korean is in the 25-language list. Code-switching within one stream is supported. Hint with `languageBias: ["Korean","English"]` (language names, not codes). | https://dev.meta.ai/docs/speech-to-text | [V] |
| 5a | Max file | 10 min of audio (HTTP 400 beyond) and a 32 MB body (HTTP 413) | https://dev.meta.ai/docs/api-reference/voice/transcribe | [V] |
| 5b | Max realtime session | 60 min by default; then close 1011 "Max session duration reached" and reconnect | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/api-reference/voice/realtime | [V] |
| 5c | Rate limits | 256 concurrent streams and 16,000 streams/hour, shared by both endpoints and applied per team, not per key | https://dev.meta.ai/docs/speech-to-text ; https://dev.meta.ai/docs/pricing-rate-limits | [V] |
| 5d | Price | $0.18 per audio hour | https://dev.meta.ai/docs/pricing-rate-limits | [V] |

### muse-spark-1.3

| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 6a | Strict JSON schema param | Chat Completions: `response_format={"type":"json_schema","json_schema":{"name","schema","strict"}}`. Responses API: `text.format`, and the other endpoint's param is ignored. Output is always constrained. `strict` (default false) only adds server-side validation of the schema against the strict subset. | https://dev.meta.ai/docs/structured-output | [V] |
| 6b | Strict subset rules | Root must be a plain object. Every object needs `additionalProperties:false` and `required` = all keys. `anyOf` is allowed below the root; `allOf`/`oneOf` are not. No recursion. Max depth 10, max 5,000 properties. | https://dev.meta.ai/docs/structured-output | [V] |
| 6c | Enum support | Yes. The limit is 1,000 enum values by default. | https://dev.meta.ai/docs/structured-output | [V] |
| 6d | Nullable fields | Not explicitly documented. Inference: since `anyOf` is allowed below the root and `required` must list every key, use `anyOf:[{type:X},{type:"null"}]` for optional fields. Test once. | https://dev.meta.ai/docs/structured-output | [not found] (inference) |
| 6e | Pydantic parse | `client.beta.chat.completions.parse()` works with the OpenAI SDK | https://dev.meta.ai/docs/structured-output | [V] |
| 7a | Tool-calling format | OpenAI-compatible `tools` (`function` type; `custom` only on Responses) | https://dev.meta.ai/docs/tool-calling | [V] |
| 7b | `tool_choice` | Only `"auto"`. Any other value, including "required" or a named function, returns HTTP 400. | https://dev.meta.ai/docs/tool-calling | [V] |
| 7c | Parallel tool calls | Supported. `parallel_tool_calls` defaults to true. Arguments stream with `stream:true`. | https://dev.meta.ai/docs/tool-calling | [V] |
| 7d | Built-ins / agent features | Server-side `web_search` and `tool_search` (with `defer_loading`). The Responses API is recommended for agents because it keeps reasoning across tool turns (`previous_response_id`). | https://dev.meta.ai/docs/tool-calling | [V] |
| 8a | Reasoning control | Chat: `reasoning_effort`. Responses: `reasoning.effort`. Values: `minimal, low, medium, high, xhigh, max`. `max` works on 1.3 Standard but not on contributor. `none` returns HTTP 400. If omitted, the model picks the level. | https://dev.meta.ai/docs/reasoning | [V] |
| 8b | Reasoning summaries | `reasoning.summary` = auto, concise or detailed (Responses API only, not guaranteed). Useful to show a "why" trace for the triage agent. | https://dev.meta.ai/docs/reasoning | [V] |
| 8c | Typical latency | No figures published. Docs only say higher effort adds latency and the first visible chunk comes after an initial delay. | https://dev.meta.ai/docs/reasoning ; https://dev.meta.ai/docs/models | [not found] |
| 8d | Context / inputs | 1,048,576 tokens. Inputs: text, image, video, audio, PDF. Audio input is "not fully supported" on 1.3. | https://dev.meta.ai/docs/models | [V] |
| 9 | Rate limits | 3,000 RPM / 4M TPM (Standard). Contributor tier: 100 RPM / 3M TPM. Per team, not per key. Pricing: $1.25 in / $4.25 out per 1M tokens. | https://dev.meta.ai/docs/pricing-rate-limits ; https://www.promptfoo.dev/docs/providers/meta/ | [V] |
| 9b | Default model gotcha | If you omit `model` you get 1.1 (this may be promptfoo's provider default rather than the API's), so always pass `muse-spark-1.3` | https://www.promptfoo.dev/docs/providers/meta/ | [S] |

### sam-3.1

| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 10 | Video or images? | Both. Use an `input_image` part (image_url) or an `input_video` part (MP4/MOV, H.264/H.265/MPEG-4) via the Responses API (`POST https://api.meta.ai/v1/responses`). Max duration and size are not stated. | https://dev.meta.ai/docs/sam/overview ; https://dev.meta.ai/docs/media-segmentation ; https://dev.meta.ai/docs/models | [V] |
| 11 | Output | Special-token text in `output_text`: one line per image, or one per frame tagged like `<0f>`. Each object has an ordinal, a box (x1,y1,x2,y2,w,h in source px) and a mask (x,y,payload). `mask_encoding` (e.g. `one_bit`) decodes to a binary raster. IDs stay stable across frames. RLE, PNG and confidence scores are not mentioned. Parser: npm `@meta-sam/parser`. | https://dev.meta.ai/docs/sam/overview | [V] |
| 12a | Text-prompt constraints | One short concrete noun phrase per request (e.g. "yellow school bus"), so several object types need several requests. Box and point prompts are also supported. No match gives an empty output_text. | https://dev.meta.ai/docs/media-segmentation ; https://dev.meta.ai/docs/sam/overview | [V] |
| 12b | Latency | Not published | https://dev.meta.ai/docs/sam/overview | [not found] |
| 12c | Limits / price | 3,000 RPM. $2.50 per 1k images; $0.20 per 1k video frames with a 50-frame minimum per video request. | https://dev.meta.ai/docs/pricing-rate-limits | [V] |

### TTS

| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 13a | Meta TTS on the Model API (Nov 2026)? | **None.** The model list has no audio-output model. Voice Transcribe "does not synthesize speech". | https://dev.meta.ai/docs/models ; https://dev.meta.ai/docs/pricing-rate-limits | [V] |
| 13b | Meta open-weights TTS option | MMS-TTS (`facebook/mms-tts-kor`, `mms-tts-eng`): VITS, about 36M params, runs on CPU via transformers. Licence is **CC-BY-NC 4.0**. Korean needs `uroman` romanisation first. It is still a Meta model, but not via the Model API. | https://huggingface.co/facebook/mms-tts-kor | [V] (CPU speed not tested) |
| 13c | Browser fallback | Web Speech API `speechSynthesis`. It is not Meta, so label it on screen and in the README. | https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis | inference |
| 13d | Are non-Meta components allowed? | No prohibition found. The gate only requires that Meta models are "genuinely" used. A secondary source says third-party help is allowed if you own the rights. Participant repos openly use ElevenLabs, Vercel and others. | https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md ; https://cryptoaimeta.com/meta/meta-1-million-ai-hackathon-rules-who-can-enter/ ; https://github.com/meta-ai-hackathon/meta-hack | [S] |

---

## B. Rules facts

| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| B1 | Rubric weights | **Impact 30 / Meta AI tooling 25 / Demo (incl. video) 25 / Technical depth & execution 20. Confirmed by 2 secondary sources; not on the official event page.** The official page gives only one-line track criteria (indie: creativity, technical ambition, whether it works). | https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/ (updated after rules posted Oct 25) ; https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md ; https://cerebralvalley.ai/e/meta-ai-developer-hackathon | [S] (consistent) |
| B1b | Tooling criterion meaning | Creative use beyond basic integration, surfacing unexpected capabilities. Each criterion is scored 0-10. The top 5 per track go to a live final on the same rubric. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md | [S] |
| B2 | Pass/Fail gates | (a) Fits a problem statement: "Build for Your World" or "Push the Frontier". (b) Must "genuinely use Meta Model API / open-weight models". Failing either disqualifies regardless of quality. No further definition of "genuine" was found. | https://github.com/meta-ai-hackathon/meta-hack ; https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md | [S] |
| B3 | Video | 3-minute demo video, the primary judging artifact. Format and resolution are not specified. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md | [S]; format [not found] |
| B4 | Repo | Public open-source repo; only work built during the event; unclear contribution leads to disqualification; list all contributors. Licence and README requirements were not found. Entrants grant organisers a perpetual, irrevocable royalty-free licence. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md ; https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/restrictions.md ; https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/ | [S]; licence/README [not found] |
| B5 | Simulated hardware / mock wearable | Not addressed anywhere. There is no hardware requirement. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md | [not found] |
| B6a | Best Agentic Use-Case ($5K) | "strongest agent autonomy and multi-step workflows" (wiki paraphrase) | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md | [S] |
| B6b | Most Viral ($20K) | Highest X engagement on the demo post through Nov 8 EOD; submit the post link on the platform | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md ; https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md | [S] |
| B6c | Community Vote ($10K) | Most votes in the public gallery. Wiki: voting opens at the closing ceremony on Mon Nov 9 at 12 PM ET, winner announced Nov 16. A blog says bonus prizes are announced "on or about November 10". **Dates conflict.** Vote mechanics not found. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md ; https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/ | [S] |
| B6d | Bonus pool | $50K total. Other bonuses: Best Open Weight Build $10K, Best Creative Build (Muse Image/Wonder) $5K. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/grading%20criteria.md ; https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/ | [S] |
| B7 | Anti-project wording | Medical/mental-health advice (e.g. "AI Mental Health Advisor, skin blemish detector"), "Basic RAG Applications", "Simple Image Analyzers", "AI for Education" chatbots, job screeners, nutrition coaches, personality analyzers, sports coaches, "Anything political or involving war". Banned patterns: health advice, machines judging people, thin wrappers. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/restrictions.md | [S] |
| B8 | Non-Meta models/services + disclosure | No rule and no disclosure requirement found. Meta usage must still be genuine. | https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/restrictions.md ; https://raw.githubusercontent.com/meta-ai-hackathon/meta-hack/main/info/event%20guide.md | [not found] |
| B9 | Deadline | Nov 4, 9:00 PM ET (= Nov 5 11:00 KST). Judging runs Nov 4/5-8; closing ceremony Nov 9. Consistent with the brief. | https://cerebralvalley.ai/e/meta-ai-developer-hackathon | [V] |

---

## Design consequences (what to change because of missing or limited capabilities)

1. **No keyword weight and no list limit documented.** Pass a short `keywords` roster (unit call signs, crew names, "mayday", "PAR", building sectors, Korean terms such as 구조대상자) at handshake. Always add **post-ASR roster snapping** (fuzzy match to the roster) in muse-spark, because biasing "does not guarantee an exact spelling". Roster changes require a reconnect, so restart the stream on roster change.
2. **No 8 kHz.** Radio-grade audio must be resampled to 16 kHz PCM s16le mono client-side (WebAudio AudioWorklet or ffmpeg) before sending. Demo clips: convert to 16 kHz mono WAV.
3. **Real-time pacing is enforced (close 1008).** For demo replay of recorded radio, stream at 1x with an 80 ms frame cadence; you cannot blast a file into the WebSocket. For batch, use `/v1/asr/transcribe` (10 min / 32 MB max).
4. **No word-level confidence or timestamps.** Uncertainty flags must come from muse-spark (a structured `asr_uncertain: bool` / `reason` field), not ASR scores. Timeline UI is per-turn (`startMs/endMs`, `audioProcessedMs`).
5. **Diarization labels are anonymous and session-scoped.** Map A/B/C to responders via channel/push-to-talk source in the simulated radio, or via call-sign self-ID parsed by the LLM ("Engine 2 to command..."). Overlapping speech is not handled, which is realistic for radio.
6. **`tool_choice` is only "auto".** You cannot force a tool. Use `response_format` json_schema for deterministic triage output (priority enum `DANGER | VICTIM_FOUND | HELP_NEEDED | ROUTINE`). Use tool calling (parallel) for the world-model agent actions (`update_responder`, `mark_victim`, `broadcast_brief`). Prefer the Responses API for the agent loop.
7. **Latency is unknown.** Use `reasoning_effort: "low"` or `"minimal"` for per-utterance triage and `"medium"`/`"high"` only for the periodic world-state synthesis. Measure and show latency in the demo.
8. **No Meta TTS on the API.** For earpiece briefings use browser `speechSynthesis` with a visible "TTS: browser (non-Meta)" label. Optionally offer Meta MMS-TTS (CC-BY-NC, CPU) as the "Meta open-weights voice" path; this needs uroman for Korean, so test speed first. Disclose either choice in the README.
9. **SAM 3.1 accepts video.** It can segment "person", "door", "window" or "fire" on a helmet-cam or drone clip, one noun phrase per call, with stable IDs across frames. Cost is about $0.20 per 1k frames (50-frame minimum). Precompute for the demo; latency is unpublished.

## Implications for our product

- The 25% "Meta tooling" weight is real but only secondary-sourced. It rewards **non-obvious, multi-model use**: ASR with keywords + DIARIZATION, plus Spark structured output and parallel tools, plus SAM 3.1 video. Show all three in one pipeline in the video.
- Make the agentic loop visible (Responses API, parallel tool calls, reasoning summaries) to target **Best Agentic Use-Case**. It is judged on autonomy and multi-step workflows.
- Steer clear of the "thin wrapper", "basic RAG" and "simple image analyzer" bans by fusing voice, touch and SAM into a stateful world model, not one call.
- Pass/fail "genuine use": every core path (triage, briefing text, victim estimate) must run through Meta models. Non-Meta parts (browser TTS, map tiles) are peripheral and should be labelled.
- Not medical advice and not war: frame victim handling as **location/status coordination**, never triage-of-injuries advice.
- The simulated wearable is not addressed by the rules. Present it honestly as a "simulated clip-on display / bone-conduction earpiece".
- Repo: public, README with model list, non-Meta disclosure, and a "built during event" statement. Add an OSS licence (MIT) even though none is required.
- Most Viral requires an X post of the demo before Nov 8 EOD. Community Vote opens around Nov 9 (dates conflict), so plan a post-deadline share.
- Budget is not a constraint: ASR costs $0.18/h and Spark rate limits (3k RPM) far exceed demo needs. The 60-min ASR session cap and 10-min file cap are the only practical limits.
