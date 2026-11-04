# Helmet-cam sample frames

Synthetic 640x480 JPEG frames used by the HELMET CAM button demo. They are drawn with
Pillow + numpy by `python -m fireline.vision` (see `src/fireline/vision/helmetcam.py`);
re-run that command to regenerate them.

| File | Scene | Expected people |
|---|---|---|
| `smoky_room_victim.jpg` | dark hazy room, doorway on the left, one person prone on the floor in a flashlight cone (E1-2, 3F, unit 302) | 1 |
| `corridor_clear.jpg` | hazy corridor with a far doorway, nobody in it (L2-1, 4F, west corridor) | 0 |
| `two_victims_404.jpg` | smoky apartment, two people seated against the back wall (L2-1, 4F, unit 404) | 2 |

## SAM prompt

Every frame is sent to **SAM 3.1** (`sam-3.1` via `POST /v1/responses`) with the text
prompt `"person"` and `include_confidence=true`. The returned boxes are normalized to
0..1, filtered to score >= 0.3, sorted by score and capped at 6 detections. The world
model turns each detection into a *suspected* victim at the responder's current cell
(`p = 0.5 + 0.4 * score`, source `camera`).

## Using a real photo

Any JPEG or PNG works on the live path. From the responder clip display tap
**HELMET CAM** and pick a file; the page base64-encodes it and posts
`{responder_id, image_b64, mime}` to `POST /api/photo`. From Python:

```python
from fireline.vision import HelmetCam, load_photo, describe
hc = HelmetCam()
photo = load_photo("my_frame.jpg", responder_id="E1-2")
dets, latency_ms, raw = await hc.find_people(photo)
print(describe(dets))     # "1 person detected (confidence 0.91)"
```

Keep frames small (<= 1280 px on the long side) so the request stays fast.

## Mock mode caveat

Without `MODEL_API_KEY` (or with `FIRELINE_MOCK=1`) nothing is sent to Meta. The mock
detector only recognises the generated samples: each carries a figure marker in its JPEG
comment segment (`fireline-helmetcam;v=1;box=x0,y0,x1,y1;...`) that records where the
silhouettes were drawn. Those boxes come back as detections (scores 0.82, 0.74, ...).
Any other image returns no detections in mock mode. Re-encoding a sample (for example
through an image editor or a canvas) strips the comment and therefore the mock result.
