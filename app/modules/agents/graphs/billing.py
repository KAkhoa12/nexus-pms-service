from __future__ import annotations

import re

from app.modules.agents.schemas.tools import (
    InvoiceInstallmentsInput,
    OverdueInvoicesInput,
)
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient, ToolDefinition
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState

GRAPH_NAME = "billing"
NODE_OVERDUE = "billing_list_overdue_invoices"
NODE_INSTALLMENTS = "billing_get_invoice_installments"
NODE_LLM_TOOL_CALL = "billing_llm_tool_call"

INSTALLMENT_QUERY_KEYWORDS = {
    "kỳ hạn",
    "ky han",
    "hợp đồng",
    "hop dong",
    "mã hợp đồng",
    "ma hop dong",
    "khách hàng",
    "khach hang",
    "lich thanh toan",
    "lịch thanh toán",
    "installment",
}


def run_billing_subgraph(
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
    node_name = NODE_OVERDUE
    tool_name = "list_overdue_invoices"
    payload: dict = {}

    if _contains_any(normalized, INSTALLMENT_QUERY_KEYWORDS):
        node_name = NODE_INSTALLMENTS
        schedule_input = InvoiceInstallmentsInput(
            query=_extract_invoice_subject(user_message),
            lease_limit=5,
            installment_limit=36,
        )
        payload = schedule_input.model_dump(mode="json")
        tool_caller = lambda: tool_gateway.get_invoice_installments(  # noqa: E731
            schedule_input,
            graph_name=GRAPH_NAME,
            node_name=node_name,
        )
        tool_name = "get_invoice_installments"
    else:
        overdue_input = OverdueInvoicesInput(limit=20, min_days_overdue=1)
        payload = overdue_input.model_dump(mode="json")
        tool_caller = lambda: tool_gateway.list_overdue_invoices(  # noqa: E731
            overdue_input,
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
                name="list_overdue_invoices",
                description="Lay danh sach hoa don qua han cua tenant hien tai.",
                json_schema=OverdueInvoicesInput.model_json_schema(),
            ),
            ToolDefinition(
                name="get_invoice_installments",
                description=(
                    "Tra cuu ky han hoa don theo ma hop dong hoac thong tin khach hang."
                ),
                json_schema=InvoiceInstallmentsInput.model_json_schema(),
            ),
        ],
        max_calls=1,
        tool_executor=lambda tool_name, args: _execute_billing_tool(
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


def _execute_billing_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict:
    if tool_name == "list_overdue_invoices":
        safe_args = dict(args or {})
        if "limit" not in safe_args:
            safe_args["limit"] = 20
        if "min_days_overdue" not in safe_args:
            safe_args["min_days_overdue"] = 1
        payload = OverdueInvoicesInput.model_validate(safe_args)
        return tool_gateway.list_overdue_invoices(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LLM_TOOL_CALL,
        ).model_dump(mode="json")
    if tool_name == "get_invoice_installments":
        safe_args = dict(args or {})
        if not str(safe_args.get("query") or "").strip():
            safe_args["query"] = _extract_invoice_subject(user_message)
        payload = InvoiceInstallmentsInput.model_validate(safe_args)
        return tool_gateway.get_invoice_installments(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LLM_TOOL_CALL,
        ).model_dump(mode="json")
    raise ToolGatewayError(
        f"Unsupported billing tool: {tool_name}",
        code="tool_not_supported",
    )


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _contains_any(value: str, keywords: set[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _extract_invoice_subject(message: str) -> str:
    text = (message or "").strip()
    patterns = [
        r"(?:khách hàng|khach hang)\s*[:\-]?\s*(.+)$",
        r"(?:mã hợp đồng|ma hop dong|hợp đồng|hop dong)\s*[:#\-]?\s*(.+)$",
    ]
    for pattern in patterns:
        matched = re.search(pattern, text, flags=re.IGNORECASE)
        if matched:
            subject = matched.group(1).strip()
            if subject:
                return subject
    id_match = re.search(r"\b(?:hd[-\s]*)?(\d{1,10})\b", text, flags=re.IGNORECASE)
    if id_match:
        return f"HD-{id_match.group(1)}"
    return text


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
