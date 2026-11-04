import os
import re

import pytest
import yaml

from server.config import ROOT
from server.models import TRIAGE_SCHEMA, Triage
from server.triage import FEW_SHOTS, SYSTEM_PROMPT, button_label, triage_button
from server.verify import verify


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def _data_texts() -> list[str]:
    out = []
    for p in (ROOT / "data").glob("*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        for ln in doc.get("lines", []):
            for k in ("text", "text_ko", "text_en"):
                if ln.get(k):
                    out.append(_norm(ln[k]))
    return out


def test_few_shots_valid_and_count():
    assert len(FEW_SHOTS) == 6
    for _, out in FEW_SHOTS:
        Triage.model_validate(out)
        assert set(out) == set(TRIAGE_SCHEMA["properties"])


def test_few_shots_not_in_data():
    texts = _data_texts()
    assert texts
    for txt, out in FEW_SHOTS:
        n = _norm(txt)
        assert not any(n in t or t in n for t in texts)
        # no 10-char window of a few-shot appears verbatim in any data line
        for i in range(0, max(1, len(n) - 10)):
            w = n[i:i + 10]
            assert not any(w in t for t in texts), w
        assert _norm(out["evidence_span"]) in n


def test_prompt_mentions_all_fields():
    for k in TRIAGE_SCHEMA["properties"]:
        assert k in SYSTEM_PROMPT


@pytest.mark.parametrize("kind,tag", [("EVACUATE", "MAYDAY"), ("VICTIM_HERE", "VICTIM_FOUND"),
                                      ("SEARCH_DONE", "ROUTINE"), ("NEED_HELP", "HELP_NEEDED")])
def test_buttons(kind, tag):
    t = triage_button("kim", kind, zone_label="2층 동쪽 창고", floor=2)
    Triage.model_validate(t.model_dump())
    assert t.tag == tag and t.evidence_span == button_label(kind)
    assert verify(t, button_label(kind))[0]
    if kind == "EVACUATE":
        assert t.distress.what == "OTHER" and t.distress.who == "한빛구조대 김하늘"
    if kind == "VICTIM_HERE":
        assert t.victims.state == "FOUND"


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("MODEL_API_KEY") and not (ROOT / ".env").exists(), reason="no MODEL_API_KEY")
async def test_triage_network():
    from server.config import get_settings
    from server.triage import triage

    if get_settings().mock:
        pytest.skip("no MODEL_API_KEY")
    t, ms, _ = await triage("지휘대장 여기 누리센터 박준 1층 서측 검색 중 이상 없음", "ko", "TAC")
    assert t.tag == "ROUTINE" and ms > 0
