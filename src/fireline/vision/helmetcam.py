"""Helmet-cam person detection with SAM 3.1 (live) or a deterministic mock.

Flow: the responder taps HELMET CAM on the clip display, the browser posts a
base64 frame (``PhotoInput``), ``HelmetCam.find_people`` sends it to SAM 3.1 with
the text prompt ``"person"`` and returns normalized ``Detection`` boxes. The world
model turns those into victim candidates at the responder's position.

Mock mode
---------
When ``settings.mock`` is True the SAM client raises ``MockMode`` and we fall back
to :func:`mock_detect`, which decodes the image with Pillow and looks for a
*figure marker* that only our generated sample frames carry: a JPEG COM segment
(``img.info["comment"]``) or a PNG text chunk of the form::

    fireline-helmetcam;v=1;box=0.31,0.55,0.69,0.84;box=...

Each ``box`` is a normalized ``x0,y0,x1,y1`` of a drawn silhouette. Arbitrary user
photos carry no marker and yield ``[]`` in mock mode.

Sample generation
-----------------
``python -m fireline.vision [out_dir]`` (or :func:`generate_samples`) draws three
640x480 JPEG frames into ``data/helmetcam/`` with the marker embedded.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import math
import time
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, PngImagePlugin

from fireline.config import DATA_DIR, Settings, get_settings
from fireline.meta import MetaAPIError, MockMode
from fireline.meta.sam import SAMClient
from fireline.models import Detection, PhotoInput

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

DEFAULT_PROMPT = "person"
MIN_SCORE = 0.3
MAX_BOXES = 6
MOCK_SCORE = 0.82
"""Score of the first mock detection; later boxes step down by MOCK_SCORE_STEP."""
MOCK_SCORE_STEP = 0.08
FALLBACK_SCORE = 0.35
"""Score used when the live call failed and we degraded to the mock result."""

MARKER_PREFIX = "fireline-helmetcam;v=1"
MARKER_PNG_KEY = "fireline-helmetcam"
SAMPLE_DIR = DATA_DIR / "helmetcam"
FRAME_SIZE = (640, 480)

Box = tuple[float, float, float, float]

# Normalized silhouette boxes of each generated sample (x0, y0, x1, y1).
SAMPLE_FIGURES: dict[str, list[Box]] = {
    "smoky_room_victim.jpg": [(0.30, 0.60, 0.72, 0.86)],
    "corridor_clear.jpg": [],
    "two_victims_404.jpg": [(0.12, 0.42, 0.34, 0.88), (0.60, 0.40, 0.84, 0.86)],
}
SAMPLE_NAMES = tuple(SAMPLE_FIGURES)


# ----------------------------------------------------------------------------
# Marker encode / decode
# ----------------------------------------------------------------------------


def encode_marker(boxes: Iterable[Box]) -> str:
    """Build the figure-marker string for a list of normalized boxes."""
    parts = [MARKER_PREFIX]
    for b in boxes:
        parts.append("box=" + ",".join(f"{v:.3f}" for v in b))
    return ";".join(parts)


def decode_marker(text: str | bytes | None) -> list[Box] | None:
    """Return the boxes in a marker string, [] for a marker with no boxes, None if absent."""
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    text = text.strip("\x00 \r\n")
    if not text.startswith(MARKER_PREFIX):
        return None
    boxes: list[Box] = []
    for field in text.split(";"):
        if not field.startswith("box="):
            continue
        try:
            vals = [float(v) for v in field[4:].split(",")]
        except ValueError:
            continue
        if len(vals) == 4:
            boxes.append((vals[0], vals[1], vals[2], vals[3]))
    return boxes


def read_marker(img: Image.Image) -> list[Box] | None:
    """Extract the figure marker from a decoded Pillow image (JPEG comment or PNG text)."""
    for key in ("comment", MARKER_PNG_KEY):
        boxes = decode_marker(img.info.get(key))
        if boxes is not None:
            return boxes
    return None


# ----------------------------------------------------------------------------
# Detection post-processing
# ----------------------------------------------------------------------------


def _clamp01(v: float) -> float:
    if not math.isfinite(v):
        return 0.0
    return min(1.0, max(0.0, float(v)))


def normalize_detection(det: Detection) -> Detection | None:
    """Clamp coords into 0..1, order corners, drop degenerate boxes / bad scores."""
    x0, x1 = sorted((_clamp01(det.x0), _clamp01(det.x1)))
    y0, y1 = sorted((_clamp01(det.y0), _clamp01(det.y1)))
    if x1 - x0 <= 0.0 or y1 - y0 <= 0.0:
        return None
    score = det.score if math.isfinite(det.score) else 0.0
    return Detection(label=det.label or DEFAULT_PROMPT, score=_clamp01(score), x0=x0, y0=y0, x1=x1, y1=y1)


def filter_detections(
    dets: Sequence[Detection], min_score: float = MIN_SCORE, max_boxes: int = MAX_BOXES
) -> list[Detection]:
    """Normalize, drop boxes under ``min_score``, sort by score desc, keep ``max_boxes``."""
    clean = [n for d in dets if (n := normalize_detection(d)) is not None]
    kept = [d for d in clean if d.score >= min_score]
    kept.sort(key=lambda d: d.score, reverse=True)
    return kept[:max_boxes]


def describe(dets: Sequence[Detection]) -> str:
    """Human line for the event log, e.g. ``"2 people detected (confidence 0.91, 0.77)"``."""
    if not dets:
        return "no people detected"
    noun = "person" if len(dets) == 1 else "people"
    confs = ", ".join(f"{d.score:.2f}" for d in dets)
    return f"{len(dets)} {noun} detected (confidence {confs})"


# ----------------------------------------------------------------------------
# Image helpers
# ----------------------------------------------------------------------------


def decode_photo(photo: PhotoInput) -> Image.Image | None:
    """Decode ``photo.image_b64`` into a Pillow image; None if it is not an image."""
    b64 = photo.image_b64.strip()
    if "," in b64 and b64.lower().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        raw = base64.b64decode(b64, validate=False)
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img
    except (binascii.Error, ValueError, OSError) as e:
        log.warning("helmetcam: could not decode photo %s: %s", photo.id, e)
        return None


def load_photo(path: str | Path, responder_id: str) -> PhotoInput:
    """Build a PhotoInput from an image file on disk (handy for demos and tests)."""
    p = Path(path)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return PhotoInput(responder_id=responder_id, image_b64=base64.b64encode(p.read_bytes()).decode("ascii"), mime=mime)


def sample_photo(name: str, responder_id: str, sample_dir: Path | None = None) -> PhotoInput:
    """PhotoInput for one of the generated samples, e.g. ``sample_photo("smoky_room_victim.jpg", "E1-2")``."""
    return load_photo((sample_dir or SAMPLE_DIR) / name, responder_id)


# ----------------------------------------------------------------------------
# Mock detector
# ----------------------------------------------------------------------------


def mock_detect(photo: PhotoInput, label: str = DEFAULT_PROMPT) -> list[Detection]:
    """Deterministic stand-in for SAM: detections only for our marked sample frames.

    * marker with boxes -> one Detection per box, scores 0.82, 0.74, ...
    * marker without boxes (``corridor_clear``) or no marker (any user photo) -> []
    * undecodable image -> []
    """
    img = decode_photo(photo)
    if img is None:
        return []
    boxes = read_marker(img)
    if not boxes:
        return []
    w, h = img.size
    if w <= 0 or h <= 0:
        return []
    dets: list[Detection] = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        dets.append(Detection(label=label, score=MOCK_SCORE - i * MOCK_SCORE_STEP, x0=x0, y0=y0, x1=x1, y1=y1))
    return filter_detections(dets)


def _centre_box(label: str, score: float) -> Detection:
    return Detection(label=label, score=score, x0=0.3, y0=0.25, x1=0.7, y1=0.9)


# ----------------------------------------------------------------------------
# HelmetCam
# ----------------------------------------------------------------------------


class HelmetCam:
    """Helmet-cam frame -> list of people. Live SAM 3.1 when a key is present, mock otherwise."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = SAMClient(self.settings)

    @property
    def model(self) -> str:
        return "mock" if self.settings.mock else self.settings.sam_model

    async def find_people(self, photo: PhotoInput, prompt: str = DEFAULT_PROMPT) -> tuple[list[Detection], int, str]:
        """Return ``(detections, latency_ms, raw)``.

        ``raw`` is the SAM token text on the live path, ``"mock"`` in mock mode, or
        ``"mock-fallback: <error>"`` when the live call failed and we degraded to the
        mock result with low scores. Never raises on a bad model answer.
        """
        t0 = time.perf_counter()
        try:
            dets, latency_ms, raw = await self.client.adetect(photo.image_b64, mime=photo.mime, prompt=prompt)
            return filter_detections(dets), latency_ms, raw
        except MockMode:
            dets = mock_detect(photo, prompt)
            return dets, _ms(t0), "mock"
        except MetaAPIError as e:
            log.error("helmetcam: SAM failed for %s: %s", photo.id, e)
            return self._degraded(photo, prompt), _ms(t0), f"mock-fallback: {e}"
        except Exception as e:  # noqa: BLE001 - the pipeline must never die on a photo
            log.exception("helmetcam: unexpected error for %s", photo.id)
            return self._degraded(photo, prompt), _ms(t0), f"mock-fallback: {type(e).__name__}: {e}"

    @staticmethod
    def _degraded(photo: PhotoInput, prompt: str) -> list[Detection]:
        """Mock result with confidence pulled down to FALLBACK_SCORE."""
        return [d.model_copy(update={"score": FALLBACK_SCORE}) for d in mock_detect(photo, prompt)]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


# ----------------------------------------------------------------------------
# Synthetic sample frames
# ----------------------------------------------------------------------------


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _haze_background(w: int, h: int, seed: int, top: float, bottom: float, warm: float = 0.0) -> Image.Image:
    """Grey haze gradient with low-frequency cloud noise, grain and a vignette."""
    rng = _rng(seed)
    y = np.linspace(0.0, 1.0, h)[:, None]
    x = np.linspace(0.0, 1.0, w)[None, :]
    base = top + (bottom - top) * y + 0.0 * x
    # low-frequency smoke clouds: sum of a few sinusoids with random phase
    cloud = np.zeros((h, w))
    for k in range(4):
        fx, fy = rng.uniform(1.0, 4.0), rng.uniform(1.0, 3.0)
        px, py = rng.uniform(0, 2 * math.pi, 2)
        cloud += np.sin(2 * math.pi * fx * x + px) * np.sin(2 * math.pi * fy * y + py) / (k + 1)
    cloud = cloud / np.abs(cloud).max() * 14.0
    grain = rng.normal(0.0, 6.0, (h, w))
    lum = np.clip(base + cloud + grain, 0, 255)
    r = np.clip(lum * (1.0 + 0.10 * warm), 0, 255)
    g = lum
    b = np.clip(lum * (1.0 - 0.06 * warm), 0, 255)
    arr = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    w, h = img.size
    y = np.linspace(-1.0, 1.0, h)[:, None]
    x = np.linspace(-1.0, 1.0, w)[None, :]
    d = np.sqrt(x * x + y * y) / math.sqrt(2.0)
    mask = 1.0 - strength * np.clip(d, 0, 1) ** 2
    arr = np.asarray(img).astype(np.float32) * mask[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _flashlight(img: Image.Image, origin: tuple[int, int], target: tuple[int, int], half_angle_deg: float = 22.0, gain: float = 70.0) -> Image.Image:
    """Additive warm light cone from ``origin`` toward ``target``, fading with distance."""
    w, h = img.size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xs - origin[0], ys - origin[1]
    dist = np.sqrt(dx * dx + dy * dy) + 1e-3
    ang = math.atan2(target[1] - origin[1], target[0] - origin[0])
    rel = np.arctan2(dy, dx) - ang
    rel = (rel + math.pi) % (2 * math.pi) - math.pi
    half = math.radians(half_angle_deg)
    cone = np.clip(1.0 - np.abs(rel) / half, 0, 1) ** 1.5
    fade = np.clip(1.0 - dist / (0.95 * h), 0, 1)
    light = cone * fade * gain
    arr = np.asarray(img).astype(np.float32)
    arr[:, :, 0] += light * 1.00
    arr[:, :, 1] += light * 0.92
    arr[:, :, 2] += light * 0.70
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _doorway(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: int = 22) -> None:
    x0, y0, x1, y1 = box
    draw.rectangle((x0 - 10, y0 - 10, x1 + 10, y1), fill=(55, 52, 50))  # frame
    draw.rectangle((x0, y0, x1, y1), fill=(fill, fill, fill + 2))


def _silhouette_layer(size: tuple[int, int], shapes: list[tuple[str, tuple[int, int, int, int]]], colour: tuple[int, int, int], blur: float) -> Image.Image:
    """Draw soft dark shapes on a transparent layer (rounded to look like a body)."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for kind, box in shapes:
        if kind == "ellipse":
            d.ellipse(box, fill=colour + (255,))
        else:
            d.rounded_rectangle(box, radius=min(box[2] - box[0], box[3] - box[1]) // 3, fill=colour + (255,))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _px_box(box: Box, size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    return int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)


def _prone_figure(size: tuple[int, int], box: Box) -> Image.Image:
    """A person lying on the floor, head to the left, inside ``box``."""
    x0, y0, x1, y1 = _px_box(box, size)
    bw, bh = x1 - x0, y1 - y0
    head = ("ellipse", (x0, y0 + int(bh * 0.25), x0 + int(bw * 0.16), y0 + int(bh * 0.70)))
    torso = ("rrect", (x0 + int(bw * 0.14), y0 + int(bh * 0.18), x0 + int(bw * 0.62), y0 + int(bh * 0.82)))
    legs = ("rrect", (x0 + int(bw * 0.58), y0 + int(bh * 0.30), x1, y0 + int(bh * 0.74)))
    arm = ("rrect", (x0 + int(bw * 0.22), y0 + int(bh * 0.00), x0 + int(bw * 0.34), y0 + int(bh * 0.40)))
    return _silhouette_layer(size, [head, torso, legs, arm], (18, 16, 16), 2.2)


def _seated_figure(size: tuple[int, int], box: Box, lean: float = 0.0) -> Image.Image:
    """A person sitting against a wall, knees up, inside ``box``."""
    x0, y0, x1, y1 = _px_box(box, size)
    bw, bh = x1 - x0, y1 - y0
    cx = x0 + int(bw * (0.45 + lean))
    head = ("ellipse", (cx - int(bw * 0.17), y0, cx + int(bw * 0.17), y0 + int(bh * 0.22)))
    torso = ("rrect", (cx - int(bw * 0.28), y0 + int(bh * 0.20), cx + int(bw * 0.28), y0 + int(bh * 0.72)))
    knees = ("ellipse", (x0 + int(bw * 0.20), y0 + int(bh * 0.48), x1, y0 + int(bh * 0.86)))
    feet = ("rrect", (x0 + int(bw * 0.55), y0 + int(bh * 0.80), x1, y1))
    return _silhouette_layer(size, [head, torso, knees, feet], (16, 15, 15), 2.0)


def _floor_line(img: Image.Image, y: int, shade: int = 8) -> None:
    """Darken the area below ``y`` slightly so the floor reads as a plane."""
    arr = np.asarray(img).astype(np.int16)
    arr[y:, :, :] -= shade
    img.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"))


def _compose(bg: Image.Image, layers: list[Image.Image]) -> Image.Image:
    out = bg.convert("RGBA")
    for layer in layers:
        out = Image.alpha_composite(out, layer)
    return out.convert("RGB")


def _hud(img: Image.Image, label: str) -> None:
    """Tiny helmet-cam HUD: REC dot and a caption in the corner."""
    d = ImageDraw.Draw(img)
    d.ellipse((14, 14, 26, 26), fill=(215, 40, 40))
    d.text((34, 12), "REC  HELMET CAM", fill=(220, 220, 220))
    d.text((34, 26), label, fill=(170, 170, 170))


def render_smoky_room_victim(size: tuple[int, int] = FRAME_SIZE) -> Image.Image:
    """Dark hazy room, doorway on the left, prone person on the floor, flashlight cone."""
    w, h = size
    bg = _haze_background(w, h, seed=11, top=78, bottom=38, warm=0.6)
    _floor_line(bg, int(h * 0.58))
    _doorway(ImageDraw.Draw(bg), (int(w * 0.08), int(h * 0.12), int(w * 0.26), int(h * 0.62)))
    img = _compose(bg, [_prone_figure(size, SAMPLE_FIGURES["smoky_room_victim.jpg"][0])])
    img = _flashlight(img, (int(w * 0.5), h + 30), (int(w * 0.50), int(h * 0.70)), half_angle_deg=28, gain=85)
    img = _vignette(img, 0.6)
    _hud(img, "E1-2  3F  UNIT 302")
    return img


def render_corridor_clear(size: tuple[int, int] = FRAME_SIZE) -> Image.Image:
    """Hazy corridor with converging walls and a far doorway, nobody in it."""
    w, h = size
    bg = _haze_background(w, h, seed=23, top=96, bottom=58, warm=0.2)
    d = ImageDraw.Draw(bg)
    vx, vy = int(w * 0.5), int(h * 0.48)
    # walls converging to the vanishing point
    d.polygon([(0, 0), (vx - 60, vy - 30), (vx - 60, vy + 40), (0, h)], fill=(70, 68, 66))
    d.polygon([(w, 0), (vx + 60, vy - 30), (vx + 60, vy + 40), (w, h)], fill=(64, 62, 60))
    d.polygon([(0, h), (vx - 60, vy + 40), (vx + 60, vy + 40), (w, h)], fill=(52, 50, 48))
    # door frames along the left wall
    for i, t in enumerate((0.15, 0.40, 0.65)):
        x = int(t * (vx - 60))
        top = int(t * (vy - 30))
        bottom = h - int(t * (h - vy - 40))
        d.rectangle((x, top + 20, x + 14, bottom - 10), fill=(40 - i * 4, 38, 36))
    _doorway(d, (vx - 38, vy - 24, vx + 38, vy + 40), fill=28)
    img = bg
    img = _flashlight(img, (int(w * 0.55), h + 20), (vx, vy), half_angle_deg=20, gain=60)
    img = _vignette(img, 0.5)
    _hud(img, "L2-1  4F  WEST CORRIDOR")
    return img


def render_two_victims_404(size: tuple[int, int] = FRAME_SIZE) -> Image.Image:
    """Smoky apartment, two people seated against the back wall."""
    w, h = size
    bg = _haze_background(w, h, seed=37, top=84, bottom=46, warm=0.8)
    d = ImageDraw.Draw(bg)
    d.rectangle((0, int(h * 0.62), w, h), fill=(46, 43, 41))  # floor
    d.rectangle((int(w * 0.40), int(h * 0.18), int(w * 0.56), int(h * 0.62)), fill=(60, 56, 52))  # wardrobe
    boxes = SAMPLE_FIGURES["two_victims_404.jpg"]
    img = _compose(bg, [_seated_figure(size, boxes[0], lean=-0.05), _seated_figure(size, boxes[1], lean=0.05)])
    img = _flashlight(img, (int(w * 0.5), h + 30), (int(w * 0.5), int(h * 0.55)), half_angle_deg=34, gain=70)
    img = _vignette(img, 0.55)
    _hud(img, "L2-1  4F  UNIT 404")
    return img


RENDERERS = {
    "smoky_room_victim.jpg": render_smoky_room_victim,
    "corridor_clear.jpg": render_corridor_clear,
    "two_victims_404.jpg": render_two_victims_404,
}


def save_marked(img: Image.Image, path: Path, boxes: Iterable[Box], quality: int = 88) -> Path:
    """Save ``img`` with the figure marker embedded (JPEG COM segment or PNG text chunk)."""
    marker = encode_marker(boxes)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".png":
        meta = PngImagePlugin.PngInfo()
        meta.add_text(MARKER_PNG_KEY, marker)
        img.save(path, "PNG", pnginfo=meta)
    else:
        img.convert("RGB").save(path, "JPEG", quality=quality, comment=marker.encode("utf-8"))
    return path


def generate_samples(out_dir: str | Path | None = None) -> list[Path]:
    """Render the three demo frames into ``out_dir`` (default data/helmetcam) and return their paths."""
    out = Path(out_dir) if out_dir else SAMPLE_DIR
    paths: list[Path] = []
    for name, render in RENDERERS.items():
        paths.append(save_marked(render(), out / name, SAMPLE_FIGURES[name]))
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: ``python -m fireline.vision [out_dir]``."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    out_dir = args[0] if args else None
    for p in generate_samples(out_dir):
        print(f"wrote {p}")
    return 0
