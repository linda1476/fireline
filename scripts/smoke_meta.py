"""One-shot connectivity check against the real Meta Model API.

    uv run python scripts/smoke_meta.py [--wav path] [--image path]

Steps: Spark ping -> Spark structured output on one radio line -> ASR file transcribe
on a WAV (generated with Windows SAPI if none given) -> SAM 3.1 detect on an image.
Prints what each surface actually returned so parsing can be fixed fast.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fireline.config import OUT_DIR, get_settings  # noqa: E402
from fireline.meta import MetaAPIError  # noqa: E402
from fireline.meta.asr import ASRClient  # noqa: E402
from fireline.meta.sam import SAMClient  # noqa: E402
from fireline.meta.spark import SparkClient  # noqa: E402


class Probe(BaseModel):
    tag: Literal["Danger", "VictimFound", "HelpNeeded", "Status"]
    priority: int = Field(..., ge=1, le=5)
    summary: str
    floor: int | None = None
    zone: str | None = None
    mayday: bool = False


LINE = ("MAYDAY MAYDAY MAYDAY. Rescue 3-2, fifth floor, stairwell B landing. "
        "The ceiling came down, Choi is pinned under it. We need the RIT up here now.")


def make_wav_sapi(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{ $s.SelectVoice('Microsoft Zira Desktop') }} catch {{ }}
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{path}', $fmt)
$s.Speak('{text.replace("'", "''")}')
$s.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)
    return path


def make_image(path: Path) -> Path:
    """Draw a simple 'person' silhouette so SAM has something to find."""
    from PIL import Image, ImageDraw  # type: ignore

    img = Image.new("RGB", (640, 480), (70, 70, 75))
    d = ImageDraw.Draw(img)
    d.ellipse((290, 120, 350, 180), fill=(220, 190, 170))
    d.rectangle((285, 180, 355, 330), fill=(40, 60, 120))
    d.rectangle((290, 330, 318, 440), fill=(30, 30, 40))
    d.rectangle((322, 330, 350, 440), fill=(30, 30, 40))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG")
    return path


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav")
    ap.add_argument("--image")
    ap.add_argument("--skip-sam", action="store_true")
    args = ap.parse_args()

    s = get_settings(refresh=True)
    print(f"base_url={s.base_url} spark={s.spark_model} asr={s.asr_model} sam={s.sam_model} mock={s.mock}")
    if s.mock:
        print("MODEL_API_KEY missing -> nothing to test. Put MODEL_API_KEY=... in .env")
        return 2
    ok = True

    # 1. Spark ping
    spark = SparkClient(s)
    try:
        t0 = time.perf_counter()
        print("[spark] ping ->", spark.ping(), f"({(time.perf_counter()-t0)*1000:.0f} ms)")
    except Exception as e:
        ok = False
        print("[spark] ping FAILED:", repr(e))

    # 2. Spark structured output
    try:
        obj, ms = await spark.acomplete_json(
            "You triage firefighter radio traffic. Return JSON only.",
            f"Radio: \"{LINE}\"\nZones: stairwell A, stairwell B, unit 504, east corridor 5.",
            Probe,
        )
        print(f"[spark] structured ({ms} ms):", obj.model_dump())
    except Exception as e:
        ok = False
        print("[spark] structured FAILED:", repr(e))

    # 3. ASR file
    asr = ASRClient(s)
    wav = Path(args.wav) if args.wav else make_wav_sapi(LINE, OUT_DIR / "smoke" / "mayday.wav")
    try:
        t0 = time.perf_counter()
        res = await asr.transcribe_file(wav, mode="PUSH_TO_TALK")
        print(f"[asr] transcribe ({(time.perf_counter()-t0)*1000:.0f} ms): text={res.text!r}")
        print("[asr] raw keys:", list(res.raw.keys()))
        print("[asr] raw:", json.dumps(res.raw)[:600])
    except Exception as e:
        ok = False
        print("[asr] transcribe FAILED:", repr(e))

    # 4. SAM
    if not args.skip_sam:
        try:
            img = Path(args.image) if args.image else make_image(OUT_DIR / "smoke" / "person.jpg")
        except Exception as e:
            img = None
            print("[sam] could not make image (pip install pillow):", e)
        if img:
            sam = SAMClient(s)
            try:
                b64 = base64.b64encode(img.read_bytes()).decode()
                dets, ms, raw = await sam.adetect(b64, mime="image/jpeg", prompt="person")
                print(f"[sam] detect ({ms} ms): {len(dets)} boxes; raw[:300]={raw[:300]!r}")
                for d in dets:
                    print("   ", d.model_dump())
            except MetaAPIError as e:
                ok = False
                print("[sam] FAILED:", e)
            except Exception as e:
                ok = False
                print("[sam] FAILED:", repr(e))

    print("RESULT:", "ALL OK" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
