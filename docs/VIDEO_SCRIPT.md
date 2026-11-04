# Earshot — 3-minute video, as built (EN narration + EN subtitles; radio audio is Korean)

Build: `uv run python scripts/record_demo.py` (Playwright records `/demo` while a REPLAY of `data/cache/best.jsonl`
plays) → `scripts/make_voices.py` (Gemini TTS narration + earpiece clips, non-Meta) → `scripts/render_cards.py`
(`video/cards/*.html` → PNG) → `scripts/build_video.py` (ffmpeg: speed segments, radio + earpiece + narration mix, ASS
subtitles) → `video/earshot_draft.mp4` (~2:57). The whole run is a REPLAY of one recorded LIVE run and is labelled so;
no separate live segment was spliced in. Numbers on screen come from the run; nothing is typed in.

Voice: Gemini TTS narration (`gemini-2.5-flash-preview-tts`, voice Charon, brisk documentary style), disclosed in the
README and on the close card. Earpiece clips in the video are Gemini TTS too (voice Kore, band-passed); the live app
uses browser TTS.

| Video | Beat | Screen | Narration (EN) |
|---|---|---|---|
| 0:00–0:13 | Hook | Black. Text appears line by line: "Bucheon, 16 October 2026. 08:48 — a crew reports flammables. 08:52 — offensive strategy declared. 09:09 — isolation recognised. 09:35 — found. RIT ordered at 09:20." then "35.6% of maydays are missed on the first call." (Project Mayday, >9,000 maydays) | "Bucheon, last month. Flammables reported at 8:48, offensive strategy at 8:52. Isolation recognised at 9:09, rescue team ordered at 9:20, found at 9:35. Across more than nine thousand maydays, 35.6 percent are missed on the first call." |
| 0:13–0:18 | Title | "Earshot — listens to every fireground radio channel so no mayday goes unheard." Label: "Synthetic scenario · Korean radio · replay of a recorded live run · every model call was live" | "Korea's AI for 119 listens to citizens calling in. Earshot listens to the crew. Two radio channels, Meta's Muse speech model on both, and an agent that decides who hears what." |
| 0:18–0:33 | Filter (replay ×2.4 → ×1) | `/demo`: L01–L05 stream on the two lanes with live partials. DANGER card after L04 with latency badge; "Confirm strategy?" proposal under it. Kim's earpiece speaks one sentence; Park's phone shows held. | "Five transmissions. One card. The exterior captain reports thinner drums on the third floor. Spark tags it danger, five and a half seconds after he stops talking. The commander declared offensive a minute ago, so the agent asks: confirm strategy? Kim, directly below, hears one sentence in her earpiece. Park, on the other side of the building, hears nothing. That's the point." |
| 0:55–1:10 | One-touch victim | Kim's phone: hold 구조대상자 여기 + TALK (L06). PTT transcript appears, pin drops on 2F-E-OFFICE, outdoor crew brief. | "Kim finds a victim. One gloved hold, one sentence. Muse transcribes it, the pin lands on the floor plan, and the crew at the front door is told to expect her." |
| 1:10–1:55 | Distress without a codeword | L08 lands on TAC while the IC talks on CMD (L09) — note on screen. MAYDAY card on top, latency badge, `필요한 것` missing → agent asks Kim (earpiece) → L10 completes the card. Ack bar runs out → pulse. IC acks, approves 무선 침묵 + RIT deploy → earpieces speak (IC-approved brief labelled). L11. | "Now the ceiling comes down. Kim never says the word. No mayday, no code. Just: I can't find the way out. And the commander is talking on the other channel at that moment. Earshot hears it anyway: card on top, four seconds after she stops. The SOP 109 field, what do you need, is empty, so the agent asks Kim, and she answers. Unacknowledged, the card pulses and sounds. The commander acknowledges, approves radio silence and the rescue team. Every earpiece speaks." |
| 1:55–2:20 | Silence → SOP 109 §1.1 (replay ×1.8) | Accountability strip: Park's last-heard timer. Ping ×3 in Park's earpiece. RULE card "3회 무응답 = 긴급탈출 상황". L13: Park answers, card resolves "found OK". | "Park has been silent for a minute. The agent pings his earpiece three times. Three unanswered calls is, by Korean SOP 109, an emergency, so it becomes a card. Park answers: radio dead spot. The card resolves itself. False alarms are cheap. Missed maydays are not." |
| 2:20–2:46 | Under the hood | Static card: Muse Voice Transcribe (2 channels + PTT, keyword biasing) → Spark strict JSON triage → world model + 7 rules (R1–R7) → Spark Responses agent, 7 tools + invariant checker. Eval table (radio · keywords on vs off). | "Under the hood: Muse Voice Transcribe on every channel with SOP keyword biasing. Spark extracts a strict JSON event with a verbatim evidence span. A world model runs seven time-bounded rules. A Spark agent routes information through seven tools, and an invariant checker rejects briefs aimed at the wrong sector. We measured it tonight on thirty-six synthetic lines, clean and codec-degraded: mayday recall thirteen of thirteen, and keyword biasing lifts critical-term recovery from eleven to fourteen of fourteen." |
| 2:46–2:57 | Limits + close | "Simulated hardware · synthetic audio · reported zones, not tracking · decision support — the IC decides · narration, radio and earpiece voices in this video are non-Meta Gemini TTS · the live app's earpiece uses browser TTS (non-Meta)". Close: "The agent decides who hears what. The commander decides who does what." + repo URL | "Simulated hardware, synthetic audio, positions as reported, not tracking. Earshot never gives an order. The agent decides who hears what. The commander decides who does what." |

Video times after the hook are approximate (the run is replayed at ×2.4 / ×1 / ×1.6 / ×1 / ×1.8 per segment; see
`SEGMENTS` in `scripts/build_video.py`).

## Most Viral cut (20 s, 9:16) — card only, cut not built
`video/cards/viral_end.html`: "35.6% of maydays are missed on the first call. Earshot." (Project Mayday, >9,000 maydays)

## Claim rules kept
- 35.6 % only; never 54 % / 36.5 % / 82.6 %.
- Bucheon: 08:48 flammables reported → 08:52 offensive declared; 09:09 isolation recognised → 09:35 found, RIT ordered
  09:20 (Kyunghyang 2026-10-23, Hankook Ilbo 2026-10-20). Never "unnoticed silence".
- No WER claim for Muse; nothing medical; no tracking claim; the agent never gives orders (IC-approved briefs labelled).
