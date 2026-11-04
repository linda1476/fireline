"""Muse Spark 1.3 via the OpenAI-compatible Chat Completions protocol.

Docs: https://dev.meta.ai/docs/structured-output , https://dev.meta.ai/docs/tool-calling
Base URL https://api.meta.ai/v1, bearer MODEL_API_KEY.
"""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, ValidationError

from fireline.config import Settings, get_settings
from fireline.meta import MetaAPIError, MockMode

T = TypeVar("T", bound=BaseModel)


def _schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema in the shape Meta's response_format expects (no recursion, depth <= 10)."""
    schema = model.model_json_schema()
    return schema


def _response_format(model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": model.__name__, "schema": _schema_for(model)},
    }


class SparkClient:
    """Sync + async structured-output helper around Muse Spark."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if self.settings.mock:
            self._sync = None
            self._async = None
        else:
            self._sync = OpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=60)
            self._async = AsyncOpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=60)

    # ----------------------------------------------------------------- helpers
    def _guard(self) -> None:
        if self.settings.mock:
            raise MockMode("MODEL_API_KEY not set (or FIRELINE_MOCK=1)")

    @staticmethod
    def _parse(content: str | None, schema: type[T]) -> T:
        if not content:
            raise MetaAPIError("empty completion content")
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return schema.model_validate_json(text)

    # ------------------------------------------------------------------ async
    async def acomplete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 900,
        model: str | None = None,
        retries: int = 1,
    ) -> tuple[T, int]:
        """Return (parsed object, latency_ms). Retries once with validation feedback."""
        self._guard()
        assert self._async is not None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        t0 = time.perf_counter()
        for attempt in range(retries + 1):
            resp = await self._async.chat.completions.create(
                model=model or self.settings.spark_model,
                messages=messages,
                response_format=_response_format(schema),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            try:
                obj = self._parse(content, schema)
                return obj, int((time.perf_counter() - t0) * 1000)
            except (ValidationError, MetaAPIError, json.JSONDecodeError) as e:
                last_err = e
                messages.append({"role": "assistant", "content": content or ""})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Your JSON did not validate: {e}. Return corrected JSON only.",
                    }
                )
        raise MetaAPIError(f"structured output failed after {retries + 1} attempts: {last_err}")

    async def achat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 700,
        model: str | None = None,
    ):
        """Raw chat completion (for tool-calling agent loops). Returns the SDK response."""
        self._guard()
        assert self._async is not None
        kwargs: dict[str, Any] = dict(
            model=model or self.settings.spark_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
        return await self._async.chat.completions.create(**kwargs)

    # ------------------------------------------------------------------- sync
    def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 900,
        model: str | None = None,
        retries: int = 1,
    ) -> tuple[T, int]:
        self._guard()
        assert self._sync is not None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        t0 = time.perf_counter()
        for _ in range(retries + 1):
            resp = self._sync.chat.completions.create(
                model=model or self.settings.spark_model,
                messages=messages,
                response_format=_response_format(schema),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            try:
                obj = self._parse(content, schema)
                return obj, int((time.perf_counter() - t0) * 1000)
            except (ValidationError, MetaAPIError, json.JSONDecodeError) as e:
                last_err = e
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({"role": "user", "content": f"Your JSON did not validate: {e}. Return corrected JSON only."})
        raise MetaAPIError(f"structured output failed: {last_err}")

    def ping(self) -> str:
        """Cheap connectivity check; returns the model's one-word reply."""
        self._guard()
        assert self._sync is not None
        resp = self._sync.chat.completions.create(
            model=self.settings.spark_model,
            messages=[{"role": "user", "content": "Reply with the single word READY."}],
            max_tokens=5,
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
