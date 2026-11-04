"""Check a LIVE run against the demo acceptance list (docs/VERIFY_RUN2.md).

Usage:
  uv run python scripts/check_run.py <state.json | run_*.jsonl> [more files ...] [--tables]

Inputs: a GET /api/state JSON dump and/or a recorded run (data/cache/run_*.jsonl). A run file is folded into a
state (last write wins per id) and also gives the card history (so "VICTIM_FOUND never escalated" is checked over
every version of the card, not just the final one). When both are given, the state JSON is the final state and the
run file adds history. Prints PASS/FAIL per check; exit code 1 if any FAIL. --tables also prints the per-event
latency table and the agent wake table as Markdown.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

LIST_KINDS = {"card": "cards", "proposal": "proposals", "brief": "briefs", "trace": "trace", "event": "events",
              "transmission": "transmissions"}


def load_run(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fold a run_*.jsonl into a state-like dict. Returns (state, card_history, rest_actions)."""
    lists: dict[str, dict[str, Any]] = {k: {} for k in LIST_KINDS.values()}
    units: dict[str, Any] = {}
    counters: dict[str, Any] = {}
    history: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    t_max = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        t_max = max(t_max, float(d.get("t") or 0))
        if "method" in d:
            rest.append(d)
            continue
        ty, p = d.get("type"), d.get("payload") or {}
        if ty == "snapshot":
            for k in LIST_KINDS.values():
                for item in p.get(k, []):
                    lists[k][item["id"]] = item
            units.update(p.get("units", {}))
            counters = p.get("counters", counters)
        elif ty in LIST_KINDS:
            lists[LIST_KINDS[ty]][p["id"]] = p
            if ty == "card":
                history.append(p)
        elif ty == "unit":
            units[p["id"]] = p
        elif ty == "counters":
            counters = p
    state = {k: list(v.values()) for k, v in lists.items()}
    state.update(units=units, counters=counters, t=t_max)
    return state, history, rest


def load(paths: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    state: dict[str, Any] | None = None
    history: list[dict[str, Any]] = []
    run_name = ""
    for p in paths:
        if p.suffix == ".jsonl":
            s, h, _ = load_run(p)
            history += h
            run_name = p.name
            if state is None:
                state = s
        else:
            state = json.loads(p.read_text(encoding="utf-8"))
    assert state is not None, "no input"
    history += state.get("cards", [])
    return state, history, run_name


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def first(items, pred):
    return next((x for x in items if pred(x)), None)


def run_checks(st: dict[str, Any], history: list[dict[str, Any]]) -> Report:
    r = Report()
    cards, props, briefs, trace = st["cards"], st["proposals"], st["briefs"], st["trace"]
    events, txs, units, counters = st["events"], st["transmissions"], st["units"], st["counters"]
    tx_by_id = {t["id"]: t for t in txs}
    ev_line = {e["id"]: (tx_by_id.get(e["transmission_id"]) or {}).get("line_id") for e in events}
    cards = sorted(cards, key=lambda c: c["created_t"])

    # ---------------------------------------------------------------- a. cards
    kinds = {c["kind"] for c in cards}
    r.check("a1 DANGER card", "DANGER" in kinds)
    vic = [c for c in cards if c["kind"] == "VICTIM_FOUND"]
    vic_ids = {c["id"] for c in vic}
    vic_events = {e for c in vic for e in c["event_ids"]}
    esc_hist = [h for h in history if h["id"] in vic_ids and (h["state"] == "escalated" or h.get("escalation_level", 0) > 0)]
    esc_calls = [t for t in trace if t["kind"] == "tool_call" and t["payload"].get("tool") == "escalate_to_ic"
                 and (t["payload"].get("args") or {}).get("event_id") in vic_events]
    esc_ok = [t for t in esc_calls if first(trace, lambda c: c["kind"] == "checker" and c["payload"].get("call_id") ==
                                            t["payload"].get("call_id") and c["payload"].get("ok"))]
    r.check("a2 VICTIM_FOUND card, never escalated", bool(vic) and not esc_hist and not esc_ok,
            f"cards={[c['id'] + ':' + c['state'] for c in vic]} escalated_versions={len(esc_hist)} "
            f"escalate_calls={len(esc_calls)} (accepted {len(esc_ok)})")
    may = [c for c in cards if c["kind"] == "MAYDAY"]
    m = may[0] if may else None
    if m:
        f = m.get("fields") or {}
        miss = [k for k in ("who", "what", "where", "needs") if not f.get(k)]
        r.check("a3 MAYDAY card who/what/where/needs filled", not miss,
                f"{m['id']} fields={json.dumps(f, ensure_ascii=False)} missing={miss}")
    else:
        r.check("a3 MAYDAY card who/what/where/needs filled", False, "no MAYDAY card")
    r2 = [c for c in cards if c["kind"] == "RULE" and c.get("rule_id") == "R2"]
    r2ok = [c for c in r2 if c["state"] == "resolved" and "found OK" in (c.get("note") or "")]
    r.check("a4 RULE R2 resolved 'found OK'", bool(r2ok), f"{[(c['id'], c['state'], c.get('note')) for c in r2]}")

    # ---------------------------------------------------------------- b. trace hygiene
    unk = [t for t in trace if t["kind"] == "checker" and "unknown unit_id None" in (t["payload"].get("error") or "")]
    empty = [t for t in trace if t["kind"] == "tool_call" and not t["payload"].get("args")]
    r.check("b1 no checker 'unknown unit_id None'", not unk, f"{len(unk)} found")
    r.check("b2 no tool_call with empty args", not empty, f"{len(empty)} found")
    trunc = [t for t in trace if t["kind"] == "reasoning" and "truncated" in str(t["payload"].get("note", ""))]
    print(f"      info: truncation retries in trace = {len(trunc)}")

    # ---------------------------------------------------------------- c. ask kim needs ≤ 10 s
    if m:
        asks = [b for b in briefs if b["unit_id"] == (m.get("unit_id") or "kim") and "missing field: needs" in (b.get("reason") or "")]
        a = min(asks, key=lambda b: b["created_t"]) if asks else None
        if a:
            dt = a["created_t"] - m["created_t"]
            r.check("c ask kim 'needs' within 10 s of MAYDAY card", a["decision"] == "push" and dt <= 10.0,
                    f"source={a['source']} dt={dt:.1f}s text={a['text']!r}")
        else:
            needs_in_tx = bool((m.get("fields") or {}).get("needs")) and "needs" not in (m.get("missing_fields") or [])
            r.check("c ask kim 'needs' within 10 s of MAYDAY card", False,
                    f"no ask brief (needs filled at end: {needs_in_tx})")
    else:
        r.check("c ask kim 'needs' within 10 s of MAYDAY card", False, "no MAYDAY card")

    # ---------------------------------------------------------------- d. proposals
    for kind in ("RIT_DEPLOY", "RADIO_SILENCE"):
        ps = [p for p in props if p["kind"] == kind]
        appr = [p for p in ps if p["state"] == "approved"]
        r.check(f"d {kind} proposed + approved", bool(appr),
                f"{[(p['id'], p['source'], p['state'], round(p['created_t'], 1), p['text']) for p in ps]}"
                + (f" mayday+{ps[0]['created_t'] - m['created_t']:.1f}s" if ps and m else ""))
    rit = first(units.values(), lambda u: u.get("role") == "RIT") or units.get("rit") or {}
    r.check("d rit.zone_id east (2F-E*)", str(rit.get("zone_id") or "").startswith("2F-E"),
            f"rit.zone_id={rit.get('zone_id')} assignment={rit.get('assignment')}")
    rit_p = first(props, lambda p: p["kind"] == "RIT_DEPLOY" and p["state"] == "approved")
    hold = [b for b in briefs if b["unit_id"] == "kim" and "구조대 투입 중" in b["text"] and b["decision"] == "push"
            and (rit_p is None or b["created_t"] >= (rit_p.get("decided_t") or 0) - 0.01)]
    r.check("d kim got '구조대 투입 중' P0", bool(hold) and hold[0]["priority"] == "P0",
            f"{[(b['id'], b['priority'], round(b['created_t'], 1), b['text']) for b in hold]}")

    # ---------------------------------------------------------------- e. counters
    fb, wk = counters.get("fallback_routes", 0), counters.get("agent_wakes", 0)
    r.check("e fallback_routes <= 2", fb <= 2, f"fallback_routes={fb} agent_wakes={wk} "
            f"checker_rejections={counters.get('checker_rejections', 0)}")

    # ---------------------------------------------------------------- f. latency after speech
    bad = [(e["id"], (e.get("latency") or {}).get("after_speech_ms")) for e in events
           if not 500 <= (e.get("latency") or {}).get("after_speech_ms", 0) <= 15000]
    r.check("f every Event 500 <= after_speech_ms <= 15000", bool(events) and not bad, f"{len(events)} events, out of range={bad}")

    # ---------------------------------------------------------------- g. park / kim DANGER
    park = units.get("park") or {}
    r.check("g park heard>=2 total>=10", park.get("heard_count", 0) >= 2 and park.get("total_count", 0) >= 10,
            f"heard={park.get('heard_count')} total={park.get('total_count')}")
    l04 = {eid for eid, ln in ev_line.items() if ln == "L04"}
    kd = [b for b in briefs if b["unit_id"] == "kim" and b["decision"] == "push" and b.get("evidence_event_id") in l04]
    r.check("g kim got DANGER brief (push, evidence L04)", bool(kd),
            f"L04 events={sorted(l04)} briefs={[(b['id'], b['source'], b['text']) for b in kd]}")
    return r


def tables(st: dict[str, Any]) -> str:
    tx_by_id = {t["id"]: t for t in st["transmissions"]}
    out = ["| event | line | tag | src | asr_ms | triage_ms | after_speech_ms | total_ms | clip_s |",
           "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for e in sorted(st["events"], key=lambda e: e["t"]):
        tx = tx_by_id.get(e["transmission_id"]) or {}
        lat = e.get("latency") or {}
        clip = (tx["t_end"] - tx["t_keyup"]) if tx.get("t_end") is not None else None
        out.append(f"| {e['id']} | {tx.get('line_id') or '-'} | {e['triage']['tag']} | {e.get('source')} | "
                   f"{lat.get('asr_ms')} | {lat.get('triage_ms')} | {lat.get('after_speech_ms')} | {lat.get('total_ms')} | "
                   f"{'' if clip is None else f'{clip:.1f}'} |")
    out += ["", "| wake | reason | t | first tool call | calls | rejections | late calls | fallback |",
            "|---|---|---:|---:|---:|---:|---:|---|"]
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in st["trace"]:
        if t["wake_id"].startswith("wake_"):
            by[t["wake_id"]].append(t)
    for wid, ts in sorted(by.items(), key=lambda kv: kv[1][0]["t"]):
        ts.sort(key=lambda x: x["t"])
        t0 = ts[0]["t"]
        calls = [x for x in ts if x["kind"] == "tool_call"]
        rej = [x for x in ts if x["kind"] == "checker" and not x["payload"].get("ok")]
        late = [x for x in calls if x["payload"].get("late")]
        fbs = [x["payload"].get("reason") for x in ts if x["kind"] == "fallback" and x["payload"].get("reason") != "agent gap fill"]
        gap = any(x["kind"] == "fallback" and x["payload"].get("reason") == "agent gap fill" for x in ts) or \
            any(x["kind"] == "wake" and x["payload"].get("gap_fill") for x in ts)
        fc = f"{calls[0]['t'] - t0:.1f} s" if calls else "-"
        fb = ", ".join(fbs) if fbs else ("no (gap fill)" if gap else "no")
        out.append(f"| {wid} | {ts[0]['wake_reason']} | {t0:.1f} | {fc} | {len(calls)} | {len(rej)} | {len(late)} | {fb} |")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    want_tables = "--tables" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    st, history, run_name = load(paths)
    if run_name:
        print(f"run file: {run_name}")
    rep = run_checks(st, history)
    n_fail = sum(1 for _, ok, _ in rep.rows if not ok)
    print(f"\n{len(rep.rows) - n_fail}/{len(rep.rows)} PASS")
    if want_tables:
        print()
        print(tables(st))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
