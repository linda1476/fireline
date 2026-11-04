"""Thin clients for the three Meta Model API surfaces Fireline uses.

- spark: Muse Spark 1.3 chat completions with JSON-schema structured output (+ tool calling)
- asr:   Muse Voice Transcribe 1.0 — file transcription and realtime WebSocket streaming
- sam:   SAM 3.1 — text-prompted detection on helmet-cam frames

All clients honour ``get_settings().mock``: in mock mode they raise ``MockMode`` so the
calling module can fall back to its own deterministic stand-in. Modules must never
call the network when ``settings.mock`` is True.
"""


class MockMode(RuntimeError):
    """Raised by a Meta client when settings.mock is True."""


class MetaAPIError(RuntimeError):
    """Raised when the Meta Model API returns an unusable response."""
