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
from app.modules.core.models import LeaseStatusEnum
from app.modules.leases.schemas import (
    LeaseCreateRequest,
    LeaseDeleteResult,
    LeaseDetailOut,
    LeaseInstallmentOut,
    LeaseInstallmentUpdateRequest,
    LeaseOut,
    LeaseUpdateRequest,
)
from app.modules.leases.service import (
    create_lease,
    get_lease,
    list_leases,
    soft_delete_lease,
    update_lease,
    update_lease_installment,
)
from app.modules.leases.service import (
    get_lease_detail as get_lease_full_detail,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[LeaseOut]])
def get_leases(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    room_id: int | None = Query(default=None),
    renter_id: int | None = Query(default=None),
    status_filter: LeaseStatusEnum | None = Query(default=None),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[LeaseOut]]:
    items, total_items = list_leases(
        db,
        current_user=current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        room_id=room_id,
        renter_id=renter_id,
        status_filter=status_filter,
        search_key=search_key,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách hợp đồng thuê thành công")


@router.get("/{lease_id}", response_model=ApiResponse[LeaseOut])
def get_lease_detail(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseOut]:
    item = get_lease(db, current_user=current_user, lease_id=lease_id)
    return success_response(item, message="Lấy chi tiết hợp đồng thuê thành công")


@router.get("/{lease_id}/detail", response_model=ApiResponse[LeaseDetailOut])
def get_lease_detail_with_installments(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseDetailOut]:
    item = get_lease_full_detail(db, current_user=current_user, lease_id=lease_id)
    return success_response(
        item, message="Lấy chi tiết hợp đồng và kỳ thanh toán thành công"
    )


@router.post("", response_model=ApiResponse[LeaseOut])
def add_lease(
    payload: LeaseCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseOut]:
    item = create_lease(db, current_user=current_user, payload=payload)
    return success_response(item, message="Tạo hợp đồng thuê thành công")


@router.put("/{lease_id}", response_model=ApiResponse[LeaseOut])
def edit_lease(
    lease_id: int,
    payload: LeaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseOut]:
    item = update_lease(
        db,
        current_user=current_user,
        lease_id=lease_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật hợp đồng thuê thành công")


@router.put(
    "/{lease_id}/invoices/{invoice_id}",
    response_model=ApiResponse[LeaseInstallmentOut],
)
def edit_lease_installment(
    lease_id: int,
    invoice_id: int,
    payload: LeaseInstallmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseInstallmentOut]:
    item = update_lease_installment(
        db,
        current_user=current_user,
        lease_id=lease_id,
        invoice_id=invoice_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật kỳ thanh toán thành công")


@router.delete("/{lease_id}", response_model=ApiResponse[LeaseDeleteResult])
def delete_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[LeaseDeleteResult]:
    result = soft_delete_lease(db, current_user=current_user, lease_id=lease_id)
    return success_response(result, message="Xóa mềm hợp đồng thuê thành công")
