from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str | None = None


class TeamMemberInviteRequest(BaseModel):
    email: EmailStr
    rbac_role_id: int | None = Field(default=None, ge=1)


class TeamMemberRoleUpdateRequest(BaseModel):
    rbac_role_id: int = Field(ge=1)


class TeamMemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: str
    member_role: str
    rbac_role_id: int | None
    invited_by_user_id: int | None
    created_at: datetime


class TeamOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: str | None
    is_active: bool
    owner_user_id: int
    owner_email: str
    owner_full_name: str
    owner_package_code: str
    owner_package_name: str
    members: list[TeamMemberOut]


class TeamActionResult(BaseModel):
    success: bool
    message: str


class TeamMemberCandidateOut(BaseModel):
    user_id: int
    email: str
    full_name: str
    roles: list[str]
    is_active: bool
    is_in_team: bool
