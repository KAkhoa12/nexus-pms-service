from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.core.models import PermissionEffectEnum


class UserPermissionUpsertRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=64)
    effect: PermissionEffectEnum = PermissionEffectEnum.ALLOW

    @field_validator("permission_code")
    @classmethod
    def normalize_permission_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("permission_code must not be empty")
        return normalized


class UserPermissionUpdateRequest(BaseModel):
    effect: PermissionEffectEnum


class UserPermissionOverrideOut(BaseModel):
    id: int
    user_id: int
    permission_code: str
    effect: PermissionEffectEnum


class DeleteUserPermissionResponse(BaseModel):
    removed: bool
