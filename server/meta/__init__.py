"""Meta Model API clients (muse-spark-1.3, muse-voice-transcribe-1.0)."""


class MetaAPIError(RuntimeError):
    """Any failure talking to api.meta.ai (HTTP status, handshake, parse)."""


class NoAPIKey(MetaAPIError):
    """MODEL_API_KEY missing: only REPLAY mode (cache) can work."""
