"""Gate before triage: drop empty / too-short / squelch-only finals. Korean normaliser for codeword matching."""

from __future__ import annotations

import re
import unicodedata

_HNUM = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_COUNTERS = r"(층|미터|명|개)"   # not 대/분: "이 대원" must stay
# Hangul numeral only when directly bound to a counter (avoids 이상/일단/사무실 etc.)
_RE_HNUM = re.compile(r"(?<![가-힣])(십[일이삼사오육칠팔구]?|[일이삼사오육칠팔구]십[일이삼사오육칠팔구]?|[일이삼사오육칠팔구])\s*" + _COUNTERS)
_RE_DUP_TOKEN = re.compile(r"(?<!\S)(\S+)(?:\s+\1)+(?!\S)")
_RE_DUP_SUFFIX = re.compile(r"([가-힣]{2,})\1(?![가-힣])")

CODEWORDS = ("긴급탈출", "맨다운", "mayday", "메이데이")


def _hnum_value(s: str) -> int:
    if s == "십":
        return 10
    if "십" in s:
        a, _, b = s.partition("십")
        return (_HNUM[a] if a else 1) * 10 + (_HNUM[b] if b else 0)
    return _HNUM[s]


def normalize_ko(text: str | None, strip_spaces: bool = False) -> str:
    """Hangul numerals → digits (일층→1층, 삼 미터→3미터), collapse doubled words (긴급탈출탈출→긴급탈출,
    "2층 2층"→"2층"); optionally strip all spaces (codeword matching)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _RE_HNUM.sub(lambda m: f"{_hnum_value(m.group(1))}{m.group(2)}", t)
    t = _RE_DUP_SUFFIX.sub(r"\1", t)
    t = _RE_DUP_TOKEN.sub(r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    if strip_spaces:
        t = t.replace(" ", "")
    return t


def has_codeword(text: str | None) -> bool:
    k = normalize_ko(text, strip_spaces=True).lower()
    return any(c in k for c in CODEWORDS)


def _tokens(text: str) -> list[str]:
    return [w for w in re.split(r"[^0-9A-Za-z가-힣]+", text) if w]


def should_triage(text: str | None) -> bool:
    if not text or not text.strip():
        return False
    if has_codeword(text):
        return True
    norm = normalize_ko(text)
    toks = _tokens(norm)
    if len(toks) < 2:
        return False
    # squelch / stutter: everything is one repeated syllable ("아 아 아", "어어어")
    letters = "".join(toks)
    if len(set(letters)) <= 1:
        return False
    return True
