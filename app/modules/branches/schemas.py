from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SoftDeleteResult(BaseModel):
    deleted: bool


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BranchUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class BranchOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    deleted_at: datetime | None
