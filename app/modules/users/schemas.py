from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.core.models import PermissionEffectEnum


class UserListFilter(str):
    ACTIVE = "active"
    TRASH = "trash"
    ALL = "all"


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6)
    role_ids: list[int] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role_ids: list[int] | None = None
    password: str | None = Field(default=None, min_length=6)


class UserActiveUpdateRequest(BaseModel):
    is_active: bool


class UserListItem(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    full_name: str
    is_active: bool
    deleted_at: datetime | None
    roles: list[str]


class UserDetailOut(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    full_name: str
    is_active: bool
    deleted_at: datetime | None
    roles: list[str]


class UserDeleteResult(BaseModel):
    deleted: bool


class UserPermissionOverrideOut(BaseModel):
    permission_code: str
    effect: PermissionEffectEnum


class UserPermissionsView(BaseModel):
    user_id: int
    role_permissions: list[str]
    overrides: list[UserPermissionOverrideOut]
    effective_permissions: list[str]


class UserRoleCatalogItem(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class UserRoleActiveUpdateRequest(BaseModel):
    is_active: bool


class PermissionCatalogItem(BaseModel):
    code: str
    module: str
    module_mean: str | None
    description: str | None


class RolePermissionCatalogItem(BaseModel):
    permission_code: str
    module: str
    module_mean: str | None
    description: str | None
    is_active: bool


class RolePermissionModuleGroup(BaseModel):
    module: str
    module_mean: str | None
    has_manage_active: bool
    permissions: list[RolePermissionCatalogItem]


class RolePermissionsView(BaseModel):
    role_id: int
    role_name: str
    role_description: str | None
    permissions: list[RolePermissionCatalogItem]
    modules: list[RolePermissionModuleGroup]


class RolePermissionActiveUpdateRequest(BaseModel):
    is_active: bool
