"""Metric functions of eval/run_eval.py on a tiny fake table (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root (no conftest owned by this module)

from eval.run_eval import (annotate, compute_metrics, load_eval_set, load_roster, macro_f1, norm, render_md,
                           term_hit)


def _row(id_, pred, expect, transcript="", **extra):
    row = {"id": id_, "condition": "clean_kw", "transcript": transcript, "pred_tag": pred, **extra}
    annotate(row, {"expect": expect}, load_roster())
    return row


def test_eval_set_is_36_and_masked_5():
    s = load_eval_set()
    assert len(s) == 36
    assert {x["id"] for x in s if x["expect"].get("codeword_masked")} == {"L08", "M01", "M02", "M03", "M04"}
    assert sum(1 for x in s if x["lang"] == "en") == 12  # E01–E10 + M03/M04 (CONTRACT says 14; data has 12)


def test_norm_and_terms():
    assert norm("일 층 동측") == "1층동측"
    assert term_hit("무선 침묵", "전 출동대 무선침묵.")
    assert term_hit("Mayday", "mayday, MAYDAY")
    assert not term_hit("긴급탈출", "긴급 상황")


def test_metrics_fake_table():
    rows = [
        _row("A", "MAYDAY", {"tag": "MAYDAY", "critical_terms": ["긴급탈출"], "unit": "kim", "floor": 2},
             "긴급탈출 한빛구조대", unit_raw="한빛 구조대", unit_snapped="kim", floor_pred=2,
             evidence_span="긴급탈출", evidence_ok=True, spark_ms=100, asr_ms=50),
        _row("B", "ROUTINE", {"tag": "MAYDAY", "codeword_masked": True, "unit": "park", "floor": 1},
             "출구를 못 찾겠다", unit_raw="누리", unit_snapped=None, floor_pred=None,
             evidence_span="없는말", evidence_ok=False, spark_ms=300, asr_ms=70),
        _row("C", "MAYDAY", {"tag": ["HELP_NEEDED", "MAYDAY"]}, "사다리 필요", spark_ms=200),
        _row("D", "MAYDAY", {"tag": "ROUTINE", "floor": None}, "진입"),
        _row("E", "DANGER", {"tag": "DANGER", "critical_terms": ["인화물질"]}, "인화 물질 확인"),
    ]
    m = compute_metrics(rows)
    assert m["mayday_recall"] == 0.5 and m["mayday_n"] == 2 and m["missed_mayday_ids"] == ["B"]
    assert m["mayday_fp"] == 1 and m["mayday_fp_ids"] == ["D"]  # C is a list label containing MAYDAY: not FP
    assert m["accuracy"] == 0.6
    assert m["critical_terms_total"] == 2 and m["critical_terms_hit"] == 2
    assert m["unit_raw_exact"] == 0.5 and m["unit_snapped_exact"] == 0.5 and m["unit_n"] == 2
    assert m["floor_exact"] == 0.5 and m["floor_n"] == 2
    assert m["codeword_masked_recall"] == "0/1"
    assert m["evidence_verbatim_rate"] == 0.5
    assert m["spark_ms_p50"] == 200.0


def test_macro_f1_list_label_credit():
    rows = [_row("1", "HELP_NEEDED", {"tag": ["HELP_NEEDED", "MAYDAY"]}),
            _row("2", "MAYDAY", {"tag": "MAYDAY"})]
    assert macro_f1(rows) == 1.0
    rows.append(_row("3", "ROUTINE", {"tag": "MAYDAY"}))
    assert 0 < macro_f1(rows) < 1


def test_render_md_gate_line():
    rows = [_row("A", "MAYDAY", {"tag": "MAYDAY"}, "x y", spark_ms=1)]
    for r in rows:
        r["condition"] = "radio_kw"
    res = {"meta": {"n": 1, "ran_at": "now", "audio_provenance_summary": "tts 1", "reasoning_effort": "minimal",
                    "spark_model": "s", "asr_model": "a"},
           "conditions": {"radio_kw": compute_metrics(rows)}, "lines": rows}
    md = render_md(res)
    assert md.strip().endswith("GATE: radio_kw MAYDAY recall = 1.00 → hero audio: radio")
