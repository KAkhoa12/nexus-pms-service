from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.agents.config import get_agent_config
from app.modules.agents.graphs.supervisor import build_supervisor_executor
from app.modules.agents.schemas.api import (
    AgentCheckpointItemOut,
    AgentCheckpointListOut,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentToolResultOut,
)
from app.modules.agents.schemas.context import RuntimeContextOut
from app.modules.agents.services.checkpointer import (
    DbCheckpointer,
    PersistentCheckpointer,
    SqliteFileCheckpointer,
)
from app.modules.agents.services.context_builder import build_runtime_context
from app.modules.agents.services.llm_client import AgentLlmClient
from app.modules.agents.services.tool_gateway import ToolGateway
from app.modules.agents.state import AgentState


class AgentRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.config = get_agent_config()

    def run_query(
        self,
        *,
        payload: AgentQueryRequest,
        current_user,
        on_answer_delta: Callable[[str], bool] | None = None,
    ) -> AgentQueryResponse:
        runtime_context = build_runtime_context(
            db=self.db,
            current_user=current_user,
            payload=payload,
            config=self.config,
        )
        checkpointer = self._build_checkpointer()
        previous_state = checkpointer.load_latest_state(
            tenant_id=runtime_context["tenant_id"],
            user_id=runtime_context["user_id"],
            thread_id=runtime_context["thread_id"],
        )

        existing_messages = _extract_safe_messages(previous_state)
        messages = [
            *existing_messages,
            {"role": "user", "content": payload.message},
        ]

        initial_state: AgentState = {
            "runtime_context": runtime_context,
            "messages": messages,
            "tool_results": [],
            "retrieved_facts": [],
            "risk_flags": [],
            "proposed_actions": [],
            "audit_trail": [],
            "requires_approval": runtime_context["approval_required"],
            "tool_call_count": 0,
        }

        checkpointer.save_checkpoint(
            runtime_context=runtime_context,
            graph_name="supervisor",
            node_name="runtime_start",
            state=initial_state,
        )

        tool_gateway = ToolGateway(db=self.db, runtime_context=runtime_context)
        llm_client = AgentLlmClient.from_config(
            self.config,
            model_tier=str(runtime_context.get("model_tier", "standard")),
        )
        executor = build_supervisor_executor(
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
            on_answer_delta=on_answer_delta,
        )

        try:
            result_state = executor(initial_state)
            self.db.commit()
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent runtime failed: {exc}",
            ) from exc

        return AgentQueryResponse(
            request_id=runtime_context["request_id"],
            thread_id=runtime_context["thread_id"],
            session_id=runtime_context["session_id"],
            intent=str(result_state.get("intent") or "unknown"),
            route=str(result_state.get("route") or "unknown"),
            execution_mode=runtime_context["execution_mode"],
            requires_approval=bool(result_state.get("requires_approval", False)),
            final_answer=str(result_state.get("final_answer") or ""),
            risk_flags=list(result_state.get("risk_flags") or []),
            task_plan=list(result_state.get("task_plan") or []),
            tool_results=[
                AgentToolResultOut(**item)
                for item in (result_state.get("tool_results") or [])
            ],
            audit_trail=list(result_state.get("audit_trail") or []),
            runtime_context=RuntimeContextOut(**runtime_context),
        )

    def list_checkpoints(
        self,
        *,
        current_user,
        thread_id: str,
        limit: int = 50,
    ) -> AgentCheckpointListOut:
        normalized_thread_id = (thread_id or "").strip()
        if not normalized_thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="thread_id is required",
            )
        checkpointer = self._build_checkpointer()
        items = checkpointer.list_checkpoints(
            tenant_id=int(getattr(current_user, "tenant_id")),
            user_id=int(getattr(current_user, "id")),
            thread_id=normalized_thread_id,
            limit=limit,
        )
        return AgentCheckpointListOut(
            thread_id=normalized_thread_id,
            items=[
                AgentCheckpointItemOut(
                    id=item.id,
                    graph_name=item.graph_name,
                    node_name=item.node_name,
                    created_at=item.created_at,
                )
                for item in items
            ],
        )

    def _build_checkpointer(self) -> PersistentCheckpointer:
        backend = str(self.config.checkpointer_backend or "db").strip().lower()
        if backend == "sqlite":
            return SqliteFileCheckpointer(self.config.checkpointer_sqlite_path)
        return DbCheckpointer(self.db)


def _extract_safe_messages(state: AgentState | None) -> list[dict[str, str]]:
    if not state:
        return []
    raw = state.get("messages")
    if not isinstance(raw, list):
        return []
    messages: list[dict[str, str]] = []
    for item in raw[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "")
        if role in {"system", "user", "assistant", "tool"}:
            messages.append({"role": role, "content": content})
    return messages
