from server.models import Location, Triage
from server.verify import load_roster, load_zones, snap_unit, snap_zone, verify


def test_loaders():
    r, z = load_roster(), load_zones()
    assert r["kim"].name == "김하늘" and z["2F-E-STORE"].parent == "2F-E"


def test_verify_evidence():
    text = "지휘대장… 한빛구조대 김하늘… 천장 무너져서 출구를 못 찾겠다. 2층 동쪽 창고 쪽."
    ok, t = verify(Triage(tag="MAYDAY", evidence_span="천장 무너져서, 출구를 못 찾겠다"), text)
    assert ok and t.evidence_span
    ok, t = verify(Triage(tag="MAYDAY", evidence_span="퇴로 차단"), text)
    assert not ok and t.evidence_span == "" and t.asr_uncertain and t.uncertain_reason == "evidence not verbatim"


def test_snap_unit():
    assert snap_unit("한빛구조대 김하늘") == "kim"
    assert snap_unit("한빛119안전센터 팀장") == "hanbit_center"
    assert snap_unit("누리 119안전센터 소방교 박준") == "park"
    assert snap_unit("지휘대장") == "ic"
    assert snap_unit("Truck 5", "en") == "en_truck5"
    assert snap_unit(None) is None
    assert snap_unit("가나다라마바") is None


def test_snap_zone():
    assert snap_zone(["동쪽 창고 쪽", "2층 동쪽 창고 쪽"], 2) == "2F-E-STORE"
    assert snap_zone(["동측 창문"], None) == "OUT-EAST"
    assert snap_zone(["동측", "2층 동측"], 2) == "2F-E"
    assert snap_zone(["계단 우측 사무실"], 2) == "2F-E-OFFICE"
    assert snap_zone(["옥상"], None) == "ROOF"
    assert snap_zone(["일층 서측"], 1) == "1F-W"
    assert snap_zone([None], None) is None
    _ = Location()
