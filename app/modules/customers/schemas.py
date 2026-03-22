from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CustomerType = Literal["renter", "member"]
CustomerLeaseState = Literal["NOT_RENTED", "ACTIVE", "PAST"]


class CustomerListItemOut(BaseModel):
    id: int
    customer_type: CustomerType
    full_name: str
    phone: str
    email: str | None
    identity_type: str | None
    id_number: str | None
    avatar_url: str | None
    date_of_birth: datetime | None
    address: str | None
    relation: str | None
    renter_id: int | None
    primary_renter_name: str | None
    lease_state: CustomerLeaseState
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CustomerPrimaryRenterOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: str | None
    identity_type: str | None
    id_number: str | None
    avatar_url: str | None
    date_of_birth: datetime | None
    address: str | None


class CustomerDetailOut(BaseModel):
    customer: CustomerListItemOut
    primary_renter: CustomerPrimaryRenterOut | None
    companions: list[CustomerListItemOut]


class CustomerCreateRequest(BaseModel):
    customer_type: CustomerType
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)
    relation: str | None = Field(default=None, max_length=64)
    renter_id: int | None = Field(default=None, ge=1)


class CustomerCompanionCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    identity_type: str | None = Field(default=None, max_length=32)
    id_number: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)
    date_of_birth: datetime | None = None
    address: str | None = Field(default=None, max_length=255)
    relation: str | None = Field(default=None, max_length=64)


class CustomerUploadOut(BaseModel):
    object_name: str
    file_name: str
    file_url: str
    access_url: str
    mime_type: str | None
    size_bytes: int
    is_image: bool
