from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.agents.state import ExecutionMode


class RuntimeContextOut(BaseModel):
    request_id: str
    tenant_id: int
    user_id: int
    role_ids: list[str] = Field(default_factory=list)
    permission_codes: list[str] = Field(default_factory=list)
    has_full_access: bool = False
    locale: str = "vi-VN"
    thread_id: str
    session_id: str
    allowed_tools: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    approval_required: bool = False
    model_tier: str = "standard"
    timeout_seconds: int = 20
    retry_limit: int = 2
    max_tool_calls: int = 8
    cost_budget_usd: float = 0.2
    memory_namespace: str
