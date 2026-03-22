from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.core.models import (
    DepositStatusEnum,
    InvoiceStatusEnum,
    PaymentMethodEnum,
    PricingModeEnum,
    RoomCurrentStatusEnum,
)


class SoftDeleteResult(BaseModel):
    deleted: bool


class AreaCreateRequest(BaseModel):
    branch_id: int
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=255)


class AreaUpdateRequest(BaseModel):
    branch_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=255)


class AreaOut(BaseModel):
    id: int
    tenant_id: int
    branch_id: int
    name: str
    address: str | None
    deleted_at: datetime | None


class BuildingCreateRequest(BaseModel):
    area_id: int
    name: str = Field(min_length=1, max_length=255)
    total_floors: int = Field(ge=1)


class BuildingUpdateRequest(BaseModel):
    area_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    total_floors: int | None = Field(default=None, ge=1)


class BuildingOut(BaseModel):
    id: int
    tenant_id: int
    area_id: int
    name: str
    total_floors: int
    deleted_at: datetime | None


class RoomTypeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_price: Decimal
    pricing_mode: PricingModeEnum
    default_occupancy: int = Field(ge=1)
    max_occupancy: int = Field(ge=1)


class RoomTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_price: Decimal | None = None
    pricing_mode: PricingModeEnum | None = None
    default_occupancy: int | None = Field(default=None, ge=1)
    max_occupancy: int | None = Field(default=None, ge=1)


class RoomTypeOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    base_price: Decimal
    pricing_mode: PricingModeEnum
    default_occupancy: int
    max_occupancy: int
    deleted_at: datetime | None


class RoomCreateRequest(BaseModel):
    branch_id: int
    area_id: int
    building_id: int
    room_type_id: int
    floor_number: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    current_status: RoomCurrentStatusEnum
    current_price: Decimal


class RoomUpdateRequest(BaseModel):
    branch_id: int | None = None
    area_id: int | None = None
    building_id: int | None = None
    room_type_id: int | None = None
    floor_number: int | None = Field(default=None, ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    current_status: RoomCurrentStatusEnum | None = None
    current_price: Decimal | None = None


class RoomOut(BaseModel):
    id: int
    tenant_id: int
    branch_id: int
    area_id: int
    building_id: int
    room_type_id: int
    floor_number: int
    code: str
    current_status: RoomCurrentStatusEnum
    current_price: Decimal
    deleted_at: datetime | None


class RenterCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)


class RenterUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)


class RenterOut(BaseModel):
    id: int
    tenant_id: int
    full_name: str
    phone: str
    identity_type: str | None
    id_number: str | None
    email: str | None
    avatar_url: str | None
    date_of_birth: datetime | None
    address: str | None
    deleted_at: datetime | None


class RenterMemberCreateRequest(BaseModel):
    renter_id: int
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)
    relation: str | None = Field(default=None, max_length=64)


class RenterMemberUpdateRequest(BaseModel):
    renter_id: int | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)
    relation: str | None = Field(default=None, max_length=64)


class RenterMemberOut(BaseModel):
    id: int
    tenant_id: int
    renter_id: int
    full_name: str
    phone: str
    identity_type: str | None
    id_number: str | None
    email: str | None
    avatar_url: str | None
    date_of_birth: datetime | None
    address: str | None
    relation: str | None
    deleted_at: datetime | None


class InvoiceItemInput(BaseModel):
    fee_type_id: int | None = None
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceItemOut(BaseModel):
    id: int
    tenant_id: int
    invoice_id: int
    fee_type_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    deleted_at: datetime | None


class InvoiceCreateRequest(BaseModel):
    branch_id: int
    room_id: int
    renter_id: int
    lease_id: int | None = None
    installment_no: int | None = Field(default=None, ge=1)
    installment_total: int | None = Field(default=None, ge=1)
    period_month: str = Field(min_length=7, max_length=7)
    due_date: datetime
    reminder_at: datetime | None = None
    total_amount: Decimal
    paid_amount: Decimal = Decimal("0")
    status: InvoiceStatusEnum
    content: str = ""
    content_html: str = ""
    items: list[InvoiceItemInput] = Field(default_factory=list)


class InvoiceUpdateRequest(BaseModel):
    branch_id: int | None = None
    room_id: int | None = None
    renter_id: int | None = None
    lease_id: int | None = None
    installment_no: int | None = Field(default=None, ge=1)
    installment_total: int | None = Field(default=None, ge=1)
    period_month: str | None = Field(default=None, min_length=7, max_length=7)
    due_date: datetime | None = None
    reminder_at: datetime | None = None
    total_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    status: InvoiceStatusEnum | None = None
    content: str | None = None
    content_html: str | None = None
    items: list[InvoiceItemInput] | None = None


class InvoiceOut(BaseModel):
    id: int
    tenant_id: int
    branch_id: int
    room_id: int
    renter_id: int
    lease_id: int | None
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
    deleted_at: datetime | None
    items: list[InvoiceItemOut]


class DepositCreateRequest(BaseModel):
    room_id: int
    renter_id: int | None = None
    lease_id: int | None = None
    amount: Decimal = Field(gt=0)
    method: PaymentMethodEnum
    status: DepositStatusEnum = DepositStatusEnum.HELD
    paid_at: datetime | None = None
    content_html: str = ""


class DepositUpdateRequest(BaseModel):
    renter_id: int | None = None
    lease_id: int | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    method: PaymentMethodEnum | None = None
    status: DepositStatusEnum | None = None
    paid_at: datetime | None = None
    content_html: str | None = None


class DepositOut(BaseModel):
    id: int
    tenant_id: int
    lease_id: int | None
    room_id: int
    renter_id: int | None
    branch_id: int
    amount: Decimal
    method: PaymentMethodEnum
    status: DepositStatusEnum
    paid_at: datetime
    content_html: str
    deleted_at: datetime | None
