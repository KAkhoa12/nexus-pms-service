from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class ServiceFeeBase(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    unit: str | None = Field(default=None, max_length=64)
    default_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    default_price: Decimal | None = Field(default=None, ge=0)
    billing_cycle: str = Field(default="MONTHLY", max_length=32)
    cycle_interval_months: int | None = Field(default=None, ge=1, le=120)
    charge_mode: str = Field(default="FIXED", max_length=32)
    description: str | None = None
    is_active: bool = True


class ServiceFeeCreateRequest(ServiceFeeBase):
    pass


class ServiceFeeUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, max_length=64)
    default_quantity: Decimal | None = Field(default=None, gt=0)
    default_price: Decimal | None = Field(default=None, ge=0)
    billing_cycle: str | None = Field(default=None, max_length=32)
    cycle_interval_months: int | None = Field(default=None, ge=1, le=120)
    charge_mode: str | None = Field(default=None, max_length=32)
    description: str | None = None
    is_active: bool | None = None


class ServiceFeeOut(BaseModel):
    id: int
    tenant_id: int
    code: str
    name: str
    unit: str | None
    default_quantity: Decimal
    default_price: Decimal | None
    billing_cycle: str
    cycle_interval_months: int | None
    charge_mode: str
    description: str | None
    is_active: bool


class ServiceFeeDeleteResult(BaseModel):
    deleted: bool
