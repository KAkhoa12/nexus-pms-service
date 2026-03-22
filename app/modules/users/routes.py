from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import (
    ApiResponse,
    PaginatedResult,
    build_paginated_result,
    success_response,
)
from app.modules.core.models import User
from app.modules.users.schemas import (
    PermissionCatalogItem,
    RoleCreateRequest,
    RolePermissionActiveUpdateRequest,
    RolePermissionCatalogItem,
    RolePermissionsView,
    UserActiveUpdateRequest,
    UserCreateRequest,
    UserDeleteResult,
    UserDetailOut,
    UserListItem,
    UserPermissionsView,
    UserRoleActiveUpdateRequest,
    UserRoleCatalogItem,
    UserUpdateRequest,
)
from app.modules.users.service import (
    create_role,
    create_user,
    get_user_detail,
    hard_delete_user,
    list_permission_catalog,
    list_role_catalog,
    list_users,
    set_role_permission_active,
    set_user_role_active,
    soft_delete_user,
    update_user,
    update_user_active,
    view_role_permissions,
    view_user_permissions,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[UserListItem]])
def get_users(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[UserListItem]]:
    users, total_items = list_users(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )
    result = build_paginated_result(
        items=users,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Users fetched successfully")


@router.get("/roles/catalog", response_model=ApiResponse[list[UserRoleCatalogItem]])
def get_roles_catalog(
    target_user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[UserRoleCatalogItem]]:
    roles = list_role_catalog(
        db,
        current_user,
        target_user_id=target_user_id,
    )
    return success_response(roles, message="Role catalog fetched successfully")


@router.post("/roles", response_model=ApiResponse[UserRoleCatalogItem])
def add_role(
    payload: RoleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserRoleCatalogItem]:
    role = create_role(db, current_user, payload)
    return success_response(role, message="Role created successfully")


@router.get(
    "/permissions/catalog", response_model=ApiResponse[list[PermissionCatalogItem]]
)
def get_permissions_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[PermissionCatalogItem]]:
    permissions = list_permission_catalog(db, current_user)
    return success_response(
        permissions, message="Permission catalog fetched successfully"
    )


@router.get(
    "/roles/{role_id}/permissions",
    response_model=ApiResponse[RolePermissionsView],
)
def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RolePermissionsView]:
    result = view_role_permissions(db, current_user, role_id=role_id)
    return success_response(result, message="Role permissions fetched successfully")


@router.patch(
    "/roles/{role_id}/permissions/{permission_code}/active",
    response_model=ApiResponse[RolePermissionCatalogItem],
)
def update_role_permission_active(
    role_id: int,
    permission_code: str,
    payload: RolePermissionActiveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RolePermissionCatalogItem]:
    result = set_role_permission_active(
        db,
        current_user,
        role_id=role_id,
        permission_code=permission_code,
        payload=payload,
    )
    return success_response(result, message="Role permission updated successfully")


@router.post("", response_model=ApiResponse[UserDetailOut])
def add_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDetailOut]:
    user = create_user(db, current_user, payload)
    return success_response(user, message="User created successfully")


@router.get("/{user_id}", response_model=ApiResponse[UserDetailOut])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDetailOut]:
    user = get_user_detail(db, current_user, user_id=user_id)
    return success_response(user, message="User detail fetched successfully")


@router.put("/{user_id}", response_model=ApiResponse[UserDetailOut])
def edit_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDetailOut]:
    user = update_user(db, current_user, user_id=user_id, payload=payload)
    return success_response(user, message="User updated successfully")


@router.patch(
    "/{user_id}/roles/{role_id}/active", response_model=ApiResponse[UserDetailOut]
)
def set_role_active_for_user(
    user_id: int,
    role_id: int,
    payload: UserRoleActiveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDetailOut]:
    user = set_user_role_active(
        db,
        current_user,
        user_id=user_id,
        role_id=role_id,
        payload=payload,
    )
    return success_response(user, message="User role active status updated")


@router.patch("/{user_id}/active", response_model=ApiResponse[UserDetailOut])
def set_user_active(
    user_id: int,
    payload: UserActiveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDetailOut]:
    user = update_user_active(db, current_user, user_id=user_id, payload=payload)
    return success_response(user, message="User active status updated")


@router.delete("/{user_id}", response_model=ApiResponse[UserDeleteResult])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDeleteResult]:
    result = soft_delete_user(db, current_user, user_id=user_id)
    return success_response(result, message="User soft deleted")


@router.delete("/{user_id}/hard", response_model=ApiResponse[UserDeleteResult])
def delete_user_forever(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserDeleteResult]:
    result = hard_delete_user(db, current_user, user_id=user_id)
    return success_response(result, message="User permanently deleted")


@router.get("/{user_id}/permissions", response_model=ApiResponse[UserPermissionsView])
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPermissionsView]:
    result = view_user_permissions(db, current_user, user_id=user_id)
    return success_response(result, message="User permissions fetched successfully")
