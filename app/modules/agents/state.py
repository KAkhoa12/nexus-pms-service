from __future__ import annotations

from typing import Any, Literal, TypedDict

ExecutionMode = Literal["read_only", "propose_write", "approved_write"]
AgentRoute = Literal[
    "reporting",
    "billing",
    "knowledge",
    "maintenance",
    "customer",
    "contract",
    "room",
]


class AgentRuntimeContext(TypedDict):
    request_id: str
    tenant_id: int
    user_id: int
    role_ids: list[str]
    permission_codes: list[str]
    has_full_access: bool
    locale: str
    thread_id: str
    session_id: str
    allowed_tools: list[str]
    execution_mode: ExecutionMode
    approval_required: bool
    model_tier: str
    timeout_seconds: int
    retry_limit: int
    max_tool_calls: int
    cost_budget_usd: float
    memory_namespace: str


class AgentMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class AgentAuditEvent(TypedDict, total=False):
    ts: str
    graph: str
    node: str
    event: str
    metadata: dict[str, Any]


class AgentToolResult(TypedDict, total=False):
    tool_name: str
    ok: bool
    payload: dict[str, Any]
    error_code: str
    error_message: str


class AgentState(TypedDict, total=False):
    runtime_context: AgentRuntimeContext
    messages: list[AgentMessage]
    intent: str
    route: AgentRoute
    selected_domains: list[str]
    entities: dict[str, Any]
    filters: dict[str, Any]
    user_preferences: dict[str, Any]
    task_plan: list[str]
    customer_candidates: list[dict[str, Any]]
    selected_customer_id: int
    contract_candidates: list[dict[str, Any]]
    selected_contract_id: int
    waiting_for_user_choice: bool
    interrupt_kind: str
    interrupt_payload: dict[str, Any]
    retrieved_facts: list[dict[str, Any]]
    tool_results: list[AgentToolResult]
    risk_flags: list[str]
    proposed_actions: list[dict[str, Any]]
    final_data: dict[str, Any]
    final_answer: str
    audit_trail: list[AgentAuditEvent]
    requires_approval: bool
    tool_call_count: int
