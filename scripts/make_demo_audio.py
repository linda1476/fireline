"""Generate the demo radio audio: SAPI speech (make_demo_audio.ps1) + ffmpeg radio effect.

    python scripts/make_demo_audio.py [--out data/audio] [--force] [--skip-tts] [--skip-fx]

For every scenario script line this produces ``data/audio/{index:02d}_{responder_id}.wav``
(index 1-based, same naming as ``fireline.server.pipeline.audio_path_for``), 16 kHz mono
16-bit, band-limited to 300-3400 Hz and compressed so it sounds like a fireground radio.
Each file is verified with ``fireline.meta.asr.wav_info`` at the end.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fireline.meta.asr import wav_info  # noqa: E402
from fireline.scenario import load_scenario  # noqa: E402
from fireline.server.pipeline import audio_path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "make_demo_audio.ps1"

RADIO_FILTER = (
    "highpass=f=300,lowpass=f=3400,"
    "acompressor=threshold=-18dB:ratio=4:attack=5:release=60:makeup=2,"
    "volume=1.3,alimiter=limit=0.95"
)


def run_tts(out_dir: Path, force: bool, scenario: str | None) -> None:
    """Call the PowerShell synthesiser (writes clean 16 kHz mono WAVs)."""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), "-OutDir", str(out_dir)]
    if scenario:
        cmd += ["-Scenario", scenario]
    if force:
        cmd.append("-Force")
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def radio_fx(path: Path, ffmpeg: str) -> None:
    """Band-pass + compress in place (via a temp file), keeping 16 kHz mono s16."""
    tmp = path.with_name(path.stem + ".radio.tmp.wav")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-af", RADIO_FILTER, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-bitexact", "-fflags", "+bitexact",
        str(tmp),
    ]
    subprocess.run(cmd, check=True)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=None, help="output dir (default data/audio)")
    ap.add_argument("--scenario", default=None, help="scenario.json path (default data/scenario.json)")
    ap.add_argument("--force", action="store_true", help="re-synthesise files that already exist")
    ap.add_argument("--skip-tts", action="store_true", help="only apply the radio effect to existing files")
    ap.add_argument("--skip-fx", action="store_true", help="keep the clean SAPI output (no ffmpeg)")
    args = ap.parse_args(argv)

    scenario = load_scenario(args.scenario)
    out_dir = Path(args.out) if args.out else audio_path_for(1, "x").parent
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = [audio_path_for(i, ln.responder_id, out_dir) for i, ln in enumerate(scenario.script, start=1)]

    if not args.skip_tts:
        run_tts(out_dir, args.force, args.scenario)

    ffmpeg = shutil.which("ffmpeg")
    if not args.skip_fx:
        if not ffmpeg:
            print("ffmpeg not on PATH: skipping the radio effect (files stay clean speech)", file=sys.stderr)
        else:
            for p in expected:
                if p.is_file():
                    radio_fx(p, ffmpeg)
                    print(f"radio  {p.name}")

    ok = True
    print()
    print(f"{'file':<16} {'rate':>6} {'ch':>3} {'bytes/sample':>13} {'seconds':>8}")
    for p in expected:
        if not p.is_file():
            print(f"{p.name:<16} MISSING")
            ok = False
            continue
        rate, ch, width = wav_info(p)
        seconds = (p.stat().st_size - 44) / (rate * ch * width)
        good = (rate, ch, width) == (16000, 1, 2)
        ok &= good
        print(f"{p.name:<16} {rate:>6} {ch:>3} {width:>13} {seconds:>8.1f}{'' if good else '  <-- BAD FORMAT'}")
    print(f"{len(expected)} files in {out_dir}: {'all 16 kHz mono s16' if ok else 'PROBLEMS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
