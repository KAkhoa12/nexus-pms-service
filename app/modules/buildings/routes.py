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
from app.modules.buildings.schemas import (
    BuildingCreateRequest,
    BuildingOut,
    BuildingUpdateRequest,
    SoftDeleteResult,
)
from app.modules.buildings.service import (
    create_building,
    hard_delete_building,
    list_buildings,
    soft_delete_building,
    update_building,
)
from app.modules.core.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[BuildingOut]])
def get_buildings(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[BuildingOut]]:
    items, total_items = list_buildings(
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
    return success_response(result, message="Lấy danh sách tòa nhà thành công")


@router.post("", response_model=ApiResponse[BuildingOut])
def add_building(
    payload: BuildingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[BuildingOut]:
    result = create_building(db, current_user, payload)
    return success_response(result, message="Tạo tòa nhà thành công")


@router.put("/{building_id}", response_model=ApiResponse[BuildingOut])
def edit_building(
    building_id: int,
    payload: BuildingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[BuildingOut]:
    result = update_building(db, current_user, building_id=building_id, payload=payload)
    return success_response(result, message="Cập nhật tòa nhà thành công")


@router.delete("/{building_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_building(
    building_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_building(db, current_user, building_id=building_id)
    return success_response(result, message="Xóa mềm tòa nhà thành công")


@router.delete("/{building_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_building_forever(
    building_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_building(db, current_user, building_id=building_id)
    return success_response(result, message="Xóa vĩnh viễn tòa nhà thành công")
