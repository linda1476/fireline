"""Render video/cards/*.html to PNG with Playwright Chromium (1920x1080; viral_end is 1080x1920).

Usage: uv run python scripts/render_cards.py [names...]   (default: every .html in video/cards)
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "video" / "cards"


def main() -> None:
    names = sys.argv[1:] or sorted(p.stem for p in CARDS.glob("*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name in names:
            w, h = (1080, 1920) if name == "viral_end" else (1920, 1080)
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            page.goto((CARDS / f"{name}.html").resolve().as_uri())
            page.wait_for_timeout(300)
            page.screenshot(path=str(CARDS / f"{name}.png"), full_page=False)
            page.close()
            print(f"{name}.png {w}x{h}")
        browser.close()


if __name__ == "__main__":
    main()
