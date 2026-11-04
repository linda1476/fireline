# Fireline — 3-minute demo video storyboard

Target 2:50. Record at 1920×1080. Two browser windows: Command dashboard (full width)
and the Responder clip display (phone-size window, right side). OBS or Windows
Game Bar (Win+G) for capture. Narration in English (write it on a card, read slowly).

| t | Screen | Narration (EN) | 한국어 메모 |
|---|---|---|---|
| 0:00–0:20 | Title card "FIRELINE — AI indoor/outdoor coordination for firefighters". Cut to a still of a mixed-use building. | "In January 2024, two firefighters in Mungyeong, Korea entered a burning factory and lost contact. Investigators cited a failure to share on-scene information. In 2010 in Bridgeport, two maydays were transmitted and never heard — command was juggling two radio channels. The radio is not the problem. The problem is that nobody can hold the whole picture." | 도입: 문경·브리지포트 사례. 톤 담담하게. |
| 0:20–0:35 | Command dashboard, empty, model badges "SPARK live · ASR live · SAM live". | "Fireline listens to every transmission, triages it, keeps one shared world model, and tells each firefighter only what they need to hear. Built in ten days on the Meta Model API: Muse Voice Transcribe, Muse Spark 1.3 as an agent, and SAM 3.1." | 배지 클로즈업. "ten days" = 행사 기간. |
| 0:35–1:10 | Click DEMO: AUDIO. Radio audio plays. Transcript ticker shows partial → final text. Queue cards appear: Status, Status, Status+hazard, VictimFound (504, suspected). | "Scripted radio traffic from a five-story mixed-use fire plays through Muse Voice Transcribe. Each turn becomes a structured event: tag, priority, floor, zone, victims, hazards. Watch the queue — the suspected victim in 504 goes above routine progress reports." | 큐 카드 색 강조. 504 카드 포인트. |
| 1:10–1:40 | Map: floor 3 tab auto-switches; E1-2 "found one victim in 302" → victim marker confirmed in 302; floor 4 → 404 suspected. Responder window (L2-1) speaks: "Ladder 2: victim confirmed in 302 …" | "The world model places every crew and every victim on the floor plan. Nobody typed this. And the briefing agent — Muse Spark deciding, per responder, whether to interrupt — tells Ladder 2 on floor 4 about the 404 report, but stays silent for the crew that made it." | 월드모델 지도 + 폰 음성 브리핑 동시에. |
| 1:40–2:10 | MAYDAY line plays. Queue flashes red, mayday card top. Map floor 5: R3-1 InDanger pulsing, hazard triangle at stairwell B. Responder window (L2-1) critical briefing: "do not use stairwell B". Assignment proposal appears; click Accept. | "Mayday. Rescue 3-2 reports a ceiling collapse on five, partner pinned. Priority five, top of the queue, red. The agent briefs everyone on floors four and five with the exact location and proposes the nearest crew for RIT. Ladder 2, carrying two victims down stairwell B, is told B is blocked above them — before they ask." | 하이라이트. 여기서 세 모듈이 한 화면에 동시에. |
| 2:10–2:30 | Responder window: tap HELMET CAM → sample frame → SAM boxes drawn → "1 person detected" → new victim marker appears on the command map. Then tap I'M OK on R3-1's display → status turns green on the dashboard. | "Inside, hands are busy. One tap sends a helmet-cam frame to SAM 3.1; detected people become victim candidates on everyone's map. One tap says I'm okay. The clip display is simulated on a phone — the hardware is the next step." | 터치 입력 + SAM. 하드웨어는 시뮬레이션임을 솔직히. |
| 2:30–2:50 | Dashboard end state: 3 victims extracted, hazards, event timeline. Terminal: `fireline-demo` output with latency stats. GitHub repo page. | "Everything you saw runs on three Meta models and a few hundred lines of world-model Python. Code is public. Fireline: so the next mayday is heard, located, and answered." | 마무리. 레포 URL 노출. |

## Recording checklist
- Server running with real key: badges must say *live*. `uv run fireline-server`.
- Windows: Command at 1440×900 or full screen; Responder in a separate Chrome window
  sized 390×844 (DevTools device mode works) — `/responder/L2-1`, and a second one for
  `/responder/R3-1` for the I'M OK beat.
- Click "ENABLE AUDIO" on the responder windows once before recording.
- Run `POST /api/demo/reset` before the take. Demo speed 1.0 (real pacing ~2 min of
  radio) — or 1.5 if the video runs long.
- System audio capture ON so the radio WAVs and the TTS briefing are in the video.
- One take is fine; cut dead air in Clipchamp.
