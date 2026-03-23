from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.agents.config import get_agent_config
from app.modules.agents.models import AgentRun, AgentRunEvent
from app.modules.agents.runtime import AgentRuntime
from app.modules.agents.schemas.api import (
    AgentQueryRequest,
    AgentRunCancelOut,
    AgentRunEventOut,
    AgentRunListOut,
    AgentRunStartOut,
    AgentRunStartRequest,
    AgentRunStatusOut,
)
from app.modules.agents.services.context_builder import build_runtime_context

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"
TERMINAL_STATUSES = {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_CANCELLED}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _load_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _append_event(
    db: Session,
    *,
    run_pk_id: int,
    event_type: str,
    payload: dict | None = None,
) -> AgentRunEvent:
    row = AgentRunEvent(
        run_pk_id=run_pk_id,
        event_type=event_type,
        payload_json=_dump_json(payload or {}),
    )
    db.add(row)
    db.flush()
    return row


def _persist_stream_delta(*, run_pk_id: int, accumulated: str) -> bool:
    stream_db = SessionLocal()
    try:
        row = stream_db.get(AgentRun, run_pk_id)
        if row is None:
            return False
        if row.status in TERMINAL_STATUSES:
            return False
        if row.cancel_requested:
            return False
        row.partial_answer = accumulated
        row.updated_at = _utcnow()
        stream_db.commit()
        return True
    except Exception:
        stream_db.rollback()
        # Do not crash the whole run because of transient streaming I/O failure.
        return True
    finally:
        stream_db.close()


def _to_event_out(row: AgentRunEvent) -> AgentRunEventOut:
    return AgentRunEventOut(
        id=int(row.id),
        event_type=row.event_type,
        payload=_load_json(row.payload_json),
        created_at=row.created_at or _utcnow(),
    )


def _to_status_out(db: Session, row: AgentRun) -> AgentRunStatusOut:
    latest_event_id = db.scalar(
        select(func.max(AgentRunEvent.id)).where(AgentRunEvent.run_pk_id == row.id)
    )
    return AgentRunStatusOut(
        run_id=row.run_id,
        status=row.status,  # type: ignore[arg-type]
        thread_id=row.thread_id,
        session_id=row.session_id,
        request_id=row.request_id,
        message=row.message,
        locale=row.locale,
        execution_mode=row.execution_mode,  # type: ignore[arg-type]
        model_tier=row.model_tier,
        cancel_requested=bool(row.cancel_requested),
        partial_answer=row.partial_answer,
        final_answer=row.final_answer,
        error_message=row.error_message,
        result=_load_json(row.result_json),
        latest_event_id=int(latest_event_id) if latest_event_id is not None else None,
        created_at=row.created_at or _utcnow(),
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _build_worker_user(row: AgentRun) -> SimpleNamespace:
    return SimpleNamespace(
        id=int(row.user_id or 0),
        tenant_id=int(row.tenant_id),
        email="",
        full_name="",
        avatar_url=None,
        auth_provider="password",
        is_active=True,
        workspace_key=row.workspace_key,
    )


class _AgentRunExecutor:
    _lock = threading.Lock()
    _executor: ThreadPoolExecutor | None = None

    @classmethod
    def submit(cls, run_id: str) -> None:
        with cls._lock:
            if cls._executor is None:
                cls._executor = ThreadPoolExecutor(
                    max_workers=4,
                    thread_name_prefix="agent-runner",
                )
        cls._executor.submit(_execute_run_worker, run_id)


def _execute_run_worker(run_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))
        if row is None:
            return

        if row.status in TERMINAL_STATUSES:
            return

        if row.cancel_requested:
            row.status = RUN_STATUS_CANCELLED
            row.finished_at = _utcnow()
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="cancelled",
                payload={"status": RUN_STATUS_CANCELLED},
            )
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="done",
                payload={"status": RUN_STATUS_CANCELLED},
            )
            db.commit()
            return

        row.status = RUN_STATUS_RUNNING
        row.started_at = _utcnow()
        row.error_message = None
        _append_event(
            db,
            run_pk_id=int(row.id),
            event_type="status",
            payload={"status": RUN_STATUS_RUNNING},
        )
        db.commit()

        payload = AgentQueryRequest(
            message=row.message,
            thread_id=row.thread_id,
            session_id=row.session_id,
            locale=row.locale,
            execution_mode=row.execution_mode,  # type: ignore[arg-type]
            model_tier=row.model_tier,  # type: ignore[arg-type]
        )
        runtime = AgentRuntime(db)
        streamed_chunks: list[str] = []
        last_flushed_length = 0
        last_flush_at = monotonic()

        def on_answer_delta(delta_text: str) -> bool:
            nonlocal last_flushed_length, last_flush_at
            if not delta_text:
                return True
            streamed_chunks.append(delta_text)
            accumulated = "".join(streamed_chunks)
            now = monotonic()
            should_flush = (
                len(accumulated) - last_flushed_length >= 120
                or (now - last_flush_at) >= 0.45
                or delta_text.endswith(("\n", ".", "!", "?"))
            )
            if not should_flush:
                return True
            persisted = _persist_stream_delta(
                run_pk_id=int(row.id),
                accumulated=accumulated,
            )
            if persisted:
                last_flushed_length = len(accumulated)
                last_flush_at = now
            return persisted

        result = runtime.run_query(
            payload=payload,
            current_user=_build_worker_user(row),
            on_answer_delta=on_answer_delta,
        )

        if streamed_chunks:
            accumulated = "".join(streamed_chunks)
            if len(accumulated) > last_flushed_length:
                _persist_stream_delta(
                    run_pk_id=int(row.id),
                    accumulated=accumulated,
                )

        db.refresh(row)

        if row.cancel_requested:
            row.status = RUN_STATUS_CANCELLED
            row.finished_at = _utcnow()
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="cancelled",
                payload={"status": RUN_STATUS_CANCELLED},
            )
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="done",
                payload={"status": RUN_STATUS_CANCELLED},
            )
            db.commit()
            return

        final_answer = str(result.final_answer or "")

        result_payload = result.model_dump(mode="json")
        row.request_id = result.request_id
        row.thread_id = result.thread_id
        row.session_id = result.session_id
        row.partial_answer = final_answer
        row.final_answer = final_answer
        row.result_json = _dump_json(result_payload)
        row.status = RUN_STATUS_COMPLETED
        row.finished_at = _utcnow()
        _append_event(
            db,
            run_pk_id=int(row.id),
            event_type="result",
            payload={"response": result_payload},
        )
        _append_event(
            db,
            run_pk_id=int(row.id),
            event_type="status",
            payload={"status": RUN_STATUS_COMPLETED},
        )
        _append_event(
            db,
            run_pk_id=int(row.id),
            event_type="done",
            payload={"status": RUN_STATUS_COMPLETED},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        row = db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))
        if row is not None:
            row.status = RUN_STATUS_FAILED
            row.error_message = str(exc)
            row.finished_at = _utcnow()
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="error",
                payload={"message": str(exc)},
            )
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="status",
                payload={"status": RUN_STATUS_FAILED},
            )
            _append_event(
                db,
                run_pk_id=int(row.id),
                event_type="done",
                payload={"status": RUN_STATUS_FAILED},
            )
            db.commit()
    finally:
        db.close()


@dataclass
class AgentRunService:
    db: Session

    def start_run(
        self, *, payload: AgentRunStartRequest, current_user
    ) -> AgentRunStartOut:
        config = get_agent_config()
        runtime_context = build_runtime_context(
            db=self.db,
            current_user=current_user,
            payload=AgentQueryRequest(**payload.model_dump(mode="json")),
            config=config,
        )
        now = _utcnow()
        run_row = AgentRun(
            run_id=f"run_{uuid4().hex}",
            tenant_id=int(runtime_context["tenant_id"]),
            user_id=int(runtime_context["user_id"]),
            request_id=str(runtime_context["request_id"]),
            thread_id=str(runtime_context["thread_id"]),
            session_id=str(runtime_context["session_id"]),
            workspace_key=str(getattr(current_user, "workspace_key", "personal")),
            status=RUN_STATUS_QUEUED,
            execution_mode=str(runtime_context["execution_mode"]),
            model_tier=str(payload.model_tier),
            message=payload.message,
            locale=payload.locale,
            cancel_requested=False,
            created_at=now,
            updated_at=now,
            runtime_context_json=_dump_json(runtime_context),
        )
        self.db.add(run_row)
        self.db.flush()
        _append_event(
            self.db,
            run_pk_id=int(run_row.id),
            event_type="status",
            payload={"status": RUN_STATUS_QUEUED},
        )
        self.db.commit()
        _AgentRunExecutor.submit(run_row.run_id)
        return AgentRunStartOut(
            run_id=run_row.run_id,
            status=RUN_STATUS_QUEUED,
            thread_id=run_row.thread_id,
            session_id=run_row.session_id,
            created_at=run_row.created_at or now,
        )

    def get_run(self, *, run_id: str, current_user) -> AgentRunStatusOut:
        row = self._get_owned_run(run_id=run_id, current_user=current_user)
        return _to_status_out(self.db, row)

    def list_active_runs(self, *, current_user, limit: int = 10) -> AgentRunListOut:
        rows = self.db.scalars(
            select(AgentRun)
            .where(
                AgentRun.user_id == int(getattr(current_user, "id")),
                AgentRun.tenant_id == int(getattr(current_user, "tenant_id")),
                AgentRun.status.in_([RUN_STATUS_QUEUED, RUN_STATUS_RUNNING]),
            )
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(max(1, min(limit, 50)))
        ).all()
        return AgentRunListOut(items=[_to_status_out(self.db, row) for row in rows])

    def list_runs_history(
        self,
        *,
        current_user,
        limit: int = 100,
        workspace_key: str | None = None,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> AgentRunListOut:
        query = select(AgentRun).where(
            AgentRun.user_id == int(getattr(current_user, "id")),
            AgentRun.tenant_id == int(getattr(current_user, "tenant_id")),
        )

        normalized_workspace = (workspace_key or "").strip()
        if normalized_workspace:
            query = query.where(AgentRun.workspace_key == normalized_workspace)

        normalized_session = (session_id or "").strip()
        if normalized_session:
            query = query.where(AgentRun.session_id == normalized_session)

        normalized_thread = (thread_id or "").strip()
        if normalized_thread:
            query = query.where(AgentRun.thread_id == normalized_thread)

        rows = self.db.scalars(
            query.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(
                max(1, min(limit, 500))
            )
        ).all()

        return AgentRunListOut(items=[_to_status_out(self.db, row) for row in rows])

    def cancel_run(self, *, run_id: str, current_user) -> AgentRunCancelOut:
        row = self._get_owned_run(run_id=run_id, current_user=current_user)
        if row.status in TERMINAL_STATUSES:
            return AgentRunCancelOut(
                run_id=row.run_id,
                status=row.status,  # type: ignore[arg-type]
                cancel_requested=bool(row.cancel_requested),
            )

        row.cancel_requested = True
        if row.status == RUN_STATUS_QUEUED:
            row.status = RUN_STATUS_CANCELLED
            row.finished_at = _utcnow()
            _append_event(
                self.db,
                run_pk_id=int(row.id),
                event_type="cancelled",
                payload={"status": RUN_STATUS_CANCELLED},
            )
            _append_event(
                self.db,
                run_pk_id=int(row.id),
                event_type="done",
                payload={"status": RUN_STATUS_CANCELLED},
            )
        else:
            _append_event(
                self.db,
                run_pk_id=int(row.id),
                event_type="status",
                payload={"status": row.status, "cancel_requested": True},
            )
        self.db.commit()
        return AgentRunCancelOut(
            run_id=row.run_id,
            status=row.status,  # type: ignore[arg-type]
            cancel_requested=True,
        )

    def list_events(
        self,
        *,
        run_id: str,
        current_user,
        after_event_id: int,
        limit: int = 200,
    ) -> list[AgentRunEventOut]:
        row = self._get_owned_run(run_id=run_id, current_user=current_user)
        events = self.db.scalars(
            select(AgentRunEvent)
            .where(
                AgentRunEvent.run_pk_id == row.id,
                AgentRunEvent.id > max(0, after_event_id),
            )
            .order_by(AgentRunEvent.id.asc())
            .limit(max(1, min(limit, 500)))
        ).all()
        return [_to_event_out(item) for item in events]

    def _get_owned_run(self, *, run_id: str, current_user) -> AgentRun:
        normalized = (run_id or "").strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="run_id is required",
            )
        row = self.db.scalar(
            select(AgentRun).where(
                AgentRun.run_id == normalized,
                AgentRun.user_id == int(getattr(current_user, "id")),
                AgentRun.tenant_id == int(getattr(current_user, "tenant_id")),
            )
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent run not found",
            )
        return row
