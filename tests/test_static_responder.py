"""Static checks for the responder clip-on display UI (no server needed)."""

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "fireline" / "server" / "static"
HTML = STATIC / "responder.html"
CSS = STATIC / "responder.css"
JS = STATIC / "responder.js"


def test_files_exist():
    for p in (HTML, CSS, JS):
        assert p.is_file(), f"missing {p}"
        assert p.stat().st_size > 500


def test_js_references_contract_endpoints():
    js = JS.read_text(encoding="utf-8")
    for needle in ("/api/state", "/ws", "/api/touch", "/api/photo", "/samples/"):
        assert needle in js, f"responder.js must reference {needle}"


def test_js_covers_touch_actions_and_ws_messages():
    js = JS.read_text(encoding="utf-8")
    for action in ("mark_victim", "need_help", "victim_out", "im_ok"):
        assert f"'{action}'" in js
    for msg in ("'state'", "'delta'", "'briefing'", "'transcript'"):
        assert msg in js
    assert "speechSynthesis" in js
    assert "image_b64" in js and "responder_id" in js
    assert "mock=1" in js


def test_js_uses_relative_ws_url():
    js = JS.read_text(encoding="utf-8")
    assert "location.host" in js
    assert re.search(r"wss?://", js) is None or "location.host + '/ws'" in js


def test_html_has_no_external_resources():
    html = HTML.read_text(encoding="utf-8")
    assert not re.search(r"(src|href)\s*=\s*[\"']https?://", html), "no CDN / external assets allowed"
    assert "responder.css" in html and "responder.js" in html
    assert 'type="file"' in html and 'capture="environment"' in html


@pytest.mark.parametrize("sample", ["smoky_room_victim", "corridor_clear", "two_victims_404"])
def test_html_lists_sample_frames(sample):
    assert sample in HTML.read_text(encoding="utf-8")


def test_css_defines_theme_and_tap_targets():
    css = CSS.read_text(encoding="utf-8")
    for colour in ("#0b0f14", "#121820", "#e6edf3", "#ff3b3b", "#ffb020", "#4f9cff", "#3ddc84"):
        assert colour in css
    assert "64px" in css
