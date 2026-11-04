"""Synthesise the 36 scenario/eval lines with Gemini TTS (non-Meta, disclosed) into data/audio/raw/<id>.wav.

Then run `uv run python scripts/make_audio.py` to produce clean/ (16 kHz) and radio/ (AMR-NB) versions.
Needs GEMINI_API_KEY in .env (Google AI Studio key). Model: gemini-2.5-flash-preview-tts (or --model gemini-2.5-pro-preview-tts).
Each unit gets its own voice; style prompts make the lines sound like handheld-radio traffic.

Usage: uv run python scripts/gemini_tts.py [--only L08,K07] [--force] [--model ...]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import wave
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = ROOT / "data"
RAW = DATA / "audio" / "raw"

# Gemini prebuilt voices (https://ai.google.dev/gemini-api/docs/speech-generation)
VOICES = {
    "ic": "Charon",            # 지휘대장: low, calm, firm
    "dispatch": "Orus",
    "hanbit_center": "Algenib",
    "kim": "Fenrir",           # 김하늘: energetic → urgent
    "park": "Enceladus",       # 박준: breathy, lower
    "rit": "Orus",
    "en_command": "Charon",
    "en_engine21": "Puck",
    "en_truck5": "Fenrir",
    "en_engine23": "Algenib",
    None: "Kore",
}

STYLE = {
    "calm": "Speak like a Korean fire incident commander on a handheld radio: low, calm, clipped, slightly fast, no emotion.",
    "normal": "Speak like a firefighter on a handheld radio: clear, slightly fast, clipped sentences, a little background effort.",
    "firm": "Speak like a fire commander broadcasting an urgent order on the radio: firm, loud, clipped, fast.",
    "urgent": "Speak like a firefighter in distress on a radio: out of breath, strained, fast, broken into short bursts, frightened but trying to stay controlled.",
    "en_calm": "Speak like a US firefighter on a handheld radio: clear, clipped, slightly fast.",
    "en_urgent": "Speak like a US firefighter in distress on a radio: out of breath, strained, fast, short bursts.",
}

# per-line delivery (ids not listed → normal / en_calm)
DELIVERY = {
    "L01": "calm", "L05": "calm", "L09": "calm", "L11": "firm",
    "L06": "normal", "L08": "urgent", "L10": "urgent",
    "K06": "firm", "K07": "urgent", "K08": "firm", "K09": "calm", "K10": "urgent",
    "M01": "urgent", "M02": "urgent", "M03": "en_urgent", "M04": "en_urgent",
    "E06": "en_calm", "E07": "en_urgent", "E08": "en_urgent", "E09": "en_calm",
}


def lines() -> list[dict]:
    out: list[dict] = []
    sc = yaml.safe_load((DATA / "scenario_hanbit.yaml").read_text(encoding="utf-8"))
    for ln in sc["lines"]:
        if ln.get("kind") == "agent":
            continue
        out.append({"id": ln["id"], "lang": "ko", "unit": ln.get("unit"), "text": ln["text_ko"]})
    ev = yaml.safe_load((DATA / "eval_lines.yaml").read_text(encoding="utf-8"))
    for ln in ev["lines"]:
        out.append({"id": ln["id"], "lang": ln["lang"], "unit": ln.get("speaker_hint"), "text": ln["text"]})
    return out


def synth(client: httpx.Client, key: str, model: str, text: str, voice: str, style: str) -> bytes:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": f"{style}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    for attempt in range(5):
        r = client.post(url, params={"key": key}, json=body, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 8 * (attempt + 1)
            print(f"   {r.status_code}, retry in {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
        mime = part.get("mimeType", "")
        if "L16" not in mime and "pcm" not in mime.lower():
            raise RuntimeError(f"unexpected mime {mime}")
        return base64.b64decode(part["data"])
    raise RuntimeError("gave up after retries")


def write_wav(path: Path, pcm: bytes, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default="gemini-2.5-flash-preview-tts")
    args = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        sys.exit("GEMINI_API_KEY missing in .env")
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    RAW.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as client:
        for ln in lines():
            lid = ln["id"]
            if only and lid not in only:
                continue
            out = RAW / f"{lid}.wav"
            side = RAW / f"{lid}.json"
            if out.exists() and not args.force:
                print(f"{lid}: exists, skip")
                continue
            voice = VOICES.get(ln["unit"], VOICES[None])
            style_key = DELIVERY.get(lid, "en_calm" if ln["lang"] == "en" else "normal")
            t0 = time.time()
            pcm = synth(client, key, args.model, ln["text"], voice, STYLE[style_key])
            write_wav(out, pcm)
            side.write_text(json.dumps({"source": "tts_gemini", "model": args.model, "voice": voice, "style": style_key},
                                       ensure_ascii=False), encoding="utf-8")
            print(f"{lid}: {voice:9s} {style_key:9s} {len(pcm) / 48000:5.1f}s  ({time.time() - t0:.1f}s)  {ln['text'][:36]}")
    print("done → now run: uv run python scripts/make_audio.py --force")


if __name__ == "__main__":
    main()
