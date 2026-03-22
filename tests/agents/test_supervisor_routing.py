from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.modules.agents.graphs.supervisor import build_supervisor_executor
from app.modules.agents.schemas.tools import (
    OverdueInvoiceItem,
    OverdueInvoicesOutput,
    SearchKnowledgeOutput,
    TenantKpiOutput,
)


class _FakeCheckpointer:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []

    def save_checkpoint(
        self,
        *,
        runtime_context,
        graph_name: str,
        node_name: str,
        state,
        metadata=None,
    ) -> int:
        self.saved.append((graph_name, node_name))
        return len(self.saved)

    def load_latest_state(self, *, tenant_id: int, user_id: int, thread_id: str):
        return None

    def list_checkpoints(
        self, *, tenant_id: int, user_id: int, thread_id: str, limit: int = 50
    ):
        return []


class _FakeGateway:
    def __init__(self) -> None:
        self.search_calls = 0

    def get_tenant_kpi(self, _payload, *, graph_name: str, node_name: str):
        return TenantKpiOutput(
            total_rooms=10,
            vacant_rooms=2,
            deposited_rooms=1,
            rented_rooms=6,
            maintenance_rooms=1,
            occupancy_rate_percent=60.0,
            active_leases=6,
            overdue_invoices=1,
            overdue_amount=Decimal("500000"),
            paid_revenue_current_month=Decimal("6000000"),
            generated_at=datetime.now(timezone.utc),
        )

    def list_overdue_invoices(self, _payload, *, graph_name: str, node_name: str):
        return OverdueInvoicesOutput(
            total_items=1,
            items=[
                OverdueInvoiceItem(
                    invoice_id=1,
                    period_month="2026-03",
                    room_code="P101",
                    renter_name="Nguyen Van A",
                    renter_phone="0900000000",
                    due_date=datetime.now(timezone.utc),
                    days_overdue=5,
                    total_amount=Decimal("3000000"),
                    paid_amount=Decimal("1000000"),
                    outstanding_amount=Decimal("2000000"),
                    status="OVERDUE",
                )
            ],
            generated_at=datetime.now(timezone.utc),
        )

    def search_internal_knowledge(self, _payload, *, graph_name: str, node_name: str):
        self.search_calls += 1
        return SearchKnowledgeOutput(
            total_hits=0,
            items=[],
            generated_at=datetime.now(timezone.utc),
        )


def _base_state(message: str) -> dict:
    return {
        "runtime_context": {
            "request_id": "req_test",
            "tenant_id": 1,
            "user_id": 1,
            "role_ids": ["ADMIN"],
            "permission_codes": ["agents:query", "agents:billing:overdue:view"],
            "has_full_access": True,
            "locale": "vi-VN",
            "thread_id": "thread_1",
            "session_id": "session_1",
            "allowed_tools": [
                "get_tenant_kpi",
                "list_overdue_invoices",
                "search_internal_knowledge",
            ],
            "execution_mode": "read_only",
            "approval_required": False,
            "model_tier": "standard",
            "timeout_seconds": 20,
            "retry_limit": 1,
            "max_tool_calls": 8,
            "cost_budget_usd": 0.2,
            "memory_namespace": "tenant:1:thread:thread_1",
        },
        "messages": [{"role": "user", "content": message}],
        "tool_results": [],
        "retrieved_facts": [],
        "risk_flags": [],
        "audit_trail": [],
        "task_plan": [],
    }


def test_supervisor_routes_to_billing_for_overdue_invoice_query() -> None:
    checkpointer = _FakeCheckpointer()
    gateway = _FakeGateway()
    executor = build_supervisor_executor(
        tool_gateway=gateway,
        checkpointer=checkpointer,
    )
    result = executor(_base_state("Cho tôi danh sách hóa đơn quá hạn"))
    assert result["route"] == "billing"
    assert "hóa đơn quá hạn" in result["final_answer"].lower()
    assert len(checkpointer.saved) >= 3
    assert gateway.search_calls == 0


def test_supervisor_handles_general_chat_without_knowledge_tool_call() -> None:
    checkpointer = _FakeCheckpointer()
    gateway = _FakeGateway()
    executor = build_supervisor_executor(
        tool_gateway=gateway,
        checkpointer=checkpointer,
    )
    result = executor(_base_state("Chào bạn, bạn là ai?"))
    assert result["intent"] == "general_chat"
    assert result["route"] == "knowledge"
    assert "ai trợ lý" in result["final_answer"].lower()
    assert gateway.search_calls == 0


def test_supervisor_handles_memory_request_without_knowledge_tool_call() -> None:
    checkpointer = _FakeCheckpointer()
    gateway = _FakeGateway()
    executor = build_supervisor_executor(
        tool_gateway=gateway,
        checkpointer=checkpointer,
    )
    result = executor(_base_state("Hãy ghi nhớ tôi là Nguyễn Văn A"))
    assert result["intent"] == "memory_request"
    assert result["route"] == "knowledge"
    assert "read_only" in result["final_answer"].lower()
    assert gateway.search_calls == 0


def test_supervisor_detects_plain_toi_la_as_memory_request() -> None:
    checkpointer = _FakeCheckpointer()
    gateway = _FakeGateway()
    executor = build_supervisor_executor(
        tool_gateway=gateway,
        checkpointer=checkpointer,
    )
    result = executor(_base_state("Tôi là Nguyễn Văn A"))
    assert result["intent"] == "memory_request"
    assert gateway.search_calls == 0


def test_supervisor_fallbacks_to_general_chat_for_non_domain_message() -> None:
    checkpointer = _FakeCheckpointer()
    gateway = _FakeGateway()
    executor = build_supervisor_executor(
        tool_gateway=gateway,
        checkpointer=checkpointer,
    )
    result = executor(_base_state("Hôm nay trời đẹp quá"))
    assert result["intent"] == "general_chat"
    assert gateway.search_calls == 0
