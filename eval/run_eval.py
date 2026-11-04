"""Earshot batch eval (PRODUCT_SPEC §9, docs/CONTRACT.md "Eval").

Set: scenario_hanbit.yaml lines with kind != agent (12) + eval_lines.yaml (24) = 36.
Conditions: {clean, radio} x {keywords on, off} -> ASRClient.transcribe_file -> gate -> triage -> verify.
Writes eval/results.json, eval/results.md, eval/transcripts.json (raw ASR, reusable via --reuse-transcripts).

  uv run python -m eval.run_eval                                   # full 144-call matrix
  uv run python -m eval.run_eval --only L08,K07 --conditions clean_kw
  uv run python -m eval.run_eval --reuse-transcripts               # re-triage without paying ASR
  uv run python -m eval.run_eval --memo                            # EARSHOT_MEMO=1 input-hash cache
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import get_settings  # noqa: E402
from server.models import TAGS, TRIAGE_SCHEMA, Triage, Unit  # noqa: E402

EVAL_DIR = ROOT / "eval"
DATA = ROOT / "data"
CONDITIONS: dict[str, tuple[str, bool]] = {
    "clean_kw": ("clean", True), "clean_nokw": ("clean", False),
    "radio_kw": ("radio", True), "radio_nokw": ("radio", False),
}
MAX_IN_FLIGHT = 4

# ============================================================================ data
def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return list(v) if isinstance(v, list) else [v]


def load_eval_set() -> list[dict[str, Any]]:
    scen = yaml.safe_load((DATA / "scenario_hanbit.yaml").read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for ln in scen["lines"]:
        if ln.get("kind") == "agent":
            continue
        out.append({"id": ln["id"], "lang": scen.get("lang", "ko"), "text": ln.get("text_ko", ""),
                    "channel": ln.get("channel", "TAC"), "expect": ln.get("expect", {}), "source": "scenario"})
    ev = yaml.safe_load((DATA / "eval_lines.yaml").read_text(encoding="utf-8"))
    for ln in ev["lines"]:
        exp = ln.get("expect", {})
        # eval lines carry no channel: IC/command speakers on CMD, everyone else on TAC
        ch = "CMD" if (ln.get("speaker_hint") in ("ic", "en_command", "dispatch")) else "TAC"
        out.append({"id": ln["id"], "lang": ln.get("lang", "ko"), "text": ln.get("text", ""),
                    "channel": ch, "expect": exp, "source": "eval"})
    return out


def load_roster() -> list[Unit]:
    data = json.loads((DATA / "roster.json").read_text(encoding="utf-8"))
    return [Unit.model_validate(u) for u in data["units"]]


# ============================================================================ normalisation
_HANGUL_NUM = {"일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "지하": "b"}


def norm(s: str | None) -> str:
    """Lowercase, NFKC, strip spaces/punctuation, Hangul numeral floors (일층 -> 1층)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"(일|이|삼|사|오)\s*층", lambda m: _HANGUL_NUM[m.group(1)] + "층", s)
    return re.sub(r"[\W_]+", "", s)


def term_hit(term: str, transcript: str) -> bool:
    return bool(norm(term)) and norm(term) in norm(transcript)


# ============================================================================ pipeline steps (with fallbacks)
def gate_ok(text: str) -> bool:
    try:
        from server.gate import should_triage
        return bool(should_triage(text))
    except ImportError:  # TODO(eval): server.gate not present at build time; thin fallback
        return len((text or "").split()) >= 2


_FALLBACK_SYSTEM = """You triage fireground radio transmissions into one structured event.
Priority: MAYDAY > DANGER > VICTIM_FOUND > HELP_NEEDED > ROUTINE. Pick the highest that applies.
긴급탈출 / 메이데이 / 맨다운 / Mayday are distress codewords => MAYDAY. A firefighter in distress without a codeword (trapped, lost, cannot find the exit, out of air, fell, pinned) is still MAYDAY. Any transmission that is part of an ongoing mayday (declaration, IC broadcast, IC instructions to the trapped member, acknowledgement) is MAYDAY.
Never invent a floor: location.floor is null unless a floor is stated. 옥상/roof -> floor null, zone_hint "옥상". Use null for any unknown field. distress is null unless a firefighter is in distress; victims is null unless civilians/victims are mentioned. needs and air are verbatim from the transcript or null.
evidence_span must be a verbatim substring of the transcript.
crew_brief: at most 2 sentences, in the same language as the transcript."""


async def run_triage(text: str, lang: str, channel: str) -> tuple[Triage, int, dict[str, Any]]:
    try:
        from server.triage import triage as _triage
    except ImportError:  # TODO(eval): server.triage not present at build time; thin fallback on SparkClient
        _triage = None
    if _triage is not None:
        return await _triage(text, lang, channel)
    from server.meta.spark import SparkClient
    s = get_settings()
    client = SparkClient(s)
    return await client.acomplete_json(
        _FALLBACK_SYSTEM, f'Channel: {channel}. Language: {lang}. Transcript: "{text}"', Triage, TRIAGE_SCHEMA,
        max_tokens=4000, reasoning_effort=s.reasoning_effort)


def evidence_verbatim(span: str, text: str) -> bool:
    """Our own check on the RAW span (before verify.py blanks bad spans)."""
    return bool(norm(span)) and norm(span) in norm(text)


def run_verify(tri: Triage, text: str) -> bool:
    try:
        from server.verify import verify
        ok, _ = verify(tri, text)
        return bool(ok)
    except ImportError:  # TODO(eval): server.verify fallback
        return evidence_verbatim(tri.evidence_span, text)


def _unit_names(u: Unit) -> list[str]:
    return [x for x in [u.id, u.callsign, u.name, *u.aliases] if x]


def snap_unit(raw: str | None, roster: list[Unit], lang: str) -> str | None:
    if not raw:
        return None
    try:
        from server.verify import snap_unit as _snap
        return _snap(raw, lang, {u.id: u for u in roster})  # verify.snap_unit(raw, lang, roster: dict)
    except ImportError:  # TODO(eval): server.verify.snap_unit fallback (rapidfuzz over aliases)
        from rapidfuzz import fuzz
        best, best_s = None, 0.0
        r = norm(raw)
        for u in roster:
            if u.lang != lang:
                continue
            for a in _unit_names(u):
                sc = fuzz.partial_ratio(norm(a), r) if len(norm(a)) >= 2 else 0
                if sc > best_s or (sc == best_s and best and len(a) > 0):
                    best, best_s = u.id, sc
        return best if best_s >= 80 else None


def raw_unit_match(raw: str | None, expected: str, roster: list[Unit]) -> bool:
    """Raw (unsnapped) speaker string equals one of the expected unit's names/aliases after normalisation."""
    if not raw:
        return False
    u = next((x for x in roster if x.id == expected), None)
    if u is None:
        return False
    return norm(raw) in {norm(a) for a in _unit_names(u)}


ASR_KEYWORD_MAX_CHARS = 30  # measured: 400 "ASR keyword N exceeds the maximum length of 30 characters"


def asr_keywords(lang: str, on: bool) -> list[str] | None:
    """kw on -> project list for lang minus terms the API rejects (>30 chars, e.g. 'personnel accountability
    report' in keywords.json en); kw off -> []. TODO(keywords.json owner): drop/shorten that en term."""
    if not on:
        return []
    from server.config import load_keywords
    return [k for k in load_keywords(lang) if len(k) <= ASR_KEYWORD_MAX_CHARS]


# ============================================================================ memo
class Memo:
    """Input-hash memo (sha256(kind + canonical input)) for ASR and triage. EARSHOT_MEMO=1 / --memo.
    TODO(eval): switch to server.cache.memo once its signature is final; this local file is equivalent."""

    def __init__(self, enabled: bool, path: Path = EVAL_DIR / ".memo.jsonl"):
        self.enabled, self.path, self.d = enabled, path, {}
        if enabled and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.d[rec["k"]] = rec["v"]

    @staticmethod
    def key(kind: str, inp: Any) -> str:
        return hashlib.sha256((kind + json.dumps(inp, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()

    def get(self, kind: str, inp: Any) -> Any:
        return self.d.get(self.key(kind, inp)) if self.enabled else None

    def put(self, kind: str, inp: Any, v: Any) -> None:
        if not self.enabled:
            return
        k = self.key(kind, inp)
        self.d[k] = v
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")


# ============================================================================ one (line, condition)
async def run_one(line: dict[str, Any], cond: str, sem: asyncio.Semaphore, memo: Memo, roster: list[Unit],
                  transcripts: dict[str, Any], reuse: bool) -> dict[str, Any]:
    audio, kw_on = CONDITIONS[cond]
    exp = line["expect"]
    wav = DATA / "audio" / audio / f"{line['id']}.wav"
    row: dict[str, Any] = {"id": line["id"], "condition": cond, "lang": line["lang"], "channel": line["channel"],
                           "reference": line["text"], "transcript": None, "asr_ms": None, "spark_ms": None,
                           "gated": False, "pred_tag": None, "error": None}
    async with sem:
        try:
            cached = transcripts.get(cond, {}).get(line["id"]) if reuse else None
            if cached is not None:
                text, asr_ms = cached["text"], cached.get("asr_ms")
            else:
                minp = {"wav": str(wav.relative_to(ROOT)), "sha": hashlib.sha256(wav.read_bytes()).hexdigest(),
                        "lang": line["lang"], "kw": kw_on}
                m = memo.get("asr", minp)
                if m is not None:
                    text, asr_ms = m["text"], m["asr_ms"]
                else:
                    from server.meta.asr import ASRClient
                    res = await ASRClient().transcribe_file(wav, lang=line["lang"], keywords=asr_keywords(line["lang"], kw_on))
                    text, asr_ms = res.text, res.latency_ms
                    memo.put("asr", minp, {"text": text, "asr_ms": asr_ms})
                transcripts.setdefault(cond, {})[line["id"]] = {"text": text, "asr_ms": asr_ms}
            row["transcript"], row["asr_ms"] = text, asr_ms
            if not gate_ok(text):
                row["gated"] = True
                row["pred_tag"] = "ROUTINE"  # gate drop = no event = no card, i.e. ROUTINE downstream
            else:
                s = get_settings()
                tinp = {"text": text, "lang": line["lang"], "ch": line["channel"], "model": s.spark_model,
                        "effort": s.reasoning_effort}
                m = memo.get("triage", tinp)
                if m is not None:
                    tri, ms = Triage.model_validate(m["triage"]), m["ms"]
                else:
                    tri, ms, usage = await run_triage(text, line["lang"], line["channel"])
                    memo.put("triage", tinp, {"triage": tri.model_dump(mode="json"), "ms": ms, "usage": usage})
                row["spark_ms"] = ms
                row["pred_tag"] = tri.tag
                row["triage"] = tri.model_dump(mode="json")
                row["evidence_span"] = tri.evidence_span
                row["evidence_ok"] = evidence_verbatim(tri.evidence_span, text)
                row["verify_ok"] = run_verify(tri, text)
                row["unit_raw"] = tri.speaker_unit
                row["unit_snapped"] = snap_unit(tri.speaker_unit, roster, line["lang"])
                row["floor_pred"] = tri.location.floor
                row["distress_what"] = tri.distress.what if tri.distress else None
        except Exception as e:  # noqa: BLE001 - one failed call must not kill the matrix
            msg = str(e)
            key = get_settings().api_key
            if key:
                msg = msg.replace(key, "***")
            row["error"] = f"{type(e).__name__}: {msg[:300]}"
    annotate(row, line, roster)
    return row


def annotate(row: dict[str, Any], line: dict[str, Any], roster: list[Unit]) -> None:
    """Attach expected labels + per-line correctness flags (pure; used by metrics)."""
    exp = line["expect"]
    row["expected_tag"] = _as_list(exp.get("tag"))
    row["tag_ok"] = row.get("pred_tag") in row["expected_tag"]
    row["codeword_masked"] = bool(exp.get("codeword_masked"))
    terms = exp.get("critical_terms") or []
    row["critical_terms"] = terms
    row["critical_hits"] = [t for t in terms if term_hit(t, row.get("transcript") or "")]
    eu = exp.get("unit")
    row["unit_expected"] = eu
    if eu:
        row["unit_raw_ok"] = raw_unit_match(row.get("unit_raw"), eu, roster)
        row["unit_snapped_ok"] = row.get("unit_snapped") == eu
    ef = exp.get("floor")
    row["floor_expected"] = ef
    if ef is not None:
        row["floor_ok"] = row.get("floor_pred") == ef


# ============================================================================ metrics (pure)
def _pct(xs: list[float], q: float) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(np.percentile(xs, q)) if xs else None


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def macro_f1(rows: list[dict[str, Any]]) -> float | None:
    pairs = []
    for r in rows:
        exp = r["expected_tag"]
        if not exp or exp == ["RULE"]:
            continue
        pred = r.get("pred_tag") or "NONE"
        true = pred if pred in exp else exp[0]  # list label: credit if predicted in list
        pairs.append((true, pred))
    if not pairs:
        return None
    f1s = []
    for c in TAGS:
        tp = sum(1 for t, p in pairs if t == c and p == c)
        fp = sum(1 for t, p in pairs if t != c and p == c)
        fn = sum(1 for t, p in pairs if t == c and p != c)
        if tp + fp + fn == 0:
            continue  # class absent from both truth and prediction
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return round(float(np.mean(f1s)), 4)


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    pos = [r for r in rows if r["expected_tag"] == ["MAYDAY"]]
    tp = sum(1 for r in pos if r.get("pred_tag") == "MAYDAY")
    fp_rows = [r for r in rows if r.get("pred_tag") == "MAYDAY" and "MAYDAY" not in r["expected_tag"]]
    acc = sum(1 for r in rows if r["tag_ok"])
    terms_total = sum(len(r["critical_terms"]) for r in rows)
    terms_hit = sum(len(r["critical_hits"]) for r in rows)
    per_term: dict[str, list[int]] = {}
    for r in rows:
        for t in r["critical_terms"]:
            per_term.setdefault(t, [0, 0])
            per_term[t][1] += 1
            per_term[t][0] += t in r["critical_hits"]
    u_rows = [r for r in rows if r.get("unit_expected")]
    f_rows = [r for r in rows if r.get("floor_expected") is not None]
    cw = [r for r in rows if r["codeword_masked"]]
    cw_hit = [r["id"] for r in cw if r.get("pred_tag") == "MAYDAY"]
    ev = [r for r in rows if r.get("evidence_span")]
    return {
        "n": n,
        "errors": sum(1 for r in rows if r.get("error")),
        "gated": sum(1 for r in rows if r.get("gated")),
        "mayday_recall": _ratio(tp, len(pos)), "mayday_tp": tp, "mayday_n": len(pos),
        "mayday_fp": len(fp_rows), "mayday_fp_ids": [r["id"] for r in fp_rows],
        "missed_mayday_ids": [r["id"] for r in pos if r.get("pred_tag") != "MAYDAY"],
        "accuracy": _ratio(acc, n), "macro_f1": macro_f1(rows),
        "critical_term_hit_rate": _ratio(terms_hit, terms_total), "critical_terms_hit": terms_hit,
        "critical_terms_total": terms_total, "critical_terms_by_term": {k: f"{v[0]}/{v[1]}" for k, v in per_term.items()},
        "unit_raw_exact": _ratio(sum(1 for r in u_rows if r.get("unit_raw_ok")), len(u_rows)),
        "unit_snapped_exact": _ratio(sum(1 for r in u_rows if r.get("unit_snapped_ok")), len(u_rows)),
        "unit_n": len(u_rows),
        "floor_exact": _ratio(sum(1 for r in f_rows if r.get("floor_ok")), len(f_rows)), "floor_n": len(f_rows),
        "codeword_masked_recall": f"{len(cw_hit)}/{len(cw)}", "codeword_masked_ids": [r["id"] for r in cw],
        "codeword_masked_hit_ids": cw_hit,
        "evidence_verbatim_rate": _ratio(sum(1 for r in ev if r.get("evidence_ok")), len(ev)),
        "evidence_n": len(ev), "evidence_empty": sum(1 for r in rows if r.get("pred_tag") and not r.get("gated")
                                                     and not r.get("evidence_span")),
        "spark_ms_p50": _pct([r.get("spark_ms") for r in rows], 50),
        "spark_ms_p95": _pct([r.get("spark_ms") for r in rows], 95),
        "asr_ms_p50": _pct([r.get("asr_ms") for r in rows], 50),
        "asr_ms_p95": _pct([r.get("asr_ms") for r in rows], 95),
    }


# ============================================================================ report
def _f(v: Any) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.0f}" if v > 2 else f"{v:.2f}"
    return str(v)


def _cell(s: Any, n: int = 60) -> str:
    s = "" if s is None else str(s)
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_md(results: dict[str, Any]) -> str:
    meta, conds, lines = results["meta"], results["conditions"], results["lines"]
    out = ["# Earshot eval", "",
           f"Synthetic, {meta['audio_provenance_summary']} + AMR-NB codec degradation, n = {meta['n']} per condition. "
           f"Ran {meta['ran_at']}; Spark `{meta['spark_model']}` (reasoning_effort={meta['reasoning_effort']}), "
           f"ASR `{meta['asr_model']}`. No WER claim for Muse in general.", ""]
    if meta.get("partial"):
        out += [f"**Partial run** (only={meta.get('only')}, conditions={meta.get('conditions_run')}).", ""]
    keys = [("n", "n"), ("errors", "errors"), ("mayday_recall", "MAYDAY recall"), ("mayday_fp", "MAYDAY FP"),
            ("accuracy", "5-way acc"), ("macro_f1", "macro-F1"), ("critical_term_hit_rate", "critical-term hit"),
            ("unit_raw_exact", "unit raw"), ("unit_snapped_exact", "unit snapped"), ("floor_exact", "floor"),
            ("codeword_masked_recall", "codeword-masked"), ("evidence_verbatim_rate", "evidence verbatim"),
            ("spark_ms_p50", "Spark p50 ms"), ("spark_ms_p95", "Spark p95 ms"),
            ("asr_ms_p50", "ASR p50 ms"), ("asr_ms_p95", "ASR p95 ms")]
    names = list(conds)
    out += ["| metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k, lab in keys:
        out.append(f"| {lab} | " + " | ".join(_f(conds[c].get(k)) for c in names) + " |")
    out += [""]
    for c in names:
        m = conds[c]
        out.append(f"- **{c}**: MAYDAY {m['mayday_tp']}/{m['mayday_n']} (missed {m['missed_mayday_ids'] or '–'}; "
                   f"FP {m['mayday_fp_ids'] or '–'}); critical terms {m['critical_terms_hit']}/{m['critical_terms_total']} "
                   f"{m['critical_terms_by_term']}; codeword-masked {m['codeword_masked_recall']} "
                   f"(set {m['codeword_masked_ids']}, hit {m['codeword_masked_hit_ids']})")
    out += ["", "## Per line", "",
            "| id | cond | transcript | pred | expected | unit raw→snapped | floor | evidence | Spark ms |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in lines:
        mark = "ok" if r["tag_ok"] else "**x**"
        unit = f"{_cell(r.get('unit_raw'), 24)}→{r.get('unit_snapped') or '–'}"
        if r.get("unit_expected"):
            unit += f" (exp {r['unit_expected']})"
        floor = f"{_f(r.get('floor_pred'))}" + (f"/{r['floor_expected']}" if r.get("floor_expected") is not None else "")
        ev = "–" if r.get("evidence_ok") is None else ("ok" if r["evidence_ok"] else "x")
        pred = r.get("pred_tag") or f"ERR {_cell(r.get('error'), 40)}"
        out.append(f"| {r['id']} | {r['condition']} | {_cell(r.get('transcript'), 70)} | {pred} {mark} | "
                   f"{'/'.join(r['expected_tag'])} | {unit} | {floor} | {ev} | {_f(r.get('spark_ms'))} |")
    out += [""]
    rk = conds.get("radio_kw")
    rec = rk.get("mayday_recall") if rk else None
    hero = "radio" if (rec is not None and rec >= 0.8) else "clean"
    out.append(f"GATE: radio_kw MAYDAY recall = {_f(rec) if rec is not None else 'n/a (radio_kw not run)'} → hero audio: {hero}")
    return "\n".join(out) + "\n"


# ============================================================================ main
def provenance_summary() -> str:
    p = DATA / "audio" / "provenance.json"
    if not p.exists():
        return "provenance unknown"
    c = Counter(v.get("source", "?") for v in json.loads(p.read_text(encoding="utf-8")).values())
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items()))


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    s = get_settings()
    conds = [c.strip() for c in args.conditions.split(",")] if args.conditions else list(CONDITIONS)
    for c in conds:
        if c not in CONDITIONS:
            raise SystemExit(f"unknown condition {c}; choose from {list(CONDITIONS)}")
    lines = load_eval_set()
    if args.only:
        want = {x.strip() for x in args.only.split(",")}
        lines = [ln for ln in lines if ln["id"] in want]
    roster = load_roster()
    memo = Memo(args.memo or os.environ.get("EARSHOT_MEMO") == "1")
    tpath = EVAL_DIR / "transcripts.json"
    transcripts = json.loads(tpath.read_text(encoding="utf-8")) if tpath.exists() else {}
    sem = asyncio.Semaphore(MAX_IN_FLIGHT)
    t0 = time.time()
    rows = await asyncio.gather(*[run_one(ln, c, sem, memo, roster, transcripts, args.reuse_transcripts)
                                  for c in conds for ln in lines])
    tpath.write_text(json.dumps(transcripts, ensure_ascii=False, indent=1), encoding="utf-8")
    results = {
        "meta": {"n": len(lines), "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "wall_s": round(time.time() - t0, 1),
                 "audio_provenance_summary": provenance_summary(), "reasoning_effort": s.reasoning_effort,
                 "spark_model": s.spark_model, "asr_model": s.asr_model,
                 "partial": bool(args.only or args.conditions), "only": args.only, "conditions_run": conds},
        "conditions": {c: compute_metrics([r for r in rows if r["condition"] == c]) for c in conds},
        "lines": list(rows),
    }
    (EVAL_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (EVAL_DIR / "results.md").write_text(render_md(results), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Earshot batch eval")
    ap.add_argument("--conditions", default="", help="comma list of " + ",".join(CONDITIONS))
    ap.add_argument("--only", default="", help="comma list of line ids, e.g. L08,K07")
    ap.add_argument("--memo", action="store_true", help="input-hash memo for ASR + triage (EARSHOT_MEMO=1)")
    ap.add_argument("--reuse-transcripts", action="store_true", help="use eval/transcripts.json instead of ASR")
    args = ap.parse_args(argv)
    res = asyncio.run(main_async(args))
    print(render_md(res))


if __name__ == "__main__":
    main()
