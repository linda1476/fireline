"""muse-voice-transcribe-1.0: file transcription and realtime streaming.

Docs: https://dev.meta.ai/docs/speech-to-text , https://dev.meta.ai/docs/api-reference/voice/schemas
  POST https://api.meta.ai/v1/asr/transcribe   multipart: request(JSON) + audio(WAV 16k/24k mono s16)
  WSS  wss://api.meta.ai/v1/asr/realtime        handshake JSON frame first, then raw PCM binary frames

Realtime handshake (first text frame):
  {"authorization": {"accessToken": "Bearer <key>"}, "audioEncoding": "PCM_16KHZ"|"PCM_24KHZ",
   "model": "muse-voice-transcribe-1.0", "mode": "PUSH_TO_TALK"|"ENDPOINTING"|"DIARIZATION",
   "partialMode": "CUMULATIVE"|"DELTA", "emitAudioProgress": false,
   "languageBias": ["Korean","English"], "keywords": [...]}
Server events: {"sessionId"} ack, then "type" in
  speechStart | transcript{transcript, final} | speaker{label} | speechEnd | speechComplete{turnId, transcript}
  | audioProgress | error{message}
Client end: {"type": "endStream"} then keep reading until close code 1000.
Pacing: send 80 ms frames at 1x real time INCLUDING silence; the server rejects streams
that run too far ahead (about 5 s backlog cap). No confidence scores are returned.
See research/smoke_b1.md for measured turn latencies and the PTT end-of-turn message.
"""

from __future__ import annotations

import asyncio
import json
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import websockets

from server.config import Settings, get_settings, load_keywords
from server.meta import MetaAPIError, NoAPIKey

# smoke_b1.md: ["Korean"] alone is best for Korean audio (adding English caused stuttered duplicates);
# keywords must be ON for Korean (긴급탈출 survives AMR degradation only with keywords).
LANGUAGE_BIAS = {"ko": ["Korean"], "en": ["English"]}
DEFAULT_LANGUAGE_BIAS = LANGUAGE_BIAS["ko"]
FRAME_MS = 80


def language_bias_for(lang: str) -> list[str]:
    return LANGUAGE_BIAS.get(lang, DEFAULT_LANGUAGE_BIAS)


@dataclass
class Turn:
    text: str
    speaker: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


@dataclass
class TranscribeResult:
    text: str
    turns: list[Turn] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    audio_duration_ms: int | None = None
    latency_ms: int = 0


def wav_info(path: str | Path) -> tuple[int, int, int]:
    """(sample_rate, channels, sample_width_bytes). Raises if not a RIFF WAV."""
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth()


def read_pcm(path: str | Path, sample_rate: int = 16000) -> bytes:
    rate, ch, width = wav_info(path)
    if rate != sample_rate or ch != 1 or width != 2:
        raise MetaAPIError(f"WAV {path} must be {sample_rate} Hz mono s16 (got {rate}/{ch}/{width}). "
                           "Convert: ffmpeg -i in -ac 1 -ar 16000 -sample_fmt s16 out.wav")
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def silence(seconds: float, sample_rate: int = 16000) -> bytes:
    return b"\x00\x00" * int(seconds * sample_rate)


def _parse_transcribe_json(data: dict[str, Any]) -> TranscribeResult:
    turns: list[Turn] = []
    for t in data.get("turns") or []:
        turns.append(Turn(text=t.get("transcript") or t.get("text") or "", speaker=t.get("speaker"),
                          start_ms=t.get("startMs"), end_ms=t.get("endMs")))
    text = data.get("transcript") or data.get("text") or " ".join(t.text for t in turns)
    return TranscribeResult(text=text.strip(), turns=turns, raw=data, session_id=data.get("sessionId"),
                            audio_duration_ms=data.get("audioDurationMs"))


class ASRClient:
    """File endpoint (eval, per-transmission fallback)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _guard(self) -> None:
        if self.settings.mock:
            raise NoAPIKey("MODEL_API_KEY not set")

    async def transcribe_file(
        self,
        wav_path: str | Path,
        *,
        lang: str = "ko",
        mode: str = "PUSH_TO_TALK",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,   # None = project default list for `lang`; [] = send no keywords
        timeout: float = 60.0,
    ) -> TranscribeResult:
        import time

        self._guard()
        rate, ch, width = wav_info(wav_path)
        if ch != 1 or width != 2 or rate not in (16000, 24000):
            raise MetaAPIError(f"WAV must be mono 16-bit at 16k/24k; got rate={rate} ch={ch} width={width}")
        request: dict[str, Any] = {
            "model": self.settings.asr_model,
            "audioEncoding": "WAV",
            "mode": mode,
            "languageBias": language_bias or language_bias_for(lang),
        }
        kw = load_keywords(lang) if keywords is None else keywords
        if kw:
            request["keywords"] = kw
        session_id = f"file-{uuid.uuid4()}"
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(wav_path, "rb") as f:
                resp = await client.post(
                    self.settings.asr_transcribe_url,
                    params={"sessionId": session_id},
                    headers={"Authorization": f"Bearer {self.settings.api_key}", "Accept": "application/json"},
                    files={"request": (None, json.dumps(request), "application/json"),
                           "audio": (Path(wav_path).name, f, "audio/wav")},
                )
        if resp.status_code != 200:
            raise MetaAPIError(f"transcribe {resp.status_code}: {resp.text[:300]} (session {session_id})")
        result = _parse_transcribe_json(resp.json())
        result.session_id = result.session_id or session_id
        result.latency_ms = int((time.perf_counter() - t0) * 1000)
        return result


EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class RealtimeTranscriber:
    """One realtime ASR session (one per radio channel, or one per crew PTT hold).

    Usage::
        rt = RealtimeTranscriber(on_event=handle)
        await rt.connect(mode="ENDPOINTING")
        await rt.send_audio(pcm_bytes)   # 80 ms frames, paced at 1x
        await rt.close()
    Events are passed through verbatim (dicts) plus "_recv_ts" (perf_counter seconds).
    """

    def __init__(self, on_event: EventCallback, settings: Settings | None = None, *, sample_rate: int = 16000):
        self.settings = settings or get_settings()
        self.on_event = on_event
        self.sample_rate = sample_rate
        if sample_rate not in (16000, 24000):
            raise ValueError("sample_rate must be 16000 or 24000")
        self.session_id = f"live-{uuid.uuid4()}"
        self._ws: Any = None
        self._reader: asyncio.Task | None = None
        self.closed = asyncio.Event()
        self.error: str | None = None

    def _guard(self) -> None:
        if self.settings.mock:
            raise NoAPIKey("MODEL_API_KEY not set")

    async def connect(
        self,
        *,
        lang: str = "ko",
        mode: str = "ENDPOINTING",
        partial_mode: str = "CUMULATIVE",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> str:
        self._guard()
        uri = f"{self.settings.asr_ws_url}?sessionId={self.session_id}"
        self._ws = await websockets.connect(uri, open_timeout=30, max_size=None)
        handshake: dict[str, Any] = {
            "authorization": {"accessToken": f"Bearer {self.settings.api_key}"},
            "audioEncoding": "PCM_16KHZ" if self.sample_rate == 16000 else "PCM_24KHZ",
            "model": self.settings.asr_model,
            "mode": mode,
            "partialMode": partial_mode,
            "emitAudioProgress": False,
            "languageBias": language_bias or language_bias_for(lang),
        }
        kw = load_keywords(lang) if keywords is None else keywords
        if kw:
            handshake["keywords"] = kw
        await self._ws.send(json.dumps(handshake))
        ack_raw = await asyncio.wait_for(self._ws.recv(), timeout=15)
        ack = json.loads(ack_raw) if isinstance(ack_raw, (str, bytes)) else ack_raw
        if not isinstance(ack, dict) or "sessionId" not in ack:
            raise MetaAPIError(f"ASR handshake failed: {ack!r}")
        self.session_id = ack["sessionId"]
        self._reader = asyncio.create_task(self._read_loop())
        return self.session_id

    async def _read_loop(self) -> None:
        import time

        try:
            async for msg in self._ws:
                if isinstance(msg, bytes):
                    continue
                try:
                    event = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                event["_recv_ts"] = time.perf_counter()
                if event.get("type") == "error":
                    self.error = event.get("message")
                res = self.on_event(event)
                if asyncio.iscoroutine(res):
                    await res
        except websockets.ConnectionClosed as e:
            if e.code not in (1000, None):
                self.error = self.error or f"ASR socket closed {e.code}: {e.reason}"
        finally:
            self.closed.set()

    async def send_audio(self, pcm: bytes) -> None:
        if self._ws is None:
            raise MetaAPIError("not connected")
        await self._ws.send(pcm)

    async def stream_pcm(self, pcm: bytes, *, realtime: bool = True, t0: float | None = None) -> None:
        """Send PCM in 80 ms frames paced against wall clock (drift-free), including silence."""
        import time

        frame = self.sample_rate * FRAME_MS // 1000 * 2
        start = t0 if t0 is not None else time.perf_counter()
        n = 0
        for i in range(0, len(pcm), frame):
            await self.send_audio(pcm[i:i + frame])
            n += 1
            if realtime:
                target = start + n * FRAME_MS / 1000
                delay = target - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)

    async def end_stream(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "endStream"}))
            except websockets.ConnectionClosed:
                pass

    async def close(self, wait: float = 10.0) -> None:
        await self.end_stream()
        try:
            await asyncio.wait_for(self.closed.wait(), timeout=wait)
        except asyncio.TimeoutError:
            pass
        if self._ws is not None:
            await self._ws.close()
        if self._reader is not None:
            self._reader.cancel()
