"""IC autopilot for a verification LIVE run: start the scenario, ack the first MAYDAY card as soon as it appears,
approve RIT_DEPLOY and RADIO_SILENCE when proposed (never CONFIRM_STRATEGY), wait for the run to end, then run
scripts/check_run.py on the recorded run file. Watch it on http://localhost:5173/demo while it runs.

Usage: uv run python scripts/drive_live.py [--base http://localhost:8000] [--audio radio] [--ack-delay 3] [--no-start]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--audio", default="radio")
    ap.add_argument("--ack-delay", type=float, default=3.0, help="seconds after the MAYDAY card before the IC acks")
    ap.add_argument("--no-start", action="store_true", help="attach to a run already started from the launcher")
    args = ap.parse_args()
    c = httpx.Client(base_url=args.base, timeout=30)
    if not args.no_start:
        r = c.post("/api/scenario/start", json={"mode": "LIVE", "scenario": "hanbit", "lang": "ko", "audio": args.audio})
        r.raise_for_status()
        print("started:", {k: r.json().get(k) for k in ("mode", "running", "run_file", "file")})
    acked: set[str] = set()
    decided: set[str] = set()
    mayday_seen_at: float | None = None
    t_end = None
    while True:
        st = c.get("/api/state").json()
        t = st.get("t", 0.0)
        for card in st.get("cards", []):
            if card["kind"] == "MAYDAY" and card["state"] in ("open", "escalated") and card["id"] not in acked:
                if mayday_seen_at is None:
                    mayday_seen_at = time.time()
                    print(f"t={t:6.1f} MAYDAY card {card['id']} seen; ack in {args.ack_delay:.0f} s")
                if time.time() - mayday_seen_at >= args.ack_delay:
                    c.post(f"/api/cards/{card['id']}/ack").raise_for_status()
                    acked.add(card["id"])
                    print(f"t={t:6.1f} acked {card['id']}")
        for p in st.get("proposals", []):
            if p["state"] == "pending" and p["kind"] in ("RIT_DEPLOY", "RADIO_SILENCE") and p["id"] not in decided:
                c.post(f"/api/proposals/{p['id']}/approve").raise_for_status()
                decided.add(p["id"])
                print(f"t={t:6.1f} approved {p['id']} {p['kind']} ({p.get('source')}): {p['text'][:50]}")
        if not st.get("running"):
            if t_end is None:
                t_end = time.time()
                print(f"t={t:6.1f} running=false; waiting 6 s for in-flight triage")
            elif time.time() - t_end > 6:
                break
        time.sleep(1.0)
    runs = c.get("/api/runs").json()
    files = runs if isinstance(runs, list) else runs.get("runs", [])
    latest = None
    for f in files:
        name = f.get("file") if isinstance(f, dict) else f
        if name and name.startswith("run_") and (latest is None or name > latest):
            latest = name
    print("run file:", latest)
    if latest:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "check_run.py"), str(ROOT / "data" / "cache" / latest)])


if __name__ == "__main__":
    main()
