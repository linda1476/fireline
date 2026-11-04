"""Process-wide settings. Loads MODEL_API_KEY from D:\\meta\\.env (never log it)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    api_key: str = os.environ.get("MODEL_API_KEY", "")
    base_url: str = "https://api.meta.ai/v1"
    spark_model: str = "muse-spark-1.3"
    asr_model: str = "muse-voice-transcribe-1.0"
    asr_ws_url: str = "wss://api.meta.ai/v1/asr/realtime"
    asr_transcribe_url: str = "https://api.meta.ai/v1/asr/transcribe"
    root: Path = ROOT
    data_dir: Path = ROOT / "data"
    audio_dir: Path = ROOT / "data" / "audio"
    cache_path: Path = ROOT / "data" / "cache" / "meta_cache.jsonl"
    eval_dir: Path = ROOT / "eval"
    # smoke_b1.md: "minimal" accepted, 3.2–7.2 s vs 7.6–17.5 s at "low", same tags. Triage uses minimal.
    reasoning_effort: str = os.environ.get("EARSHOT_REASONING_EFFORT", "minimal")
    # Agent loop keeps "low" (needs the reasoning summary + multi-tool planning).
    agent_reasoning_effort: str = os.environ.get("EARSHOT_AGENT_REASONING_EFFORT", "low")
    # Round 1 of a wake (the one that must beat agent_timeout_s) runs at "minimal": measured 2026-11-04 on the MAYDAY
    # demo wake, minimal 5.2–6.4 s vs low 8.6–12.1 s to the first tool call, same tool calls. Later rounds use
    # agent_reasoning_effort.
    agent_round1_reasoning_effort: str = os.environ.get("EARSHOT_AGENT_ROUND1_EFFORT", "minimal")
    # Realtime ENDPOINTING splits a transmission at pauses ≥ ~0.86 s (smoke_b1.md): merge turns closer than this.
    turn_merge_gap_s: float = 1.5
    # Agent wake timeout before router_fallback takes over (seconds).
    agent_timeout_s: float = float(os.environ.get("EARSHOT_AGENT_TIMEOUT", "12"))
    # Demo-timescale rule thresholds (seconds); labelled "demo timescale" on screen.
    r1_ack_s: float = 10.0
    r1_level2_s: float = 20.0
    r2_silent_s: float = 60.0
    r2_ping_gap_s: float = 8.0
    r2_pings: int = 3
    r4_assign_s: float = 30.0
    r5_exit_s: float = 60.0
    r6_ask_s: float = 6.0        # MAYDAY card missing SOP 109 fields, no ask sent -> rule asks (R6)
    r7_rit_s: float = 15.0       # MAYDAY card with known where, no RIT_DEPLOY proposal -> rule proposes (R7)
    max_open_cards: int = 5
    dedupe_window_s: float = 30.0

    @property
    def mock(self) -> bool:
        return not self.api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _is_hangul(term: str) -> bool:
    return any("가" <= ch <= "힣" for ch in term)


ASR_KEYWORD_MAX_CHARS = 30   # the ASR API rejects (400) any keyword longer than this
log = logging.getLogger("earshot.config")


def filter_keywords(terms: list[str], max_chars: int = ASR_KEYWORD_MAX_CHARS) -> list[str]:
    """Dedupe (order kept) and drop terms longer than max_chars, logging each dropped term."""
    out: list[str] = []
    for term in terms:
        if len(term) > max_chars:
            log.warning("ASR keyword dropped (%d chars > %d): %r", len(term), max_chars, term)
            continue
        if term not in out:
            out.append(term)
    return out


@lru_cache(maxsize=4)
def load_keywords(lang: str = "ko") -> list[str]:
    """Keyword-biasing list per language (data/keywords.json): SOP/LUNAR terms + roster + zones.
    ko: Korean SOP terms + Korean roster/zone terms (~65). en: English terms + English roster/zone terms."""
    data = json.loads((ROOT / "data" / "keywords.json").read_text(encoding="utf-8"))
    sop = data.get("sop_terms_ko" if lang == "ko" else "sop_terms_en", [])
    extra = [t for t in data.get("roster_terms", []) + data.get("zone_terms", []) if _is_hangul(t) == (lang == "ko")]
    return filter_keywords(list(sop) + extra)
