"""Muse Voice Transcribe 1.0 — file transcription and realtime streaming.

Docs: https://dev.meta.ai/docs/speech-to-text
  POST https://api.meta.ai/v1/asr/transcribe   multipart: request(JSON) + audio(WAV 16k/24k mono s16)
  WSS  wss://api.meta.ai/v1/asr/realtime        handshake JSON frame first, then raw PCM binary frames

Realtime handshake (first text frame):
  {"authorization": {"accessToken": "Bearer <key>"}, "audioEncoding": "PCM_16KHZ"|"PCM_24KHZ",
   "model": "muse-voice-transcribe-1.0", "mode": "PUSH_TO_TALK"|"ENDPOINTING"|"DIARIZATION",
   "partialMode": "CUMULATIVE"|"DELTA", "emitAudioProgress": false,
   "languageBias": ["English"], "keywords": ["mayday", "stairwell"]}
Server events: {"sessionId"} ack, then type in
  speechStart | transcript{transcript, final} | speaker{label} | speechEnd | speechComplete{turnId, transcript}
  | audioProgress | error{message}
Client end: {"type": "endStream"} then keep reading until close code 1000.
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

from fireline.config import Settings, get_settings
from fireline.meta import MetaAPIError, MockMode

DEFAULT_KEYWORDS = [
    "mayday", "stairwell A", "stairwell B", "RIT", "SCBA", "low air", "PAR",
    "Command", "Engine 1", "Ladder 2", "Rescue 3", "staging", "collapse",
    "unit 302", "unit 404", "unit 504", "victim", "lobby", "corridor",
]


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


def wav_info(path: str | Path) -> tuple[int, int, int]:
    """(sample_rate, channels, sample_width_bytes). Raises if not a RIFF WAV."""
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth()


def _parse_transcribe_json(data: dict[str, Any]) -> TranscribeResult:
    """Defensive parse — the schema page lists transcript + turns[speaker,startMs,endMs]."""
    turns: list[Turn] = []
    for t in data.get("turns") or []:
        text = t.get("transcript") or t.get("text") or ""
        turns.append(
            Turn(
                text=text,
                speaker=t.get("speaker"),
                start_ms=t.get("startMs"),
                end_ms=t.get("endMs"),
            )
        )
    text = data.get("transcript") or data.get("text") or " ".join(t.text for t in turns)
    return TranscribeResult(text=text.strip(), turns=turns, raw=data, session_id=data.get("sessionId"))


class ASRClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _guard(self) -> None:
        if self.settings.mock:
            raise MockMode("MODEL_API_KEY not set (or FIRELINE_MOCK=1)")

    # ------------------------------------------------------------- file mode
    async def transcribe_file(
        self,
        wav_path: str | Path,
        *,
        mode: str = "PUSH_TO_TALK",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,
        timeout: float = 60.0,
    ) -> TranscribeResult:
        self._guard()
        rate, ch, width = wav_info(wav_path)
        if ch != 1 or width != 2 or rate not in (16000, 24000):
            raise MetaAPIError(
                f"WAV must be mono 16-bit at 16k/24k; got rate={rate} ch={ch} width={width}. "
                "Convert with: ffmpeg -i in.wav -ac 1 -ar 16000 -sample_fmt s16 out.wav"
            )
        request: dict[str, Any] = {
            "model": self.settings.asr_model,
            "audioEncoding": "WAV",
            "mode": mode,
            "languageBias": language_bias or ["English"],
            "keywords": keywords or DEFAULT_KEYWORDS,
        }
        session_id = f"file-{uuid.uuid4()}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(wav_path, "rb") as f:
                resp = await client.post(
                    self.settings.asr_transcribe_url,
                    params={"sessionId": session_id},
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Accept": "application/json",
                    },
                    files={
                        "request": (None, json.dumps(request), "application/json"),
                        "audio": (Path(wav_path).name, f, "audio/wav"),
                    },
                )
        if resp.status_code != 200:
            raise MetaAPIError(f"transcribe {resp.status_code}: {resp.text[:300]} (session {session_id})")
        result = _parse_transcribe_json(resp.json())
        result.session_id = result.session_id or session_id
        return result

    def transcribe_file_sync(self, wav_path: str | Path, **kw) -> TranscribeResult:
        return asyncio.run(self.transcribe_file(wav_path, **kw))


EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class RealtimeTranscriber:
    """One realtime ASR session. Feed PCM s16le mono bytes; events go to the callback.

    Usage::

        rt = RealtimeTranscriber(on_event=handle)
        await rt.connect(mode="ENDPOINTING")
        await rt.send_audio(pcm_bytes)   # pace at ~real time, <= 5 s ahead
        await rt.close()
    """

    def __init__(
        self,
        on_event: EventCallback,
        settings: Settings | None = None,
        *,
        sample_rate: int = 16000,
    ):
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
            raise MockMode("MODEL_API_KEY not set (or FIRELINE_MOCK=1)")

    async def connect(
        self,
        *,
        mode: str = "ENDPOINTING",
        partial_mode: str = "CUMULATIVE",
        language_bias: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> str:
        self._guard()
        uri = f"{self.settings.asr_ws_url}?sessionId={self.session_id}"
        self._ws = await websockets.connect(uri, open_timeout=30, max_size=None)
        handshake = {
            "authorization": {"accessToken": f"Bearer {self.settings.api_key}"},
            "audioEncoding": "PCM_16KHZ" if self.sample_rate == 16000 else "PCM_24KHZ",
            "model": self.settings.asr_model,
            "mode": mode,
            "partialMode": partial_mode,
            "emitAudioProgress": False,
            "languageBias": language_bias or ["English"],
            "keywords": keywords or DEFAULT_KEYWORDS,
        }
        await self._ws.send(json.dumps(handshake))
        ack_raw = await asyncio.wait_for(self._ws.recv(), timeout=15)
        ack = json.loads(ack_raw) if isinstance(ack_raw, (str, bytes)) else ack_raw
        if not isinstance(ack, dict) or "sessionId" not in ack:
            raise MetaAPIError(f"ASR handshake failed: {ack!r}")
        self.session_id = ack["sessionId"]
        self._reader = asyncio.create_task(self._read_loop())
        return self.session_id

    async def _read_loop(self) -> None:
        try:
            async for msg in self._ws:
                if isinstance(msg, bytes):
                    continue
                try:
                    event = json.loads(msg)
                except json.JSONDecodeError:
                    continue
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


class MicStreamer:
    """Capture the default microphone as PCM s16le mono and push to a RealtimeTranscriber.

    Runs sounddevice's callback thread -> asyncio queue -> websocket. 80 ms frames.
    """

    def __init__(self, transcriber: RealtimeTranscriber, *, device: int | str | None = None):
        self.rt = transcriber
        self.device = device
        self.sample_rate = transcriber.sample_rate
        self.frame_samples = self.sample_rate * 80 // 1000
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: Any = None
        self._pump: asyncio.Task | None = None
        self.running = False

    def _callback(self, indata, frames, time_info, status) -> None:  # sounddevice thread
        if self._loop is None:
            return
        data = bytes(indata)
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, data)
        except RuntimeError:
            pass

    async def start(self) -> None:
        import sounddevice as sd  # imported lazily: needs PortAudio

        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.frame_samples,
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()
        self.running = True
        self._pump = asyncio.create_task(self._pump_loop())

    async def _pump_loop(self) -> None:
        while self.running:
            chunk = await self._queue.get()
            try:
                await self.rt.send_audio(chunk)
            except Exception:
                self.running = False
                break

    async def stop(self) -> None:
        self.running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        if self._pump is not None:
            self._pump.cancel()


async def stream_wav_file(rt: RealtimeTranscriber, wav_path: str | Path, *, realtime: bool = True) -> None:
    """Push a 16k/24k mono s16 WAV through a connected RealtimeTranscriber, paced at ~1x."""
    rate, ch, width = wav_info(wav_path)
    if rate != rt.sample_rate or ch != 1 or width != 2:
        raise MetaAPIError(f"WAV {wav_path} must be {rt.sample_rate} Hz mono s16")
    frame = rate * 80 // 1000 * 2
    with wave.open(str(wav_path), "rb") as w:
        while True:
            chunk = w.readframes(frame // 2)
            if not chunk:
                break
            await rt.send_audio(chunk)
            if realtime:
                await asyncio.sleep(0.08)
