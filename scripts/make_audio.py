"""Build data/audio/{clean,radio}/<id>.wav for every scenario + eval line.

Source priority per line id:
  1. data/audio/raw/<id>.*   (the builder's own voice; any format ffmpeg reads)
  2. Windows SAPI TTS        (Microsoft Heami Desktop for ko, Microsoft Zira Desktop for en) — disclosed fallback
clean = 16 kHz mono s16 WAV. radio = gap_3 §5 chain (300–3400 Hz band-pass, compressor, clip, AMR-NB 7.95k, squelch tail),
decoded back to 16 kHz WAV. Provenance (own_voice / tts_heami / tts_zira) is written to data/audio/provenance.json.

Usage: uv run python scripts/make_audio.py [--only L08,K07] [--force] [--radio-only]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 console
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW, CLEAN, RADIO = DATA / "audio" / "raw", DATA / "audio" / "clean", DATA / "audio" / "radio"
VOICES = {"ko": "Microsoft Heami Desktop", "en": "Microsoft Zira Desktop"}

RADIO_FILTER = (
    "[0:a]aresample=16000,highpass=f=300,lowpass=f=3400,"
    "acompressor=threshold=-20dB:ratio=6:attack=5:release=50,volume=6dB,alimiter=limit=0.7,"
    "aformat=channel_layouts=mono[v];"
    "[1:a]afade=t=out:st=0.05:d=0.2,aformat=channel_layouts=mono[sq];"
    "[v][sq]concat=n=2:v=0:a=1[out]"
)


def lines() -> list[dict]:
    out: list[dict] = []
    sc = yaml.safe_load((DATA / "scenario_hanbit.yaml").read_text(encoding="utf-8"))
    for ln in sc["lines"]:
        if ln.get("kind") == "agent":
            continue
        out.append({"id": ln["id"], "lang": sc.get("lang", "ko"), "text": ln["text_ko"], "text_en": ln.get("text_en")})
    ev = yaml.safe_load((DATA / "eval_lines.yaml").read_text(encoding="utf-8"))
    for ln in ev["lines"]:
        out.append({"id": ln["id"], "lang": ln["lang"], "text": ln["text"]})
    return out


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-400:]}")


def find_raw(line_id: str) -> Path | None:
    for p in RAW.glob(f"{line_id}.*"):
        if p.suffix.lower() in (".wav", ".m4a", ".mp3", ".webm", ".ogg", ".flac", ".aac", ".mp4", ".opus", ".wma"):
            return p
    return None


def tts(text: str, lang: str, out: Path) -> None:
    tf = out.with_suffix(".txt")
    tf.write_text(text, encoding="utf-8")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{VOICES[lang]}')
$s.Rate = 1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile('{out}', $fmt)
$t = [System.IO.File]::ReadAllText('{tf}', [System.Text.Encoding]::UTF8)
$s.Speak($t)
$s.Dispose()
"""
    run(["powershell", "-NoProfile", "-Command", ps])
    tf.unlink(missing_ok=True)


def to_clean(src: Path, out: Path) -> None:
    # own-voice: strip leading/trailing silence below -40 dB, keep 0.3 s pads, light highpass, 16k mono s16
    af = ("silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.3,"
          "areverse,silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.3,areverse,"
          "highpass=f=80,loudnorm=I=-18:TP=-2:LRA=11")
    run(["ffmpeg", "-y", "-i", str(src), "-af", af, "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(out)])


def to_radio(clean: Path, out: Path) -> None:
    amr = out.with_suffix(".amr")
    run(["ffmpeg", "-y", "-i", str(clean), "-f", "lavfi", "-t", "0.25", "-i", "anoisesrc=c=white:a=0.3:r=16000",
         "-filter_complex", RADIO_FILTER, "-map", "[out]", "-ar", "8000", "-ac", "1",
         "-c:a", "libopencore_amrnb", "-b:a", "7.95k", str(amr)])
    run(["ffmpeg", "-y", "-i", str(amr), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(out)])
    amr.unlink(missing_ok=True)


def duration(p: Path) -> float:
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--radio-only", action="store_true")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    for d in (RAW, CLEAN, RADIO):
        d.mkdir(parents=True, exist_ok=True)
    prov_path = DATA / "audio" / "provenance.json"
    prov: dict = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}

    for ln in lines():
        lid = ln["id"]
        if only and lid not in only:
            continue
        clean, radio = CLEAN / f"{lid}.wav", RADIO / f"{lid}.wav"
        raw = find_raw(lid)
        source = "own_voice" if raw else ("tts_heami" if ln["lang"] == "ko" else "tts_zira")
        need_clean = args.force or not clean.exists() or prov.get(lid, {}).get("source") != source \
            or (raw and raw.stat().st_mtime > clean.stat().st_mtime)
        if need_clean and not args.radio_only:
            if raw:
                to_clean(raw, clean)
            else:
                tmp = CLEAN / f"{lid}.tts.wav"
                tts(ln["text"], ln["lang"], tmp)
                to_clean(tmp, clean)
                tmp.unlink(missing_ok=True)
        if need_clean or args.force or not radio.exists():
            to_radio(clean, radio)
        prov[lid] = {"source": source, "lang": ln["lang"], "duration_s": round(duration(clean), 2), "text": ln["text"]}
        print(f"{lid:4s} {source:10s} {prov[lid]['duration_s']:5.1f}s  {ln['text'][:40]}")
    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    n_own = sum(1 for v in prov.values() if v["source"] == "own_voice")
    print(f"done: {len(prov)} lines, {n_own} own voice, {len(prov) - n_own} TTS → {prov_path}")


if __name__ == "__main__":
    main()
