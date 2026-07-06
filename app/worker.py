"""Background worker process. Runs the sync + cron jobs on a schedule, separate
from the API process. Start with:  python -m app.worker
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .workers import auto_closer, conversations, microview, notion_sync, notion_writeback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("worker")


async def _job(name, coro_fn):
    try:
        result = await coro_fn()
        log.info("%s -> %s", name, result)
    except Exception:  # keep the scheduler alive across a single failed tick
        log.exception("%s failed", name)


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler()
    sched.add_job(lambda: asyncio.ensure_future(_job("notion_sync", notion_sync.run_once)),
                  "interval", seconds=settings.sync_interval_seconds, id="notion_sync")
    sched.add_job(lambda: asyncio.ensure_future(_job("auto_closer", auto_closer.run_once)),
                  "interval", seconds=settings.autocloser_interval_seconds, id="auto_closer")
    sched.add_job(lambda: asyncio.ensure_future(_job("conversations", conversations.run_once)),
                  "interval", seconds=settings.conversations_interval_seconds, id="conversations")
    sched.add_job(lambda: asyncio.ensure_future(_job("microview", microview.run_once)),
                  "interval", hours=24, id="microview")
    # Outbox flush: refreshes the rollup queue then sends — but ONLY when
    # NOTION_WRITE_ENABLED=true; disabled (default) it just reports queue depth.
    sched.add_job(lambda: asyncio.ensure_future(_job("notion_writeback", notion_writeback.run_once)),
                  "interval", seconds=settings.writeback_flush_seconds, id="notion_writeback")
    return sched


async def main():
    sched = build_scheduler()
    sched.start()
    log.info("worker started: sync=%ss autoclose=%ss conv=%ss",
             settings.sync_interval_seconds, settings.autocloser_interval_seconds,
             settings.conversations_interval_seconds)
    # Run one sync immediately so a fresh DB isn't empty for 2 minutes.
    await _job("notion_sync", notion_sync.run_once)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
