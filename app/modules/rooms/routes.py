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
from app.modules.rooms.schemas import (
    RoomCreateRequest,
    RoomOut,
    RoomUpdateRequest,
    SoftDeleteResult,
)
from app.modules.rooms.service import (
    create_room,
    hard_delete_room,
    list_rooms,
    soft_delete_room,
    update_room,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[RoomOut]])
def get_rooms(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[RoomOut]]:
    items, total_items = list_rooms(
        db,
        current_user,
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
    return success_response(result, message="Lấy danh sách phòng thành công")


@router.post("", response_model=ApiResponse[RoomOut])
def add_room(
    payload: RoomCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RoomOut]:
    result = create_room(db, current_user, payload)
    return success_response(result, message="Tạo phòng thành công")


@router.put("/{room_id}", response_model=ApiResponse[RoomOut])
def edit_room(
    room_id: int,
    payload: RoomUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RoomOut]:
    result = update_room(db, current_user, room_id=room_id, payload=payload)
    return success_response(result, message="Cập nhật phòng thành công")


@router.delete("/{room_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_room(db, current_user, room_id=room_id)
    return success_response(result, message="Xóa mềm phòng thành công")


@router.delete("/{room_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_room_forever(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_room(db, current_user, room_id=room_id)
    return success_response(result, message="Xóa vĩnh viễn phòng thành công")
