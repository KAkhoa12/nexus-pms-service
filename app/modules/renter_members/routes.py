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
from app.modules.renter_members.schemas import (
    RenterMemberCreateRequest,
    RenterMemberOut,
    RenterMemberUpdateRequest,
    SoftDeleteResult,
)
from app.modules.renter_members.service import (
    create_renter_member,
    hard_delete_renter_member,
    list_renter_members,
    soft_delete_renter_member,
    update_renter_member,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[RenterMemberOut]])
def get_renter_members(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[RenterMemberOut]]:
    items, total_items = list_renter_members(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Renter members fetched successfully")


@router.post("", response_model=ApiResponse[RenterMemberOut])
def add_renter_member(
    payload: RenterMemberCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RenterMemberOut]:
    result = create_renter_member(db, current_user, payload)
    return success_response(result, message="Renter member created successfully")


@router.put("/{member_id}", response_model=ApiResponse[RenterMemberOut])
def edit_renter_member(
    member_id: int,
    payload: RenterMemberUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RenterMemberOut]:
    result = update_renter_member(
        db, current_user, member_id=member_id, payload=payload
    )
    return success_response(result, message="Renter member updated successfully")


@router.delete("/{member_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_renter_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_renter_member(db, current_user, member_id=member_id)
    return success_response(result, message="Renter member soft deleted")


@router.delete("/{member_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_renter_member_forever(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_renter_member(db, current_user, member_id=member_id)
    return success_response(result, message="Renter member permanently deleted")
