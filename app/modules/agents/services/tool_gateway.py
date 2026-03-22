from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, TypeVar

from sqlalchemy.orm import Session

from app.modules.agents.policies.errors import AgentPolicyError
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
    is_tool_allowed,
)
from app.modules.agents.schemas.tools import (
    ContractLookupInput,
    ContractLookupOutput,
    InvoiceInstallmentsInput,
    InvoiceInstallmentsOutput,
    OverdueInvoicesInput,
    OverdueInvoicesOutput,
    RoomStatusOverviewInput,
    RoomStatusOverviewOutput,
    SearchCustomersInput,
    SearchCustomersOutput,
    SearchKnowledgeInput,
    SearchKnowledgeOutput,
    TeamMembersInput,
    TeamMembersOutput,
    TeamNotificationInput,
    TeamNotificationOutput,
    TenantKpiInput,
    TenantKpiOutput,
)
from app.modules.agents.services.audit import ToolCallAuditInput, record_tool_call
from app.modules.agents.services.domain_services import (
    DomainDataProvider,
    SqlAlchemyDomainDataProvider,
)
from app.modules.agents.state import AgentRuntimeContext, ExecutionMode

T = TypeVar("T")


class ToolGatewayError(Exception):
    def __init__(self, message: str, *, code: str = "tool_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ToolGateway:
    db: Session
    runtime_context: AgentRuntimeContext
    provider: DomainDataProvider | None = None

    def __post_init__(self) -> None:
        if self.provider is None:
            self.provider = SqlAlchemyDomainDataProvider(self.db)
        self._tool_call_count = 0

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    def get_tenant_kpi(
        self, payload: TenantKpiInput, *, graph_name: str, node_name: str
    ) -> TenantKpiOutput:
        return self._run_tool(
            tool_name=TOOL_GET_TENANT_KPI,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_tenant_kpi(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"])
            ),
        )

    def get_room_status_overview(
        self, payload: RoomStatusOverviewInput, *, graph_name: str, node_name: str
    ) -> RoomStatusOverviewOutput:
        return self._run_tool(
            tool_name=TOOL_GET_ROOM_STATUS_OVERVIEW,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_room_status_overview(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                branch_id=payload.branch_id,
                area_id=payload.area_id,
                building_id=payload.building_id,
                include_rooms=payload.include_rooms,
                room_limit=payload.room_limit,
            ),
        )

    def get_team_members(
        self, payload: TeamMembersInput, *, graph_name: str, node_name: str
    ) -> TeamMembersOutput:
        return self._run_tool(
            tool_name=TOOL_GET_TEAM_MEMBERS,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_team_members(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                user_id=int(self.runtime_context["user_id"]),
                team_id=payload.team_id,
                team_limit=payload.team_limit,
                member_limit=payload.member_limit,
            ),
        )

    def list_overdue_invoices(
        self, payload: OverdueInvoicesInput, *, graph_name: str, node_name: str
    ) -> OverdueInvoicesOutput:
        return self._run_tool(
            tool_name=TOOL_LIST_OVERDUE_INVOICES,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_overdue_invoices(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                limit=payload.limit,
                min_days_overdue=payload.min_days_overdue,
            ),
        )

    def get_invoice_installments(
        self, payload: InvoiceInstallmentsInput, *, graph_name: str, node_name: str
    ) -> InvoiceInstallmentsOutput:
        return self._run_tool(
            tool_name=TOOL_GET_INVOICE_INSTALLMENTS,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_invoice_installments(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                query=payload.query,
                lease_limit=payload.lease_limit,
                installment_limit=payload.installment_limit,
            ),
        )

    def search_customers(
        self, payload: SearchCustomersInput, *, graph_name: str, node_name: str
    ) -> SearchCustomersOutput:
        return self._run_tool(
            tool_name=TOOL_SEARCH_CUSTOMERS,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.search_customers(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                query=payload.query,
                limit=payload.limit,
            ),
        )

    def get_contracts(
        self, payload: ContractLookupInput, *, graph_name: str, node_name: str
    ) -> ContractLookupOutput:
        return self._run_tool(
            tool_name=TOOL_GET_CONTRACTS,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_contracts(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                query=payload.query,
                customer_id=payload.customer_id,
                only_active=payload.only_active,
                limit=payload.limit,
            ),
        )

    def dispatch_team_notification(
        self, payload: TeamNotificationInput, *, graph_name: str, node_name: str
    ) -> TeamNotificationOutput:
        execution_mode = str(self.runtime_context.get("execution_mode", "read_only"))
        dry_run = execution_mode != "approved_write"
        return self._run_tool(
            tool_name=TOOL_DISPATCH_TEAM_NOTIFICATION,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.dispatch_team_notification(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                user_id=int(self.runtime_context["user_id"]),
                team_id=payload.team_id,
                title=payload.title,
                body=payload.body,
                recipient_user_ids=payload.recipient_user_ids,
                dry_run=dry_run,
            ),
        )

    def search_internal_knowledge(
        self, payload: SearchKnowledgeInput, *, graph_name: str, node_name: str
    ) -> SearchKnowledgeOutput:
        return self._run_tool(
            tool_name=TOOL_SEARCH_INTERNAL_KNOWLEDGE,
            graph_name=graph_name,
            node_name=node_name,
            input_payload=payload.model_dump(mode="json"),
            fn=lambda: self.provider.fetch_internal_knowledge(  # type: ignore[union-attr]
                tenant_id=int(self.runtime_context["tenant_id"]),
                query=payload.query,
                limit=payload.limit,
            ),
        )

    def _run_tool(
        self,
        *,
        tool_name: str,
        graph_name: str,
        node_name: str,
        input_payload: dict[str, Any],
        fn: Callable[[], T],
    ) -> T:
        self._ensure_tool_allowed(tool_name=tool_name)
        self._ensure_within_budget()

        retry_limit = int(self.runtime_context["retry_limit"])
        timeout_seconds = int(self.runtime_context["timeout_seconds"])
        last_error: Exception | None = None

        for attempt in range(retry_limit + 1):
            started = perf_counter()
            try:
                result = fn()
                elapsed_ms = int((perf_counter() - started) * 1000)
                if elapsed_ms > timeout_seconds * 1000:
                    raise ToolGatewayError(
                        f"Tool {tool_name} timed out after {elapsed_ms}ms",
                        code="tool_timeout",
                    )

                self._tool_call_count += 1
                record_tool_call(
                    self.db,
                    ToolCallAuditInput(
                        tenant_id=int(self.runtime_context["tenant_id"]),
                        user_id=int(self.runtime_context["user_id"]),
                        request_id=str(self.runtime_context["request_id"]),
                        thread_id=str(self.runtime_context["thread_id"]),
                        graph_name=graph_name,
                        node_name=node_name,
                        tool_name=tool_name,
                        status="success",
                        latency_ms=elapsed_ms,
                        retry_count=attempt,
                        input_payload=input_payload,
                        output_payload=_normalize_output_payload(result),
                    ),
                )
                return result
            except AgentPolicyError:
                raise
            except Exception as exc:
                last_error = exc
                elapsed_ms = int((perf_counter() - started) * 1000)
                if attempt >= retry_limit:
                    record_tool_call(
                        self.db,
                        ToolCallAuditInput(
                            tenant_id=int(self.runtime_context["tenant_id"]),
                            user_id=int(self.runtime_context["user_id"]),
                            request_id=str(self.runtime_context["request_id"]),
                            thread_id=str(self.runtime_context["thread_id"]),
                            graph_name=graph_name,
                            node_name=node_name,
                            tool_name=tool_name,
                            status="error",
                            latency_ms=elapsed_ms,
                            retry_count=attempt,
                            input_payload=input_payload,
                            error_code=getattr(exc, "code", "tool_error"),
                            error_message=str(exc),
                        ),
                    )
                    raise ToolGatewayError(
                        f"Tool {tool_name} failed: {exc}",
                        code=getattr(exc, "code", "tool_error"),
                    ) from exc

        raise ToolGatewayError(
            f"Tool {tool_name} failed: {last_error}",
            code=getattr(last_error, "code", "tool_error"),
        )

    def _ensure_tool_allowed(self, *, tool_name: str) -> None:
        allowed_tools = set(self.runtime_context["allowed_tools"])
        if tool_name not in allowed_tools:
            raise AgentPolicyError(
                f"Tool {tool_name} is not whitelisted for current context",
                code="tool_not_whitelisted",
            )
        if not is_tool_allowed(
            tool_name=tool_name,
            permission_codes=set(self.runtime_context["permission_codes"]),
            has_full_access=bool(self.runtime_context.get("has_full_access", False))
            or _has_full_access_permission(
                set(self.runtime_context["permission_codes"])
            ),
            execution_mode=self.runtime_context["execution_mode"],
        ):
            raise AgentPolicyError(
                f"Permission denied for tool {tool_name}",
                code="permission_denied",
            )

    def _ensure_within_budget(self) -> None:
        max_calls = int(self.runtime_context["max_tool_calls"])
        if self._tool_call_count >= max_calls:
            raise ToolGatewayError(
                f"Maximum tool call budget exceeded ({max_calls})",
                code="tool_budget_exceeded",
            )


def _normalize_output_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return {"value": str(result)}


def _has_full_access_permission(permission_codes: set[str]) -> bool:
    return bool(permission_codes.intersection({"*", "all:*", "admin:*"}))


def is_read_only_mode(mode: ExecutionMode) -> bool:
    return mode == "read_only"
