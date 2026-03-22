from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agents.models import AgentCheckpoint
from app.modules.agents.state import AgentState


@dataclass
class CheckpointItem:
    id: int
    graph_name: str
    node_name: str
    created_at: Any


class PersistentCheckpointer(Protocol):
    def save_checkpoint(
        self,
        *,
        runtime_context: dict[str, Any],
        graph_name: str,
        node_name: str,
        state: AgentState,
        metadata: dict[str, Any] | None = None,
    ) -> int: ...

    def load_latest_state(
        self, *, tenant_id: int, user_id: int, thread_id: str
    ) -> AgentState | None: ...

    def list_checkpoints(
        self, *, tenant_id: int, user_id: int, thread_id: str, limit: int = 50
    ) -> list[CheckpointItem]: ...


@dataclass
class DbCheckpointer:
    db: Session

    def save_checkpoint(
        self,
        *,
        runtime_context: dict[str, Any],
        graph_name: str,
        node_name: str,
        state: AgentState,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        row = AgentCheckpoint(
            tenant_id=int(runtime_context["tenant_id"]),
            user_id=int(runtime_context["user_id"]),
            request_id=str(runtime_context["request_id"]),
            thread_id=str(runtime_context["thread_id"]),
            checkpoint_ns=str(runtime_context["memory_namespace"]),
            graph_name=graph_name,
            node_name=node_name,
            execution_mode=str(runtime_context["execution_mode"]),
            state_json=_dump_json(state),
            metadata_json=_dump_json(metadata) if metadata else None,
        )
        self.db.add(row)
        self.db.flush()
        return int(row.id)

    def load_latest_state(
        self, *, tenant_id: int, user_id: int, thread_id: str
    ) -> AgentState | None:
        row = self.db.scalar(
            select(AgentCheckpoint)
            .where(
                AgentCheckpoint.tenant_id == tenant_id,
                AgentCheckpoint.user_id == user_id,
                AgentCheckpoint.thread_id == thread_id,
            )
            .order_by(AgentCheckpoint.id.desc())
        )
        if row is None:
            return None
        return _load_state_json(row.state_json)

    def list_checkpoints(
        self, *, tenant_id: int, user_id: int, thread_id: str, limit: int = 50
    ) -> list[CheckpointItem]:
        rows = self.db.scalars(
            select(AgentCheckpoint)
            .where(
                AgentCheckpoint.tenant_id == tenant_id,
                AgentCheckpoint.user_id == user_id,
                AgentCheckpoint.thread_id == thread_id,
            )
            .order_by(AgentCheckpoint.id.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            CheckpointItem(
                id=int(row.id),
                graph_name=row.graph_name,
                node_name=row.node_name,
                created_at=row.created_at,
            )
            for row in rows
        ]


@dataclass
class SqliteFileCheckpointer:
    sqlite_path: str

    def __post_init__(self) -> None:
        file_path = Path(self.sqlite_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(file_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NULL,
                    request_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    graph_name TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    metadata_json TEXT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_agent_checkpoints_tenant_thread_created
                ON agent_checkpoints (tenant_id, user_id, thread_id, created_at)
                """
            )

    def save_checkpoint(
        self,
        *,
        runtime_context: dict[str, Any],
        graph_name: str,
        node_name: str,
        state: AgentState,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_checkpoints (
                    tenant_id,
                    user_id,
                    request_id,
                    thread_id,
                    checkpoint_ns,
                    graph_name,
                    node_name,
                    execution_mode,
                    state_json,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(runtime_context["tenant_id"]),
                    int(runtime_context["user_id"]),
                    str(runtime_context["request_id"]),
                    str(runtime_context["thread_id"]),
                    str(runtime_context["memory_namespace"]),
                    graph_name,
                    node_name,
                    str(runtime_context["execution_mode"]),
                    _dump_json(state),
                    _dump_json(metadata) if metadata else None,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def load_latest_state(
        self, *, tenant_id: int, user_id: int, thread_id: str
    ) -> AgentState | None:
        with sqlite3.connect(self.sqlite_path) as conn:
            row = conn.execute(
                """
                SELECT state_json
                FROM agent_checkpoints
                WHERE tenant_id = ?
                  AND user_id = ?
                  AND thread_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id, user_id, thread_id),
            ).fetchone()
        if row is None:
            return None
        return _load_state_json(str(row[0]))

    def list_checkpoints(
        self, *, tenant_id: int, user_id: int, thread_id: str, limit: int = 50
    ) -> list[CheckpointItem]:
        with sqlite3.connect(self.sqlite_path) as conn:
            rows = conn.execute(
                """
                SELECT id, graph_name, node_name, created_at
                FROM agent_checkpoints
                WHERE tenant_id = ?
                  AND user_id = ?
                  AND thread_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (tenant_id, user_id, thread_id, max(1, min(limit, 200))),
            ).fetchall()
        return [
            CheckpointItem(
                id=int(row[0]),
                graph_name=str(row[1]),
                node_name=str(row[2]),
                created_at=row[3],
            )
            for row in rows
        ]


def _dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _load_state_json(raw: str) -> AgentState | None:
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if isinstance(parsed, dict):
        return parsed  # type: ignore[return-value]
    return None
