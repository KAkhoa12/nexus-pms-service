from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MaterialAssetTypeBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MaterialAssetTypeCreateRequest(MaterialAssetTypeBase):
    pass


class MaterialAssetTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class MaterialAssetTypeOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class MaterialAssetImageOut(BaseModel):
    id: int
    image_url: str
    caption: str | None
    sort_order: int
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class MaterialAssetBase(BaseModel):
    room_id: int | None = Field(default=None, ge=1)
    renter_id: int | None = Field(default=None, ge=1)
    owner_scope: str = Field(default="RENTER", max_length=16)
    asset_type_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    identifier: str | None = Field(default=None, max_length=64)
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    unit: str | None = Field(default=None, max_length=64)
    status: str = Field(default="ACTIVE", max_length=32)
    condition_status: str = Field(default="GOOD", max_length=32)
    acquired_at: datetime | None = None
    metadata_json: str | None = None
    note: str | None = None
    primary_image_url: str | None = Field(default=None, max_length=1024)
    image_urls: list[str] = Field(default_factory=list)


class MaterialAssetCreateRequest(MaterialAssetBase):
    pass


class MaterialAssetUpdateRequest(BaseModel):
    room_id: int | None = Field(default=None, ge=1)
    renter_id: int | None = Field(default=None, ge=1)
    owner_scope: str | None = Field(default=None, max_length=16)
    asset_type_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    identifier: str | None = Field(default=None, max_length=64)
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    condition_status: str | None = Field(default=None, max_length=32)
    acquired_at: datetime | None = None
    metadata_json: str | None = None
    note: str | None = None
    primary_image_url: str | None = Field(default=None, max_length=1024)
    image_urls: list[str] | None = None


class MaterialAssetOut(BaseModel):
    id: int
    tenant_id: int
    room_id: int
    renter_id: int | None
    owner_scope: str
    asset_type_id: int
    name: str
    identifier: str | None
    quantity: Decimal
    unit: str | None
    status: str
    condition_status: str
    acquired_at: datetime | None
    metadata_json: str | None
    note: str | None
    primary_image_url: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    asset_type_name: str | None
    room_code: str | None
    renter_full_name: str | None
    images: list[MaterialAssetImageOut]


class DeleteResult(BaseModel):
    deleted: bool


class MaterialAssetUploadOut(BaseModel):
    object_name: str
    file_name: str
    file_url: str
    access_url: str
    mime_type: str | None
    size_bytes: int
    is_image: bool
