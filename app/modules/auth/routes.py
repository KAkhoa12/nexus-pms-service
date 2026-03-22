from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.response import ApiResponse, success_response
from app.core.security import TokenDecodeError, decode_refresh_token
from app.modules.auth.google_service import verify_google_credential
from app.modules.auth.schemas import (
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshTokenRequest,
    RegisterEmployeeRequest,
    TokenResponse,
    UserOut,
    UserPreferencesOut,
    UserPreferencesUpdateRequest,
)
from app.modules.auth.service import (
    authenticate_google_user,
    authenticate_user,
    build_access_token,
    build_refresh_token,
    cleanup_expired_revoked_tokens,
    create_employee,
    ensure_can_create_employee,
    get_user_auth_context,
    get_user_preferences,
    is_refresh_token_revoked,
    resolve_effective_package_context,
    revoke_refresh_token,
    update_user_preferences,
)
from app.modules.core.models import User

router = APIRouter()


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(
    payload: LoginRequest, db: Session = Depends(get_db)
) -> ApiResponse[TokenResponse]:
    user = authenticate_user(db=db, email=str(payload.email), password=payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    access_token = build_access_token(user)
    refresh_token = build_refresh_token(user)
    token = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return success_response(token, message="Đăng nhập thành công")


@router.post("/google", response_model=ApiResponse[TokenResponse])
def login_google(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    identity = verify_google_credential(payload.credential)
    user = authenticate_google_user(db, identity)

    access_token = build_access_token(user)
    refresh_token = build_refresh_token(user)
    token = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return success_response(token, message="Đăng nhập Google thành công")


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
def refresh_token(
    payload: RefreshTokenRequest, db: Session = Depends(get_db)
) -> ApiResponse[TokenResponse]:
    cleanup_expired_revoked_tokens(db)
    if is_refresh_token_revoked(db, payload.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    try:
        refresh_payload = decode_refresh_token(payload.refresh_token)
        user_id = int(refresh_payload.get("sub", "0"))
        tenant_id = int(refresh_payload.get("tenant_id", "0"))
    except (TokenDecodeError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = db.get(User, user_id)
    if (
        not user
        or user.deleted_at is not None
        or not user.is_active
        or user.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    revoke_refresh_token(db, payload.refresh_token)
    new_access_token = build_access_token(user)
    new_refresh_token = build_refresh_token(user)
    token = TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return success_response(token, message="Token refreshed")


@router.post("/logout", response_model=ApiResponse[dict])
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    cleanup_expired_revoked_tokens(db)
    if is_refresh_token_revoked(db, payload.refresh_token):
        return success_response({"revoked": True}, message="Logged out")

    try:
        revoke_refresh_token(db, payload.refresh_token)
    except (TokenDecodeError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    return success_response({"revoked": True}, message="Logged out")


@router.post("/register", response_model=ApiResponse[UserOut])
def register_employee(
    payload: RegisterEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserOut]:
    ensure_can_create_employee(db, current_user)
    user = create_employee(db, current_user, payload)
    user_out = UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
    )
    return success_response(user_out, message="Employee created successfully")


@router.get("/me", response_model=ApiResponse[MeResponse])
def me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[MeResponse]:
    context = get_user_auth_context(db, current_user)
    package_context = resolve_effective_package_context(db, current_user)
    preference_theme_mode, preference_workspace_key = get_user_preferences(
        db, current_user
    )
    profile = MeResponse(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        auth_provider=current_user.auth_provider,
        is_active=current_user.is_active,
        roles=sorted(context.roles),
        permissions=sorted(context.permissions),
        effective_package_code=package_context.code,
        effective_package_name=package_context.name,
        effective_package_source=package_context.source,
        effective_team_id=package_context.team_id,
        feature_codes=sorted(package_context.feature_codes),
        can_use_sunset_theme=package_context.can_use_sunset_theme,
        ai_task_management_enabled=package_context.ai_task_management_enabled,
        internal_chat_enabled=package_context.internal_chat_enabled,
        preference_theme_mode=preference_theme_mode,
        preference_workspace_key=preference_workspace_key,
    )
    return success_response(profile, message="Current user profile")


@router.get("/preferences", response_model=ApiResponse[UserPreferencesOut])
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPreferencesOut]:
    theme_mode, workspace_key = get_user_preferences(db, current_user)
    response = UserPreferencesOut(theme_mode=theme_mode, workspace_key=workspace_key)
    return success_response(response, message="User preferences fetched successfully")


@router.put("/preferences", response_model=ApiResponse[UserPreferencesOut])
def save_preferences(
    payload: UserPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPreferencesOut]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preference field provided",
        )
    update_kwargs: dict[str, str | None] = {}
    if "theme_mode" in updates:
        update_kwargs["theme_mode"] = updates["theme_mode"]
    if "workspace_key" in updates:
        update_kwargs["workspace_key"] = updates["workspace_key"]
    theme_mode, workspace_key = update_user_preferences(
        db,
        current_user,
        **update_kwargs,
    )
    response = UserPreferencesOut(theme_mode=theme_mode, workspace_key=workspace_key)
    return success_response(response, message="User preferences updated successfully")
