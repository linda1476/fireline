"""muse-spark-1.3 via the OpenAI-compatible Chat Completions / Responses protocols.

Docs: https://dev.meta.ai/docs/structured-output , https://dev.meta.ai/docs/tool-calling ,
      https://dev.meta.ai/docs/reasoning . Base URL https://api.meta.ai/v1, bearer MODEL_API_KEY.

Observed 2026-11-04: Spark is a reasoning model (default effort "high"); reasoning tokens
count against max_tokens, so a small max_tokens returns EMPTY content. Always pass
reasoning_effort (default "low") and max_tokens >= 3000.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, ValidationError

from server.config import Settings, get_settings
from server.meta import MetaAPIError, NoAPIKey

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("earshot.spark")


def _truncated(resp: Any) -> bool:
    try:
        return resp.choices[0].finish_reason == "length"
    except Exception:
        return False


def usage_dict(resp: Any) -> dict[str, Any]:
    try:
        usage = resp.usage.model_dump() if resp.usage else {}
        details = usage.get("completion_tokens_details") or {}
        return {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": details.get("reasoning_tokens"),
        }
    except Exception:
        return {}


def response_format(name: str, schema: dict[str, Any], strict: bool = True) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": strict, "schema": schema}}


class SparkClient:
    """Structured-output helper + raw access to the SDK clients (for the Responses agent)."""

    def __init__(self, settings: Settings | None = None, timeout: float = 60):
        self.settings = settings or get_settings()
        if self.settings.mock:
            self._sync = None
            self._async = None
        else:
            self._sync = OpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=timeout)
            self._async = AsyncOpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key, timeout=timeout)

    @property
    def async_client(self) -> AsyncOpenAI:
        self._guard()
        assert self._async is not None
        return self._async

    @property
    def sync_client(self) -> OpenAI:
        self._guard()
        assert self._sync is not None
        return self._sync

    def _guard(self) -> None:
        if self.settings.mock:
            raise NoAPIKey("MODEL_API_KEY not set")

    @staticmethod
    def parse(content: str | None, schema: type[T]) -> T:
        if not content:
            raise MetaAPIError("empty completion content")
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return schema.model_validate_json(text)

    async def acomplete_json(
        self,
        system: str,
        user: str,
        model_cls: type[T],
        json_schema: dict[str, Any],
        *,
        schema_name: str = "radio_event",
        strict: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        retries: int = 1,
        reasoning_effort: str | None = None,
    ) -> tuple[T, int, dict[str, Any]]:
        """Return (parsed, latency_ms, usage). Retries once with validation feedback,
        or with a doubled budget when the answer was truncated."""
        self._guard()
        assert self._async is not None
        effort = reasoning_effort or self.settings.reasoning_effort
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        t0 = time.perf_counter()
        resp: Any = None
        for attempt in range(retries + 1):
            resp = await self._async.chat.completions.create(
                model=self.settings.spark_model,
                messages=messages,
                response_format=response_format(schema_name, json_schema, strict),
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=effort,
            )
            content = resp.choices[0].message.content
            try:
                obj = self.parse(content, model_cls)
                return obj, int((time.perf_counter() - t0) * 1000), usage_dict(resp)
            except (ValidationError, MetaAPIError, json.JSONDecodeError) as e:
                last_err = e
                log.warning("spark parse failure attempt=%d finish=%s usage=%s content=%r err=%s",
                            attempt, getattr(resp.choices[0], "finish_reason", None), usage_dict(resp),
                            (content or "")[:200], str(e)[:200])
                if _truncated(resp):
                    max_tokens = max(max_tokens * 2, 6000)
                    continue
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({"role": "user", "content": f"Your JSON did not validate: {e}. Return corrected JSON only."})
        raise MetaAPIError(f"structured output failed after {retries + 1} attempts: {last_err}")

    def complete_json(self, *args: Any, **kwargs: Any) -> tuple[Any, int, dict[str, Any]]:
        """Sync convenience for scripts ONLY (asyncio.run); inside a running loop use acomplete_json."""
        import asyncio

        return asyncio.run(self.acomplete_json(*args, **kwargs))

    def ping(self) -> str:
        """Cheap connectivity check; returns the model's one-word reply."""
        self._guard()
        assert self._sync is not None
        resp = self._sync.chat.completions.create(
            model=self.settings.spark_model,
            messages=[{"role": "user", "content": "Reply with the single word READY."}],
            max_tokens=400,
            temperature=0,
            reasoning_effort="low",
        )
        return (resp.choices[0].message.content or "").strip()
