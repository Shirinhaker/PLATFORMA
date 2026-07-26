from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import os
import signal
import socket
from typing import Any

from app.core.config import Settings
from app.db.session import Database
from app.outbox.repository import (
    claim_events,
    mark_failed,
    mark_processed,
)


Handler = Callable[[dict[str, Any]], Awaitable[None]]


async def foundation_echo(payload: dict[str, Any]) -> None:
    if payload.get("message") != "phase1":
        raise ValueError("Foundation echo payload noto‘g‘ri.")


HANDLERS: dict[str, Handler] = {
    "foundation.echo": foundation_echo,
}


async def process_batch(
    database: Database,
    worker_id: str,
    *,
    limit: int = 50,
) -> int:
    async with database.session() as session:
        async with session.begin():
            events = await claim_events(session, worker_id, limit=limit)
    for event in events:
        handler = HANDLERS.get(event.topic)
        if handler is None:
            async with database.session() as session:
                async with session.begin():
                    await mark_failed(
                        session,
                        event.id,
                        f"Ro‘yxatdan o‘tmagan topic: {event.topic}",
                    )
            continue
        try:
            await handler(event.payload)
        except Exception as exc:
            async with database.session() as session:
                async with session.begin():
                    await mark_failed(session, event.id, str(exc))
        else:
            async with database.session() as session:
                async with session.begin():
                    await mark_processed(session, event.id)
    return len(events)


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    database = Database(settings.database_url)
    await database.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    try:
        while not stop.is_set():
            count = await process_batch(database, worker_id)
            if once:
                return
            if count == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    continue
    finally:
        await database.stop()


def main() -> None:
    settings = Settings()
    once = os.environ.get("KOPRIK_WORKER_ONCE") == "1"
    asyncio.run(run_worker(settings, once=once))


if __name__ == "__main__":
    main()
