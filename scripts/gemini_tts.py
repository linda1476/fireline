"""Synthesise the 36 scenario/eval lines with Gemini TTS (non-Meta, disclosed) into data/audio/raw/<id>.wav.

Then run `uv run python scripts/make_audio.py` to produce clean/ (16 kHz) and radio/ (AMR-NB) versions.
Auth, in order: GEMINI_API_KEY in .env (Google AI Studio) → else Vertex AI with the gcloud CLI token
(`gcloud auth print-access-token`, project from GOOGLE_CLOUD_PROJECT or `gcloud config get project`, region us-central1).
Model: gemini-2.5-flash-preview-tts (or --model gemini-2.5-pro-preview-tts).
Each unit gets its own voice; style prompts make the lines sound like handheld-radio traffic.

Usage: uv run python scripts/gemini_tts.py [--only L08,K07] [--force] [--model ...] [--project ID] [--location us-central1]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
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

# One directive sentence, then a colon, then the line (the documented "Say cheerfully: …" form). An earlier form with a
# colon-separated adjective list ("…radio: low, calm, clipped…") was read aloud on 3 of 36 lines.
STYLE = {
    "calm": "Say this the way a calm, low-voiced Korean fire incident commander talks quickly into a handheld radio",
    "normal": "Say this the way a firefighter talks quickly and clearly into a handheld radio while working",
    "firm": "Say this the way a fire commander shouts a firm, fast, urgent order into the radio",
    "urgent": "Say this the way a frightened, out-of-breath firefighter in distress gasps it into a radio in short bursts",
    "en_calm": "Say this the way a US firefighter talks quickly and clearly into a handheld radio",
    "en_urgent": "Say this the way a frightened, out-of-breath US firefighter in distress gasps it into a radio in short bursts",
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


class Auth:
    """Either an AI Studio key (query param) or a Vertex AI bearer token from the gcloud CLI."""

    def __init__(self, model: str, project: str | None, location: str) -> None:
        self.key = os.environ.get("GEMINI_API_KEY", "")
        self.model, self.location = model, location
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self.token, self.token_t = "", 0.0
        if self.key:
            self.kind = "aistudio"
            return
        gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd")
        if not gcloud:
            sys.exit("no GEMINI_API_KEY in .env and no gcloud CLI on PATH")
        self.gcloud = gcloud
        if not self.project:
            self.project = subprocess.run([gcloud, "config", "get", "project"], capture_output=True, text=True).stdout.strip()
        if not self.project:
            sys.exit("no gcloud project: pass --project or run `gcloud config set project ID`")
        self.kind = "vertex"

    def refresh(self) -> None:
        if self.kind == "vertex" and time.time() - self.token_t > 1800:
            r = subprocess.run([self.gcloud, "auth", "print-access-token"], capture_output=True, text=True)
            if r.returncode != 0 or not r.stdout.strip():
                sys.exit("gcloud auth print-access-token failed; run `gcloud auth login`")
            self.token, self.token_t = r.stdout.strip(), time.time()

    def url(self) -> str:
        if self.kind == "aistudio":
            return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        host = "aiplatform.googleapis.com" if self.location == "global" else f"{self.location}-aiplatform.googleapis.com"
        return (f"https://{host}/v1/projects/{self.project}/locations/{self.location}"
                f"/publishers/google/models/{self.model}:generateContent")

    def post(self, client: httpx.Client, body: dict) -> httpx.Response:
        self.refresh()
        if self.kind == "aistudio":
            return client.post(self.url(), params={"key": self.key}, json=body, timeout=120)
        return client.post(self.url(), headers={"Authorization": f"Bearer {self.token}"}, json=body, timeout=120)


def synth(client: httpx.Client, auth: Auth, text: str, voice: str, style: str) -> bytes:
    # systemInstruction is rejected by the TTS models (400 INVALID_ARGUMENT), so the directive rides inline.
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"{style}: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    for attempt in range(5):
        r = auth.post(client, body)
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
    ap.add_argument("--project", default=None, help="GCP project for the Vertex path (default: gcloud config)")
    ap.add_argument("--location", default="us-central1")
    args = ap.parse_args()
    auth = Auth(args.model, args.project, args.location)
    print(f"auth: {auth.kind}" + (f" (project {auth.project}, {auth.location})" if auth.kind == "vertex" else ""))
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
            pcm = synth(client, auth, ln["text"], voice, STYLE[style_key])
            write_wav(out, pcm)
            side.write_text(json.dumps({"source": "tts_gemini", "model": args.model, "voice": voice, "style": style_key,
                                        "via": auth.kind}, ensure_ascii=False), encoding="utf-8")
            print(f"{lid}: {voice:9s} {style_key:9s} {len(pcm) / 48000:5.1f}s  ({time.time() - t0:.1f}s)  {ln['text'][:36]}")
    print("done → now run: uv run python scripts/make_audio.py --force")


if __name__ == "__main__":
    main()
