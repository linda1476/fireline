import json, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, r"D:\meta\scripts")
import httpx
from gemini_tts import Auth, synth, write_wav

OUT = Path(r"D:\meta\video\build")
VO_VOICE, VO_STYLE = "Charon", "Narrate this at a brisk, confident documentary pace, without pauses between sentences"
EAR_VOICE, EAR_STYLE = "Kore", "Say this as a short, flat, synthetic earpiece announcement, clearly and a little quickly"

VO = {
 "vo_01": "Bucheon, last month. Flammables reported at 8:48. Offensive strategy at 8:52. A firefighter isolated at 9:09, found at 9:35. Across nine thousand maydays, more than a third are missed on the first call.",
 "vo_02": "Korea's AI for 119 listens to citizens calling in. Earshot listens to the crew. Two radio channels, Meta's Muse speech model on both, and an agent that decides who hears what.",
 "vo_03": "Five transmissions. One card. The exterior captain reports thinner drums on the third floor. Spark tags it danger, five and a half seconds after he stops talking. The commander declared offensive a minute ago, so the agent asks: confirm strategy? Kim, directly below, hears one sentence in her earpiece. Park, on the other side of the building, hears nothing. That's the point.",
 "vo_04": "Kim finds a victim. One gloved hold, one sentence. Muse transcribes it, the pin lands on the floor plan, and the crew at the front door is told to expect her.",
 "vo_05": "Now the ceiling comes down. Kim never says the word. No mayday, no code. Just: I can't find the way out. And the commander is talking on the other channel at that moment. Earshot hears it anyway: card on top, four seconds after she stops. The SOP 109 field, what do you need, is empty, so the agent asks Kim, and she answers. Unacknowledged, the card pulses and sounds. The commander acknowledges, approves radio silence and the rescue team. Every earpiece speaks.",
 "vo_06": "Park has been silent for a minute. The agent pings his earpiece three times. Three unanswered calls is, by Korean SOP 109, an emergency, so it becomes a card. Park answers: radio dead spot. The card resolves itself. False alarms are cheap. Missed maydays are not.",
 "vo_07": "Under the hood: Muse Voice Transcribe on every channel with SOP keyword biasing. Spark extracts a strict JSON event with a verbatim evidence span. A world model runs seven time-bounded rules. A Spark agent routes information through seven tools, and an invariant checker rejects briefs aimed at the wrong sector. We measured it tonight on thirty-six synthetic lines, clean and codec-degraded: mayday recall thirteen of thirteen, and keyword biasing lifts critical-term recovery from eleven to fourteen of fourteen.",
 "vo_08": "Simulated hardware, synthetic audio, positions as reported, not tracking. Earshot never gives an order. The agent decides who hears what. The commander decides who does what.",
}
EAR = {
 "ear_b01": "3층 도장공장에 신나 드럼 다수 등 인화물질. 2층 동측 천장으로 연소 확대 우려.",
 "ear_b02": "필요한 것이 무엇입니까? 사다리, 공기용기 등",
 "ear_b03": "2층 동쪽 창고에서 대원 고립, 천장 붕괴로 탈출 불가. 공기 잔량 부족.",
 "ear_b04": "고립대원 동측 창문으로 이동 중, 사다리와 공기용기 필요.",
 "ear_b05": "구조대 투입 중, 위치 유지.",
 "ear_b06": "전 출동대 무선 침묵, 긴급탈출 관련 교신만",
 "ear_b07": "신속동료구조팀 2층 동쪽 창고 투입",
 "ear_ping": "누리센터 박준, 응답하십시오.",
 "ear_b08": "긴급탈출 발생, 2층 동쪽 창고에 대원 고립.",
}


def ff(*args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return round(float(r.stdout.strip()), 3)


auth = Auth("gemini-2.5-flash-preview-tts", None, "us-central1")
print("auth:", auth.kind, auth.project if auth.kind == "vertex" else "", flush=True)
failed, result = [], {}
jobs = [(k, t, VO_VOICE, VO_STYLE) for k, t in VO.items()] + [(k, t, EAR_VOICE, EAR_STYLE) for k, t in EAR.items()]
with httpx.Client() as client:
    for name, text, voice, style in jobs:
        raw = OUT / f"{name}.wav"
        try:
            if not raw.exists() or "--force" in sys.argv:
                t0 = time.time()
                pcm = synth(client, auth, text, voice, style)
                write_wav(raw, pcm)
                print(f"{name}: {len(pcm)/48000:.1f}s ({time.time()-t0:.1f}s)", flush=True)
            else:
                print(f"{name}: exists", flush=True)
            if name.startswith("vo_"):
                final = OUT / f"{name}_n.wav"
                ff("-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "24000", "-ac", "1", str(final))
            else:
                final = OUT / f"{name}_fx.wav"
                ff("-i", str(raw), "-af", "highpass=f=300,lowpass=f=3400,acompressor=threshold=-18dB:ratio=4,volume=-6dB",
                   "-ar", "16000", "-ac", "1", str(final))
            result[name] = {"file": str(final), "seconds": dur(final)}
        except Exception as e:
            print(f"{name}: FAILED {e}", flush=True)
            failed.append(name)

(OUT / "voices.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
print("failed:", failed)
