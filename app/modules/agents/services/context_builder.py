from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.agents.config import AgentConfig
from app.modules.agents.policies.execution_mode import (
    normalize_execution_mode,
    requires_approval_for_mode,
)
from app.modules.agents.policies.permissions import resolve_allowed_tools
from app.modules.agents.schemas.api import AgentQueryRequest
from app.modules.agents.state import AgentRuntimeContext
from app.modules.auth.service import get_user_auth_context

AGENT_ENTRY_PERMISSION_CODES = frozenset({"agents:query"})
SENSITIVE_RBAC_QUERY_PERMISSION_CODES = frozenset(
    {
        "users:permissions:view",
        "users:permissions:manage",
        "users:permissions:update",
        "users:permissions:create",
        "users:manage",
        "platform:developer:access",
        "teams:members:manage",
    }
)
_RBAC_QUERY_TERMS = frozenset(
    {
        "permission",
        "permissions",
        "phan quyen",
        "phân quyền",
        "rbac",
        "role",
        "roles",
        "vai tro",
        "vai trò",
        "quyen",
        "quyền",
    }
)
_PRIVILEGED_ROLE_TERMS = frozenset(
    {
        "admin",
        "owner",
        "super_admin",
        "tenant_admin",
        "quan tri",
        "quản trị",
    }
)


def build_runtime_context(
    *,
    db: Session,
    current_user,
    payload: AgentQueryRequest,
    config: AgentConfig,
) -> AgentRuntimeContext:
    auth_context = get_user_auth_context(db, current_user)
    mode = normalize_execution_mode(
        requested_mode=payload.execution_mode,
        default_mode=config.default_execution_mode,
        enable_write_actions=config.enable_write_actions,
    )
    permission_codes = set(auth_context.permissions)
    if not auth_context.has_full_access and not permission_codes.intersection(
        AGENT_ENTRY_PERMISSION_CODES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền sử dụng AI agent",
        )
    if _is_sensitive_rbac_query(payload.message) and (
        not auth_context.has_full_access
        and not permission_codes.intersection(SENSITIVE_RBAC_QUERY_PERMISSION_CODES)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền tra cứu thông tin phân quyền quản trị",
        )

    allowed_tools = resolve_allowed_tools(
        permission_codes=permission_codes,
        has_full_access=auth_context.has_full_access,
        execution_mode=mode,
    )
    if not allowed_tools:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền sử dụng AI agent trong không gian làm việc hiện tại",
        )

    thread_id = (payload.thread_id or "").strip() or f"thread_{uuid4().hex}"
    session_id = (payload.session_id or "").strip() or f"session_{uuid4().hex}"
    request_id = f"req_{uuid4().hex}"
    tenant_id = int(getattr(current_user, "tenant_id"))
    user_id = int(getattr(current_user, "id"))

    return AgentRuntimeContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        role_ids=sorted(auth_context.roles),
        permission_codes=sorted(permission_codes),
        has_full_access=auth_context.has_full_access,
        locale=(payload.locale or "vi-VN").strip() or "vi-VN",
        thread_id=thread_id,
        session_id=session_id,
        allowed_tools=allowed_tools,
        execution_mode=mode,
        approval_required=requires_approval_for_mode(mode),
        model_tier=payload.model_tier,
        timeout_seconds=config.default_timeout_seconds,
        retry_limit=config.retry_limit,
        max_tool_calls=config.max_tool_calls,
        cost_budget_usd=config.cost_budget_usd,
        memory_namespace=f"tenant:{tenant_id}:thread:{thread_id}",
    )


def _is_sensitive_rbac_query(message: str) -> bool:
    normalized = " ".join((message or "").strip().lower().split())
    if not normalized:
        return False
    has_rbac_term = any(term in normalized for term in _RBAC_QUERY_TERMS)
    has_privileged_term = any(term in normalized for term in _PRIVILEGED_ROLE_TERMS)
    return has_rbac_term and has_privileged_term
