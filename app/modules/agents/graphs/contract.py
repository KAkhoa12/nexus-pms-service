from __future__ import annotations

from app.modules.agents.schemas.tools import ContractLookupInput
from app.modules.agents.services.audit import append_audit_event
from app.modules.agents.services.checkpointer import PersistentCheckpointer
from app.modules.agents.services.llm_client import AgentLlmClient
from app.modules.agents.services.tool_gateway import ToolGateway, ToolGatewayError
from app.modules.agents.state import AgentState
from app.modules.agents.tools.registry import build_tool_definitions_for_domains

GRAPH_NAME = "contract"
NODE_LOOKUP = "contract_lookup_contracts"
NODE_LLM_TOOL_CALL = "contract_llm_tool_call"


def run_contract_subgraph(
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

    audit_trail = append_audit_event(
        state.get("audit_trail"),
        graph=GRAPH_NAME,
        node=NODE_LOOKUP,
        event="node_start",
    )
    try:
        payload = ContractLookupInput(
            query=user_message,
            only_active=False,
            limit=10,
        )
        output = tool_gateway.get_contracts(
            payload,
            graph_name=GRAPH_NAME,
            node_name=NODE_LOOKUP,
        )
        output_json = output.model_dump(mode="json")
        next_state: AgentState = {
            "tool_results": [
                *(state.get("tool_results") or []),
                {
                    "tool_name": "get_contracts",
                    "ok": True,
                    "payload": output_json,
                },
            ],
            "retrieved_facts": [
                *(state.get("retrieved_facts") or []),
                {"source": "tool:get_contracts", "data": output_json},
            ],
            "contract_candidates": list(output_json.get("items") or []),
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=NODE_LOOKUP,
                event="node_success",
            ),
        }
    except ToolGatewayError as exc:
        next_state = {
            "tool_results": [
                *(state.get("tool_results") or []),
                {
                    "tool_name": "get_contracts",
                    "ok": False,
                    "error_code": exc.code,
                    "error_message": str(exc),
                },
            ],
            "risk_flags": [*(state.get("risk_flags") or []), exc.code],
            "audit_trail": append_audit_event(
                audit_trail,
                graph=GRAPH_NAME,
                node=NODE_LOOKUP,
                event="node_error",
                metadata={"error": str(exc), "code": exc.code},
            ),
        }

    snapshot: AgentState = dict(state)
    snapshot.update(next_state)
    checkpointer.save_checkpoint(
        runtime_context=runtime_context,
        graph_name=GRAPH_NAME,
        node_name=NODE_LOOKUP,
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
    definitions = build_tool_definitions_for_domains(
        domains={"contract"},
        allowed_tools=set(runtime_context.get("allowed_tools") or []),
    )
    if not definitions:
        return None

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
        tool_definitions=definitions,
        max_calls=1,
        tool_executor=lambda tool_name, args: _execute_contract_tool(
            tool_name=tool_name,
            args=args,
            user_message=user_message,
            tool_gateway=tool_gateway,
        ),
        conversation_messages=[
            {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
            for item in (state.get("messages") or [])
            if isinstance(item, dict)
        ],
    )
    if not execution.called:
        return None

    tool_results = [*(state.get("tool_results") or [])]
    retrieved_facts = [*(state.get("retrieved_facts") or [])]
    risk_flags = [*(state.get("risk_flags") or [])]
    contract_candidates: list[dict] = list(state.get("contract_candidates") or [])
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
            if item.tool_name == "get_contracts":
                contract_candidates = list(item.payload.get("items") or [])
        elif item.error_code:
            risk_flags.append(item.error_code)

    next_state: AgentState = {
        "tool_results": tool_results,
        "retrieved_facts": retrieved_facts,
        "risk_flags": risk_flags,
        "contract_candidates": contract_candidates,
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


def _execute_contract_tool(
    *,
    tool_name: str,
    args: dict,
    user_message: str,
    tool_gateway: ToolGateway,
) -> dict:
    if tool_name != "get_contracts":
        raise ToolGatewayError(
            f"Unsupported contract tool: {tool_name}",
            code="tool_not_supported",
        )
    safe_args = dict(args or {})
    if not str(safe_args.get("query") or "").strip() and not safe_args.get(
        "customer_id"
    ):
        safe_args["query"] = user_message
    payload = ContractLookupInput.model_validate(safe_args)
    return tool_gateway.get_contracts(
        payload,
        graph_name=GRAPH_NAME,
        node_name=NODE_LLM_TOOL_CALL,
    ).model_dump(mode="json")


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
