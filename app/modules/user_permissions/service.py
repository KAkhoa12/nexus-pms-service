from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.service import get_user_auth_context
from app.modules.core.models import (
    Permission,
    PermissionEffectEnum,
    User,
    UserPermissionOverride,
)
from app.modules.user_permissions import repository

MANAGE_PERMISSIONS_ALL = {"users:permissions:manage"}
MANAGE_PERMISSIONS_CREATE = MANAGE_PERMISSIONS_ALL | {"users:permissions:create"}
MANAGE_PERMISSIONS_UPDATE = MANAGE_PERMISSIONS_ALL | {"users:permissions:update"}
MANAGE_PERMISSIONS_DELETE = MANAGE_PERMISSIONS_ALL | {"users:permissions:delete"}


def _normalize_permission_code(permission_code: str) -> str:
    normalized = permission_code.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="permission_code must not be empty",
        )
    return normalized


def _ensure_action_allowed(
    db: Session, current_user: User, required_permissions: set[str]
) -> None:
    auth_context = get_user_auth_context(db, current_user)
    if auth_context.has_full_access:
        return
    if auth_context.permissions.intersection(required_permissions):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to manage user permissions",
    )


def _get_target_user(db: Session, current_user: User, target_user_id: int) -> User:
    stmt = select(User).where(
        User.id == target_user_id,
        User.tenant_id == current_user.tenant_id,
        User.deleted_at.is_(None),
    )
    target_user = db.scalar(stmt)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return target_user


def _ensure_permission_code_exists(db: Session, permission_code: str) -> None:
    stmt = select(Permission.code).where(
        Permission.code == permission_code,
        Permission.deleted_at.is_(None),
    )
    if db.scalar(stmt) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission code not found"
        )


def add_user_permission_override(
    db: Session,
    *,
    current_user: User,
    target_user_id: int,
    permission_code: str,
    effect: PermissionEffectEnum,
) -> UserPermissionOverride:
    normalized_permission_code = _normalize_permission_code(permission_code)
    _ensure_action_allowed(db, current_user, MANAGE_PERMISSIONS_CREATE)
    target_user = _get_target_user(db, current_user, target_user_id)
    _ensure_permission_code_exists(db, normalized_permission_code)

    override = repository.get_override_any_state(
        db,
        tenant_id=current_user.tenant_id,
        user_id=target_user.id,
        permission_code=normalized_permission_code,
    )
    if override is None:
        override = UserPermissionOverride(
            tenant_id=current_user.tenant_id,
            user_id=target_user.id,
            permission_code=normalized_permission_code,
            effect=effect,
        )
    else:
        override.effect = effect
        override.deleted_at = None

    saved = repository.save_override(db, override)
    db.commit()
    return saved


def update_user_permission_override(
    db: Session,
    *,
    current_user: User,
    target_user_id: int,
    permission_code: str,
    effect: PermissionEffectEnum,
) -> UserPermissionOverride:
    normalized_permission_code = _normalize_permission_code(permission_code)
    _ensure_action_allowed(db, current_user, MANAGE_PERMISSIONS_UPDATE)
    _get_target_user(db, current_user, target_user_id)

    override = repository.get_active_override(
        db,
        tenant_id=current_user.tenant_id,
        user_id=target_user_id,
        permission_code=normalized_permission_code,
    )
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User permission override not found",
        )

    override.effect = effect
    saved = repository.save_override(db, override)
    db.commit()
    return saved


def delete_user_permission_override(
    db: Session,
    *,
    current_user: User,
    target_user_id: int,
    permission_code: str,
) -> bool:
    normalized_permission_code = _normalize_permission_code(permission_code)
    _ensure_action_allowed(db, current_user, MANAGE_PERMISSIONS_DELETE)
    _get_target_user(db, current_user, target_user_id)

    override = repository.get_active_override(
        db,
        tenant_id=current_user.tenant_id,
        user_id=target_user_id,
        permission_code=normalized_permission_code,
    )
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User permission override not found",
        )

    repository.soft_delete_override(db, override)
    db.commit()
    return True


def hard_delete_user_permission_override(
    db: Session,
    *,
    current_user: User,
    target_user_id: int,
    permission_code: str,
) -> bool:
    normalized_permission_code = _normalize_permission_code(permission_code)
    _ensure_action_allowed(db, current_user, MANAGE_PERMISSIONS_DELETE)
    _get_target_user(db, current_user, target_user_id)

    override = repository.get_override_any_state(
        db,
        tenant_id=current_user.tenant_id,
        user_id=target_user_id,
        permission_code=normalized_permission_code,
    )
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User permission override not found",
        )
    if override.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Override must be soft deleted before hard delete",
        )

    repository.hard_delete_override(db, override)
    db.commit()
    return True
