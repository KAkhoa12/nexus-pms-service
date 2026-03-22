from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FormTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_type: str = Field(default="GENERAL", min_length=1, max_length=32)
    page_size: str = Field(default="A4", min_length=1, max_length=16)
    orientation: str = Field(default="portrait", min_length=1, max_length=16)
    font_family: str = Field(default="Arial", min_length=1, max_length=64)
    font_size: int = Field(default=14, ge=8, le=72)
    text_color: str = Field(default="#111827", min_length=3, max_length=16)
    content_html: str = Field(default="")
    config_json: str | None = None
    is_active: bool = True


class FormTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    template_type: str | None = Field(default=None, min_length=1, max_length=32)
    page_size: str | None = Field(default=None, min_length=1, max_length=16)
    orientation: str | None = Field(default=None, min_length=1, max_length=16)
    font_family: str | None = Field(default=None, min_length=1, max_length=64)
    font_size: int | None = Field(default=None, ge=8, le=72)
    text_color: str | None = Field(default=None, min_length=3, max_length=16)
    content_html: str | None = None
    config_json: str | None = None
    is_active: bool | None = None


class FormTemplateOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    template_type: str
    page_size: str
    orientation: str
    font_family: str
    font_size: int
    text_color: str
    content_html: str
    config_json: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class FormTemplateDeleteResult(BaseModel):
    deleted: bool
