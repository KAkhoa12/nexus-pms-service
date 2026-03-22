from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.core.models import UserPermissionOverride


def get_active_override(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    permission_code: str,
) -> UserPermissionOverride | None:
    stmt = select(UserPermissionOverride).where(
        UserPermissionOverride.tenant_id == tenant_id,
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.permission_code == permission_code,
        UserPermissionOverride.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def get_override_any_state(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    permission_code: str,
) -> UserPermissionOverride | None:
    stmt = select(UserPermissionOverride).where(
        UserPermissionOverride.tenant_id == tenant_id,
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.permission_code == permission_code,
    )
    return db.scalar(stmt)


def save_override(
    db: Session, override: UserPermissionOverride
) -> UserPermissionOverride:
    db.add(override)
    db.flush()
    db.refresh(override)
    return override


def soft_delete_override(db: Session, override: UserPermissionOverride) -> None:
    override.deleted_at = datetime.now(timezone.utc)
    db.add(override)
    db.flush()


def hard_delete_override(db: Session, override: UserPermissionOverride) -> None:
    db.delete(override)
    db.flush()
