"""Runtime settings. Reads D:\\meta\\.env (or the repo root .env) via python-dotenv.

Environment variables
---------------------
MODEL_API_KEY        Meta Model API key (https://dev.meta.ai). Required for live mode.
FIRELINE_MOCK=1      Force mock mode even if a key is present (tests, offline dev).
FIRELINE_SPARK_MODEL default muse-spark-1.3
FIRELINE_ASR_MODEL   default muse-voice-transcribe-1.0
FIRELINE_SAM_MODEL   default sam-3.1
FIRELINE_HOST/PORT   server bind (default 0.0.0.0:8000)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = REPO_ROOT / "out"

load_dotenv(REPO_ROOT / ".env", override=False)


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.environ.get("MODEL_API_KEY", "").strip())
    base_url: str = field(default_factory=lambda: os.environ.get("FIRELINE_BASE_URL", "https://api.meta.ai/v1"))
    spark_model: str = field(default_factory=lambda: os.environ.get("FIRELINE_SPARK_MODEL", "muse-spark-1.3"))
    asr_model: str = field(default_factory=lambda: os.environ.get("FIRELINE_ASR_MODEL", "muse-voice-transcribe-1.0"))
    sam_model: str = field(default_factory=lambda: os.environ.get("FIRELINE_SAM_MODEL", "sam-3.1"))
    host: str = field(default_factory=lambda: os.environ.get("FIRELINE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("FIRELINE_PORT", "8000")))
    force_mock: bool = field(default_factory=lambda: os.environ.get("FIRELINE_MOCK", "") in ("1", "true", "yes"))

    @property
    def mock(self) -> bool:
        """True when we must not call the network (no key, or forced)."""
        return self.force_mock or not self.api_key

    @property
    def asr_ws_url(self) -> str:
        return self.base_url.replace("https://", "wss://").replace("http://", "ws://") + "/asr/realtime"

    @property
    def asr_transcribe_url(self) -> str:
        return self.base_url + "/asr/transcribe"


_settings: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    global _settings
    if _settings is None or refresh:
        load_dotenv(REPO_ROOT / ".env", override=True)
        _settings = Settings()
    return _settings
