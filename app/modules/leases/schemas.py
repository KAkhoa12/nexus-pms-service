from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.core.models import (
    InvoiceStatusEnum,
    LeaseStatusEnum,
    PaymentMethodEnum,
    PricingModeEnum,
)


class LeaseSelectedServiceFeeRequest(BaseModel):
    service_fee_id: int = Field(ge=1)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class LeaseCreateRequest(BaseModel):
    branch_id: int = Field(ge=1)
    room_id: int = Field(ge=1)
    renter_id: int = Field(ge=1)
    lease_years: int = Field(default=1, ge=1, le=50)
    handover_at: datetime
    start_date: datetime | None = None
    end_date: datetime | None = None
    rent_price: Decimal = Field(gt=0)
    pricing_mode: PricingModeEnum
    status: LeaseStatusEnum = LeaseStatusEnum.ACTIVE
    content: str = ""
    content_html: str = ""
    security_deposit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    security_deposit_paid_amount: Decimal | None = Field(default=None, ge=0)
    security_deposit_payment_method: PaymentMethodEnum | None = None
    security_deposit_paid_at: datetime | None = None
    security_deposit_note: str = ""
    mark_room_as_deposited: bool = True
    auto_generate_invoices: bool = True
    invoice_reminder_days: int = Field(default=7, ge=0, le=60)
    selected_service_fees: list[LeaseSelectedServiceFeeRequest] | None = None


class LeaseUpdateRequest(BaseModel):
    lease_years: int | None = Field(default=None, ge=1, le=50)
    handover_at: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    rent_price: Decimal | None = Field(default=None, gt=0)
    pricing_mode: PricingModeEnum | None = None
    status: LeaseStatusEnum | None = None
    content: str | None = None
    content_html: str | None = None
    security_deposit_amount: Decimal | None = Field(default=None, ge=0)
    security_deposit_paid_amount: Decimal | None = Field(default=None, ge=0)
    security_deposit_payment_method: PaymentMethodEnum | None = None
    security_deposit_paid_at: datetime | None = None
    security_deposit_note: str | None = None


class LeaseOut(BaseModel):
    id: int
    tenant_id: int
    branch_id: int
    room_id: int
    room_code: str | None
    renter_id: int
    renter_full_name: str | None
    renter_phone: str | None
    created_by_user_id: int | None
    lease_years: int
    handover_at: datetime | None
    start_date: datetime
    end_date: datetime | None
    rent_price: Decimal
    pricing_mode: PricingModeEnum
    status: LeaseStatusEnum
    content: str
    content_html: str
    security_deposit_amount: Decimal
    security_deposit_paid_amount: Decimal
    security_deposit_payment_method: PaymentMethodEnum | None
    security_deposit_paid_at: datetime | None
    security_deposit_note: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class LeaseRenterSummaryOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: str | None


class LeaseRoomSummaryOut(BaseModel):
    id: int
    code: str
    branch_id: int
    area_id: int
    building_id: int
    floor_number: int
    current_status: str


class LeaseInstallmentItemOut(BaseModel):
    id: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class LeaseInstallmentOut(BaseModel):
    id: int
    installment_no: int | None
    installment_total: int | None
    period_month: str
    due_date: datetime
    reminder_at: datetime | None
    total_amount: Decimal
    paid_amount: Decimal
    status: InvoiceStatusEnum
    content: str
    content_html: str
    items: list[LeaseInstallmentItemOut]


class LeaseDetailOut(BaseModel):
    lease: LeaseOut
    renter: LeaseRenterSummaryOut | None
    room: LeaseRoomSummaryOut | None
    installments: list[LeaseInstallmentOut]


class LeaseInstallmentItemUpdateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal


class LeaseInstallmentUpdateRequest(BaseModel):
    due_date: datetime | None = None
    reminder_at: datetime | None = None
    status: InvoiceStatusEnum | None = None
    content: str | None = None
    content_html: str | None = None
    items: list[LeaseInstallmentItemUpdateRequest] | None = None


class LeaseDeleteResult(BaseModel):
    deleted: bool
