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
from app.modules.room_types.schemas import (
    RoomTypeCreateRequest,
    RoomTypeOut,
    RoomTypeUpdateRequest,
    SoftDeleteResult,
)
from app.modules.room_types.service import (
    create_room_type,
    hard_delete_room_type,
    list_room_types,
    soft_delete_room_type,
    update_room_type,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[RoomTypeOut]])
def get_room_types(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[RoomTypeOut]]:
    items, total_items = list_room_types(
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
    return success_response(result, message="Lấy danh sách loại phòng thành công")


@router.post("", response_model=ApiResponse[RoomTypeOut])
def add_room_type(
    payload: RoomTypeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RoomTypeOut]:
    result = create_room_type(db, current_user, payload)
    return success_response(result, message="Tạo loại phòng thành công")


@router.put("/{room_type_id}", response_model=ApiResponse[RoomTypeOut])
def edit_room_type(
    room_type_id: int,
    payload: RoomTypeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RoomTypeOut]:
    result = update_room_type(
        db, current_user, room_type_id=room_type_id, payload=payload
    )
    return success_response(result, message="Cập nhật loại phòng thành công")


@router.delete("/{room_type_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_room_type(
    room_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_room_type(db, current_user, room_type_id=room_type_id)
    return success_response(result, message="Xóa mềm loại phòng thành công")


@router.delete("/{room_type_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_room_type_forever(
    room_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_room_type(db, current_user, room_type_id=room_type_id)
    return success_response(result, message="Xóa vĩnh viễn loại phòng thành công")
