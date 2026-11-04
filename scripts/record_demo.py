"""Record /demo while a REPLAY of a recorded run plays: Playwright Chromium, 1920x1080, dark scheme, WebM video.

Usage: uv run python scripts/record_demo.py [--run best.jsonl] [--out video/build/demo.webm] [--web http://localhost:5173]
       [--api http://localhost:8000] [--extra 4]
The web dev server (5173) and the API (8000) must be running. The video has no audio track; the build script mixes
the radio clips and voices from the run timeline.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="best.jsonl")
    ap.add_argument("--out", default="video/build/demo.webm")
    ap.add_argument("--web", default="http://localhost:5173")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--extra", type=float, default=4.0, help="seconds to keep recording after running=false")
    ap.add_argument("--lead", type=float, default=2.0, help="seconds of idle page before the run starts")
    args = ap.parse_args()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "_pw_video"
    shutil.rmtree(tmp, ignore_errors=True)
    api = httpx.Client(base_url=args.api, timeout=30)
    api.post("/api/scenario/stop")
    api.post("/api/scenario/reset")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                                  color_scheme="dark", record_video_dir=str(tmp),
                                  record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.goto(f"{args.web}/demo", wait_until="networkidle")
        # page.wait_for_timeout, not time.sleep: the sync driver only consumes screencast frames while it is pumped,
        # and a blocking sleep left a 4.8 s video the first time
        page.wait_for_timeout(args.lead * 1000)
        t_start = time.perf_counter()
        r = api.post("/api/scenario/start", json={"mode": "REPLAY", "scenario": "hanbit", "lang": "ko",
                                                  "audio": "radio", "run": args.run})
        r.raise_for_status()
        print(f"REPLAY started ({args.run}); run t=0 at video {args.lead:.1f}s (+page lead)", flush=True)
        while True:
            st = api.get("/api/state").json()
            if not st.get("running"):
                break
            page.wait_for_timeout(1000)
        t_end = time.perf_counter() - t_start
        print(f"running=false after {t_end:.1f}s; recording {args.extra:.0f}s more", flush=True)
        page.wait_for_timeout(args.extra * 1000)
        video = page.video
        ctx.close()
        browser.close()
        src = Path(video.path())
        shutil.move(str(src), str(out))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"saved {out} ; run started at ~{args.lead:.1f}s into the video", flush=True)
    (out.parent / "demo_timing.txt").write_text(f"lead_s={args.lead}\nrun_wall_s={t_end:.3f}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
