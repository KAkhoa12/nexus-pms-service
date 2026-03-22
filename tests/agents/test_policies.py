from __future__ import annotations

import pytest

from app.modules.agents.policies.execution_mode import ensure_write_allowed
from app.modules.agents.policies.permissions import (
    TOOL_DISPATCH_TEAM_NOTIFICATION,
    TOOL_GET_CONTRACTS,
    TOOL_SEARCH_CUSTOMERS,
    resolve_allowed_tools,
)


def test_permission_enforcement_blocks_when_no_permissions() -> None:
    allowed = resolve_allowed_tools(
        permission_codes=set(),
        has_full_access=False,
        execution_mode="read_only",
    )
    assert allowed == []


def test_read_only_mode_disallows_write_actions() -> None:
    with pytest.raises(Exception):
        ensure_write_allowed("read_only")


def test_read_only_mode_does_not_allow_team_notification_dispatch() -> None:
    allowed = resolve_allowed_tools(
        permission_codes={"collaboration:notifications:create"},
        has_full_access=False,
        execution_mode="read_only",
    )
    assert TOOL_DISPATCH_TEAM_NOTIFICATION not in allowed


def test_read_only_mode_allows_customer_tools_with_domain_permissions() -> None:
    allowed = resolve_allowed_tools(
        permission_codes={"renters:view", "leases:view"},
        has_full_access=False,
        execution_mode="read_only",
    )
    assert TOOL_SEARCH_CUSTOMERS in allowed
    assert TOOL_GET_CONTRACTS in allowed
