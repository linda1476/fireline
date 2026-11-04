"""SAM 3.1 text-prompted detection via POST /v1/responses.

Docs: https://dev.meta.ai/docs/sam/segmenting , /docs/sam/reading-segmentation
Request: model "sam-3.1", input=[message with input_text (noun phrase) + input_image (data: URL)],
metadata {"include_confidence": "true", "mask_encoding": "one_bit"} (string values).
Response text is a token grammar, one line per frame:
  <0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600;c=0.93|><|mask;x=0;y=0;data=...|>,1<|box;...|>...
Boxes are source pixels (x2/y2 inclusive); w/h are the source size; c is confidence if requested.
We only need boxes -> normalized Detection objects. Masks are ignored.
"""

from __future__ import annotations

import re
import time
from typing import Any

from openai import AsyncOpenAI, OpenAI

from fireline.config import Settings, get_settings
from fireline.meta import MetaAPIError, MockMode
from fireline.models import Detection

_BOX_RE = re.compile(r"<\|box;([^|>]*)\|>")


def parse_sam_output(text: str, label: str = "person") -> list[Detection]:
    """Parse SAM 3.1 output_text into normalized Detection boxes."""
    dets: list[Detection] = []
    for m in _BOX_RE.finditer(text or ""):
        fields: dict[str, float] = {}
        for kv in m.group(1).split(";"):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            try:
                fields[k.strip()] = float(v)
            except ValueError:
                continue
        w = fields.get("w", 0) or 0
        h = fields.get("h", 0) or 0
        if w <= 0 or h <= 0:
            continue
        dets.append(
            Detection(
                label=label,
                score=float(fields.get("c", 1.0)),
                x0=max(0.0, fields.get("x1", 0) / w),
                y0=max(0.0, fields.get("y1", 0) / h),
                x1=min(1.0, (fields.get("x2", 0) + 1) / w),
                y1=min(1.0, (fields.get("y2", 0) + 1) / h),
            )
        )
    return dets


def _extract_text(resp: Any) -> str:
    text = getattr(resp, "output_text", None)
    if text:
        return text
    parts: list[str] = []
    for item in getattr(resp, "output", None) or []:
        for c in getattr(item, "content", None) or []:
            t = getattr(c, "text", None)
            if t:
                parts.append(t)
    return "".join(parts)


class SAMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if self.settings.mock:
            self._sync = None
            self._async = None
        else:
            self._sync = OpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=90)
            self._async = AsyncOpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=90)

    def _guard(self) -> None:
        if self.settings.mock:
            raise MockMode("MODEL_API_KEY not set (or FIRELINE_MOCK=1)")

    @staticmethod
    def _input(prompt: str, image_b64: str, mime: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{image_b64}"},
                ],
            }
        ]

    async def adetect(self, image_b64: str, *, mime: str = "image/jpeg", prompt: str = "person") -> tuple[list[Detection], int, str]:
        """Return (detections, latency_ms, raw_text)."""
        self._guard()
        assert self._async is not None
        t0 = time.perf_counter()
        raw = ""
        try:
            async with self._async.responses.stream(
                model=self.settings.sam_model,
                input=self._input(prompt, image_b64, mime),
                metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
            ) as stream:
                async for event in stream:
                    if getattr(event, "type", "") == "response.output_text.delta":
                        raw += event.delta
        except Exception as e:  # fall back to non-streaming create
            try:
                resp = await self._async.responses.create(
                    model=self.settings.sam_model,
                    input=self._input(prompt, image_b64, mime),
                    metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
                )
                raw = _extract_text(resp)
            except Exception as e2:
                raise MetaAPIError(f"SAM request failed: {e} / {e2}") from e2
        return parse_sam_output(raw, prompt), int((time.perf_counter() - t0) * 1000), raw

    def detect(self, image_b64: str, *, mime: str = "image/jpeg", prompt: str = "person") -> tuple[list[Detection], int, str]:
        self._guard()
        assert self._sync is not None
        t0 = time.perf_counter()
        resp = self._sync.responses.create(
            model=self.settings.sam_model,
            input=self._input(prompt, image_b64, mime),
            metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
        )
        raw = _extract_text(resp)
        return parse_sam_output(raw, prompt), int((time.perf_counter() - t0) * 1000), raw
