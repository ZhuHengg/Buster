"""Playback control shared by every camera pipeline: loop the clips, or play once and hold.

The demo clips are short and loop forever, which makes it hard to see what the system did. With
loop off each camera plays its clip once and holds at the end (verification and escalation carry on).
`restart` plays the clip again from the start, and turning loop back on also resumes from the start.
"""
import asyncio
from collections.abc import Awaitable, Callable


class PlaybackControl:
    def __init__(self, on_change: Callable[[dict], Awaitable[None]] | None = None):
        self.loop = True
        self.generation = 0  # bumped by restart(): pipelines compare it to the one they started with
        self.on_change = on_change
        self._running: set[str] = set()
        self._held: set[str] = set()
        self._cond = asyncio.Condition()

    @property
    def held(self) -> bool:
        """True when every running camera has finished its pass and is holding."""
        return bool(self._running) and self._held >= self._running

    def snapshot(self) -> dict:
        return {"loop": self.loop, "held": self.held}

    async def _notify(self) -> None:
        if self.on_change is not None:
            await self.on_change(self.snapshot())

    def register(self, camera_id: str) -> None:
        self._running.add(camera_id)

    async def unregister(self, camera_id: str) -> None:
        self._running.discard(camera_id)
        self._held.discard(camera_id)
        await self._notify()

    async def set_loop(self, loop: bool) -> None:
        async with self._cond:
            self.loop = loop
            self._cond.notify_all()
        await self._notify()

    async def restart(self) -> None:
        async with self._cond:
            self.generation += 1
            self._cond.notify_all()
        await self._notify()

    async def hold(self, camera_id: str, generation: int) -> None:
        """Called by a pipeline that finished its pass with loop off. Returns when the clip should play
        again: a restart was requested, or looping was turned back on."""
        self._held.add(camera_id)
        await self._notify()
        try:
            async with self._cond:
                await self._cond.wait_for(lambda: self.loop or self.generation != generation)
        finally:
            self._held.discard(camera_id)
        await self._notify()
