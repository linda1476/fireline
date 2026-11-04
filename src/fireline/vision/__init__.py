"""Vision module: helmet-cam frames -> people (SAM 3.1 live, deterministic mock otherwise).

    from fireline.vision import HelmetCam
    hc = HelmetCam()
    dets, latency_ms, raw = await hc.find_people(photo)   # photo: PhotoInput
"""

from fireline.vision.helmetcam import (
    DEFAULT_PROMPT,
    MAX_BOXES,
    MIN_SCORE,
    SAMPLE_DIR,
    SAMPLE_FIGURES,
    SAMPLE_NAMES,
    HelmetCam,
    describe,
    filter_detections,
    generate_samples,
    load_photo,
    mock_detect,
    sample_photo,
)

__all__ = [
    "DEFAULT_PROMPT",
    "MAX_BOXES",
    "MIN_SCORE",
    "SAMPLE_DIR",
    "SAMPLE_FIGURES",
    "SAMPLE_NAMES",
    "HelmetCam",
    "describe",
    "filter_detections",
    "generate_samples",
    "load_photo",
    "mock_detect",
    "sample_photo",
]
