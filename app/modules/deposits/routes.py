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
from app.modules.deposits.schemas import (
    DepositCreateRequest,
    DepositOut,
    DepositUpdateRequest,
    SoftDeleteResult,
)
from app.modules.deposits.service import (
    create_deposit,
    get_deposit,
    hard_delete_deposit,
    list_deposits,
    soft_delete_deposit,
    update_deposit,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[DepositOut]])
def get_deposits(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    room_id: int | None = Query(default=None),
    lease_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[DepositOut]]:
    items, total_items = list_deposits(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        room_id=room_id,
        lease_id=lease_id,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách đặt cọc thành công")


@router.post("", response_model=ApiResponse[DepositOut])
def add_deposit(
    payload: DepositCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DepositOut]:
    result = create_deposit(db, current_user, payload)
    return success_response(result, message="Tạo phiếu đặt cọc thành công")


@router.get("/{deposit_id}", response_model=ApiResponse[DepositOut])
def get_deposit_detail(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DepositOut]:
    result = get_deposit(db, current_user, deposit_id=deposit_id)
    return success_response(result, message="Lấy chi tiết phiếu đặt cọc thành công")


@router.put("/{deposit_id}", response_model=ApiResponse[DepositOut])
def edit_deposit(
    deposit_id: int,
    payload: DepositUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DepositOut]:
    result = update_deposit(db, current_user, deposit_id=deposit_id, payload=payload)
    return success_response(result, message="Cập nhật phiếu đặt cọc thành công")


@router.delete("/{deposit_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_deposit(db, current_user, deposit_id=deposit_id)
    return success_response(result, message="Xóa mềm phiếu đặt cọc thành công")


@router.delete("/{deposit_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_deposit_forever(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_deposit(db, current_user, deposit_id=deposit_id)
    return success_response(result, message="Xóa vĩnh viễn phiếu đặt cọc thành công")
