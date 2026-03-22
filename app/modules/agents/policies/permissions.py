from __future__ import annotations

from dataclasses import dataclass

from app.modules.agents.state import ExecutionMode

TOOL_GET_TENANT_KPI = "get_tenant_kpi"
TOOL_GET_ROOM_STATUS_OVERVIEW = "get_room_status_overview"
TOOL_GET_TEAM_MEMBERS = "get_team_members"
TOOL_LIST_OVERDUE_INVOICES = "list_overdue_invoices"
TOOL_GET_INVOICE_INSTALLMENTS = "get_invoice_installments"
TOOL_SEARCH_INTERNAL_KNOWLEDGE = "search_internal_knowledge"
TOOL_SEARCH_CUSTOMERS = "search_customers"
TOOL_GET_CONTRACTS = "get_contracts"
TOOL_CREATE_NOTIFICATION_DRAFT = "create_notification_draft"
TOOL_DISPATCH_TEAM_NOTIFICATION = "dispatch_team_notification"

READ_ONLY_TOOLS: tuple[str, ...] = (
    TOOL_GET_TENANT_KPI,
    TOOL_GET_ROOM_STATUS_OVERVIEW,
    TOOL_GET_TEAM_MEMBERS,
    TOOL_LIST_OVERDUE_INVOICES,
    TOOL_GET_INVOICE_INSTALLMENTS,
    TOOL_SEARCH_INTERNAL_KNOWLEDGE,
    TOOL_SEARCH_CUSTOMERS,
    TOOL_GET_CONTRACTS,
)

WRITE_TOOLS: tuple[str, ...] = (
    TOOL_CREATE_NOTIFICATION_DRAFT,
    TOOL_DISPATCH_TEAM_NOTIFICATION,
)


@dataclass(frozen=True)
class ToolPermissionRule:
    required_any: frozenset[str]
    execution_modes: frozenset[ExecutionMode]


TOOL_PERMISSION_RULES: dict[str, ToolPermissionRule] = {
    TOOL_GET_TENANT_KPI: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:reporting:kpi:view",
                "dashboard:view",
                "rooms:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_GET_ROOM_STATUS_OVERVIEW: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:reporting:rooms:view",
                "rooms:view",
                "room:view",
                "branches:view",
                "areas:view",
                "buildings:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_GET_TEAM_MEMBERS: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:teams:members:view",
                "teams:view",
                "teams:members:manage",
                "users:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_LIST_OVERDUE_INVOICES: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:billing:overdue:view",
                "invoices:view",
                "invoice:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_GET_INVOICE_INSTALLMENTS: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:billing:installments:view",
                "invoices:view",
                "invoice:view",
                "leases:view",
                "lease:view",
                "renters:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_SEARCH_INTERNAL_KNOWLEDGE: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:knowledge:search",
                "form_templates:view",
                "platform:landing:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_SEARCH_CUSTOMERS: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:customers:view",
                "renters:view",
                "renter:view",
                "users:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_GET_CONTRACTS: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:contracts:view",
                "leases:view",
                "lease:view",
                "invoices:view",
                "renters:view",
            }
        ),
        execution_modes=frozenset({"read_only", "propose_write", "approved_write"}),
    ),
    TOOL_CREATE_NOTIFICATION_DRAFT: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:notifications:draft:create",
                "collaboration:notifications:create",
            }
        ),
        execution_modes=frozenset({"propose_write", "approved_write"}),
    ),
    TOOL_DISPATCH_TEAM_NOTIFICATION: ToolPermissionRule(
        required_any=frozenset(
            {
                "agents:notifications:team:send",
                "collaboration:notifications:create",
                "notifications:create",
                "platform:developer:access",
            }
        ),
        execution_modes=frozenset({"propose_write", "approved_write"}),
    ),
}

FULL_ACCESS_PERMISSION_CODES = frozenset({"*", "all:*", "admin:*"})


def _can_access_with_permissions(
    *,
    permission_codes: set[str],
    has_full_access: bool,
    rule: ToolPermissionRule,
    execution_mode: ExecutionMode,
) -> bool:
    if execution_mode not in rule.execution_modes:
        return False
    if has_full_access:
        return True
    if permission_codes.intersection(FULL_ACCESS_PERMISSION_CODES):
        return True
    return bool(permission_codes.intersection(rule.required_any))


def resolve_allowed_tools(
    *,
    permission_codes: set[str],
    has_full_access: bool,
    execution_mode: ExecutionMode,
) -> list[str]:
    allowed: list[str] = []
    for tool_name, rule in TOOL_PERMISSION_RULES.items():
        if _can_access_with_permissions(
            permission_codes=permission_codes,
            has_full_access=has_full_access,
            rule=rule,
            execution_mode=execution_mode,
        ):
            allowed.append(tool_name)
    return allowed


def is_tool_allowed(
    *,
    tool_name: str,
    permission_codes: set[str],
    has_full_access: bool,
    execution_mode: ExecutionMode,
) -> bool:
    rule = TOOL_PERMISSION_RULES.get(tool_name)
    if rule is None:
        return False
    return _can_access_with_permissions(
        permission_codes=permission_codes,
        has_full_access=has_full_access,
        rule=rule,
        execution_mode=execution_mode,
    )
