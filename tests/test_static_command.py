"""Static checks for the command dashboard files (src/fireline/server/static/command.*).

The page is vanilla HTML/CSS/JS served by the integration owner's server; these tests
only assert that the files exist, reference each other, and code against the exact
HTTP + WebSocket endpoints in docs/CONTRACT.md.
"""

from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "fireline" / "server" / "static"
HTML = STATIC / "command.html"
CSS = STATIC / "command.css"
JS = STATIC / "command.js"

ENDPOINTS = [
    "/api/state",
    "/api/health",
    "/api/ack",
    "/api/assignment",
    "/api/report",
    "/api/demo/run",
    "/api/demo/reset",
    "/api/mic/start",
    "/api/mic/stop",
    "/ws",
]

WS_TYPES = ["state", "delta", "transcript", "briefing", "assignment", "event", "error"]


@pytest.mark.parametrize("path", [HTML, CSS, JS])
def test_files_exist(path: Path):
    assert path.is_file(), f"missing {path}"
    assert path.stat().st_size > 0


def test_html_references_css_and_js_relatively():
    html = HTML.read_text(encoding="utf-8")
    assert 'href="command.css"' in html
    assert 'src="command.js"' in html
    assert "<!doctype html>" in html.lower()


def test_html_has_required_controls():
    html = HTML.read_text(encoding="utf-8")
    for element_id in [
        "btn-demo-text", "btn-demo-audio", "btn-reset", "btn-mic", "mic-speaker",
        "queue", "map", "floor-tabs", "ticker", "responders", "briefings",
        "assignments", "timeline", "inject-text", "inject-speaker",
        "badge-spark", "badge-asr", "badge-sam", "clock", "incident",
    ]:
        assert f'id="{element_id}"' in html, f"missing #{element_id}"


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_js_references_contract_endpoint(endpoint: str):
    js = JS.read_text(encoding="utf-8")
    assert f"'{endpoint}'" in js, f"command.js does not call {endpoint}"


def test_js_uses_relative_websocket_url():
    js = JS.read_text(encoding="utf-8")
    assert "location.host" in js
    assert "wss" in js and "'/ws'" in js


@pytest.mark.parametrize("ws_type", WS_TYPES)
def test_js_handles_ws_message_type(ws_type: str):
    js = JS.read_text(encoding="utf-8")
    assert f"case '{ws_type}':" in js


def test_js_has_mock_harness_and_contract_bodies():
    js = JS.read_text(encoding="utf-8")
    assert "mock=1" in js
    assert "report_id" in js            # POST /api/ack {report_id}
    assert "assignment_id" in js        # POST /api/assignment {assignment_id, accepted}
    assert "mode: 'text'" in js and "mode: 'audio'" in js
    assert "responder_id" in js


def test_no_external_resources():
    """Demo may be shown offline: no CDN scripts/styles/fonts."""
    html = HTML.read_text(encoding="utf-8")
    stripped = html.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in stripped and "https://" not in stripped
    css = CSS.read_text(encoding="utf-8")
    assert "@import" not in css and "url(" not in css
