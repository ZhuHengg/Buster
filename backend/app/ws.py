import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class WsHub:
    """Fan-out of CMS messages (camera.sync, detections, incident.updated) to all sockets."""

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()
        self._lock = asyncio.Lock()  # one broadcast at a time keeps message order across pipelines

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._sockets.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._sockets.discard(ws)

    async def broadcast(self, msg: dict) -> None:
        async with self._lock:
            sockets = list(self._sockets)
            if not sockets:
                return
            results = await asyncio.gather(*(ws.send_json(msg) for ws in sockets), return_exceptions=True)
            for ws, result in zip(sockets, results):
                if isinstance(result, Exception):
                    log.info("dropping websocket: %s", result)
                    self._sockets.discard(ws)
