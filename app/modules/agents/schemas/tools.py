from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TenantKpiInput(BaseModel):
    as_of: datetime | None = None


class TenantKpiOutput(BaseModel):
    total_rooms: int
    vacant_rooms: int
    deposited_rooms: int
    rented_rooms: int
    maintenance_rooms: int
    occupancy_rate_percent: float
    active_leases: int
    overdue_invoices: int
    overdue_amount: Decimal
    paid_revenue_current_month: Decimal
    generated_at: datetime


class OverdueInvoicesInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    min_days_overdue: int = Field(default=1, ge=1, le=3650)


class OverdueInvoiceItem(BaseModel):
    invoice_id: int
    period_month: str
    room_code: str | None = None
    renter_name: str | None = None
    renter_phone: str | None = None
    due_date: datetime
    days_overdue: int
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    status: str


class OverdueInvoicesOutput(BaseModel):
    total_items: int
    items: list[OverdueInvoiceItem] = Field(default_factory=list)
    generated_at: datetime


class SearchKnowledgeInput(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeHit(BaseModel):
    source_type: str
    source_id: str
    title: str
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchKnowledgeOutput(BaseModel):
    total_hits: int
    items: list[KnowledgeHit] = Field(default_factory=list)
    generated_at: datetime


class TeamMembersInput(BaseModel):
    team_id: int | None = Field(default=None, ge=1)
    team_limit: int = Field(default=10, ge=1, le=50)
    member_limit: int = Field(default=100, ge=1, le=500)


class TeamMemberInfo(BaseModel):
    user_id: int
    full_name: str
    email: str
    avatar_url: str | None = None
    member_role: str
    rbac_role_name: str | None = None


class TeamInfo(BaseModel):
    team_id: int
    team_name: str
    description: str | None = None
    owner_user_id: int
    member_count: int
    members: list[TeamMemberInfo] = Field(default_factory=list)


class TeamMembersOutput(BaseModel):
    total_teams: int
    items: list[TeamInfo] = Field(default_factory=list)
    generated_at: datetime


class RoomStatusOverviewInput(BaseModel):
    branch_id: int | None = Field(default=None, ge=1)
    area_id: int | None = Field(default=None, ge=1)
    building_id: int | None = Field(default=None, ge=1)
    include_rooms: bool = False
    room_limit: int = Field(default=100, ge=1, le=500)


class RoomStatusSummaryItem(BaseModel):
    status: str
    count: int


class BranchOverviewItem(BaseModel):
    branch_id: int
    branch_name: str
    room_count: int


class AreaOverviewItem(BaseModel):
    area_id: int
    area_name: str
    branch_id: int
    branch_name: str
    room_count: int


class BuildingOverviewItem(BaseModel):
    building_id: int
    building_name: str
    area_id: int
    area_name: str
    branch_id: int
    branch_name: str
    total_floors: int
    room_count: int


class RoomStatusRoomItem(BaseModel):
    room_id: int
    room_code: str
    floor_number: int
    status: str
    branch_id: int
    branch_name: str
    area_id: int
    area_name: str
    building_id: int
    building_name: str


class RoomStatusOverviewOutput(BaseModel):
    total_rooms: int
    status_summary: list[RoomStatusSummaryItem] = Field(default_factory=list)
    branches: list[BranchOverviewItem] = Field(default_factory=list)
    areas: list[AreaOverviewItem] = Field(default_factory=list)
    buildings: list[BuildingOverviewItem] = Field(default_factory=list)
    rooms: list[RoomStatusRoomItem] = Field(default_factory=list)
    generated_at: datetime


class TeamNotificationInput(BaseModel):
    team_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    recipient_user_ids: list[int] = Field(default_factory=list)


class TeamNotificationOutput(BaseModel):
    sent: bool
    draft_only: bool
    notification_id: int | None = None
    team_id: int
    notification_type: str
    title: str
    body: str
    total_recipients: int
    recipient_user_ids: list[int] = Field(default_factory=list)
    generated_at: datetime


class InvoiceInstallmentsInput(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    lease_limit: int = Field(default=5, ge=1, le=50)
    installment_limit: int = Field(default=24, ge=1, le=120)


class InstallmentInfo(BaseModel):
    invoice_id: int
    period_month: str
    installment_no: int | None = None
    installment_total: int | None = None
    due_date: datetime
    status: str
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal


class LeaseInstallmentInfo(BaseModel):
    lease_id: int
    lease_code: str
    lease_status: str
    renter_id: int
    renter_name: str
    renter_phone: str | None = None
    room_id: int
    room_code: str | None = None
    installments: list[InstallmentInfo] = Field(default_factory=list)


class InvoiceInstallmentsOutput(BaseModel):
    total_matches: int
    items: list[LeaseInstallmentInfo] = Field(default_factory=list)
    generated_at: datetime


class SearchCustomersInput(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    limit: int = Field(default=10, ge=1, le=100)


class CustomerSearchItem(BaseModel):
    renter_id: int
    full_name: str
    phone: str | None = None
    email: str | None = None
    active_lease_count: int = 0
    total_lease_count: int = 0
    outstanding_amount: Decimal = Decimal("0")


class SearchCustomersOutput(BaseModel):
    total_items: int
    items: list[CustomerSearchItem] = Field(default_factory=list)
    generated_at: datetime


class ContractLookupInput(BaseModel):
    query: str | None = Field(default=None, max_length=255)
    customer_id: int | None = Field(default=None, ge=1)
    only_active: bool = False
    limit: int = Field(default=10, ge=1, le=100)


class ContractLookupItem(BaseModel):
    lease_id: int
    lease_code: str
    lease_status: str
    renter_id: int
    renter_name: str
    renter_phone: str | None = None
    room_id: int
    room_code: str | None = None
    branch_id: int
    branch_name: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    handover_at: datetime | None = None
    rent_price: Decimal = Decimal("0")
    security_deposit_amount: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")


class ContractLookupOutput(BaseModel):
    total_items: int
    items: list[ContractLookupItem] = Field(default_factory=list)
    generated_at: datetime
