from server.gate import has_codeword, normalize_ko, should_triage


def test_numerals():
    assert normalize_ko("일층 후면 출입구 안쪽 삼 미터") == "1층 후면 출입구 안쪽 3미터"
    assert normalize_ko("이층 동쪽") == "2층 동쪽"
    assert normalize_ko("이상 없음") == "이상 없음"
    assert normalize_ko("이 대원 사무실") == "이 대원 사무실"


def test_doubled():
    assert normalize_ko("긴급탈출탈출") == "긴급탈출"
    assert normalize_ko("2층 2층 동쪽") == "2층 동쪽"
    assert normalize_ko("긴급 탈출", strip_spaces=True) == "긴급탈출"


def test_gate():
    assert not should_triage("")
    assert not should_triage("   ")
    assert not should_triage(".")
    assert not should_triage("네")
    assert not should_triage("아 아 아")
    assert should_triage("긴급탈출")
    assert should_triage("1층 서측 진입, 인명검색 시작")
    assert has_codeword("긴급 발출 긴급 탈출")


def test_asr_keywords_max_30_chars(caplog):
    from server.config import filter_keywords, load_keywords

    for lang in ("ko", "en"):
        kws = load_keywords(lang)
        assert kws and all(len(k) <= 30 for k in kws)
    assert "accountability report" in load_keywords("en")
    with caplog.at_level("WARNING"):
        assert filter_keywords(["PAR", "x" * 31, "PAR"]) == ["PAR"]
    assert "dropped" in caplog.text


def test_short_urgent_calls_reach_triage():
    for t in ("철수!", "붕괴 붕괴", "대피 대피 대피", "Evacuate!", "Collapse!"):
        assert should_triage(t), t
    assert not should_triage("네")
    assert not should_triage("어어어")


def test_demonstrative_i_is_not_two():
    assert normalize_ko("이 명령 확인") == "이 명령 확인"
    assert normalize_ko("이 층 동측 우선 탐색") == "2층 동측 우선 탐색"   # real ASR split (L02)
    assert normalize_ko("이 개 확인") == "이 개 확인"
    assert normalize_ko("이명 구조") == "2명 구조"
    assert normalize_ko("십이 층") == "12층"
