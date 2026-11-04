"""Post-triage verification: evidence span must be verbatim; snap raw unit / zone strings to roster / zones.

Other modules import load_roster() / load_zones() from here.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache

from rapidfuzz import fuzz

from server.config import ROOT
from server.gate import normalize_ko
from server.models import Triage, Unit, Zone

_KEEP = re.compile(r"[^0-9a-z가-힣]+")


def norm_key(text: str | None) -> str:
    """NFKC, lowercase, Hangul numerals → digits, drop everything that is not Hangul/alnum (spaces, …, commas)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).lower()
    t = normalize_ko(t, strip_spaces=False)
    return _KEEP.sub("", t)


@lru_cache(maxsize=1)
def _roster_raw() -> list[dict]:
    return json.loads((ROOT / "data" / "roster.json").read_text(encoding="utf-8"))["units"]


@lru_cache(maxsize=1)
def _zones_raw() -> list[dict]:
    return json.loads((ROOT / "data" / "zones.json").read_text(encoding="utf-8"))["zones"]


def load_roster() -> dict[str, Unit]:
    """Fresh Unit objects every call (callers may mutate them)."""
    return {u["id"]: Unit.model_validate(u) for u in _roster_raw()}


def load_zones() -> dict[str, Zone]:
    return {z["id"]: Zone.model_validate(z) for z in _zones_raw()}


# ----------------------------------------------------------------------------- evidence
def verify(triage: Triage, text: str) -> tuple[bool, Triage]:
    """evidence_span must be a normalised substring of text; else blank it and flag asr_uncertain."""
    span = norm_key(triage.evidence_span)
    if span and span in norm_key(text):
        return True, triage
    t2 = triage.model_copy(deep=True)
    t2.evidence_span = ""
    t2.asr_uncertain = True
    t2.uncertain_reason = "evidence not verbatim"
    return False, t2


# ----------------------------------------------------------------------------- unit snap
FUZZ_MIN = 80
FUZZ_MIN_LEN = 4


def snap_unit(raw: str | None, lang: str = "ko", roster: dict[str, Unit] | None = None) -> str | None:
    """Snap a raw speaker self-ID (triage.speaker_unit, never the whole transcript) to a Unit.id."""
    key = norm_key(raw)
    if not key:
        return None
    units = [u for u in (roster or load_roster()).values() if u.lang == lang] or list((roster or load_roster()).values())
    # 1) longest alias that is a substring of the raw (or raw ⊂ alias for long raws)
    best: tuple[int, str] | None = None
    for u in units:
        for a in [u.callsign, *(u.aliases or []), u.name or ""]:
            ak = norm_key(a)
            if not ak:
                continue
            if ak in key or (len(key) >= FUZZ_MIN_LEN and key in ak):
                score = len(ak)
                if best is None or score > best[0]:
                    best = (score, u.id)
    if best:
        return best[1]
    # 2) fuzzy
    if len(key) < FUZZ_MIN_LEN:
        return None
    best_f: tuple[float, str] | None = None
    for u in units:
        for a in [u.callsign, *(u.aliases or [])]:
            ak = norm_key(a)
            if len(ak) < FUZZ_MIN_LEN:
                continue
            s = max(fuzz.token_set_ratio(key, ak), fuzz.partial_ratio(key, ak) if len(ak) <= len(key) else 0)
            if s >= FUZZ_MIN and (best_f is None or s > best_f[0]):
                best_f = (s, u.id)
    return best_f[1] if best_f else None


# ----------------------------------------------------------------------------- zone snap
def snap_zone(raw_hints: list[str | None] | str | None, floor: int | None = None, lang: str = "ko",
              zones: dict[str, Zone] | None = None) -> str | None:
    """Longest normalised alias contained in any hint wins (deepest match); floor filters when given.
    All hints ([zone_hint, raw, where_raw]) are searched jointly; the longest alias across them wins."""
    if isinstance(raw_hints, str) or raw_hints is None:
        raw_hints = [raw_hints]
    zs = list((zones or load_zones()).values())
    best: tuple[int, int, str] | None = None
    for hint in raw_hints:
        key = norm_key(hint)
        if not key:
            continue
        for z in zs:
            if floor is not None and z.floor is not None and z.floor != floor:
                continue
            for a in [z.label_ko, z.label_en, *(z.aliases or [])]:
                ak = norm_key(a)
                if ak and ak in key:
                    depth = 1 if z.parent else 0
                    cand = (len(ak), depth, z.id)
                    if best is None or cand[:2] > best[:2]:
                        best = cand
    if best:
        return best[2]
    # floor-only fallback: the floor's top-level zone if exactly one
    if floor is not None:
        tops = [z.id for z in zs if z.floor == floor and not z.parent]
        if len(tops) == 1:
            return tops[0]
    return None


def snap_event(triage: Triage, text: str, lang: str = "ko") -> tuple[bool, Triage, str | None, str | None]:
    """Convenience: (evidence_verified, triage', unit_id, zone_id)."""
    ok, t2 = verify(triage, text)
    unit = snap_unit(t2.speaker_unit, lang)
    hints = [t2.location.zone_hint, t2.location.raw]
    if t2.distress:
        hints.append(t2.distress.where_raw)
    if t2.victims:
        hints.append(t2.victims.where_raw)
    zone = snap_zone(hints, t2.location.floor, lang)
    return ok, t2, unit, zone
