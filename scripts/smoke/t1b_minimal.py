"""TEST 1b: reasoning_effort=minimal on a/b/c + bad-schema probe (is strict validated?)."""
import json, copy
from t1_structured import call, INPUTS, SCHEMA, OUT
R = [call(t, effort="minimal", label=f"{k}/strict/minimal") for k, t in INPUTS.items()]
bad = copy.deepcopy(SCHEMA); bad["required"] = ["tag"]  # violates strict rule (required must list all keys)
R.append(call(INPUTS["a"], schema=bad, effort="minimal", label="a/BAD-schema(required subset)/strict"))
json.dump(R, open(OUT / "t1b.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
