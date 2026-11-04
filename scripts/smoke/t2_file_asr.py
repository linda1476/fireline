"""TEST 2: File ASR Korean, keywords on/off."""
import json, time
import httpx
from _common import KEY, BASE, AUDIO, OUT, KEYWORDS, scrub

URL = f"{BASE}/asr/transcribe"
def tx(wav, label, **req_extra):
    req = {"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
    req.update({k: v for k, v in req_extra.items() if v is not ...})
    t0 = time.perf_counter()
    try:
        with open(AUDIO / wav, "rb") as f:
            r = httpx.post(URL, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"},
                files={"request": (None, json.dumps(req, ensure_ascii=False), "application/json"),
                       "audio": (wav, f, "audio/wav")}, timeout=60)
        dt = time.perf_counter() - t0
        if r.status_code != 200:
            out = {"label": label, "status": r.status_code, "error": scrub(r.text)[:600], "latency_s": round(dt, 2)}
        else:
            d = r.json()
            out = {"label": label, "latency_s": round(dt, 2), "transcript": d.get("transcript"),
                   "audioDurationMs": d.get("audioDurationMs"), "n_turns": len(d.get("turns") or []), "keys": list(d)}
    except Exception as e:
        out = {"label": label, "error": scrub(repr(e))[:600], "latency_s": round(time.perf_counter() - t0, 2)}
    print(json.dumps(out, ensure_ascii=False))
    return out

R = []
for wav in ["i_kimhaneul.wav", "ii_nuri.wav"]:
    R.append(tx(wav, f"{wav} kw=ON  lb=[Korean]", languageBias=["Korean"], keywords=KEYWORDS))
    R.append(tx(wav, f"{wav} kw=OFF lb=[Korean]", languageBias=["Korean"]))
R.append(tx("i_kimhaneul.wav", "i kw=ON lb=[Korean,English]", languageBias=["Korean", "English"], keywords=KEYWORDS))
R.append(tx("i_kimhaneul.wav", "i kw=[] (empty) lb=[Korean]", languageBias=["Korean"], keywords=[]))
R.append(tx("i_kimhaneul.wav", "i no languageBias, kw=ON", keywords=KEYWORDS))
R.append(tx("i_kimhaneul.wav", "i no languageBias, no kw"))
R.append(tx("radio_16k.wav", "radio(i) kw=ON lb=[Korean]", languageBias=["Korean"], keywords=KEYWORDS))
R.append(tx("radio_16k.wav", "radio(i) kw=OFF lb=[Korean]", languageBias=["Korean"]))
json.dump(R, open(OUT / "t2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
