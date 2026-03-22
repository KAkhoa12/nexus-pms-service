from __future__ import annotations

from app.modules.agents.schemas.tools import SearchKnowledgeInput
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient, ToolDefinition
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState

GRAPH_NAME = "knowledge"
NODE_NAME = "knowledge_search_internal"
NODE_LLM_TOOL_CALL = "knowledge_llm_tool_call"


def run_knowledge_subgraph(
    *,
    state: AgentState,
    user_message: str,
    tool_gateway: ToolGateway,
    checkpointer: PersistentCheckpointer,
    llm_client: AgentLlmClient | None = None,
) -> AgentState:
    runtime_context = state["runtime_context"]
    intent = str(state.get("intent") or "").strip().lower()
    if intent in {"general_chat", "memory_request"}:
        next_state: AgentState = {
            "audit_trail": append_audit_event(
                state.get("audit_trail"),
                graph=GRAPH_NAME,
                node=NODE_NAME,
                event="node_skipped",
                metadata={"reason": intent},
            )
        }
        snapshot: AgentState = dict(state)
        snapshot.update(next_state)
        checkpointer.save_checkpoint(
            runtime_context=runtime_context,
            graph_name=GRAPH_NAME,
            node_name=NODE_NAME,
            state=snapshot,
        )
        return next_state

    llm_next_state = _run_with_llm_tool_call(
        state=state,
        user_message=user_message,
        tool_gateway=tool_gateway,
        checkpointer=checkpointer,
        llm_client=llm_client,
    )
    if llm_next_state is not None:
        return llm_next_state

    audit_trail = append_audit_event(
        state.get("audit_trail"),
        graph=GRAPH_NAME,
        node=NODE_NAME,
        event="node_start",
    )
    try:
        output = tool_gateway.search_internal_knowledge(
            SearchKnowledgeInput(query=user_message, limit=5),
            graph_name=GRAPH_NAME,
            node_name=NODE_NAME,
        )
        tool_result = {
            "tool_name": "search_internal_knowledge",
            "ok": True,
            "payload": output.model_dump(mode="json"),
        }
        next_state: AgentState = {
            "tool_results": [*(state.get("tool_results") or []), tool_result],
            "retrieved_facts": [
                *(state.get("retrieved_facts") or []),
                {
                    "source": "tool:search_internal_knowledge",
                    "data": output.model_dump(mode="json"),
                },
            ],
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=NODE_NAME,
                event="node_success",
            ),
        }
    except ToolGatewayError as exc:
        next_state = {
            "tool_results": [
                *(state.get("tool_results") or []),
                {
                    "tool_name": "search_internal_knowledge",
                    "ok": False,
                    "error_code": exc.code,
                    "error_message": str(exc),
                },
            ],
            "risk_flags": [*(state.get("risk_flags") or []), exc.code],
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=NODE_NAME,
                event="node_error",
                metadata={"error": str(exc), "code": exc.code},
            ),
        }

    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=GRAPH_NAME,
        node_name=NODE_NAME,
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
                name="search_internal_knowledge",
                description="Tim kiem tai lieu noi bo trong tenant hien tai.",
                json_schema=SearchKnowledgeInput.model_json_schema(),
            )
        ],
        max_calls=1,
        tool_executor=lambda tool_name, args: _execute_knowledge_tool(
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


def _execute_knowledge_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict:
    if tool_name != "search_internal_knowledge":
        raise ToolGatewayError(
            f"Unsupported knowledge tool: {tool_name}",
            code="tool_not_supported",
        )
    safe_args = dict(args or {})
    if not str(safe_args.get("query") or "").strip():
        safe_args["query"] = user_message
    payload = SearchKnowledgeInput.model_validate(safe_args)
    return tool_gateway.search_internal_knowledge(
        payload,
        graph_name=GRAPH_NAME,
        node_name=NODE_LLM_TOOL_CALL,
    ).model_dump(mode="json")
