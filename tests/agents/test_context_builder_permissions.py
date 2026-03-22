from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.agents.config import AgentConfig
from app.modules.agents.schemas.api import AgentQueryRequest
from app.modules.agents.services import context_builder
from app.modules.auth.service import AuthContext


class _User:
    def __init__(self, *, user_id: int = 7, tenant_id: int = 3) -> None:
        self.id = user_id
        self.tenant_id = tenant_id


def _config() -> AgentConfig:
    return AgentConfig(
        default_model="gpt-oss:120b-cloud",
        cheap_model="kimi-k2.5:cloud",
        ollama_host="http://127.0.0.1:11434",
        ollama_api_key="",
        ollama_model_fallbacks="",
        max_tool_calls=8,
        default_timeout_seconds=20,
        retry_limit=2,
        enable_write_actions=False,
        require_approval_for_writes=True,
        default_execution_mode="read_only",
        checkpointer_backend="db",
        checkpointer_sqlite_path="agent_checkpoints.sqlite3",
        token_budget=8192,
        cost_budget_usd=0.5,
    )


def test_context_builder_requires_agents_query_permission(monkeypatch) -> None:
    monkeypatch.setattr(
        context_builder,
        "get_user_auth_context",
        lambda db, current_user: AuthContext(roles=set(), permissions={"rooms:view"}),
    )
    payload = AgentQueryRequest(message="Cho toi KPI van hanh hien tai")

    with pytest.raises(HTTPException) as exc_info:
        context_builder.build_runtime_context(
            db=None,
            current_user=_User(),
            payload=payload,
            config=_config(),
        )

    assert exc_info.value.status_code == 403
    assert "AI agent" in str(exc_info.value.detail)


def test_context_builder_blocks_sensitive_admin_query_without_permission(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        context_builder,
        "get_user_auth_context",
        lambda db, current_user: AuthContext(
            roles=set(),
            permissions={"agents:query", "form_templates:view"},
        ),
    )
    payload = AgentQueryRequest(message="Quyền của admin trong hệ thống là gì?")

    with pytest.raises(HTTPException) as exc_info:
        context_builder.build_runtime_context(
            db=None,
            current_user=_User(),
            payload=payload,
            config=_config(),
        )

    assert exc_info.value.status_code == 403
    assert "phân quyền" in str(exc_info.value.detail)


def test_context_builder_allows_sensitive_admin_query_with_permission(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        context_builder,
        "get_user_auth_context",
        lambda db, current_user: AuthContext(
            roles=set(),
            permissions={
                "agents:query",
                "form_templates:view",
                "users:permissions:view",
            },
        ),
    )
    payload = AgentQueryRequest(message="Quyền của admin trong hệ thống là gì?")
    runtime_context = context_builder.build_runtime_context(
        db=None,
        current_user=_User(),
        payload=payload,
        config=_config(),
    )

    assert runtime_context["tenant_id"] == 3
    assert "search_internal_knowledge" in runtime_context["allowed_tools"]
