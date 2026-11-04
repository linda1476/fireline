"""Per-transmission triage with muse-spark-1.3 (strict JSON) + the synthetic crew-button path.

Few-shots below are NOT taken from data/*.yaml (tests/test_triage_schema.py enforces it).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from server.models import CREW_BUTTON_KO, TRIAGE_SCHEMA, Triage, Unit

CREW_BUTTON_EN = {"EVACUATE": "Mayday button", "VICTIM_HERE": "Victim here", "SEARCH_DONE": "Search complete",
                  "NEED_HELP": "Need help"}

SYSTEM = """You are the radio triage extractor for a Korean fire incident command post (Earshot).
Input: ONE final radio transmission (ASR transcript; may contain recognition errors, missing punctuation,
stuttered duplicates like "긴급탈출탈출", Hangul numerals like "이층" = 2층). Output: ONE JSON object under the schema.

TAG (SOP 107 priority order, 대원안전 > 구조대상자 > 주요요소 > 전략; when several apply pick the highest):
  MAYDAY       a firefighter is in distress: trapped / lost / cannot find the exit / fell / injured / missing /
               out of air / man-down, WITH OR WITHOUT the codeword (긴급탈출, 맨다운, mayday). ALSO: any transmission that
               is part of an ongoing 긴급탈출/mayday — the declaration, the IC's broadcast about it, the IC's instructions
               to the trapped member, the acknowledgement — is MAYDAY.
  DANGER       hazard that threatens crews: collapse risk, flammables/explosives, flashover/backdraft signs,
               fire spread toward crews, withdrawal / evacuation orders, defensive switch.
  VICTIM_FOUND a civilian 구조대상자 found / located / being extracted.
  HELP_NEEDED  a crew (not in distress) requests resources: air cylinders, ladder, hose, more personnel.
               Command (지휘대장/IC) asking dispatch (상황실) for more apparatus or a higher alarm is ROUTINE, not HELP_NEEDED.
  ROUTINE      everything else: arrival, command declaration, entering, progress "이상 없음", staging, dispatch requests.
  If unsure between DANGER and ROUTINE choose DANGER with confidence < 0.6.

FIELDS (SOP 109 for MAYDAY: who / what / where / needs / air):
  speaker_unit   the speaker's self-identification verbatim ("여기 X" / "this is X"), else null.
  addressee      who is called ("지휘대장", "Command"), else null.
  location.floor integer only if a floor is stated (2층, 이층, second floor). NEVER invent a floor; else null.
                 옥상/roof → floor null and zone_hint "옥상" (or "roof").
  location.zone_hint  the sub-floor place words verbatim (e.g. "서쪽 계단실 옆", "기계실 앞", "후면 주차장"), else null.
  location.raw   the whole location phrase verbatim, else null.
  distress       object only for MAYDAY (else null). who = distressed member as said; what = TRAPPED | FALL | INJURY |
                 MISSING | COLLAPSE | GAS | LOW_AIR | LOST | OTHER | UNKNOWN (cannot find the way out = LOST or TRAPPED);
                 where_raw verbatim; needs and air are VERBATIM substrings of the transcript or null — never a
                 paraphrase, never an inference ("구조 요청", "rescue", "low" are wrong unless literally said).
  victims        object only when civilians are mentioned (else null): count as said, where_raw verbatim,
                 state REPORTED | FOUND | EXTRACTING | UNKNOWN. Location and status as reported only; no medical content.
  hazard_terms   hazard words verbatim from the transcript (e.g. "가스 냄새", "바닥 꺼짐"), [] if none.
  status_change  ENTERING | EXITING | LOW_AIR | TRAPPED | OK ("이상 없음") | NONE.
  strategy_declared OFFENSIVE (공격전략) | DEFENSIVE (방어전략, 전 대원 철수) | NONE.
  needs_ack      true for MAYDAY, DANGER, VICTIM_FOUND, HELP_NEEDED and for orders that need a reply.
  confidence     0..1 your confidence in the tag.
  asr_uncertain  true if the transcript looks garbled where it matters; uncertain_reason says why, else null.
  evidence_span  the shortest span that justifies the tag, copied VERBATIM (character for character) from the transcript.
  crew_brief     at most 2 short sentences, SAME LANGUAGE as the transcript, what a crew member nearby must know.
Return JSON only."""

# 6 few-shots: 3 ko + 3 en, 2 codeword-free distress lines. Wording deliberately absent from data/*.yaml.
FEW_SHOTS: list[tuple[str, dict[str, Any]]] = [
    ("가람구조대 최민 지휘대장 나갈 길이 안 보인다 연기 꽉 찼다 3층 기계실 근처 혼자 남았다", {
        "tag": "MAYDAY", "speaker_unit": "가람구조대 최민", "addressee": "지휘대장",
        "location": {"floor": 3, "zone_hint": "기계실 근처", "raw": "3층 기계실 근처"},
        "distress": {"who": "가람구조대 최민", "what": "LOST", "where_raw": "3층 기계실 근처", "needs": None, "air": None},
        "victims": None, "hazard_terms": ["연기 꽉 찼다"], "status_change": "TRAPPED", "strategy_declared": "NONE",
        "needs_ack": True, "confidence": 0.9, "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "나갈 길이 안 보인다 연기 꽉 찼다",
        "crew_brief": "가람구조대 최민이 3층 기계실 근처에서 퇴로를 잃음. 연기 충만."}),
    ("지휘대장 여기 솔빛센터 팀장 후면 외벽 균열 커지고 있음 지붕 트러스 내려앉는 중 내부 대원 확인 바람", {
        "tag": "DANGER", "speaker_unit": "솔빛센터 팀장", "addressee": "지휘대장",
        "location": {"floor": None, "zone_hint": "후면 외벽", "raw": "후면 외벽"},
        "distress": None, "victims": None, "hazard_terms": ["외벽 균열", "지붕 트러스 내려앉는 중"],
        "status_change": "NONE", "strategy_declared": "NONE", "needs_ack": True, "confidence": 0.9,
        "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "후면 외벽 균열 커지고 있음 지붕 트러스 내려앉는 중",
        "crew_brief": "후면 외벽 균열, 지붕 트러스 처짐. 붕괴 위험."}),
    ("지휘대장 여기 솔빛구조대 옥상 도착 배연구 개방 완료", {
        "tag": "ROUTINE", "speaker_unit": "솔빛구조대", "addressee": "지휘대장",
        "location": {"floor": None, "zone_hint": "옥상", "raw": "옥상"},
        "distress": None, "victims": None, "hazard_terms": [], "status_change": "NONE", "strategy_declared": "NONE",
        "needs_ack": False, "confidence": 0.85, "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "옥상 도착 배연구 개방 완료", "crew_brief": "솔빛구조대 옥상 배연구 개방 완료."}),
    ("Command, Ladder 9, we're stuck, can't get back to the stairs, fourth floor rear hallway, two of us", {
        "tag": "MAYDAY", "speaker_unit": "Ladder 9", "addressee": "Command",
        "location": {"floor": 4, "zone_hint": "rear hallway", "raw": "fourth floor rear hallway"},
        "distress": {"who": "Ladder 9, two of us", "what": "TRAPPED", "where_raw": "fourth floor rear hallway",
                     "needs": None, "air": None},
        "victims": None, "hazard_terms": [], "status_change": "TRAPPED", "strategy_declared": "NONE",
        "needs_ack": True, "confidence": 0.9, "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "we're stuck, can't get back to the stairs",
        "crew_brief": "Ladder 9 (two members) cannot get back to the stairs, 4th floor rear hallway."}),
    ("Command, Rescue 4, we have a child located downstairs by the washing machines, moving her out now", {
        "tag": "VICTIM_FOUND", "speaker_unit": "Rescue 4", "addressee": "Command",
        "location": {"floor": None, "zone_hint": "downstairs by the washing machines", "raw": "downstairs by the washing machines"},
        "distress": None, "victims": {"count": 1, "where_raw": "downstairs by the washing machines", "state": "EXTRACTING"},
        "hazard_terms": [], "status_change": "NONE", "strategy_declared": "NONE", "needs_ack": True,
        "confidence": 0.92, "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "we have a child located downstairs by the washing machines, moving her out now",
        "crew_brief": "Rescue 4 is bringing one child out from downstairs by the washing machines."}),
    ("Command from Engine 40, send us another hose line and a second crew to the west side", {
        "tag": "HELP_NEEDED", "speaker_unit": "Engine 40", "addressee": "Command",
        "location": {"floor": None, "zone_hint": "west side", "raw": "west side"},
        "distress": None, "victims": None, "hazard_terms": [], "status_change": "NONE", "strategy_declared": "NONE",
        "needs_ack": True, "confidence": 0.85, "asr_uncertain": False, "uncertain_reason": None,
        "evidence_span": "send us another hose line and a second crew",
        "crew_brief": "Engine 40 needs another hose line and a second crew on the west side."}),
]


def _user(text: str, lang: str, channel: str) -> str:
    return f"channel: {channel}\nlang: {lang}\ntranscript: {text}"


def build_system() -> str:
    parts = [SYSTEM, "\nEXAMPLES (input → output):"]
    for i, (txt, out) in enumerate(FEW_SHOTS, 1):
        lang = "ko" if any("가" <= c <= "힣" for c in txt) else "en"
        parts.append(f"\n[{i}] {_user(txt, lang, 'TAC')}\n→ {json.dumps(out, ensure_ascii=False)}")
    return "\n".join(parts)


SYSTEM_PROMPT = build_system()
_client = None


def _spark():
    global _client
    if _client is None:
        from server.meta.spark import SparkClient

        _client = SparkClient()
    return _client


def _memo_payload(text: str, lang: str, channel: str) -> dict[str, Any]:
    from server.config import get_settings

    st = get_settings()
    return {"text": text, "lang": lang, "channel": channel, "model": st.spark_model,
            "reasoning_effort": st.reasoning_effort,
            "prompt_sha": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]}


async def triage(text: str, lang: str = "ko", channel: str = "TAC") -> tuple[Triage, int, dict[str, Any]]:
    """(Triage, latency_ms, usage). reasoning_effort / max_tokens come from SparkClient defaults (Settings).

    EARSHOT_MEMO=1 (dev only): input-hash memo via server.cache.memo keyed on text/lang/channel/model/effort/prompt.
    A hit returns the cached Triage with the ms of the ORIGINAL call and usage {"memo": true, ...} so the badge
    is never passed off as a fresh measurement."""
    from server import cache

    if not cache.memo_enabled():
        return await _spark().acomplete_json(SYSTEM_PROMPT, _user(text, lang, channel), Triage, TRIAGE_SCHEMA,
                                             schema_name="radio_event")
    fresh: dict[str, Any] = {}

    async def compute() -> dict[str, Any]:
        tr, ms, usage = await _spark().acomplete_json(SYSTEM_PROMPT, _user(text, lang, channel), Triage,
                                                      TRIAGE_SCHEMA, schema_name="radio_event")
        fresh["hit"] = False
        return {"triage": tr.model_dump(mode="json"), "ms": int(ms), "usage": usage or {}}

    rec = await cache.memo("triage", _memo_payload(text, lang, channel), compute)
    usage = dict(rec.get("usage") or {})
    if fresh.get("hit", True):
        usage["memo"] = True
    return Triage.model_validate(rec["triage"]), int(rec.get("ms", 0)), usage


# ----------------------------------------------------------------------------- synthetic crew buttons
def button_label(kind: str, lang: str = "ko") -> str:
    return CREW_BUTTON_KO[kind] if lang == "ko" else CREW_BUTTON_EN[kind]


def triage_button(unit: Unit | str, kind: str, lang: str = "ko", zone_label: str | None = None,
                  floor: int | None = None) -> Triage:
    """Event-ready Triage for the 4 crew buttons, no Spark call. evidence_span = the button label
    (use button_label(kind, lang) as the Event text so verify() passes)."""
    if isinstance(unit, str):
        from server.verify import load_roster

        unit = load_roster().get(unit) or Unit(id=unit, callsign=unit)
    who = f"{unit.callsign} {unit.name}" if unit.name else unit.callsign
    label = button_label(kind, lang)
    loc = {"floor": floor, "zone_hint": zone_label, "raw": zone_label}
    base: dict[str, Any] = {"speaker_unit": who, "addressee": None, "location": loc, "distress": None,
                            "victims": None, "hazard_terms": [], "status_change": "NONE", "strategy_declared": "NONE",
                            "needs_ack": True, "confidence": 1.0, "asr_uncertain": False, "uncertain_reason": None,
                            "evidence_span": label}
    ko = lang == "ko"
    if kind == "EVACUATE":
        base.update(tag="MAYDAY", distress={"who": who, "what": "OTHER", "where_raw": zone_label, "needs": None,
                                            "air": None},
                    crew_brief=f"{who} 긴급탈출 버튼 발신." if ko else f"{who} pressed the mayday button.")
    elif kind == "VICTIM_HERE":
        base.update(tag="VICTIM_FOUND", victims={"count": None, "where_raw": zone_label, "state": "FOUND"},
                    crew_brief=f"{who} 구조대상자 발견." if ko else f"{who} found a victim.")
    elif kind == "SEARCH_DONE":
        base.update(tag="ROUTINE", status_change="OK", needs_ack=False,
                    crew_brief=f"{who} 검색완료." if ko else f"{who} search complete.")
    elif kind == "NEED_HELP":
        base.update(tag="HELP_NEEDED", crew_brief=f"{who} 지원요청." if ko else f"{who} needs help.")
    else:
        raise ValueError(f"unknown crew button {kind!r}")
    return Triage.model_validate(base)
