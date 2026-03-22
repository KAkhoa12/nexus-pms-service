from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.core.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserPermissionOverride,
    UserRole,
)


def list_users(
    db: Session,
    *,
    tenant_id: int,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[User], int]:
    stmt = select(User).where(User.tenant_id == tenant_id)
    if deleted_mode == "active":
        stmt = stmt.where(User.deleted_at.is_(None))
    elif deleted_mode == "trash":
        stmt = stmt.where(User.deleted_at.is_not(None))
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(User.id.desc())
    users = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return users, total_items


def get_user_by_id(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    include_deleted: bool = False,
) -> User | None:
    stmt = select(User).where(
        User.id == user_id,
        User.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return db.scalar(stmt)


def get_role_names_for_users(
    db: Session, *, user_ids: list[int]
) -> dict[int, list[str]]:
    if not user_ids:
        return {}
    stmt = (
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.user_id.in_(user_ids),
            UserRole.deleted_at.is_(None),
            Role.deleted_at.is_(None),
        )
    )
    result: dict[int, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, role_name in db.execute(stmt).all():
        result.setdefault(user_id, []).append(role_name)
    return result


def get_roles_by_ids(db: Session, *, tenant_id: int, role_ids: list[int]) -> list[Role]:
    if not role_ids:
        return []
    stmt = select(Role).where(
        Role.id.in_(role_ids),
        Role.tenant_id == tenant_id,
        Role.deleted_at.is_(None),
    )
    return list(db.scalars(stmt).all())


def get_role_by_id(db: Session, *, tenant_id: int, role_id: int) -> Role | None:
    stmt = select(Role).where(
        Role.id == role_id,
        Role.tenant_id == tenant_id,
        Role.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def get_role_by_name_any_state(
    db: Session, *, tenant_id: int, name: str
) -> Role | None:
    stmt = select(Role).where(
        Role.tenant_id == tenant_id,
        Role.name == name,
    )
    return db.scalar(stmt)


def list_roles(db: Session, *, tenant_id: int) -> list[Role]:
    stmt = (
        select(Role)
        .where(
            Role.tenant_id == tenant_id,
            Role.deleted_at.is_(None),
        )
        .order_by(Role.name.asc())
    )
    return list(db.scalars(stmt).all())


def list_permissions(db: Session) -> list[Permission]:
    stmt = (
        select(Permission)
        .where(Permission.deleted_at.is_(None))
        .order_by(Permission.module.asc(), Permission.code.asc())
    )
    return list(db.scalars(stmt).all())


def get_permission_by_code(db: Session, *, permission_code: str) -> Permission | None:
    stmt = select(Permission).where(
        Permission.code == permission_code,
        Permission.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def get_active_permission_codes_for_role(db: Session, *, role_id: int) -> set[str]:
    stmt = select(RolePermission.permission_code).where(
        RolePermission.role_id == role_id,
        RolePermission.deleted_at.is_(None),
    )
    return set(db.scalars(stmt).all())


def get_role_permission_any_state(
    db: Session,
    *,
    tenant_id: int,
    role_id: int,
    permission_code: str,
) -> RolePermission | None:
    stmt = select(RolePermission).where(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role_id == role_id,
        RolePermission.permission_code == permission_code,
    )
    return db.scalar(stmt)


def get_active_role_ids_for_user(db: Session, *, user_id: int) -> set[int]:
    stmt = select(UserRole.role_id).where(
        UserRole.user_id == user_id,
        UserRole.deleted_at.is_(None),
    )
    return set(db.scalars(stmt).all())


def get_user_role_by_role_id(
    db: Session, *, tenant_id: int, user_id: int, role_id: int
) -> UserRole | None:
    stmt = select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
    )
    return db.scalar(stmt)


def get_user_by_email(db: Session, *, tenant_id: int, email: str) -> User | None:
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.email == email,
        User.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def replace_user_roles(
    db: Session, *, tenant_id: int, user_id: int, role_ids: list[int]
) -> None:
    existing_stmt = select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == user_id,
    )
    existing = list(db.scalars(existing_stmt).all())
    existing_by_role = {item.role_id: item for item in existing}
    now = datetime.now(timezone.utc)

    for role_id, item in existing_by_role.items():
        if role_id not in role_ids and item.deleted_at is None:
            item.deleted_at = now
            db.add(item)

    for role_id in role_ids:
        item = existing_by_role.get(role_id)
        if item is None:
            db.add(
                UserRole(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role_id=role_id,
                )
            )
        elif item.deleted_at is not None:
            item.deleted_at = None
            db.add(item)

    db.flush()


def soft_delete_user(db: Session, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)
    db.add(user)
    db.flush()


def set_user_active(db: Session, user: User, *, is_active: bool) -> None:
    user.is_active = is_active
    db.add(user)
    db.flush()


def set_user_role_active(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    role_id: int,
    is_active: bool,
) -> None:
    user_role = get_user_role_by_role_id(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role_id,
    )
    now = datetime.now(timezone.utc)
    if user_role is None:
        if not is_active:
            return
        db.add(
            UserRole(
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=role_id,
            )
        )
        db.flush()
        return

    if is_active:
        user_role.deleted_at = None
    else:
        if user_role.deleted_at is None:
            user_role.deleted_at = now
    db.add(user_role)
    db.flush()


def hard_delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.flush()


def get_user_role_permissions(db: Session, *, user_id: int) -> list[str]:
    stmt = (
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(
            UserRole.user_id == user_id,
            UserRole.deleted_at.is_(None),
            RolePermission.deleted_at.is_(None),
        )
    )
    return list(db.scalars(stmt).all())


def get_user_permission_overrides(
    db: Session, *, user_id: int
) -> list[UserPermissionOverride]:
    stmt = select(UserPermissionOverride).where(
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.deleted_at.is_(None),
    )
    return list(db.scalars(stmt).all())
