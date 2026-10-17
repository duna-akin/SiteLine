"""In-process event bus streamed to the browser over Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

_subscribers: set[asyncio.Queue[str]] = set()


def publish(event: str, data: dict) -> None:
    message = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    for q in list(_subscribers):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            pass


async def stream() -> AsyncIterator[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
    _subscribers.add(q)
    try:
        yield "event: hello\ndata: {}\n\n"
        while True:
            try:
                yield await asyncio.wait_for(q.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _subscribers.discard(q)
