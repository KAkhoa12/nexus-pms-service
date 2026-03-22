from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.agents.schemas.context import RuntimeContextOut
from app.modules.agents.state import ExecutionMode


class AgentQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    locale: str = Field(default="vi-VN", min_length=2, max_length=16)
    execution_mode: ExecutionMode | None = None
    model_tier: Literal["standard", "cheap"] = "standard"


class AgentToolResultOut(BaseModel):
    tool_name: str
    ok: bool
    payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class AgentAuditEventOut(BaseModel):
    ts: str
    graph: str
    node: str
    event: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentQueryResponse(BaseModel):
    request_id: str
    thread_id: str
    session_id: str
    intent: str
    route: str
    execution_mode: ExecutionMode
    requires_approval: bool
    final_answer: str
    risk_flags: list[str] = Field(default_factory=list)
    task_plan: list[str] = Field(default_factory=list)
    tool_results: list[AgentToolResultOut] = Field(default_factory=list)
    audit_trail: list[AgentAuditEventOut] = Field(default_factory=list)
    runtime_context: RuntimeContextOut


class AgentCheckpointItemOut(BaseModel):
    id: int
    graph_name: str
    node_name: str
    created_at: datetime


class AgentCheckpointListOut(BaseModel):
    thread_id: str
    items: list[AgentCheckpointItemOut] = Field(default_factory=list)


AgentRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class AgentRunStartRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    locale: str = Field(default="vi-VN", min_length=2, max_length=16)
    execution_mode: ExecutionMode | None = None
    model_tier: Literal["standard", "cheap"] = "standard"


class AgentRunStartOut(BaseModel):
    run_id: str
    status: AgentRunStatus
    thread_id: str
    session_id: str
    created_at: datetime


class AgentRunEventOut(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AgentRunStatusOut(BaseModel):
    run_id: str
    status: AgentRunStatus
    thread_id: str
    session_id: str
    request_id: str
    message: str
    locale: str
    execution_mode: ExecutionMode
    model_tier: str
    cancel_requested: bool
    partial_answer: str | None = None
    final_answer: str | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None
    latest_event_id: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentRunListOut(BaseModel):
    items: list[AgentRunStatusOut] = Field(default_factory=list)


class AgentRunCancelOut(BaseModel):
    run_id: str
    status: AgentRunStatus
    cancel_requested: bool
