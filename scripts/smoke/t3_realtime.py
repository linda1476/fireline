"""TEST 3: Realtime WS ENDPOINTING + PUSH_TO_TALK (Korean)."""
import asyncio, json, time, sys, wave
import numpy as np, websockets
from _common import KEY, AUDIO, OUT, KEYWORDS, scrub

URI = "wss://api.meta.ai/v1/asr/realtime"
SR = 16000; FRAME = int(SR * 0.08)

def pcm(name):
    with wave.open(str(AUDIO / name), "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        return w.readframes(w.getnframes())
def sil(s): return b"\x00\x00" * int(SR * s)
def trim_end(b):
    """time (s) of last sample above threshold => true end of speech within the wav"""
    a = np.frombuffer(b, dtype=np.int16).astype(np.float32)
    idx = np.nonzero(np.abs(a) > 300)[0]
    return (idx[0] / SR, idx[-1] / SR) if len(idx) else (0, len(a) / SR)

async def session(mode, segments, label, read_timeout=30):
    stream = b"".join(seg for seg, _ in segments)
    marks, pos = [], 0.0
    for seg, name in segments:
        d = len(seg) / 2 / SR
        if name:
            s, e = trim_end(seg)
            marks.append({"seg": name, "wav_start_s": round(pos, 3), "speech_start_s": round(pos + s, 3), "speech_end_s": round(pos + e, 3), "wav_end_s": round(pos + d, 3)})
        pos += d
    print(f"=== {label} mode={mode} stream={pos:.2f}s marks={marks}")
    events = []
    ws = await websockets.connect(URI, open_timeout=30, max_size=None)
    hs = {"authorization": {"accessToken": f"Bearer {KEY}"}, "audioEncoding": "PCM_16KHZ",
          "model": "muse-voice-transcribe-1.0", "mode": mode, "partialMode": "CUMULATIVE",
          "emitAudioProgress": False, "languageBias": ["Korean"], "keywords": KEYWORDS}
    await ws.send(json.dumps(hs, ensure_ascii=False))
    ack = json.loads(await asyncio.wait_for(ws.recv(), 15))
    print("ack keys:", list(ack))
    t0 = time.perf_counter()
    end_sent = {}
    def log(ev):
        t = time.perf_counter() - t0
        ev_s = {k: v for k, v in ev.items()}
        events.append({"t": round(t, 3), **ev_s})
        print(f"  t={t:7.3f} {json.dumps(ev_s, ensure_ascii=False)}")
    async def reader():
        try:
            async for m in ws:
                if isinstance(m, bytes): log({"type": "<binary>", "len": len(m)}); continue
                log(json.loads(m))
        except websockets.ConnectionClosed as e:
            log({"type": "<closed>", "code": e.code, "reason": str(e.reason)})
        else:
            log({"type": "<closed>", "code": ws.close_code, "reason": ws.close_reason})
    rt = asyncio.create_task(reader())
    try:
        n = 0
        for i in range(0, len(stream), FRAME * 2):
            target = t0 + n * 0.08
            delay = target - time.perf_counter()
            if delay > 0: await asyncio.sleep(delay)
            await ws.send(stream[i:i + FRAME * 2]); n += 1
            if rt.done(): break
        end_sent["t"] = round(time.perf_counter() - t0, 3)
        print(f"  t={end_sent['t']:7.3f} >>> endStream (frames={n})")
        await ws.send(json.dumps({"type": "endStream"}))
        await asyncio.wait_for(rt, read_timeout)
    except asyncio.TimeoutError:
        print("  TIMEOUT waiting for close"); events.append({"type": "<timeout>"})
    except Exception as e:
        print("  EXC", scrub(repr(e))); events.append({"type": "<exc>", "err": scrub(repr(e))})
    finally:
        await ws.close()
    return {"label": label, "mode": mode, "marks": marks, "endStream_t": end_sent.get("t"), "events": events}

async def main():
    i, ii = pcm("i_kimhaneul.wav"), pcm("ii_nuri.wav")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    R = []
    if which in ("all", "ep"):
        R.append(await session("ENDPOINTING", [(sil(1.0), None), (i, "i"), (sil(2.0), None), (ii, "ii"), (sil(2.0), None)], "endpointing"))
    if which in ("all", "ptt"):
        R.append(await session("PUSH_TO_TALK", [(sil(0.5), None), (ii, "ii"), (sil(0.5), None)], "ptt"))
    json.dump(R, open(OUT / f"t3_{which}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
asyncio.run(main())
