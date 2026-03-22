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
from app.modules.branches.schemas import (
    BranchCreateRequest,
    BranchOut,
    BranchUpdateRequest,
    SoftDeleteResult,
)
from app.modules.branches.service import (
    create_branch,
    hard_delete_branch,
    list_branches,
    soft_delete_branch,
    update_branch,
)
from app.modules.core.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[BranchOut]])
def get_branches(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[BranchOut]]:
    items, total_items = list_branches(
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
    return success_response(result, message="Lấy danh sách chi nhánh thành công")


@router.post("", response_model=ApiResponse[BranchOut])
def add_branch(
    payload: BranchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[BranchOut]:
    result = create_branch(db, current_user, payload)
    return success_response(result, message="Tạo chi nhánh thành công")


@router.put("/{branch_id}", response_model=ApiResponse[BranchOut])
def edit_branch(
    branch_id: int,
    payload: BranchUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[BranchOut]:
    result = update_branch(db, current_user, branch_id=branch_id, payload=payload)
    return success_response(result, message="Cập nhật chi nhánh thành công")


@router.delete("/{branch_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_branch(db, current_user, branch_id=branch_id)
    return success_response(result, message="Xóa mềm chi nhánh thành công")


@router.delete("/{branch_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_branch_forever(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_branch(db, current_user, branch_id=branch_id)
    return success_response(result, message="Xóa vĩnh viễn chi nhánh thành công")
