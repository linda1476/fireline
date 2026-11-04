"""WebSocket hub: fan-out of :class:`~fireline.models.WsMessage` to every connected client.

The hub never raises into the pipeline: a dead socket is dropped on the first failed
send. In-process listeners (``subscribe``) receive every message too, which is how
``fireline.demo`` and the tests observe traffic without a socket.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional

from pydantic import BaseModel

from fireline.models import WsMessage

log = logging.getLogger("fireline.server")

Listener = Callable[[WsMessage], Optional[Awaitable[None]]]
SnapshotFn = Callable[[], dict]


def to_payload(obj: Any) -> dict:
    """JSON-safe dict for a pydantic model (or pass a dict through)."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return dict(obj)


def message(kind: str, payload: Any) -> WsMessage:
    """Build a :class:`WsMessage` of ``kind`` from a model or dict."""
    return WsMessage(type=kind, payload=to_payload(payload))


class Hub:
    """Set of live WebSocket clients plus in-process listeners.

    ``snapshot_fn`` returns the *current* world-state dict; it is a callable (not a
    WorldModel) because a scenario reset replaces the model behind it.
    """

    def __init__(self, snapshot_fn: SnapshotFn | None = None):
        self.snapshot_fn: SnapshotFn = snapshot_fn or (lambda: {})
        self._clients: set[Any] = set()
        self._listeners: list[Listener] = []
        self.sent = 0

    # ------------------------------------------------------------ clients
    @property
    def clients(self) -> list[Any]:
        return list(self._clients)

    def __len__(self) -> int:
        return len(self._clients)

    async def connect(self, ws: Any) -> None:
        """Accept the socket and register it (the caller runs the receive loop)."""
        await ws.accept()
        self._clients.add(ws)
        log.info("ws client connected (%d online)", len(self._clients))

    def disconnect(self, ws: Any) -> None:
        if ws in self._clients:
            self._clients.discard(ws)
            log.info("ws client disconnected (%d online)", len(self._clients))

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Register an in-process listener; returns an unsubscribe function."""
        self._listeners.append(listener)

        def _off() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _off

    # ------------------------------------------------------------ sending
    async def send(self, ws: Any, msg: WsMessage) -> bool:
        """Send one message to one socket; False (and dropped) if it failed."""
        try:
            await ws.send_text(msg.model_dump_json())
            return True
        except Exception as e:  # noqa: BLE001 - any transport error drops the client
            log.debug("ws send failed (%s); dropping client", e)
            self.disconnect(ws)
            return False

    async def send_state(self, ws: Any) -> bool:
        """Send the full ``state`` snapshot to one socket (what a client gets on connect)."""
        return await self.send(ws, message("state", self.snapshot_fn()))

    async def broadcast(self, msg: WsMessage) -> int:
        """Deliver ``msg`` to every client and listener; returns how many sockets got it."""
        self.sent += 1
        for listener in list(self._listeners):
            try:
                res = listener(msg)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:  # noqa: BLE001
                log.exception("hub listener failed")
        clients = list(self._clients)
        if not clients:
            return 0
        results = await asyncio.gather(*(self.send(ws, msg) for ws in clients))
        return sum(1 for ok in results if ok)

    async def broadcast_many(self, msgs: Iterable[WsMessage]) -> None:
        for m in msgs:
            await self.broadcast(m)
