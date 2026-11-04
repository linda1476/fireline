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
