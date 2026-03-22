from __future__ import annotations

from typing import Any, Callable

from app.modules.agents.graphs.billing import run_billing_subgraph
from app.modules.agents.graphs.contract import run_contract_subgraph
from app.modules.agents.graphs.customer import run_customer_subgraph
from app.modules.agents.graphs.knowledge import run_knowledge_subgraph
from app.modules.agents.graphs.maintenance import run_maintenance_subgraph
from app.modules.agents.graphs.reporting import run_reporting_subgraph
from app.modules.agents.graphs.room import run_room_subgraph
from app.modules.agents.nodes.classifier import build_task_plan, classify_intent
from app.modules.agents.nodes.responder import compose_final_answer
from app.modules.agents.policies.permissions import (
    TOOL_DISPATCH_TEAM_NOTIFICATION,
    TOOL_GET_CONTRACTS,
    TOOL_GET_INVOICE_INSTALLMENTS,
    TOOL_GET_ROOM_STATUS_OVERVIEW,
    TOOL_GET_TEAM_MEMBERS,
    TOOL_GET_TENANT_KPI,
    TOOL_LIST_OVERDUE_INVOICES,
    TOOL_SEARCH_CUSTOMERS,
    TOOL_SEARCH_INTERNAL_KNOWLEDGE,
)
from app.modules.agents.schemas.tools import (
    ContractLookupInput,
    InvoiceInstallmentsInput,
    OverdueInvoicesInput,
    RoomStatusOverviewInput,
    SearchCustomersInput,
    SearchKnowledgeInput,
    TeamMembersInput,
    TeamNotificationInput,
    TenantKpiInput,
)
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient, ToolDefinition
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState
from app.modules.agents.tools.registry import (
    build_tool_definitions_for_domains,
    resolve_route_for_tool,
)

SUPERVISOR_GRAPH_NAME = "supervisor"
SUPERVISOR_CLASSIFY_NODE = "supervisor_classify_intent"
SUPERVISOR_FINALIZE_NODE = "supervisor_finalize_answer"
StreamDeltaCallback = Callable[[str], bool]


def build_supervisor_executor(
    *,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
    on_answer_delta: StreamDeltaCallback | None = None,
) -> Callable[[AgentState], AgentState]:
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:
        return lambda state: _run_without_langgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
            on_answer_delta=on_answer_delta,
        )

    workflow = StateGraph(AgentState)

    workflow.add_node(
        SUPERVISOR_CLASSIFY_NODE,
        lambda state: _classify_node(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "reporting_subgraph",
        lambda state: run_reporting_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "room_subgraph",
        lambda state: run_room_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "customer_subgraph",
        lambda state: run_customer_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "contract_subgraph",
        lambda state: run_contract_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "billing_subgraph",
        lambda state: run_billing_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "knowledge_subgraph",
        lambda state: run_knowledge_subgraph(
            state=state,
            user_message=_get_user_message(state),
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        "maintenance_subgraph",
        lambda state: run_maintenance_subgraph(
            state=state,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        ),
    )
    workflow.add_node(
        SUPERVISOR_FINALIZE_NODE,
        lambda state: _finalize_node(
            state=state,
            checkpointer=checkpointer,
            llm_client=llm_client,
            on_answer_delta=on_answer_delta,
        ),
    )

    workflow.add_edge(START, SUPERVISOR_CLASSIFY_NODE)
    workflow.add_conditional_edges(
        SUPERVISOR_CLASSIFY_NODE,
        _route_selector,
        {
            "finalize": SUPERVISOR_FINALIZE_NODE,
            "reporting": "reporting_subgraph",
            "room": "room_subgraph",
            "customer": "customer_subgraph",
            "contract": "contract_subgraph",
            "billing": "billing_subgraph",
            "knowledge": "knowledge_subgraph",
            "maintenance": "maintenance_subgraph",
        },
    )
    workflow.add_edge("reporting_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("room_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("customer_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("contract_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("billing_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("knowledge_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge("maintenance_subgraph", SUPERVISOR_FINALIZE_NODE)
    workflow.add_edge(SUPERVISOR_FINALIZE_NODE, END)

    compiled = workflow.compile()
    return lambda state: compiled.invoke(state)


def _run_without_langgraph(
    *,
    state: AgentState,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
    on_answer_delta: StreamDeltaCallback | None = None,
) -> AgentState:
    merged: AgentState = dict(state)
    merged.update(
        _classify_node(
            state=merged,
            tool_gateway=tool_gateway,
            checkpointer=checkpointer,
            llm_client=llm_client,
        )
    )
    if _should_finalize_direct(merged):
        merged.update(
            _finalize_node(
                state=merged,
                checkpointer=checkpointer,
                llm_client=llm_client,
                on_answer_delta=on_answer_delta,
            )
        )
        return merged

    route = merged.get("route")
    if route == "reporting":
        merged.update(
            run_reporting_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    elif route == "room":
        merged.update(
            run_room_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    elif route == "customer":
        merged.update(
            run_customer_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    elif route == "contract":
        merged.update(
            run_contract_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    elif route == "billing":
        merged.update(
            run_billing_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    elif route == "maintenance":
        merged.update(
            run_maintenance_subgraph(
                state=merged,
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    else:
        merged.update(
            run_knowledge_subgraph(
                state=merged,
                user_message=_get_user_message(merged),
                tool_gateway=tool_gateway,
                checkpointer=checkpointer,
                llm_client=llm_client,
            )
        )
    merged.update(
        _finalize_node(
            state=merged,
            checkpointer=checkpointer,
            llm_client=llm_client,
            on_answer_delta=on_answer_delta,
        )
    )
    return merged


def _classify_node(
    *,
    state: AgentState,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
) -> AgentState:
    runtime_context = state["runtime_context"]
    user_message = _get_user_message(state)
    base_audit = append_audit_event(
        state.get("audit_trail"),
        graph=SUPERVISOR_GRAPH_NAME,
        node=SUPERVISOR_CLASSIFY_NODE,
        event="node_start",
    )

    # LLM-first dispatch: cho model tu chon tool dua tren mo ta tool.
    if llm_client is not None and llm_client.enabled:
        execution = llm_client.execute_tool_calls(
            route=SUPERVISOR_GRAPH_NAME,
            user_message=user_message,
            locale=str(runtime_context.get("locale", "vi-VN")),
            tool_definitions=_build_supervisor_tool_definitions(
                set(runtime_context.get("allowed_tools") or [])
            ),
            max_calls=1,
            tool_executor=lambda tool_name, args: _execute_supervisor_tool(
                tool_name=tool_name,
                args=args,
                user_message=user_message,
                tool_gateway=tool_gateway,
            ),
            conversation_messages=[
                {
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                }
                for item in (state.get("messages") or [])
                if isinstance(item, dict)
            ],
        )
        if execution.called and execution.calls:
            tool_results = [*(state.get("tool_results") or [])]
            retrieved_facts = [*(state.get("retrieved_facts") or [])]
            risk_flags = [*(state.get("risk_flags") or [])]
            primary_tool_name = execution.calls[0].tool_name
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
            route = _route_from_tool_name(primary_tool_name)
            next_state: AgentState = {
                "intent": f"tool_dispatch:{primary_tool_name}",
                "route": route,
                "task_plan": build_task_plan(route),
                "tool_results": tool_results,
                "retrieved_facts": retrieved_facts,
                "risk_flags": risk_flags,
                "audit_trail": append_audit_event(
                    base_audit,
                    graph=SUPERVISOR_GRAPH_NAME,
                    node=SUPERVISOR_CLASSIFY_NODE,
                    event="node_success",
                    metadata={
                        "dispatch": "llm_tool_call",
                        "tool_name": primary_tool_name,
                        "route": route,
                        "tool_count": len(execution.calls),
                    },
                ),
            }
            snapshot: AgentState = dict(state)
            snapshot.update(next_state)
            checkpointer.save_checkpoint(
                runtime_context=runtime_context,
                graph_name=SUPERVISOR_GRAPH_NAME,
                node_name=SUPERVISOR_CLASSIFY_NODE,
                state=snapshot,
            )
            return next_state

        # Khong co tool phu hop => xu ly hoi thoai tu nhien, khong ep qua knowledge search.
        next_state = {
            "intent": "general_chat",
            "route": "knowledge",
            "task_plan": [
                "Trả lời hội thoại tự nhiên trong phạm vi trợ lý hệ thống",
                "Không bịa dữ liệu nghiệp vụ nếu chưa có tool result",
                "Gợi ý người dùng đặt câu hỏi nghiệp vụ khi cần số liệu cụ thể",
            ],
            "audit_trail": append_audit_event(
                base_audit,
                graph=SUPERVISOR_GRAPH_NAME,
                node=SUPERVISOR_CLASSIFY_NODE,
                event="node_success",
                metadata={
                    "dispatch": "llm_tool_call",
                    "tool_name": None,
                    "route": "knowledge",
                    "intent": "general_chat",
                },
            ),
        }
        snapshot: AgentState = dict(state)
        snapshot.update(next_state)
        checkpointer.save_checkpoint(
            runtime_context=runtime_context,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
            state=snapshot,
        )
        return next_state

    # Fallback chi dung khi LLM khong san sang.
    intent, route = classify_intent(user_message)
    next_state = {
        "intent": intent,
        "route": route,
        "task_plan": build_task_plan(route),
        "audit_trail": append_audit_event(
            base_audit,
            graph=SUPERVISOR_GRAPH_NAME,
            node=SUPERVISOR_CLASSIFY_NODE,
            event="node_success",
            metadata={
                "dispatch": "heuristic_fallback",
                "intent": intent,
                "route": route,
            },
        ),
    }
    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=SUPERVISOR_GRAPH_NAME,
        node_name=SUPERVISOR_CLASSIFY_NODE,
        state=snapshot,
    )
    return next_state


def _finalize_node(
    *,
    state: AgentState,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
    on_answer_delta: StreamDeltaCallback | None = None,
) -> AgentState:
    runtime_context = state["runtime_context"]
    answer = compose_final_answer(
        state,
        llm_client=llm_client,
        on_delta=on_answer_delta,
    )
    next_state: AgentState = {
        "final_answer": answer,
        "messages": [
            *(state.get("messages") or []),
            {"role": "assistant", "content": answer},
        ],
        "audit_trail": append_audit_event(
            state.get("audit_trail"),
            graph=SUPERVISOR_GRAPH_NAME,
            node=SUPERVISOR_FINALIZE_NODE,
            event="node_success",
        ),
    }
    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=SUPERVISOR_GRAPH_NAME,
        node_name=SUPERVISOR_FINALIZE_NODE,
        state=snapshot,
    )
    return next_state


def _route_selector(state: AgentState) -> str:
    if _should_finalize_direct(state):
        return "finalize"
    route = str(state.get("route") or "knowledge")
    if route in {
        "reporting",
        "room",
        "customer",
        "contract",
        "billing",
        "knowledge",
        "maintenance",
    }:
        return route
    return "knowledge"


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _should_finalize_direct(state: AgentState) -> bool:
    intent = str(state.get("intent") or "").strip().lower()
    if intent in {"general_chat", "memory_request"}:
        return True
    return intent.startswith("tool_dispatch:")


def _route_from_tool_name(tool_name: str) -> str:
    return resolve_route_for_tool(tool_name)


def _build_supervisor_tool_definitions(allowed_tools: set[str]) -> list[ToolDefinition]:
    return build_tool_definitions_for_domains(
        domains={
            "reporting",
            "room",
            "customer",
            "contract",
            "billing",
            "knowledge",
            "maintenance",
        },
        allowed_tools=allowed_tools,
    )


def _execute_supervisor_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict[str, Any]:
    if tool_name == TOOL_GET_TENANT_KPI:
        payload = TenantKpiInput.model_validate(args or {})
        return tool_gateway.get_tenant_kpi(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_GET_ROOM_STATUS_OVERVIEW:
        payload = RoomStatusOverviewInput.model_validate(args or {})
        return tool_gateway.get_room_status_overview(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_GET_TEAM_MEMBERS:
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
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_LIST_OVERDUE_INVOICES:
        payload = OverdueInvoicesInput.model_validate(args or {})
        return tool_gateway.list_overdue_invoices(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_GET_INVOICE_INSTALLMENTS:
        safe_args = dict(args or {})
        if not str(safe_args.get("query") or "").strip():
            safe_args["query"] = user_message
        payload = InvoiceInstallmentsInput.model_validate(safe_args)
        return tool_gateway.get_invoice_installments(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_SEARCH_CUSTOMERS:
        safe_args = dict(args or {})
        if not str(safe_args.get("query") or "").strip():
            safe_args["query"] = user_message
        payload = SearchCustomersInput.model_validate(safe_args)
        return tool_gateway.search_customers(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_GET_CONTRACTS:
        safe_args = dict(args or {})
        if not str(safe_args.get("query") or "").strip() and not safe_args.get(
            "customer_id"
        ):
            safe_args["query"] = user_message
        payload = ContractLookupInput.model_validate(safe_args)
        return tool_gateway.get_contracts(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_SEARCH_INTERNAL_KNOWLEDGE:
        safe_args = dict(args or {})
        if not str(safe_args.get("query") or "").strip():
            safe_args["query"] = user_message
        payload = SearchKnowledgeInput.model_validate(safe_args)
        return tool_gateway.search_internal_knowledge(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    if tool_name == TOOL_DISPATCH_TEAM_NOTIFICATION:
        safe_args = dict(args or {})
        if not str(safe_args.get("title") or "").strip():
            safe_args["title"] = "Thong bao tu AI Agent"
        if not str(safe_args.get("body") or "").strip():
            safe_args["body"] = user_message
        payload = TeamNotificationInput.model_validate(safe_args)
        return tool_gateway.dispatch_team_notification(
            payload,
            graph_name=SUPERVISOR_GRAPH_NAME,
            node_name=SUPERVISOR_CLASSIFY_NODE,
        ).model_dump(mode="json")
    raise ToolGatewayError(
        f"Unsupported supervisor tool: {tool_name}",
        code="tool_not_supported",
    )


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
