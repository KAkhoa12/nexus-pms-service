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
from app.modules.areas.schemas import (
    AreaCreateRequest,
    AreaOut,
    AreaUpdateRequest,
    SoftDeleteResult,
)
from app.modules.areas.service import (
    create_area,
    hard_delete_area,
    list_areas,
    soft_delete_area,
    update_area,
)
from app.modules.core.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[AreaOut]])
def get_areas(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    branch_id: int | None = Query(default=None, alias="brandid"),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[AreaOut]]:
    items, total_items = list_areas(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        branch_id=branch_id,
        search_key=search_key,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách khu vực thành công")


@router.post("", response_model=ApiResponse[AreaOut])
def add_area(
    payload: AreaCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AreaOut]:
    result = create_area(db, current_user, payload)
    return success_response(result, message="Tạo khu vực thành công")


@router.put("/{area_id}", response_model=ApiResponse[AreaOut])
def edit_area(
    area_id: int,
    payload: AreaUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AreaOut]:
    result = update_area(db, current_user, area_id=area_id, payload=payload)
    return success_response(result, message="Cập nhật khu vực thành công")


@router.delete("/{area_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_area(db, current_user, area_id=area_id)
    return success_response(result, message="Xóa mềm khu vực thành công")


@router.delete("/{area_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_area_forever(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_area(db, current_user, area_id=area_id)
    return success_response(result, message="Xóa vĩnh viễn khu vực thành công")
