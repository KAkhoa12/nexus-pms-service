from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenDecodeError, decode_access_token
from app.db.session import SessionLocal
from app.modules.core.models import PlatformAdmin, Team, TeamMember, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
developer_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/developer/auth/login",
    auto_error=False,
)


def _resolve_token_from_request(
    request: Request, fallback_token: str | None
) -> str | None:
    if fallback_token:
        return fallback_token
    cookie_token = (request.cookies.get("auth_access_token") or "").strip()
    if cookie_token:
        return cookie_token
    query_token = (request.query_params.get("token") or "").strip()
    if query_token:
        return query_token
    return None


@dataclass
class AuthenticatedUser:
    id: int
    tenant_id: int
    email: str
    full_name: str
    avatar_url: str | None
    auth_provider: str
    is_active: bool
    workspace_key: str


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> AuthenticatedUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    payload = getattr(request.state, "token_payload", None)
    try:
        if payload is None:
            resolved_token = _resolve_token_from_request(request, token)
            if not resolved_token:
                raise credentials_error
            payload = decode_access_token(resolved_token)
        user_id = int(payload.get("sub", "0"))
        tenant_id = int(payload.get("tenant_id", "0"))
    except (TokenDecodeError, TypeError, ValueError):
        raise credentials_error

    stmt = select(User).where(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.deleted_at.is_(None),
    )
    user = db.scalar(stmt)
    if not user or not user.is_active:
        raise credentials_error

    workspace_key = request.headers.get("X-Workspace-Key", "").strip()
    if not workspace_key:
        workspace_key = (request.query_params.get("workspace_key") or "").strip()
    if not workspace_key:
        workspace_key = "personal"
    effective_tenant_id = user.tenant_id
    if workspace_key.startswith("team:"):
        team_id_raw = workspace_key.split(":", 1)[1]
        if team_id_raw.isdigit():
            team_id = int(team_id_raw)
            team = db.scalar(
                select(Team)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(
                    Team.id == team_id,
                    Team.deleted_at.is_(None),
                    Team.is_active.is_(True),
                    TeamMember.user_id == user.id,
                    TeamMember.deleted_at.is_(None),
                )
            )
            if team is not None:
                effective_tenant_id = team.tenant_id
            else:
                workspace_key = "personal"
        else:
            workspace_key = "personal"
    elif workspace_key != "personal":
        workspace_key = "personal"

    return AuthenticatedUser(
        id=user.id,
        tenant_id=effective_tenant_id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        auth_provider=user.auth_provider,
        is_active=user.is_active,
        workspace_key=workspace_key,
    )


def get_current_platform_admin(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(developer_oauth2_scheme),
) -> PlatformAdmin:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate developer credentials",
    )
    payload = getattr(request.state, "token_payload", None)
    try:
        if payload is None:
            resolved_token = _resolve_token_from_request(request, token)
            if not resolved_token:
                raise credentials_error
            payload = decode_access_token(resolved_token)
        if payload.get("scope") != "developer_portal":
            raise credentials_error
        admin_id = int(payload.get("sub", "0"))
    except (TokenDecodeError, TypeError, ValueError):
        raise credentials_error

    stmt = select(PlatformAdmin).where(
        PlatformAdmin.id == admin_id,
        PlatformAdmin.deleted_at.is_(None),
    )
    admin = db.scalar(stmt)
    if not admin or not admin.is_active:
        raise credentials_error
    return admin
