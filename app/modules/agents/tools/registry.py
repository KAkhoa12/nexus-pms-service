from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

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
from app.modules.agents.services.llm_client import ToolDefinition
from app.modules.agents.state import AgentRoute

SchemaBuilder = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    domain: AgentRoute
    description: str
    schema_builder: SchemaBuilder


TOOL_REGISTRY: tuple[AgentToolSpec, ...] = (
    AgentToolSpec(
        name=TOOL_GET_TENANT_KPI,
        domain="reporting",
        description="Lay KPI tong quan tenant hien tai.",
        schema_builder=TenantKpiInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_GET_TEAM_MEMBERS,
        domain="reporting",
        description="Lay danh sach team va thanh vien ma user hien tai co the xem.",
        schema_builder=TeamMembersInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_GET_ROOM_STATUS_OVERVIEW,
        domain="room",
        description=(
            "Lay tong quan trang thai phong. Co the loc theo branch_id, area_id, building_id."
        ),
        schema_builder=RoomStatusOverviewInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_SEARCH_CUSTOMERS,
        domain="customer",
        description=(
            "Tim kiem khach thue (renter) theo ten, so dien thoai, email hoac ma khach."
        ),
        schema_builder=SearchCustomersInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_GET_CONTRACTS,
        domain="contract",
        description=(
            "Tra cuu hop dong thue theo customer_id hoac keyword (ma HD, ten khach, ma phong)."
        ),
        schema_builder=ContractLookupInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_LIST_OVERDUE_INVOICES,
        domain="billing",
        description="Lay danh sach hoa don qua han cua tenant hien tai.",
        schema_builder=OverdueInvoicesInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_GET_INVOICE_INSTALLMENTS,
        domain="billing",
        description="Tra cuu ky han hoa don theo ma hop dong hoac thong tin khach hang.",
        schema_builder=InvoiceInstallmentsInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_SEARCH_INTERNAL_KNOWLEDGE,
        domain="knowledge",
        description="Tim kiem tai lieu noi bo trong tenant hien tai.",
        schema_builder=SearchKnowledgeInput.model_json_schema,
    ),
    AgentToolSpec(
        name=TOOL_DISPATCH_TEAM_NOTIFICATION,
        domain="maintenance",
        description=(
            "Gui hoac tao nhap thong bao cho thanh vien trong team (phu thuoc execution mode va quyen)."
        ),
        schema_builder=TeamNotificationInput.model_json_schema,
    ),
)


def build_tool_definitions_for_domains(
    *,
    domains: set[AgentRoute],
    allowed_tools: set[str],
) -> list[ToolDefinition]:
    definitions: list[ToolDefinition] = []
    for spec in TOOL_REGISTRY:
        if spec.domain not in domains:
            continue
        if spec.name not in allowed_tools:
            continue
        definitions.append(
            ToolDefinition(
                name=spec.name,
                description=spec.description,
                json_schema=spec.schema_builder(),
            )
        )
    return definitions


def resolve_route_for_tool(tool_name: str) -> AgentRoute:
    for spec in TOOL_REGISTRY:
        if spec.name == tool_name:
            return spec.domain
    return "knowledge"
