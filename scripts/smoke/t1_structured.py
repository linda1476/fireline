"""TEST 1: Spark strict structured output with nullable fields."""
import json, time, copy, sys
from openai import OpenAI
from _common import KEY, BASE, OUT, scrub

client = OpenAI(api_key=KEY, base_url=BASE, timeout=90)
MODEL = "muse-spark-1.3"

def n(t): return {"anyOf": [{"type": t}, {"type": "null"}]}
def obj(props): return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}

DISTRESS = obj({"who": n("string"),
    "what": {"type": "string", "enum": ["TRAPPED","FALL","INJURY","MISSING","COLLAPSE","GAS","LOW_AIR","LOST","OTHER","UNKNOWN"]},
    "where_raw": n("string"), "needs": n("string"), "air": n("string")})
VICTIMS = obj({"count": n("integer"), "where_raw": n("string"),
    "state": {"type": "string", "enum": ["REPORTED","FOUND","EXTRACTING","UNKNOWN"]}})
SCHEMA = obj({
  "tag": {"type": "string", "enum": ["MAYDAY","DANGER","VICTIM_FOUND","HELP_NEEDED","ROUTINE"]},
  "speaker_unit": n("string"), "addressee": n("string"),
  "location": obj({"floor": n("integer"), "zone_hint": n("string"), "raw": n("string")}),
  "distress": {"anyOf": [DISTRESS, {"type": "null"}]},
  "victims": {"anyOf": [VICTIMS, {"type": "null"}]},
  "hazard_terms": {"type": "array", "items": {"type": "string"}},
  "status_change": {"type": "string", "enum": ["ENTERING","EXITING","LOW_AIR","TRAPPED","OK","NONE"]},
  "strategy_declared": {"type": "string", "enum": ["OFFENSIVE","DEFENSIVE","NONE"]},
  "needs_ack": {"type": "boolean"}, "confidence": {"type": "number"},
  "asr_uncertain": {"type": "boolean"}, "uncertain_reason": n("string"),
  "evidence_span": {"type": "string"}, "crew_brief": n("string"),
})

SYSTEM = """You triage fireground radio transmissions into one structured event.
Priority: MAYDAY > DANGER > VICTIM_FOUND > HELP_NEEDED > ROUTINE. Pick the highest that applies.
긴급탈출 / 메이데이 / 맨다운 / Mayday are distress codewords => MAYDAY. A firefighter in distress without a codeword (e.g. "출구를 못 찾겠다", trapped, lost, out of air) is still MAYDAY.
Never invent a floor: location.floor is null unless a floor is stated. Use null for any unknown field. distress is null unless a firefighter is in distress; victims is null unless civilians/victims are mentioned.
evidence_span must be a verbatim substring of the transcript.
crew_brief: at most 2 sentences, in the same language as the transcript."""

INPUTS = {
 "a": "지휘대장, 여기 누리119안전센터 소방교 박준. 1층 서측 진입, 인명검색 시작.",
 "b": "지휘대장… 한빛구조대 김하늘… 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽. 공기 얼마 안 남았다.",
 "c": "Command, Truck 5, victim found, second floor Bravo-Charlie corner bedroom, unconscious adult, removing via interior stairs.",
}

def call(text, schema=SCHEMA, strict=True, effort="low", label=""):
    rf = {"type": "json_schema", "json_schema": {"name": "radio_event", "schema": schema}}
    if strict is not None: rf["json_schema"]["strict"] = strict
    kw = dict(model=MODEL, messages=[{"role": "system", "content": SYSTEM},
              {"role": "user", "content": f"Transcript: \"{text}\""}],
              response_format=rf, max_tokens=4000, temperature=0.1)
    if effort: kw["reasoning_effort"] = effort
    t0 = time.perf_counter()
    try:
        r = client.chat.completions.create(**kw)
    except Exception as e:
        dt = time.perf_counter() - t0
        print(f"[{label}] ERROR after {dt:.2f}s: {scrub(repr(e))[:1500]}")
        return {"label": label, "error": scrub(repr(e))[:3000], "latency_s": round(dt, 2)}
    dt = time.perf_counter() - t0
    content = r.choices[0].message.content
    usage = r.usage.model_dump() if r.usage else None
    try: parsed = json.loads(content); perr = None
    except Exception as e: parsed = None; perr = repr(e)
    ev_ok = parsed is not None and parsed.get("evidence_span", "") in text
    print(f"[{label}] {dt:.2f}s finish={r.choices[0].finish_reason} usage={usage}")
    print(f"  content: {content}")
    if perr: print("  PARSE ERR", perr)
    print(f"  evidence_span verbatim: {ev_ok}")
    return {"label": label, "latency_s": round(dt, 2), "finish": r.choices[0].finish_reason,
            "usage": usage, "content": content, "parsed": parsed, "evidence_verbatim": ev_ok}

if __name__ == "__main__":
  results = []
  for k, t in INPUTS.items():
      results.append(call(t, label=f"{k}/strict/low"))
  results.append(call(INPUTS["b"], effort="minimal", label="b/strict/minimal"))
  # Repeat a and b once more for latency variance
  results.append(call(INPUTS["a"], label="a/strict/low#2"))
  results.append(call(INPUTS["b"], label="b/strict/low#2"))
  if any("error" in r for r in results[:3]):
      results.append(call(INPUTS["b"], strict=None, label="b/nostrict/low"))
  json.dump(results, open(OUT / "t1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
