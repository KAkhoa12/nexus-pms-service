from __future__ import annotations

import re

from app.modules.agents.schemas.tools import (
    RoomStatusOverviewInput,
    TeamMembersInput,
    TenantKpiInput,
)
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient, ToolDefinition
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState

GRAPH_NAME = "reporting"
NODE_KPI = "reporting_get_tenant_kpi"
NODE_ROOM_OVERVIEW = "reporting_get_room_status_overview"
NODE_TEAM_MEMBERS = "reporting_get_team_members"
NODE_LLM_TOOL_CALL = "reporting_llm_tool_call"

TEAM_QUERY_KEYWORDS = {
    "team",
    "nhom",
    "nhóm",
    "thanh vien",
    "thành viên",
    "member",
    "nguoi",
    "người",
    "bao nhieu",
    "bao nhiêu",
    "co ai",
    "có ai",
    "bao gom",
    "bao gồm",
    "ai",
    "danh sach",
    "danh sách",
    "liet ke",
    "liệt kê",
}
ROOM_QUERY_KEYWORDS = {
    "phong",
    "phòng",
    "room",
    "chi nhanh",
    "chi nhánh",
    "branch",
    "khu vuc",
    "khu vực",
    "area",
    "toa",
    "tòa",
    "building",
    "tang",
    "tầng",
    "trang thai phong",
    "trạng thái phòng",
}
INCLUDE_ROOM_LIST_KEYWORDS = {
    "danh sach phong",
    "danh sách phòng",
    "chi tiet phong",
    "chi tiết phòng",
    "list room",
}


def run_reporting_subgraph(
    *,
    state: AgentState,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
) -> AgentState:
    runtime_context = state["runtime_context"]
    user_message = _get_user_message(state)

    llm_next_state = _run_with_llm_tool_call(
        state=state,
        user_message=user_message,
        tool_gateway=tool_gateway,
        checkpointer=checkpointer,
        llm_client=llm_client,
    )
    if llm_next_state is not None:
        return llm_next_state

    normalized = _normalize(user_message)
    node_name = NODE_KPI
    tool_name = "get_tenant_kpi"
    payload: dict = {}

    if _contains_any(normalized, TEAM_QUERY_KEYWORDS):
        node_name = NODE_TEAM_MEMBERS
        team_id = _extract_id(
            user_message,
            patterns=[r"(?:team)\s*#?:?\s*(\d+)"],
        )
        team_input = TeamMembersInput(
            team_id=team_id,
            team_limit=10,
            member_limit=200,
        )
        payload = team_input.model_dump(mode="json")
        tool_caller = lambda: tool_gateway.get_team_members(  # noqa: E731
            team_input,
            graph_name=GRAPH_NAME,
            node_name=node_name,
        )
        tool_name = "get_team_members"
    elif _contains_any(normalized, ROOM_QUERY_KEYWORDS):
        node_name = NODE_ROOM_OVERVIEW
        room_input = RoomStatusOverviewInput(
            branch_id=_extract_id(
                user_message,
                patterns=[r"(?:chi nhánh|chi nhanh|branch)\s*#?:?\s*(\d+)"],
            ),
            area_id=_extract_id(
                user_message,
                patterns=[r"(?:khu vực|khu vuc|area)\s*#?:?\s*(\d+)"],
            ),
            building_id=_extract_id(
                user_message,
                patterns=[r"(?:tòa|toa|building)\s*#?:?\s*(\d+)"],
            ),
            include_rooms=_contains_any(normalized, INCLUDE_ROOM_LIST_KEYWORDS),
            room_limit=200,
        )
        payload = room_input.model_dump(mode="json")
        tool_caller = lambda: tool_gateway.get_room_status_overview(  # noqa: E731
            room_input,
            graph_name=GRAPH_NAME,
            node_name=node_name,
        )
        tool_name = "get_room_status_overview"
    else:
        kpi_input = TenantKpiInput()
        payload = kpi_input.model_dump(mode="json")
        tool_caller = lambda: tool_gateway.get_tenant_kpi(  # noqa: E731
            kpi_input,
            graph_name=GRAPH_NAME,
            node_name=node_name,
        )

    audit_trail = append_audit_event(
        state.get("audit_trail"),
        graph=GRAPH_NAME,
        node=node_name,
        event="node_start",
    )
    try:
        output = tool_caller()
        tool_result = {
            "tool_name": tool_name,
            "ok": True,
            "payload": output.model_dump(mode="json"),
        }
        next_state: AgentState = {
            "tool_results": [*(state.get("tool_results") or []), tool_result],
            "retrieved_facts": [
                *(state.get("retrieved_facts") or []),
                {
                    "source": f"tool:{tool_name}",
                    "data": output.model_dump(mode="json"),
                },
            ],
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=node_name,
                event="node_success",
            ),
        }
    except ToolGatewayError as exc:
        next_state = {
            "tool_results": [
                *(state.get("tool_results") or []),
                {
                    "tool_name": tool_name,
                    "ok": False,
                    "error_code": exc.code,
                    "error_message": str(exc),
                },
            ],
            "risk_flags": [*(state.get("risk_flags") or []), exc.code],
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=node_name,
                event="node_error",
                metadata={"error": str(exc), "code": exc.code, "input": payload},
            ),
        }

    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=GRAPH_NAME,
        node_name=node_name,
        state=snapshot,
    )
    return next_state


def _run_with_llm_tool_call(
    *,
    state: AgentState,
    user_message: str,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None,
) -> AgentState | None:
    if llm_client is None or not llm_client.enabled:
        return None
    runtime_context = state["runtime_context"]
    audit_trail = append_audit_event(
        state.get("audit_trail"),
        graph=GRAPH_NAME,
        node=NODE_LLM_TOOL_CALL,
        event="node_start",
    )
    execution = llm_client.execute_tool_calls(
        route=GRAPH_NAME,
        user_message=user_message,
        locale=str(runtime_context.get("locale", "vi-VN")),
        tool_definitions=[
            ToolDefinition(
                name="get_tenant_kpi",
                description="Lay KPI tong quan tenant hien tai.",
                json_schema=TenantKpiInput.model_json_schema(),
            ),
            ToolDefinition(
                name="get_room_status_overview",
                description=(
                    "Lay tong quan trang thai phong. "
                    "Co the loc theo branch_id, area_id, building_id."
                ),
                json_schema=RoomStatusOverviewInput.model_json_schema(),
            ),
            ToolDefinition(
                name="get_team_members",
                description="Lay danh sach team va thanh vien ma user hien tai co the xem.",
                json_schema=TeamMembersInput.model_json_schema(),
            ),
        ],
        max_calls=1,
        tool_executor=lambda tool_name, args: _execute_reporting_tool(
            tool_name=tool_name,
            args=args,
            user_message=user_message,
            tool_gateway=tool_gateway,
        ),
    )
    if not execution.called:
        return None

    tool_results = [*(state.get("tool_results") or [])]
    retrieved_facts = [*(state.get("retrieved_facts") or [])]
    risk_flags = [*(state.get("risk_flags") or [])]
    for item in execution.calls:
        tool_results.append(
            {
                "tool_name": item.tool_name,
                "ok": item.ok,
                "payload": item.payload,
                "error_code": item.error_code,
                "error_message": item.error_message,
            }
        )
        if item.ok and item.payload is not None:
            retrieved_facts.append(
                {"source": f"tool:{item.tool_name}", "data": item.payload}
            )
        elif item.error_code:
            risk_flags.append(item.error_code)

    next_state: AgentState = {
        "tool_results": tool_results,
        "retrieved_facts": retrieved_facts,
        "risk_flags": risk_flags,
        "audit_trail": append_audit_event(
            audit_trail,
            graph=GRAPH_NAME,
            node=NODE_LLM_TOOL_CALL,
            event="node_success",
            metadata={
                "tool_count": len(execution.calls),
                "assistant_message": execution.assistant_message or "",
            },
        ),
    }
    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=GRAPH_NAME,
        node_name=NODE_LLM_TOOL_CALL,
        state=snapshot,
    )
    return next_state


def _execute_reporting_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict:
    if tool_name == "get_tenant_kpi":
        payload = TenantKpiInput.model_validate(args or {})
        return tool_gateway.get_tenant_kpi(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LLM_TOOL_CALL,
        ).model_dump(mode="json")
    if tool_name == "get_room_status_overview":
        payload = RoomStatusOverviewInput.model_validate(args or {})
        return tool_gateway.get_room_status_overview(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LLM_TOOL_CALL,
        ).model_dump(mode="json")
    if tool_name == "get_team_members":
        safe_args = dict(args or {})
        team_id_raw = safe_args.get("team_id")
        if team_id_raw in (None, "", "null", "None"):
            safe_args.pop("team_id", None)
        else:
            try:
                safe_args["team_id"] = int(team_id_raw)
            except Exception:
                safe_args.pop("team_id", None)
        safe_args["team_limit"] = _coerce_int_with_bounds(
            safe_args.get("team_limit", 10),
            default=10,
            min_value=1,
            max_value=50,
        )
        safe_args["member_limit"] = _coerce_int_with_bounds(
            safe_args.get("member_limit", 200),
            default=200,
            min_value=1,
            max_value=500,
        )
        payload = TeamMembersInput.model_validate(safe_args)
        return tool_gateway.get_team_members(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LLM_TOOL_CALL,
        ).model_dump(mode="json")
    raise ToolGatewayError(
        f"Unsupported reporting tool: {tool_name}",
        code="tool_not_supported",
    )


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _coerce_int_with_bounds(
    value: object,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(parsed, max_value))


def _contains_any(value: str, keywords: set[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _extract_id(message: str, *, patterns: list[str]) -> int | None:
    for pattern in patterns:
        matched = re.search(pattern, message, flags=re.IGNORECASE)
        if matched and matched.group(1).isdigit():
            return int(matched.group(1))
    return None


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
