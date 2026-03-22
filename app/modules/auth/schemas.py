from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class RegisterEmployeeRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6)
    role_ids: list[int] = Field(default_factory=list)


class UserOut(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    full_name: str
    is_active: bool


class UserPreferencesOut(BaseModel):
    theme_mode: str | None = None
    workspace_key: str | None = None


class UserPreferencesUpdateRequest(BaseModel):
    theme_mode: str | None = None
    workspace_key: str | None = None


class MeResponse(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    auth_provider: str
    is_active: bool
    roles: list[str]
    permissions: list[str]
    effective_package_code: str
    effective_package_name: str
    effective_package_source: str
    effective_team_id: int | None = None
    feature_codes: list[str]
    can_use_sunset_theme: bool
    ai_task_management_enabled: bool
    internal_chat_enabled: bool
    preference_theme_mode: str | None = None
    preference_workspace_key: str | None = None
