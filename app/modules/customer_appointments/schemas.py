from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CustomerAppointmentBase(BaseModel):
    branch_id: int | None = Field(default=None, ge=1)
    room_id: int | None = Field(default=None, ge=1)
    contact_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    note: str | None = None
    start_at: datetime
    end_at: datetime
    status: str = Field(default="SCHEDULED", max_length=32)
    source: str | None = Field(default=None, max_length=64)
    assigned_user_id: int | None = Field(default=None, ge=1)


class CustomerAppointmentCreateRequest(CustomerAppointmentBase):
    pass


class CustomerAppointmentUpdateRequest(BaseModel):
    branch_id: int | None = Field(default=None, ge=1)
    room_id: int | None = Field(default=None, ge=1)
    contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    note: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=64)
    assigned_user_id: int | None = Field(default=None, ge=1)


class CustomerAppointmentOut(BaseModel):
    id: int
    tenant_id: int
    branch_id: int | None
    room_id: int | None
    contact_name: str
    phone: str
    email: str | None
    note: str | None
    start_at: datetime
    end_at: datetime
    status: str
    source: str | None
    assigned_user_id: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CustomerAppointmentDeleteResult(BaseModel):
    deleted: bool
