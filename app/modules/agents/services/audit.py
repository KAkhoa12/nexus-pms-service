from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.agents.models import AgentToolAuditLog

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(
    audit_trail: list[dict[str, Any]] | None,
    *,
    graph: str,
    node: str,
    event: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    next_trail = list(audit_trail or [])
    next_trail.append(
        {
            "ts": utc_now_iso(),
            "graph": graph,
            "node": node,
            "event": event,
            "metadata": metadata or {},
        }
    )
    return next_trail


@dataclass
class ToolCallAuditInput:
    tenant_id: int
    user_id: int | None
    request_id: str
    thread_id: str
    graph_name: str
    node_name: str
    tool_name: str
    status: str
    latency_ms: int
    retry_count: int
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


def record_tool_call(db: Session, payload: ToolCallAuditInput) -> None:
    try:
        row = AgentToolAuditLog(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            request_id=payload.request_id,
            thread_id=payload.thread_id,
            graph_name=payload.graph_name,
            node_name=payload.node_name,
            tool_name=payload.tool_name,
            status=payload.status,
            latency_ms=max(0, int(payload.latency_ms)),
            retry_count=max(0, int(payload.retry_count)),
            input_json=_safe_json(payload.input_payload),
            output_json=_safe_json(payload.output_payload),
            error_code=payload.error_code,
            error_message=payload.error_message,
        )
        db.add(row)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("agent_tool_call_audit_failed: %s", exc)
        return

    logger.info(
        "agent_tool_call request_id=%s tenant_id=%s thread_id=%s graph=%s node=%s tool=%s status=%s latency_ms=%s retry=%s",
        payload.request_id,
        payload.tenant_id,
        payload.thread_id,
        payload.graph_name,
        payload.node_name,
        payload.tool_name,
        payload.status,
        payload.latency_ms,
        payload.retry_count,
    )


def _safe_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"_unserializable": True}, ensure_ascii=False)
