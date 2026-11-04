"""Vision module tests (mock mode) + one live SAM 3.1 check."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from fireline.meta.sam import parse_sam_output
from fireline.models import Detection, PhotoInput
from fireline.vision import (
    MAX_BOXES,
    SAMPLE_DIR,
    SAMPLE_FIGURES,
    HelmetCam,
    describe,
    filter_detections,
    generate_samples,
    mock_detect,
    sample_photo,
)
from fireline.vision.helmetcam import FALLBACK_SCORE, decode_marker, encode_marker, save_marked

# --------------------------------------------------------------------------- parse


def test_parse_no_boxes_returns_empty():
    assert parse_sam_output("<0f>0") == []
    assert parse_sam_output("") == []
    assert parse_sam_output(None) == []  # type: ignore[arg-type]


def test_parse_confidence_missing_defaults_to_one():
    dets = parse_sam_output("<0f>0<|box;x1=10;y1=20;x2=109;y2=219;w=640;h=480|>")
    assert len(dets) == 1
    assert dets[0].score == 1.0
    assert dets[0].label == "person"
    assert dets[0].x0 == pytest.approx(10 / 640)
    assert dets[0].x1 == pytest.approx(110 / 640)
    assert dets[0].y1 == pytest.approx(220 / 480)


def test_parse_two_records_one_line():
    raw = (
        "<0f>0<|box;x1=0;y1=0;x2=99;y2=99;w=200;h=100;c=0.93|><|mask;x=0;y=0;data=AAAA|>"
        ",1<|box;x1=100;y1=0;x2=199;y2=99;w=200;h=100;c=0.55|><|mask;x=0;y=0;data=BBBB|>"
    )
    dets = parse_sam_output(raw)
    assert [d.score for d in dets] == [0.93, 0.55]
    assert dets[0].x1 == pytest.approx(0.5)
    assert dets[1].x0 == pytest.approx(0.5)


def test_parse_clamps_out_of_range_boxes():
    dets = parse_sam_output("<0f>0<|box;x1=-5;y1=-5;x2=900;y2=900;w=640;h=480;c=0.7|>")
    assert dets[0].x0 == 0.0 and dets[0].y0 == 0.0
    assert dets[0].x1 == 1.0 and dets[0].y1 == 1.0


def test_parse_skips_zero_size_and_garbage():
    assert parse_sam_output("<|box;x1=1;y1=1;x2=5;y2=5;w=0;h=0|>") == []
    assert parse_sam_output("<|box;x1=a;y1=b;c=zz|>") == []


# --------------------------------------------------------------------------- filter


def test_filter_min_score_sort_and_cap():
    dets = [Detection(label="person", score=s, x0=0.1, y0=0.1, x1=0.5, y1=0.5) for s in (0.2, 0.9, 0.5, 0.31, 0.7, 0.8, 0.6, 0.95)]
    out = filter_detections(dets)
    assert len(out) == MAX_BOXES
    assert [d.score for d in out] == sorted([d.score for d in out], reverse=True)
    assert out[0].score == 0.95 and all(d.score >= 0.3 for d in out)


def test_filter_normalizes_bad_model_output():
    swapped = Detection(label="", score=1.7, x0=0.9, y0=0.8, x1=0.2, y1=0.1)
    degenerate = Detection(label="person", score=0.9, x0=0.5, y0=0.5, x1=0.5, y1=0.9)
    nan = Detection(label="person", score=float("nan"), x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    out = filter_detections([swapped, degenerate, nan])
    assert len(out) == 1
    d = out[0]
    assert d.label == "person" and d.score == 1.0
    assert (d.x0, d.y0, d.x1, d.y1) == (0.2, 0.1, 0.9, 0.8)


# --------------------------------------------------------------------------- describe


def test_describe_wording():
    two = [Detection(label="person", score=0.91, x0=0, y0=0, x1=0.5, y1=0.5), Detection(label="person", score=0.77, x0=0.5, y0=0, x1=1, y1=0.5)]
    assert describe(two) == "2 people detected (confidence 0.91, 0.77)"
    assert describe(two[:1]) == "1 person detected (confidence 0.91)"
    assert describe([]) == "no people detected"


# --------------------------------------------------------------------------- marker + mock


def test_marker_roundtrip():
    boxes = [(0.1, 0.2, 0.3, 0.4), (0.5, 0.5, 0.9, 0.9)]
    assert decode_marker(encode_marker(boxes)) == boxes
    assert decode_marker(encode_marker([])) == []
    assert decode_marker("JPEG made by someone else") is None
    assert decode_marker(None) is None


def _photo_from_image(img: Image.Image, fmt: str = "JPEG", **save_kwargs) -> PhotoInput:
    buf = io.BytesIO()
    img.save(buf, fmt, **save_kwargs)
    return PhotoInput(responder_id="E1-2", image_b64=base64.b64encode(buf.getvalue()).decode("ascii"), mime=f"image/{fmt.lower()}")


def test_mock_ignores_arbitrary_images_and_garbage():
    plain = _photo_from_image(Image.new("RGB", (320, 240), (90, 90, 90)))
    assert mock_detect(plain) == []
    assert mock_detect(PhotoInput(responder_id="E1-2", image_b64="not base64 at all!!")) == []
    assert mock_detect(PhotoInput(responder_id="E1-2", image_b64=base64.b64encode(b"hello").decode())) == []


def test_mock_reads_png_marker(tmp_path):
    p = save_marked(Image.new("RGB", (100, 100), (40, 40, 40)), tmp_path / "x.png", [(0.1, 0.1, 0.6, 0.9)])
    photo = PhotoInput(responder_id="R3-1", image_b64=base64.b64encode(p.read_bytes()).decode(), mime="image/png")
    dets = mock_detect(photo)
    assert len(dets) == 1 and dets[0].score == pytest.approx(0.82)
    assert (dets[0].x0, dets[0].y0, dets[0].x1, dets[0].y1) == (0.1, 0.1, 0.6, 0.9)


def test_mock_accepts_data_url_prefix():
    photo = sample_photo("smoky_room_victim.jpg", "E1-2")
    photo.image_b64 = "data:image/jpeg;base64," + photo.image_b64
    assert len(mock_detect(photo)) == 1


# --------------------------------------------------------------------------- samples + HelmetCam


def test_samples_exist_and_are_640x480():
    for name in SAMPLE_FIGURES:
        p = SAMPLE_DIR / name
        assert p.exists(), f"missing sample {p}; run python -m fireline.vision"
        assert Image.open(p).size == (640, 480)


def test_generate_samples_is_deterministic(tmp_path):
    a = generate_samples(tmp_path / "a")
    b = generate_samples(tmp_path / "b")
    assert [p.name for p in a] == list(SAMPLE_FIGURES)
    for pa, pb in zip(a, b):
        assert pa.read_bytes() == pb.read_bytes()


@pytest.mark.parametrize("name,expected", [("smoky_room_victim.jpg", 1), ("corridor_clear.jpg", 0), ("two_victims_404.jpg", 2)])
async def test_find_people_mock_counts(settings, name, expected):
    hc = HelmetCam(settings)
    assert hc.model == "mock"
    dets, latency_ms, raw = await hc.find_people(sample_photo(name, "L2-1"))
    assert raw == "mock"
    assert len(dets) == expected
    assert isinstance(latency_ms, int) and latency_ms >= 0
    for d in dets:
        assert d.label == "person" and 0.3 <= d.score <= 1.0
        assert 0 <= d.x0 < d.x1 <= 1 and 0 <= d.y0 < d.y1 <= 1
    if expected:
        assert dets[0].score == pytest.approx(0.82)
        assert [d.score for d in dets] == sorted((d.score for d in dets), reverse=True)


async def test_find_people_custom_prompt_labels(settings):
    hc = HelmetCam(settings)
    dets, _, _ = await hc.find_people(sample_photo("two_victims_404.jpg", "L2-1"), prompt="firefighter")
    assert dets and all(d.label == "firefighter" for d in dets)


async def test_find_people_degrades_when_live_call_fails(settings, monkeypatch):
    """A broken live call must not raise: we fall back to the mock boxes with low confidence."""
    from fireline.meta import MetaAPIError

    hc = HelmetCam(settings)

    async def boom(*a, **k):
        raise MetaAPIError("SAM request failed: 500")

    monkeypatch.setattr(hc.client, "adetect", boom)
    dets, _, raw = await hc.find_people(sample_photo("smoky_room_victim.jpg", "E1-2"))
    assert raw.startswith("mock-fallback:")
    assert len(dets) == 1 and dets[0].score == pytest.approx(FALLBACK_SCORE)

    async def crash(*a, **k):
        raise ValueError("unexpected shape")

    monkeypatch.setattr(hc.client, "adetect", crash)
    dets, _, raw = await hc.find_people(sample_photo("corridor_clear.jpg", "E1-2"))
    assert dets == [] and "ValueError" in raw


async def test_find_people_live_path_filters_model_output(settings, monkeypatch):
    """Simulate a live SAM answer: filtering/sorting is applied to whatever the client returns."""
    hc = HelmetCam(settings)
    raw = "<0f>0<|box;x1=0;y1=0;x2=99;y2=99;w=200;h=100;c=0.2|>,1<|box;x1=100;y1=0;x2=199;y2=99;w=200;h=100;c=0.9|>"

    async def fake(*a, **k):
        return parse_sam_output(raw), 123, raw

    monkeypatch.setattr(hc.client, "adetect", fake)
    dets, latency_ms, got = await hc.find_people(sample_photo("corridor_clear.jpg", "E1-2"))
    assert got == raw and latency_ms == 123
    assert [d.score for d in dets] == [0.9]


# --------------------------------------------------------------------------- live


@pytest.mark.live
async def test_live_sam_smoky_room_victim():
    from fireline.config import get_settings

    hc = HelmetCam(get_settings(refresh=True))
    assert not hc.settings.mock
    dets, latency_ms, raw = await hc.find_people(sample_photo("smoky_room_victim.jpg", "E1-2"))
    print(f"\nSAM {hc.model} latency={latency_ms}ms raw={raw[:400]!r}")
    for d in dets:
        print(f"  {d.label} {d.score:.2f} box=({d.x0:.2f},{d.y0:.2f},{d.x1:.2f},{d.y1:.2f})")
    print(describe(dets))
    assert raw != "mock"
    assert isinstance(dets, list)
