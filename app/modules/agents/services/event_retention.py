from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.agents.models import AgentRunEvent

logger = logging.getLogger(__name__)

_worker_lock = threading.Lock()
_worker_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None


def cleanup_agent_run_events_once() -> int:
    retention_days = int(settings.AGENT_RUN_EVENTS_RETENTION_DAYS)
    if retention_days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        result = db.execute(
            delete(AgentRunEvent).where(AgentRunEvent.created_at < cutoff)
        )
        db.commit()
        return int(result.rowcount or 0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _retention_loop() -> None:
    interval_minutes = max(1, int(settings.AGENT_RUN_EVENTS_RETENTION_INTERVAL_MINUTES))
    wait_seconds = interval_minutes * 60
    logger.info(
        "agent_run_events retention worker started (days=%s, interval_minutes=%s)",
        settings.AGENT_RUN_EVENTS_RETENTION_DAYS,
        interval_minutes,
    )

    while not _worker_stop_event.is_set():
        try:
            deleted = cleanup_agent_run_events_once()
            if deleted > 0:
                logger.info("agent_run_events retention removed %s row(s)", deleted)
        except Exception:
            logger.exception("agent_run_events retention cleanup failed")

        if _worker_stop_event.wait(wait_seconds):
            break

    logger.info("agent_run_events retention worker stopped")


def start_agent_run_events_retention_worker() -> None:
    global _worker_thread
    if int(settings.AGENT_RUN_EVENTS_RETENTION_DAYS) <= 0:
        logger.info("agent_run_events retention disabled (retention_days <= 0)")
        return

    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_stop_event.clear()
        _worker_thread = threading.Thread(
            target=_retention_loop,
            name="agent-run-events-retention",
            daemon=True,
        )
        _worker_thread.start()


def stop_agent_run_events_retention_worker() -> None:
    global _worker_thread
    with _worker_lock:
        thread = _worker_thread
        if not thread:
            return
        _worker_stop_event.set()
        thread.join(timeout=5)
        _worker_thread = None
