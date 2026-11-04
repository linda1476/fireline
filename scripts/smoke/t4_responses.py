"""TEST 4: Responses API tool loop + previous_response_id + streaming."""
import json, time
from openai import OpenAI
from _common import KEY, BASE, OUT, scrub

client = OpenAI(api_key=KEY, base_url=BASE, timeout=90)
TOOLS = [{"type": "function", "name": "send_brief",
  "description": "Send a short radio brief to one crew unit.",
  "parameters": {"type": "object", "additionalProperties": False,
     "properties": {"unit_id": {"type": "string"}, "text": {"type": "string"},
                    "priority": {"type": "string", "enum": ["P0", "P1", "P2"]}, "reason": {"type": "string"}},
     "required": ["unit_id", "text", "priority", "reason"]}, "strict": True}]
INPUT = [
 {"role": "system", "content": "You route fireground radio info to crews. Call send_brief for the unit in the affected sector."},
 {"role": "user", "content": "World snapshot: units: kim @ 2F-E (east, 2nd floor), park @ 1F-W (west, 1st floor).\nEvent: DANGER: 3F flammables above 2F-E."},
]
COMMON = dict(model="muse-spark-1.3", tools=TOOLS, tool_choice="auto", reasoning={"effort": "low", "summary": "concise"})

def dump(r):
    out = []
    for it in r.output:
        d = it.model_dump()
        if d.get("type") == "reasoning":
            out.append({"type": "reasoning", "summary": d.get("summary"), "has_content": bool(d.get("content")), "encrypted": bool(d.get("encrypted_content"))})
        else:
            out.append(d)
    return out

R = {}
t0 = time.perf_counter()
try:
    r1 = client.responses.create(input=INPUT, stream=False, **COMMON)
    dt = time.perf_counter() - t0
    R["call1"] = {"latency_s": round(dt, 2), "id": r1.id, "status": r1.status, "output": dump(r1), "usage": r1.usage.model_dump() if r1.usage else None}
    print("CALL1", json.dumps(R["call1"], ensure_ascii=False, indent=1))
except Exception as e:
    R["call1"] = {"error": scrub(repr(e))[:1500]}; print("CALL1 ERR", R["call1"]); r1 = None

if r1:
    fc = [it for it in r1.output if it.type == "function_call"]
    if fc:
        t0 = time.perf_counter()
        try:
            r2 = client.responses.create(previous_response_id=r1.id, stream=False,
                input=[{"type": "function_call_output", "call_id": fc[0].call_id,
                        "output": json.dumps({"ok": False, "error": "rate limit: unit kim briefed 5 s ago"})}], **COMMON)
            dt = time.perf_counter() - t0
            R["call2"] = {"latency_s": round(dt, 2), "id": r2.id, "status": r2.status, "output": dump(r2), "usage": r2.usage.model_dump() if r2.usage else None}
            print("CALL2", json.dumps(R["call2"], ensure_ascii=False, indent=1))
        except Exception as e:
            R["call2"] = {"error": scrub(repr(e))[:1500]}; print("CALL2 ERR", R["call2"])
            # fallback: replay full history without previous_response_id
            t0 = time.perf_counter()
            try:
                hist = INPUT + [it.model_dump(exclude_none=True) for it in r1.output] + [{"type": "function_call_output", "call_id": fc[0].call_id, "output": json.dumps({"ok": False, "error": "rate limit: unit kim briefed 5 s ago"})}]
                r2 = client.responses.create(input=hist, stream=False, **COMMON)
                R["call2_replay"] = {"latency_s": round(time.perf_counter() - t0, 2), "output": dump(r2)}
                print("CALL2_REPLAY", json.dumps(R["call2_replay"], ensure_ascii=False, indent=1))
            except Exception as e2:
                R["call2_replay"] = {"error": scrub(repr(e2))[:1500]}; print("CALL2_REPLAY ERR", R["call2_replay"])

# streaming
t0 = time.perf_counter(); types = {}; first = None
try:
    st = client.responses.create(input=INPUT, stream=True, **COMMON)
    for ev in st:
        if first is None: first = time.perf_counter() - t0
        types[ev.type] = types.get(ev.type, 0) + 1
    R["stream"] = {"latency_total_s": round(time.perf_counter() - t0, 2), "first_event_s": round(first or 0, 2), "event_types": types}
except Exception as e:
    R["stream"] = {"error": scrub(repr(e))[:1500], "event_types_so_far": types}
print("STREAM", json.dumps(R["stream"], indent=1))
json.dump(R, open(OUT / "t4.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
