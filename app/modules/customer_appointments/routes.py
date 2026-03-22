from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import ApiResponse, PaginatedResult, build_paginated_result, success_response
from app.modules.customer_appointments.schemas import (
    CustomerAppointmentCreateRequest,
    CustomerAppointmentDeleteResult,
    CustomerAppointmentOut,
    CustomerAppointmentUpdateRequest,
)
from app.modules.customer_appointments.service import (
    create_customer_appointment,
    get_customer_appointment,
    hard_delete_customer_appointment,
    list_customer_appointments,
    soft_delete_customer_appointment,
    update_customer_appointment,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[CustomerAppointmentOut]])
def get_customer_appointments(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=500),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[CustomerAppointmentOut]]:
    items, total_items = list_customer_appointments(
        db,
        tenant_id=current_user.tenant_id,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        search_key=search_key,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách khách hẹn thành công")


@router.get("/{appointment_id}", response_model=ApiResponse[CustomerAppointmentOut])
def get_customer_appointment_detail(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerAppointmentOut]:
    item = get_customer_appointment(
        db,
        tenant_id=current_user.tenant_id,
        item_id=appointment_id,
    )
    return success_response(item, message="Lấy chi tiết khách hẹn thành công")


@router.post("", response_model=ApiResponse[CustomerAppointmentOut])
def add_customer_appointment(
    payload: CustomerAppointmentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerAppointmentOut]:
    item = create_customer_appointment(
        db,
        tenant_id=current_user.tenant_id,
        payload=payload,
    )
    return success_response(item, message="Tạo khách hẹn thành công")


@router.put("/{appointment_id}", response_model=ApiResponse[CustomerAppointmentOut])
def edit_customer_appointment(
    appointment_id: int,
    payload: CustomerAppointmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerAppointmentOut]:
    item = update_customer_appointment(
        db,
        tenant_id=current_user.tenant_id,
        item_id=appointment_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật khách hẹn thành công")


@router.delete("/{appointment_id}", response_model=ApiResponse[CustomerAppointmentDeleteResult])
def delete_customer_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerAppointmentDeleteResult]:
    result = soft_delete_customer_appointment(
        db,
        tenant_id=current_user.tenant_id,
        item_id=appointment_id,
    )
    return success_response(result, message="Xóa mềm khách hẹn thành công")


@router.delete("/{appointment_id}/hard", response_model=ApiResponse[CustomerAppointmentDeleteResult])
def delete_customer_appointment_hard(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerAppointmentDeleteResult]:
    result = hard_delete_customer_appointment(
        db,
        tenant_id=current_user.tenant_id,
        item_id=appointment_id,
    )
    return success_response(result, message="Xóa vĩnh viễn khách hẹn thành công")
