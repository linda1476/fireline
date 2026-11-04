"""Run recording / replay + input-hash memo (docs/CONTRACT.md "LIVE vs REPLAY").

RunRecorder  LIVE only: every outbound WS message {t, type, payload} and REST action {t, method, path, body}
             → data/cache/run_<ts>.jsonl
RunReplayer  re-emits a run file at 1x through the same broadcast callback ("best" → data/cache/best.jsonl).
memo(kind, payload, compute)  sha256(kind + canonical input) → cached JSON in data/cache/memo.jsonl when EARSHOT_MEMO=1.
Nothing is silently faked: a missing run file raises FileNotFoundError.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from server.config import ROOT
from server.models import WsMessage

CACHE_DIR = ROOT / "data" / "cache"
MEMO_PATH = CACHE_DIR / "memo.jsonl"


def _dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


class RunRecorder:
    def __init__(self, path: str | Path | None = None):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.path = Path(path) if path else CACHE_DIR / f"run_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        self._f = self.path.open("a", encoding="utf-8")

    def _write(self, rec: dict[str, Any]) -> None:
        if self._f.closed:
            return
        self._f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._f.flush()

    def record_ws(self, t: float, msg: WsMessage) -> None:
        if msg.type == "clock":
            return  # replay regenerates the clock
        self._write({"t": round(float(t), 3), "type": msg.type, "payload": _dump(msg.payload)})

    def record_rest(self, t: float, method: str, path: str, body: Any = None) -> None:
        self._write({"t": round(float(t), 3), "method": method, "path": path, "body": _dump(body)})

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()


def resolve_run(run: str | None) -> Path:
    if not run or run == "best":
        p = CACHE_DIR / "best.jsonl"
    else:
        p = Path(run)
        if not p.is_absolute():
            p = CACHE_DIR / p if (CACHE_DIR / p).exists() or not p.exists() else p
    if not p.exists():
        raise FileNotFoundError(f"replay run file not found: {p.name}")
    return p


def load_run(run: str | None) -> list[dict[str, Any]]:
    p = resolve_run(run)
    recs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            recs.append(json.loads(line))
    recs.sort(key=lambda r: r.get("t", 0.0))  # stable: keeps order within the same t
    return recs


# ----------------------------------------------------------------------------- run files (GET /api/runs, promote)
BEST_NAME = "best.jsonl"


def _cache_dir(cache_dir: Path | None = None) -> Path:
    return Path(cache_dir) if cache_dir is not None else CACHE_DIR


def run_t_max(path: Path) -> float:
    t_max = 0.0
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            try:
                t_max = max(t_max, float(json.loads(line).get("t", 0.0)))
            except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
                continue
    return t_max


def list_runs(cache_dir: Path | None = None) -> list[dict[str, Any]]:
    """run_*.jsonl (+ best.jsonl) newest first: {file, size, t_max, mtime, best}."""
    d = _cache_dir(cache_dir)
    if not d.exists():
        return []
    files = sorted(d.glob("run_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    best = d / BEST_NAME
    if best.exists():
        files.insert(0, best)
    return [{"file": p.name, "size": p.stat().st_size, "t_max": run_t_max(p), "mtime": p.stat().st_mtime,
             "best": p.name == BEST_NAME} for p in files]


def newest_run(cache_dir: Path | None = None) -> Path | None:
    d = _cache_dir(cache_dir)
    files = sorted(d.glob("run_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if d.exists() else []
    return files[0] if files else None


def run_file(name: str, cache_dir: Path | None = None) -> Path:
    """A run file by bare name inside the cache dir (no path traversal). Raises FileNotFoundError / ValueError."""
    if not name or Path(name).name != name or not name.endswith(".jsonl") or not name.startswith("run_"):
        raise ValueError(f"not a run file name: {name!r}")
    p = _cache_dir(cache_dir) / name
    if not p.is_file():
        raise FileNotFoundError(f"run file not found: {name}")
    return p


def promote(name: str, cache_dir: Path | None = None) -> Path:
    """Copy run_<ts>.jsonl → best.jsonl (the run REPLAY run:"best" plays)."""
    import shutil

    src = run_file(name, cache_dir)
    dst = _cache_dir(cache_dir) / BEST_NAME
    shutil.copyfile(src, dst)
    return dst


class RunReplayer:
    """Re-emit a recorded run at 1x. REST records become WS 'toast' messages {method, path, body}.

    on_t(t) is called as the replay clock advances (main uses it for state.t / clock frames)."""

    def __init__(self, run: str | None, broadcast: Callable[[WsMessage], Awaitable[None] | None], *,
                 speed: float = 1.0, clock: Callable[[], float] = time.perf_counter,
                 on_t: Callable[[float], None] | None = None):
        self.records = load_run(run)
        self.broadcast = broadcast
        self.speed = speed
        self.clock = clock
        self.on_t = on_t
        self.start_wall: float | None = None
        self.running = False
        self._task: asyncio.Task | None = None
        self.duration = max((r.get("t", 0.0) for r in self.records), default=0.0)

    def t(self) -> float:
        if self.start_wall is None:
            return 0.0
        return (self.clock() - self.start_wall) * self.speed

    async def _emit(self, msg: WsMessage) -> None:
        res = self.broadcast(msg)
        if inspect.isawaitable(res):
            await res

    async def run(self) -> None:
        self.running = True
        self.start_wall = self.clock()
        try:
            for rec in self.records:
                if not self.running:
                    break
                delay = rec.get("t", 0.0) / self.speed - (self.clock() - self.start_wall)
                if delay > 0:
                    await asyncio.sleep(delay)
                if self.on_t:
                    self.on_t(float(rec.get("t", 0.0)))
                if "type" in rec:
                    await self._emit(WsMessage(type=rec["type"], payload=rec.get("payload") or {}))
                else:
                    await self._emit(WsMessage(type="toast", payload={
                        "method": rec.get("method"), "path": rec.get("path"), "body": rec.get("body"), "t": rec.get("t")}))
        finally:
            self.running = False

    async def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


# ----------------------------------------------------------------------------- input-hash memo
def memo_enabled() -> bool:
    return os.environ.get("EARSHOT_MEMO", "0") == "1"


def memo_key(kind: str, payload: Any) -> str:
    canon = json.dumps(_dump(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((kind + "\n" + canon).encode("utf-8")).hexdigest()


_memo: dict[str, Any] | None = None


def _memo_load() -> dict[str, Any]:
    global _memo
    if _memo is None:
        _memo = {}
        if MEMO_PATH.exists():
            for line in MEMO_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                    _memo[r["key"]] = r["value"]
                except (json.JSONDecodeError, KeyError):
                    continue
    return _memo


def memo_get(kind: str, payload: Any) -> Any | None:
    if not memo_enabled() or kind == "agent":
        return None
    return _memo_load().get(memo_key(kind, payload))


def memo_put(kind: str, payload: Any, value: Any) -> None:
    if not memo_enabled() or kind == "agent":
        return
    key = memo_key(kind, payload)
    m = _memo_load()
    m[key] = _dump(value)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with MEMO_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "kind": kind, "value": m[key]}, ensure_ascii=False) + "\n")


async def memo(kind: str, payload: Any, compute: Callable[[], Awaitable[Any]] | None = None) -> Any | None:
    """Cached JSON for (kind, payload) when EARSHOT_MEMO=1; otherwise (or on miss) awaits compute() and stores it.
    kind ∈ {"transcribe", "triage"}; never "agent"."""
    hit = memo_get(kind, payload)
    if hit is not None:
        return hit
    if compute is None:
        return None
    value = await compute()
    memo_put(kind, payload, value)
    return value
