from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.agents.schemas.tools import (
    ContractLookupInput,
    ContractLookupOutput,
    InvoiceInstallmentsInput,
    InvoiceInstallmentsOutput,
    LeaseInstallmentInfo,
    OverdueInvoicesOutput,
    RoomStatusOverviewInput,
    RoomStatusOverviewOutput,
    SearchCustomersInput,
    SearchCustomersOutput,
    SearchKnowledgeOutput,
    TeamInfo,
    TeamMembersInput,
    TeamMembersOutput,
    TeamNotificationInput,
    TeamNotificationOutput,
    TenantKpiInput,
    TenantKpiOutput,
)
from app.modules.agents.services.tool_gateway import ToolGateway


class _FakeSession:
    def add(self, _value):
        return None

    def flush(self):
        return None


class _FakeProvider:
    def __init__(self) -> None:
        self.called_tenant_ids: list[int] = []
        self.dispatch_dry_run_values: list[bool] = []

    def fetch_tenant_kpi(self, *, tenant_id: int) -> TenantKpiOutput:
        self.called_tenant_ids.append(tenant_id)
        return TenantKpiOutput(
            total_rooms=20,
            vacant_rooms=5,
            deposited_rooms=1,
            rented_rooms=13,
            maintenance_rooms=1,
            occupancy_rate_percent=65.0,
            active_leases=13,
            overdue_invoices=2,
            overdue_amount=Decimal("2100000"),
            paid_revenue_current_month=Decimal("12000000"),
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_overdue_invoices(
        self, *, tenant_id: int, limit: int, min_days_overdue: int
    ):
        self.called_tenant_ids.append(tenant_id)
        return OverdueInvoicesOutput(
            total_items=0,
            items=[],
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_internal_knowledge(self, *, tenant_id: int, query: str, limit: int):
        self.called_tenant_ids.append(tenant_id)
        return SearchKnowledgeOutput(
            total_hits=0,
            items=[],
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_room_status_overview(
        self,
        *,
        tenant_id: int,
        branch_id: int | None,
        area_id: int | None,
        building_id: int | None,
        include_rooms: bool,
        room_limit: int,
    ) -> RoomStatusOverviewOutput:
        self.called_tenant_ids.append(tenant_id)
        return RoomStatusOverviewOutput(
            total_rooms=0,
            status_summary=[],
            branches=[],
            areas=[],
            buildings=[],
            rooms=[],
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_team_members(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        team_limit: int,
        member_limit: int,
    ) -> TeamMembersOutput:
        self.called_tenant_ids.append(tenant_id)
        return TeamMembersOutput(
            total_teams=1,
            items=[
                TeamInfo(
                    team_id=1,
                    team_name="Team 1",
                    description=None,
                    owner_user_id=user_id,
                    member_count=1,
                    members=[],
                )
            ],
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_invoice_installments(
        self,
        *,
        tenant_id: int,
        query: str,
        lease_limit: int,
        installment_limit: int,
    ) -> InvoiceInstallmentsOutput:
        self.called_tenant_ids.append(tenant_id)
        return InvoiceInstallmentsOutput(
            total_matches=1,
            items=[
                LeaseInstallmentInfo(
                    lease_id=10,
                    lease_code="HD-10",
                    lease_status="ACTIVE",
                    renter_id=20,
                    renter_name="Nguyen Van A",
                    renter_phone="0900000000",
                    room_id=30,
                    room_code="P101",
                    installments=[],
                )
            ],
            generated_at=datetime.now(timezone.utc),
        )

    def search_customers(
        self, *, tenant_id: int, query: str, limit: int
    ) -> SearchCustomersOutput:
        self.called_tenant_ids.append(tenant_id)
        return SearchCustomersOutput(
            total_items=1,
            items=[
                {
                    "renter_id": 20,
                    "full_name": "Nguyen Van A",
                    "phone": "0900000000",
                    "email": "a@example.com",
                    "active_lease_count": 1,
                    "total_lease_count": 2,
                    "outstanding_amount": "1000000",
                }
            ],
            generated_at=datetime.now(timezone.utc),
        )

    def fetch_contracts(
        self,
        *,
        tenant_id: int,
        query: str | None,
        customer_id: int | None,
        only_active: bool,
        limit: int,
    ) -> ContractLookupOutput:
        self.called_tenant_ids.append(tenant_id)
        return ContractLookupOutput(
            total_items=1,
            items=[
                {
                    "lease_id": 10,
                    "lease_code": "HD-10",
                    "lease_status": "ACTIVE",
                    "renter_id": 20,
                    "renter_name": "Nguyen Van A",
                    "renter_phone": "0900000000",
                    "room_id": 30,
                    "room_code": "P101",
                    "branch_id": 2,
                    "branch_name": "CN 1",
                    "start_date": datetime.now(timezone.utc),
                    "end_date": None,
                    "handover_at": None,
                    "rent_price": "3000000",
                    "security_deposit_amount": "1000000",
                    "outstanding_amount": "500000",
                }
            ],
            generated_at=datetime.now(timezone.utc),
        )

    def dispatch_team_notification(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        title: str,
        body: str,
        recipient_user_ids: list[int],
        dry_run: bool,
    ) -> TeamNotificationOutput:
        self.called_tenant_ids.append(tenant_id)
        self.dispatch_dry_run_values.append(dry_run)
        return TeamNotificationOutput(
            sent=not dry_run,
            draft_only=dry_run,
            notification_id=None if dry_run else 99,
            team_id=team_id or 1,
            notification_type="ALL_USERS",
            title=title,
            body=body,
            total_recipients=3,
            recipient_user_ids=[1, 2, 3],
            generated_at=datetime.now(timezone.utc),
        )


def _runtime_context() -> dict:
    return {
        "request_id": "req_test",
        "tenant_id": 88,
        "user_id": 7,
        "role_ids": ["ADMIN"],
        "permission_codes": ["agents:query", "agents:reporting:kpi:view"],
        "has_full_access": True,
        "locale": "vi-VN",
        "thread_id": "thread_test",
        "session_id": "session_test",
        "allowed_tools": ["get_tenant_kpi"],
        "execution_mode": "read_only",
        "approval_required": False,
        "model_tier": "standard",
        "timeout_seconds": 20,
        "retry_limit": 1,
        "max_tool_calls": 8,
        "cost_budget_usd": 0.2,
        "memory_namespace": "tenant:88:thread:thread_test",
    }


def test_tool_gateway_enforces_tenant_scope_from_runtime_context() -> None:
    provider = _FakeProvider()
    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=_runtime_context(),
        provider=provider,
    )

    _ = gateway.get_tenant_kpi(
        TenantKpiInput(),
        graph_name="reporting",
        node_name="node",
    )

    assert provider.called_tenant_ids == [88]


def test_tool_gateway_denies_non_whitelisted_tool() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = []

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    with pytest.raises(Exception):
        gateway.get_tenant_kpi(
            TenantKpiInput(),
            graph_name="reporting",
            node_name="node",
        )


def test_tool_gateway_room_overview_enforces_tenant_scope() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = ["get_room_status_overview"]
    context["permission_codes"] = ["agents:reporting:rooms:view"]

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    _ = gateway.get_room_status_overview(
        RoomStatusOverviewInput(),
        graph_name="reporting",
        node_name="node",
    )
    assert provider.called_tenant_ids == [88]


def test_tool_gateway_notification_dispatch_is_draft_in_propose_write() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = ["dispatch_team_notification"]
    context["permission_codes"] = ["collaboration:notifications:create"]
    context["execution_mode"] = "propose_write"

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    _ = gateway.dispatch_team_notification(
        TeamNotificationInput(team_id=2, title="Thong bao", body="Noi dung"),
        graph_name="maintenance",
        node_name="node",
    )
    assert provider.dispatch_dry_run_values == [True]


def test_tool_gateway_invoice_installments_uses_tenant_scope() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = ["get_invoice_installments"]
    context["permission_codes"] = ["invoices:view"]

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    _ = gateway.get_invoice_installments(
        InvoiceInstallmentsInput(query="HD-10"),
        graph_name="billing",
        node_name="node",
    )
    assert provider.called_tenant_ids == [88]


def test_tool_gateway_search_customers_uses_tenant_scope() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = ["search_customers"]
    context["permission_codes"] = ["renters:view"]

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    _ = gateway.search_customers(
        SearchCustomersInput(query="Nguyen Van A"),
        graph_name="customer",
        node_name="node",
    )
    assert provider.called_tenant_ids == [88]


def test_tool_gateway_get_contracts_uses_tenant_scope() -> None:
    provider = _FakeProvider()
    context = _runtime_context()
    context["allowed_tools"] = ["get_contracts"]
    context["permission_codes"] = ["leases:view"]

    gateway = ToolGateway(
        db=_FakeSession(),
        runtime_context=context,
        provider=provider,
    )
    _ = gateway.get_contracts(
        ContractLookupInput(query="HD-10"),
        graph_name="contract",
        node_name="node",
    )
    assert provider.called_tenant_ids == [88]
