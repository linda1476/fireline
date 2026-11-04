"""Assemble the 3-minute draft video from: the /demo REPLAY screen recording (scripts/record_demo.py), the run
timeline (video/build/timeline.json from data/cache/best.jsonl), the radio clips (data/audio/radio), the voice tracks
(video/build/voices.json from Gemini TTS: EN narration + KO earpiece lines) and the title cards (video/cards/*.png).

Time map: the recording is cut into run-time segments, some sped up (setpts), so the draft fits 3 minutes. Every
radio clip, earpiece line and subtitle is placed through the same run_t -> video_t map.

Usage: uv run python scripts/build_video.py [--out video/earshot_draft.mp4] [--no-vo]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
BUILD, CARDS = ROOT / "video" / "build", ROOT / "video" / "cards"
RADIO = ROOT / "data" / "audio" / "radio"
FPS = 30

# ------------------------------------------------------------------ timeline design (video seconds)
HOOK = [("hook_1", 2.5), ("hook_2", 2.9), ("hook_3", 3.1), ("hook_4", 2.7), ("hook_5", 2.3)]   # 13.5 s (vo_01 20.4 s fits at ×1.17)
TITLE_S = 5.0
# run-time segments: (run_t0, run_t1, speed)
SEGMENTS = [(0.0, 34.0, 2.4), (34.0, 101.0, 1.0), (101.0, 119.5, 1.6), (119.5, 126.0, 1.0), (126.0, 167.5, 1.8)]
HOOD_MIN_S, CLOSE_S = 15.0, 10.5

# earpiece lines: (run_t, unit, voice file key, EN subtitle)   unit: kim | park
EAR = [
    (62.9, "kim", "ear_b01", "Kim's earpiece · Thinner drums, flammables in the 3F paint shop. Fire may spread through the 2F east ceiling."),
    (99.3, "kim", "ear_b02", "Kim's earpiece · What do you need? Ladder, air cylinder…"),
    (102.3, "park", "ear_b03", "Park's earpiece · Member trapped in the 2F east storeroom, ceiling collapse, low on air."),
    (111.6, "park", "ear_b04", "Park's earpiece · Trapped member moving to the east windows; needs a ladder and an air cylinder."),
    (120.6, "kim", "ear_b05", "Kim's earpiece (IC-approved) · Rescue team on the way. Hold your position."),
    (123.8, "park", "ear_b06", "Park's earpiece · All units: radio silence. Emergency traffic only."),
    (128.7, "park", "ear_ping", "Park's earpiece · Nuri Station Park, respond."),
    (136.8, "park", "ear_ping", "Park's earpiece · Nuri Station Park, respond. (2)"),
    (144.9, "park", "ear_ping", "Park's earpiece · Nuri Station Park, respond. (3) → SOP 109 §1.1 card"),
]
HOLD_SUBS = [  # (run_t, EN) shown in the earpiece lane for holds
    (63.4, "Park's phone · held — not your sector (1F west)"),
]
CHANNEL_TAG = {"CMD": "지휘망 CMD", "TAC": "작전망 TAC", "PTT": "PTT · Kim"}


def ff(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-1500:])


def dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


class TimeMap:
    def __init__(self, run_t0_video: float):
        self.base = run_t0_video
        self.pieces = []   # (run_t0, run_t1, speed, video_t0)
        v = run_t0_video
        for a, b, s in SEGMENTS:
            self.pieces.append((a, b, s, v))
            v += (b - a) / s
        self.end = v

    def __call__(self, t: float) -> float:
        for a, b, s, v0 in self.pieces:
            if t < b or (a, b, s, v0) == self.pieces[-1]:
                return v0 + max(0.0, t - a) / s
        return self.end

    def speed_at(self, t: float) -> float:
        for a, b, s, _ in self.pieces:
            if a <= t < b:
                return s
        return 1.0


def ass_time(s: float) -> str:
    h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="video/earshot_draft.mp4")
    ap.add_argument("--no-vo", action="store_true", help="skip narration (user records their own)")
    args = ap.parse_args()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    tl = json.load(open(BUILD / "timeline.json", encoding="utf-8"))
    voices = json.load(open(BUILD / "voices.json", encoding="utf-8")) if (BUILD / "voices.json").exists() else {}
    timing = dict(l.split("=") for l in (BUILD / "demo_timing.txt").read_text().split())
    lead = float(timing["lead_s"])
    demo = BUILD / "demo.webm"
    sc = yaml.safe_load((ROOT / "data" / "scenario_hanbit.yaml").read_text(encoding="utf-8"))
    text_en = {l["id"]: l.get("text_en", "") for l in sc["lines"]}

    def vo_len(k: str) -> float:
        return float(voices[k]["seconds"]) if (k in voices and not args.no_vo) else 0.0

    # ---------------------------------------------------------------- video segments
    hook_s = sum(d for _, d in HOOK)
    run_v0 = hook_s + TITLE_S
    tm = TimeMap(run_v0)
    # narration slots (video seconds each VO may occupy); a VO longer than its slot is sped up, at most ×1.35
    VO_MAX_TEMPO = 1.35
    def fit(k: str, slot: float) -> float:
        L = vo_len(k)
        return 1.0 if L <= slot or L == 0 else min(VO_MAX_TEMPO, L / slot)
    hood_s = max(HOOD_MIN_S, min(26.0, vo_len("vo_07") / VO_MAX_TEMPO + 1.5))
    close_s = max(CLOSE_S, min(16.0, vo_len("vo_08") / VO_MAX_TEMPO + 1.0))
    total = tm.end + hood_s + close_s
    print(f"hook {hook_s:.1f}s · title {TITLE_S:.0f}s · run {run_v0:.1f}→{tm.end:.1f}s · hood {hood_s:.1f}s · close {close_s:.1f}s = {total:.1f}s")

    segs: list[Path] = []
    def card(name: str, seconds: float, idx: int) -> Path:
        p = BUILD / f"seg_{idx:02d}_{name}.mp4"
        ff(["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(CARDS / f"{name}.png"),
            "-vf", "scale=1920:1080,format=yuv420p", "-r", str(FPS), "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(p)])
        return p
    i = 0
    for name, d in HOOK:
        segs.append(card(name, d, i)); i += 1
    segs.append(card("title", TITLE_S, i)); i += 1
    for a, b, s in SEGMENTS:
        p = BUILD / f"seg_{i:02d}_run_{int(a)}_{int(b)}.mp4"
        ff(["-ss", f"{lead + a:.3f}", "-t", f"{b - a:.3f}", "-i", str(demo),
            "-vf", f"setpts=PTS/{s},scale=1920:1080,fps={FPS},format=yuv420p", "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(p)])
        segs.append(p); i += 1
    segs.append(card("hood", hood_s, i)); i += 1
    segs.append(card("close", close_s, i)); i += 1
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    vonly = BUILD / "video_only.mp4"
    ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vonly)])
    print(f"video-only: {dur(vonly):.1f}s")

    # ---------------------------------------------------------------- audio mix
    inputs: list[str] = []
    chains: list[str] = []
    n = 0
    def add(path: Path, at_s: float, gain_db: float, extra: str = "", pan: float | None = None, tempo: float = 1.0) -> None:
        nonlocal n
        inputs.extend(["-i", str(path)])
        f = f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo"
        if tempo != 1.0:
            f += f",atempo={tempo:.3f}"
        if extra:
            f += "," + extra
        if pan is not None:   # 0 = left … 1 = right
            l, r = (1.0 - pan), pan
            f += f",pan=stereo|c0={l:.2f}*c0+{l:.2f}*c1|c1={r:.2f}*c0+{r:.2f}*c1"
        f += f",volume={gain_db:+.1f}dB,adelay={int(at_s * 1000)}|{int(at_s * 1000)}[a{n}]"
        chains.append(f)
        n += 1
    # radio clips: at the cue time, through the map; sped segments → atempo
    for cue in tl["audio_cues"]:
        t = cue["t"]; lid = cue["line_id"]
        add(RADIO / f"{lid}.wav", tm(t), -2.0, pan=0.35 if cue["channel"] != "PTT" else 0.6, tempo=tm.speed_at(t))
    # earpiece lines (right side, phone-ish)
    for t, unit, key, _ in EAR:
        if key in voices:
            add(Path(voices[key]["file"]), tm(t), -3.0, pan=0.72 if unit == "kim" else 0.9, tempo=tm.speed_at(t))
    # narration
    if not args.no_vo:
        vo_at = {"vo_01": (0.4, hook_s + TITLE_S - 1.0), "vo_02": (hook_s + 0.3, TITLE_S + (tm(34.0) - run_v0) - 1.0),
                 "vo_03": (tm(34.0) + 0.5, tm(56.0) - tm(34.0) - 1.0), "vo_04": (tm(56.0) + 0.5, tm(78.0) - tm(56.0) - 1.0),
                 "vo_05": (tm(78.0) + 0.3, tm(126.0) - tm(78.0) - 1.0), "vo_06": (tm(126.0) + 0.3, tm.end - tm(126.0) - 0.5),
                 "vo_07": (tm.end + 0.6, hood_s - 1.0), "vo_08": (tm.end + hood_s + 0.4, close_s - 0.8)}
        for k, (at, slot) in vo_at.items():
            if k in voices:
                tempo = fit(k, slot)
                print(f"  {k}: {vo_len(k):.1f}s in a {slot:.1f}s slot → tempo ×{tempo:.2f}")
                add(Path(voices[k]["file"]), at, 0.0, tempo=tempo)
    mix = BUILD / "mix.wav"
    fc = ";".join(chains) + ";" + "".join(f"[a{k}]" for k in range(n)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,apad,alimiter=limit=0.95[out]"
    (BUILD / "mix_filter.txt").write_text(fc, encoding="utf-8")
    ff([*inputs, "-filter_complex_script", str(BUILD / "mix_filter.txt"), "-map", "[out]", "-t", f"{total:.3f}",
        "-ar", "48000", "-ac", "2", str(mix)])
    print(f"mix: {dur(mix):.1f}s from {n} sources")

    # ---------------------------------------------------------------- subtitles (ASS)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Radio,Segoe UI,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,3,2,0,1,350,790,215,1
Style: Ear,Segoe UI,32,&H0030B6F5,&H0030B6F5,&H00000000,&H78000000,0,0,0,0,100,100,0,0,3,2,0,3,1180,40,34,1
Style: Note,Segoe UI,28,&H00D4D4D8,&H00D4D4D8,&H00000000,&H78000000,0,0,0,0,100,100,0,0,3,2,0,2,790,780,236,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev: list[str] = []
    def line(style: str, a: float, b: float, text: str) -> None:
        ev.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{esc(text)}")
    for tx in tl["transmissions"]:
        if tx["t_keyup"] is None:
            continue
        a, b = tm(tx["t_keyup"]), tm(tx["t_end"] or tx["t_keyup"] + 6)
        tag = CHANNEL_TAG.get(tx["channel"], tx["channel"])
        line("Radio", a, max(b, a + 2.0), f"[{tag}] {text_en.get(tx['line'], tx['text'])}")
    for t, unit, key, sub in EAR:
        a = tm(t); b = a + max(3.5, (float(voices[key]["seconds"]) if key in voices else 3.5) / tm.speed_at(t) + 0.6)
        line("Ear", a, b, sub)
    for t, sub in HOLD_SUBS:
        line("Ear", tm(t) + 0.2, tm(t) + 4.5, sub)
    # draft notes (top-left): sped-up stretches are labelled so nobody mistakes them for real-time latency
    for a, b, s in SEGMENTS:
        if s != 1.0:
            line("Note", tm(a), tm(b), f"replay ×{s:g}")
    line("Note", tm(78.0), tm(93.5), "Kim's MAYDAY lands on TAC while the IC is talking on CMD")
    subs = BUILD / "subs.ass"
    subs.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- final
    subs_arg = subs.as_posix().replace(":", "\\:")
    ff(["-i", str(vonly), "-i", str(mix), "-vf", f"ass='{subs_arg}'", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    print(f"done → {out} ({dur(out):.1f}s)")


if __name__ == "__main__":
    main()
