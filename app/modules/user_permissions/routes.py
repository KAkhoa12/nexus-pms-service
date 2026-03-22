from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import ApiResponse, success_response
from app.modules.core.models import User
from app.modules.user_permissions.schemas import (
    DeleteUserPermissionResponse,
    UserPermissionOverrideOut,
    UserPermissionUpdateRequest,
    UserPermissionUpsertRequest,
)
from app.modules.user_permissions.service import (
    add_user_permission_override,
    delete_user_permission_override,
    hard_delete_user_permission_override,
    update_user_permission_override,
)

router = APIRouter()


@router.post(
    "/users/{target_user_id}/permissions",
    response_model=ApiResponse[UserPermissionOverrideOut],
)
def create_user_permission(
    target_user_id: int,
    payload: UserPermissionUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPermissionOverrideOut]:
    override = add_user_permission_override(
        db,
        current_user=current_user,
        target_user_id=target_user_id,
        permission_code=payload.permission_code,
        effect=payload.effect,
    )
    response = UserPermissionOverrideOut(
        id=override.id,
        user_id=override.user_id,
        permission_code=override.permission_code,
        effect=override.effect,
    )
    return success_response(response, message="User permission override created")


@router.put(
    "/users/{target_user_id}/permissions/{permission_code}",
    response_model=ApiResponse[UserPermissionOverrideOut],
)
def edit_user_permission(
    target_user_id: int,
    permission_code: str,
    payload: UserPermissionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserPermissionOverrideOut]:
    override = update_user_permission_override(
        db,
        current_user=current_user,
        target_user_id=target_user_id,
        permission_code=permission_code.strip(),
        effect=payload.effect,
    )
    response = UserPermissionOverrideOut(
        id=override.id,
        user_id=override.user_id,
        permission_code=override.permission_code,
        effect=override.effect,
    )
    return success_response(response, message="User permission override updated")


@router.delete(
    "/users/{target_user_id}/permissions/{permission_code}",
    response_model=ApiResponse[DeleteUserPermissionResponse],
)
def remove_user_permission(
    target_user_id: int,
    permission_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DeleteUserPermissionResponse]:
    removed = delete_user_permission_override(
        db,
        current_user=current_user,
        target_user_id=target_user_id,
        permission_code=permission_code.strip(),
    )
    response = DeleteUserPermissionResponse(removed=removed)
    return success_response(response, message="User permission override deleted")


@router.delete(
    "/users/{target_user_id}/permissions/{permission_code}/hard",
    response_model=ApiResponse[DeleteUserPermissionResponse],
)
def remove_user_permission_forever(
    target_user_id: int,
    permission_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DeleteUserPermissionResponse]:
    removed = hard_delete_user_permission_override(
        db,
        current_user=current_user,
        target_user_id=target_user_id,
        permission_code=permission_code.strip(),
    )
    response = DeleteUserPermissionResponse(removed=removed)
    return success_response(
        response, message="User permission override permanently deleted"
    )
