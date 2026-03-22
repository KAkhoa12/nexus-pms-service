from __future__ import annotations

import re

from app.modules.agents.schemas.tools import TeamNotificationInput
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient, ToolDefinition
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState

GRAPH_NAME = "maintenance"
NODE_STUB = "maintenance_stub"
NODE_DISPATCH_NOTIFICATION = "maintenance_dispatch_team_notification"
NODE_LLM_TOOL_CALL = "maintenance_llm_tool_call"
NOTIFICATION_KEYWORDS = {"thong bao", "thông báo", "notify", "notification"}


def run_maintenance_subgraph(
    *,
    state: AgentState,
    tool_gateway: ToolGateway | None = None,
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
    should_dispatch = tool_gateway is not None and _contains_any(
        normalized, NOTIFICATION_KEYWORDS
    )
    node_name = NODE_DISPATCH_NOTIFICATION if should_dispatch else NODE_STUB

    if should_dispatch:
        notification_input = TeamNotificationInput(
            team_id=_extract_team_id(user_message),
            title=_extract_notification_title(user_message),
            body=_extract_notification_body(user_message),
            recipient_user_ids=[],
        )
        audit_trail = append_audit_event(
            state.get("audit_trail"),
            graph=GRAPH_NAME,
            node=node_name,
            event="node_start",
            metadata={"input": notification_input.model_dump(mode="json")},
        )
        try:
            output = tool_gateway.dispatch_team_notification(
                notification_input,
                graph_name=GRAPH_NAME,
                node_name=node_name,
            )
            next_state: AgentState = {
                "tool_results": [
                    *(state.get("tool_results") or []),
                    {
                        "tool_name": "dispatch_team_notification",
                        "ok": True,
                        "payload": output.model_dump(mode="json"),
                    },
                ],
                "retrieved_facts": [
                    *(state.get("retrieved_facts") or []),
                    {
                        "source": "tool:dispatch_team_notification",
                        "data": output.model_dump(mode="json"),
                    },
                ],
                "requires_approval": bool(output.draft_only),
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
                        "tool_name": "dispatch_team_notification",
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
                    metadata={"error": str(exc), "code": exc.code},
                ),
            }
    else:
        next_state = {
            "risk_flags": [*(state.get("risk_flags") or []), "maintenance_not_enabled"],
            "audit_trail": append_audit_event(
                state.get("audit_trail"),
                graph=GRAPH_NAME,
                node=node_name,
                event="node_skipped",
                metadata={"reason": "phase_1_read_only"},
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
    tool_gateway: ToolGateway | None,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None,
) -> AgentState | None:
    if tool_gateway is None or llm_client is None or not llm_client.enabled:
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
                name="dispatch_team_notification",
                description=(
                    "Gui thong bao toi thanh vien trong team. "
                    "Co the chay dry-run theo execution mode."
                ),
                json_schema=TeamNotificationInput.model_json_schema(),
            )
        ],
        max_calls=1,
        tool_executor=lambda tool_name, args: _execute_maintenance_tool(
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
    requires_approval = bool(state.get("requires_approval", False))
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
            if bool(item.payload.get("draft_only")):
                requires_approval = True
        elif item.error_code:
            risk_flags.append(item.error_code)

    next_state: AgentState = {
        "tool_results": tool_results,
        "retrieved_facts": retrieved_facts,
        "risk_flags": risk_flags,
        "requires_approval": requires_approval,
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


def _execute_maintenance_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict:
    if tool_name != "dispatch_team_notification":
        raise ToolGatewayError(
            f"Unsupported maintenance tool: {tool_name}",
            code="tool_not_supported",
        )
    safe_args = dict(args or {})
    if not str(safe_args.get("title") or "").strip():
        safe_args["title"] = _extract_notification_title(user_message)
    if not str(safe_args.get("body") or "").strip():
        safe_args["body"] = _extract_notification_body(user_message)
    payload = TeamNotificationInput.model_validate(safe_args)
    return tool_gateway.dispatch_team_notification(
        payload,
        graph_name=GRAPH_NAME,
        node_name=NODE_LLM_TOOL_CALL,
    ).model_dump(mode="json")


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _contains_any(value: str, keywords: set[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _extract_team_id(message: str) -> int | None:
    matched = re.search(r"(?:team)\s*#?:?\s*(\d+)", message or "", re.IGNORECASE)
    if matched and matched.group(1).isdigit():
        return int(matched.group(1))
    return None


def _extract_notification_body(message: str) -> str:
    text = (message or "").strip()
    if ":" in text:
        body = text.split(":", 1)[1].strip()
        if body:
            return body
    return text or "Thông báo từ AI Agent"


def _extract_notification_title(message: str) -> str:
    text = (message or "").strip()
    if ":" in text:
        title = text.split(":", 1)[0].strip()
        if title:
            return title[:255]
    return "Thông báo từ AI Agent"


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
