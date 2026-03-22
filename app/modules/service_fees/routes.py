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
from app.modules.service_fees.schemas import (
    ServiceFeeCreateRequest,
    ServiceFeeDeleteResult,
    ServiceFeeOut,
    ServiceFeeUpdateRequest,
)
from app.modules.service_fees.service import (
    create_service_fee,
    hard_delete_service_fee,
    list_service_fees,
    soft_delete_service_fee,
    update_service_fee,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[ServiceFeeOut]])
def get_service_fees(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=500),
    search_key: str | None = Query(default=None),
    billing_cycle: str | None = Query(default=None),
    charge_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[ServiceFeeOut]]:
    items, total_items = list_service_fees(
        db,
        tenant_id=current_user.tenant_id,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        search_key=search_key,
        billing_cycle=billing_cycle,
        charge_mode=charge_mode,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách phí thu thành công")


@router.post("", response_model=ApiResponse[ServiceFeeOut])
def add_service_fee(
    payload: ServiceFeeCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[ServiceFeeOut]:
    item = create_service_fee(db, tenant_id=current_user.tenant_id, payload=payload)
    return success_response(item, message="Tạo phí thu thành công")


@router.put("/{fee_id}", response_model=ApiResponse[ServiceFeeOut])
def edit_service_fee(
    fee_id: int,
    payload: ServiceFeeUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[ServiceFeeOut]:
    item = update_service_fee(
        db,
        tenant_id=current_user.tenant_id,
        item_id=fee_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật phí thu thành công")


@router.delete("/{fee_id}", response_model=ApiResponse[ServiceFeeDeleteResult])
def delete_service_fee(
    fee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[ServiceFeeDeleteResult]:
    result = soft_delete_service_fee(
        db,
        tenant_id=current_user.tenant_id,
        item_id=fee_id,
    )
    return success_response(result, message="Xóa mềm phí thu thành công")


@router.delete("/{fee_id}/hard", response_model=ApiResponse[ServiceFeeDeleteResult])
def delete_service_fee_hard(
    fee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[ServiceFeeDeleteResult]:
    result = hard_delete_service_fee(
        db,
        tenant_id=current_user.tenant_id,
        item_id=fee_id,
    )
    return success_response(result, message="Xóa vĩnh viễn phí thu thành công")
