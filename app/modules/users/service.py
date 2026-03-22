from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.auth.service import get_user_auth_context
from app.modules.core.models import PermissionEffectEnum, Role, RolePermission, User
from app.modules.users import repository
from app.modules.users.schemas import (
    PermissionCatalogItem,
    RoleCreateRequest,
    RolePermissionActiveUpdateRequest,
    RolePermissionCatalogItem,
    RolePermissionModuleGroup,
    RolePermissionsView,
    UserActiveUpdateRequest,
    UserCreateRequest,
    UserDeleteResult,
    UserDetailOut,
    UserListItem,
    UserPermissionOverrideOut,
    UserPermissionsView,
    UserRoleActiveUpdateRequest,
    UserRoleCatalogItem,
    UserUpdateRequest,
)
from app.utils.validators import password_strength_errors

MANAGE_USER_CODES = {"user:mangage", "users:manage"}
VIEW_USER_CODES = {"users:view", "user:view"}
CREATE_USER_CODES = {"users:create", "user:create"}
UPDATE_USER_CODES = {"users:update", "user:update"}
DELETE_USER_CODES = {"users:delete", "user:delete"}
VIEW_USER_PERMISSION_CODES = {"user:permision:view", "users:permissions:view"}
MANAGE_ROLE_PERMISSION_CODES = {
    "users:permissions:manage",
    "users:permissions:create",
    "users:permissions:update",
}
MANAGE_ROLE_CODES = MANAGE_ROLE_PERMISSION_CODES | MANAGE_USER_CODES | UPDATE_USER_CODES
MAX_ITEMS_PER_PAGE = 200


def _ensure_permission(
    db: Session, current_user: User, required_codes: set[str]
) -> None:
    context = get_user_auth_context(db, current_user)
    if context.has_full_access:
        return
    if context.permissions.intersection(MANAGE_USER_CODES):
        return
    if context.permissions.intersection(required_codes):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission"
    )


def _validate_roles(db: Session, current_user: User, role_ids: list[int]) -> None:
    roles = repository.get_roles_by_ids(
        db,
        tenant_id=current_user.tenant_id,
        role_ids=role_ids,
    )
    found_ids = {role.id for role in roles}
    if len(found_ids) != len(set(role_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more role_ids are invalid",
        )


def _get_tenant_user(
    db: Session, current_user: User, user_id: int, include_deleted: bool = False
) -> User:
    user = repository.get_user_by_id(
        db,
        tenant_id=current_user.tenant_id,
        user_id=user_id,
        include_deleted=include_deleted,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def _get_tenant_role(db: Session, current_user: User, role_id: int):
    role = repository.get_role_by_id(
        db,
        tenant_id=current_user.tenant_id,
        role_id=role_id,
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role


def _normalize_role_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name must not be empty",
        )
    return normalized


def list_users(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[UserListItem], int]:
    _ensure_permission(db, current_user, VIEW_USER_CODES)
    if deleted_mode not in {"active", "trash", "all"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="deleted_mode must be active, trash or all",
        )
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page must be between 1 and {MAX_ITEMS_PER_PAGE}",
        )

    users, total_items = repository.list_users(
        db,
        tenant_id=current_user.tenant_id,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )
    role_map = repository.get_role_names_for_users(
        db, user_ids=[item.id for item in users]
    )
    return [
        UserListItem(
            id=item.id,
            tenant_id=item.tenant_id,
            email=item.email,
            full_name=item.full_name,
            is_active=item.is_active,
            deleted_at=item.deleted_at,
            roles=sorted(role_map.get(item.id, [])),
        )
        for item in users
    ], total_items


def create_role(
    db: Session, current_user: User, payload: RoleCreateRequest
) -> UserRoleCatalogItem:
    _ensure_permission(db, current_user, MANAGE_ROLE_CODES)
    normalized_name = _normalize_role_name(payload.name)
    normalized_description = (
        payload.description.strip() if payload.description is not None else None
    )
    if normalized_description == "":
        normalized_description = None

    existing = repository.get_role_by_name_any_state(
        db,
        tenant_id=current_user.tenant_id,
        name=normalized_name,
    )
    role: Role
    if existing is None:
        role = Role(
            tenant_id=current_user.tenant_id,
            name=normalized_name,
            description=normalized_description,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
    elif existing.deleted_at is not None:
        existing.deleted_at = None
        existing.description = normalized_description
        db.add(existing)
        db.commit()
        db.refresh(existing)
        role = existing
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists",
        )

    return UserRoleCatalogItem(
        id=role.id,
        name=role.name,
        description=role.description,
        is_active=True,
    )


def get_user_detail(db: Session, current_user: User, *, user_id: int) -> UserDetailOut:
    _ensure_permission(db, current_user, VIEW_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=True)
    return _build_user_detail(db, user)


def _build_user_detail(db: Session, user: User) -> UserDetailOut:
    role_map = repository.get_role_names_for_users(db, user_ids=[user.id])
    return UserDetailOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        deleted_at=user.deleted_at,
        roles=sorted(role_map.get(user.id, [])),
    )


def create_user(
    db: Session, current_user: User, payload: UserCreateRequest
) -> UserDetailOut:
    _ensure_permission(db, current_user, CREATE_USER_CODES)
    password_errors = password_strength_errors(payload.password)
    if password_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password is too weak", "errors": password_errors},
        )

    existing = repository.get_user_by_email(
        db,
        tenant_id=current_user.tenant_id,
        email=str(payload.email),
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists in tenant",
        )

    assigned_role_ids = payload.role_ids
    if assigned_role_ids:
        _validate_roles(db, current_user, assigned_role_ids)
    else:
        assigned_role_ids = [
            role.id
            for role in repository.list_roles(
                db,
                tenant_id=current_user.tenant_id,
            )
        ]
        if not assigned_role_ids:
            assigned_role_ids = sorted(
                repository.get_active_role_ids_for_user(
                    db,
                    user_id=current_user.id,
                )
            )

    user = User(
        tenant_id=current_user.tenant_id,
        email=str(payload.email),
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    repository.replace_user_roles(
        db,
        tenant_id=current_user.tenant_id,
        user_id=user.id,
        role_ids=assigned_role_ids,
    )
    db.commit()
    db.refresh(user)
    return _build_user_detail(db, user)


def update_user(
    db: Session, current_user: User, *, user_id: int, payload: UserUpdateRequest
) -> UserDetailOut:
    _ensure_permission(db, current_user, UPDATE_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=False)

    if payload.email is not None:
        existing = repository.get_user_by_email(
            db,
            tenant_id=current_user.tenant_id,
            email=str(payload.email),
        )
        if existing is not None and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists in tenant",
            )
        user.email = str(payload.email)

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.password is not None:
        password_errors = password_strength_errors(payload.password)
        if password_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Password is too weak", "errors": password_errors},
            )
        user.password_hash = get_password_hash(payload.password)

    if payload.role_ids is not None:
        _validate_roles(db, current_user, payload.role_ids)
        repository.replace_user_roles(
            db,
            tenant_id=current_user.tenant_id,
            user_id=user.id,
            role_ids=payload.role_ids,
        )

    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_user_detail(db, user)


def update_user_active(
    db: Session,
    current_user: User,
    *,
    user_id: int,
    payload: UserActiveUpdateRequest,
) -> UserDetailOut:
    _ensure_permission(db, current_user, UPDATE_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=False)
    repository.set_user_active(db, user, is_active=payload.is_active)
    db.commit()
    db.refresh(user)
    return _build_user_detail(db, user)


def soft_delete_user(
    db: Session, current_user: User, *, user_id: int
) -> UserDeleteResult:
    _ensure_permission(db, current_user, DELETE_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=False)
    repository.soft_delete_user(db, user)
    db.commit()
    return UserDeleteResult(deleted=True)


def hard_delete_user(
    db: Session, current_user: User, *, user_id: int
) -> UserDeleteResult:
    _ensure_permission(db, current_user, DELETE_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=True)
    if user.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be soft deleted before hard delete",
        )
    repository.hard_delete_user(db, user)
    db.commit()
    return UserDeleteResult(deleted=True)


def view_user_permissions(
    db: Session, current_user: User, *, user_id: int
) -> UserPermissionsView:
    _ensure_permission(db, current_user, VIEW_USER_PERMISSION_CODES | VIEW_USER_CODES)
    target_user = _get_tenant_user(db, current_user, user_id, include_deleted=True)
    role_permissions = sorted(
        set(repository.get_user_role_permissions(db, user_id=target_user.id))
    )
    overrides = repository.get_user_permission_overrides(db, user_id=target_user.id)
    effective_permissions = set(role_permissions)
    normalized_overrides: list[UserPermissionOverrideOut] = []
    for override in overrides:
        normalized_overrides.append(
            UserPermissionOverrideOut(
                permission_code=override.permission_code,
                effect=override.effect,
            )
        )
        if override.effect == PermissionEffectEnum.DENY:
            effective_permissions.discard(override.permission_code)
        else:
            effective_permissions.add(override.permission_code)

    return UserPermissionsView(
        user_id=target_user.id,
        role_permissions=role_permissions,
        overrides=normalized_overrides,
        effective_permissions=sorted(effective_permissions),
    )


def list_role_catalog(
    db: Session, current_user: User, *, target_user_id: int | None = None
) -> list[UserRoleCatalogItem]:
    _ensure_permission(
        db,
        current_user,
        VIEW_USER_CODES
        | UPDATE_USER_CODES
        | VIEW_USER_PERMISSION_CODES
        | MANAGE_ROLE_PERMISSION_CODES,
    )
    roles = repository.list_roles(db, tenant_id=current_user.tenant_id)
    active_role_ids: set[int] = set()
    if target_user_id is not None:
        target_user = _get_tenant_user(
            db, current_user, target_user_id, include_deleted=True
        )
        active_role_ids = repository.get_active_role_ids_for_user(
            db, user_id=target_user.id
        )

    return [
        UserRoleCatalogItem(
            id=role.id,
            name=role.name,
            description=role.description,
            is_active=role.id in active_role_ids,
        )
        for role in roles
    ]


def set_user_role_active(
    db: Session,
    current_user: User,
    *,
    user_id: int,
    role_id: int,
    payload: UserRoleActiveUpdateRequest,
) -> UserDetailOut:
    _ensure_permission(db, current_user, UPDATE_USER_CODES)
    user = _get_tenant_user(db, current_user, user_id, include_deleted=False)
    role = repository.get_roles_by_ids(
        db, tenant_id=current_user.tenant_id, role_ids=[role_id]
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    repository.set_user_role_active(
        db,
        tenant_id=current_user.tenant_id,
        user_id=user.id,
        role_id=role_id,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(user)
    return _build_user_detail(db, user)


def list_permission_catalog(
    db: Session, current_user: User
) -> list[PermissionCatalogItem]:
    _ensure_permission(db, current_user, VIEW_USER_PERMISSION_CODES | VIEW_USER_CODES)
    permissions = repository.list_permissions(db)
    return [
        PermissionCatalogItem(
            code=item.code,
            module=item.module,
            module_mean=item.module_mean,
            description=item.description,
        )
        for item in permissions
    ]


def _is_manage_permission_code(permission_code: str) -> bool:
    return permission_code.strip().split(":")[-1] == "manage"


def _permission_sort_key(permission_code: str) -> tuple[int, str]:
    is_manage = _is_manage_permission_code(permission_code)
    return (0 if is_manage else 1, permission_code)


def _build_role_permission_item(
    *,
    permission_code: str,
    module: str,
    module_mean: str | None,
    description: str | None,
    is_active: bool,
) -> RolePermissionCatalogItem:
    return RolePermissionCatalogItem(
        permission_code=permission_code,
        module=module,
        module_mean=module_mean,
        description=description,
        is_active=is_active,
    )


def _group_role_permission_items(
    items: list[RolePermissionCatalogItem],
) -> list[RolePermissionModuleGroup]:
    grouped: dict[str, list[RolePermissionCatalogItem]] = {}
    module_mean_by_module: dict[str, str | None] = {}
    for item in items:
        grouped.setdefault(item.module, []).append(item)
        module_mean_by_module.setdefault(item.module, item.module_mean)

    result: list[RolePermissionModuleGroup] = []
    for module in sorted(grouped.keys()):
        module_items = sorted(
            grouped[module],
            key=lambda item: _permission_sort_key(item.permission_code),
        )
        has_manage_active = any(
            _is_manage_permission_code(item.permission_code) and item.is_active
            for item in module_items
        )
        result.append(
            RolePermissionModuleGroup(
                module=module,
                module_mean=module_mean_by_module.get(module),
                has_manage_active=has_manage_active,
                permissions=module_items,
            )
        )
    return result


def view_role_permissions(
    db: Session,
    current_user: User,
    *,
    role_id: int,
) -> RolePermissionsView:
    _ensure_permission(db, current_user, VIEW_USER_PERMISSION_CODES | VIEW_USER_CODES)
    role = _get_tenant_role(db, current_user, role_id)
    permissions = repository.list_permissions(db)
    active_permission_codes = repository.get_active_permission_codes_for_role(
        db, role_id=role.id
    )

    permission_items = sorted(
        [
            _build_role_permission_item(
                permission_code=item.code,
                module=item.module,
                module_mean=item.module_mean,
                description=item.description,
                is_active=item.code in active_permission_codes,
            )
            for item in permissions
        ],
        key=lambda item: (item.module, *_permission_sort_key(item.permission_code)),
    )
    return RolePermissionsView(
        role_id=role.id,
        role_name=role.name,
        role_description=role.description,
        permissions=permission_items,
        modules=_group_role_permission_items(permission_items),
    )


def set_role_permission_active(
    db: Session,
    current_user: User,
    *,
    role_id: int,
    permission_code: str,
    payload: RolePermissionActiveUpdateRequest,
) -> RolePermissionCatalogItem:
    normalized_permission_code = permission_code.strip()
    if not normalized_permission_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="permission_code must not be empty",
        )
    _ensure_permission(db, current_user, MANAGE_ROLE_PERMISSION_CODES)
    role = _get_tenant_role(db, current_user, role_id)
    permission = repository.get_permission_by_code(
        db,
        permission_code=normalized_permission_code,
    )
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission code not found",
        )

    is_manage_permission = _is_manage_permission_code(normalized_permission_code)
    if payload.is_active and is_manage_permission:
        module_permissions = [
            item
            for item in repository.list_permissions(db)
            if item.module == permission.module
        ]
        for module_permission in module_permissions:
            role_permission = repository.get_role_permission_any_state(
                db,
                tenant_id=current_user.tenant_id,
                role_id=role.id,
                permission_code=module_permission.code,
            )
            if role_permission is None:
                db.add(
                    RolePermission(
                        tenant_id=current_user.tenant_id,
                        role_id=role.id,
                        permission_code=module_permission.code,
                    )
                )
            elif role_permission.deleted_at is not None:
                role_permission.deleted_at = None
                db.add(role_permission)
    else:
        role_permission = repository.get_role_permission_any_state(
            db,
            tenant_id=current_user.tenant_id,
            role_id=role.id,
            permission_code=normalized_permission_code,
        )
        if payload.is_active:
            if role_permission is None:
                db.add(
                    RolePermission(
                        tenant_id=current_user.tenant_id,
                        role_id=role.id,
                        permission_code=normalized_permission_code,
                    )
                )
            elif role_permission.deleted_at is not None:
                role_permission.deleted_at = None
                db.add(role_permission)
        else:
            if role_permission is not None and role_permission.deleted_at is None:
                role_permission.deleted_at = datetime.now(timezone.utc)
                db.add(role_permission)

    db.commit()
    active_permission_codes = repository.get_active_permission_codes_for_role(
        db, role_id=role.id
    )
    return _build_role_permission_item(
        permission_code=permission.code,
        module=permission.module,
        module_mean=permission.module_mean,
        description=permission.description,
        is_active=permission.code in active_permission_codes,
    )
