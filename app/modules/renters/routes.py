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
from app.modules.renters.schemas import (
    RenterCreateRequest,
    RenterOut,
    RenterUpdateRequest,
    SoftDeleteResult,
)
from app.modules.renters.service import (
    create_renter,
    hard_delete_renter,
    list_renters,
    soft_delete_renter,
    update_renter,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[RenterOut]])
def get_renters(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[RenterOut]]:
    items, total_items = list_renters(
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
    return success_response(result, message="Renters fetched successfully")


@router.post("", response_model=ApiResponse[RenterOut])
def add_renter(
    payload: RenterCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RenterOut]:
    result = create_renter(db, current_user, payload)
    return success_response(result, message="Renter created successfully")


@router.put("/{renter_id}", response_model=ApiResponse[RenterOut])
def edit_renter(
    renter_id: int,
    payload: RenterUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RenterOut]:
    result = update_renter(db, current_user, renter_id=renter_id, payload=payload)
    return success_response(result, message="Renter updated successfully")


@router.delete("/{renter_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_renter(
    renter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_renter(db, current_user, renter_id=renter_id)
    return success_response(result, message="Renter soft deleted")


@router.delete("/{renter_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_renter_forever(
    renter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_renter(db, current_user, renter_id=renter_id)
    return success_response(result, message="Renter permanently deleted")
