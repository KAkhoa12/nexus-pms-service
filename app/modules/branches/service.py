from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.service import get_user_auth_context
from app.modules.branches.schemas import (
    BranchCreateRequest,
    BranchOut,
    BranchUpdateRequest,
    SoftDeleteResult,
)
from app.modules.core.models import Branch, User

MANAGE_CODES = {"user:mangage", "users:manage"}
BRANCH_VIEW_CODES = {"branches:view", "branch:view", "areas:view", "area:view"}
BRANCH_CREATE_CODES = {"branches:create", "branch:create"}
BRANCH_UPDATE_CODES = {"branches:update", "branch:update"}
BRANCH_DELETE_CODES = {"branches:delete", "branch:delete"}
MAX_ITEMS_PER_PAGE = 200


def _ensure_permission(
    db: Session, current_user: User, required_codes: set[str]
) -> None:
    context = get_user_auth_context(db, current_user)
    if context.has_full_access:
        return
    if context.permissions.intersection(MANAGE_CODES):
        return
    if context.permissions.intersection(required_codes):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền thực hiện thao tác này",
    )


def list_branches(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
) -> tuple[list[BranchOut], int]:
    _ensure_permission(db, current_user, BRANCH_VIEW_CODES)
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số trang phải lớn hơn hoặc bằng 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số bản ghi mỗi trang phải từ 1 đến {MAX_ITEMS_PER_PAGE}",
        )
    stmt = select(Branch).where(Branch.tenant_id == current_user.tenant_id)
    if deleted_mode == "active":
        stmt = stmt.where(Branch.deleted_at.is_(None))
    elif deleted_mode == "trash":
        stmt = stmt.where(Branch.deleted_at.is_not(None))
    elif deleted_mode != "all":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="deleted_mode chỉ nhận: active, trash hoặc all",
        )
    if search_key:
        keyword = search_key.strip().lower()
        if keyword:
            like_pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    func.lower(Branch.name).like(like_pattern),
                )
            )
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(Branch.id.desc())
    items = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return [
        BranchOut(
            id=item.id,
            tenant_id=item.tenant_id,
            name=item.name,
            deleted_at=item.deleted_at,
        )
        for item in items
    ], total_items


def _get_branch(
    db: Session, tenant_id: int, branch_id: int, include_deleted: bool = False
) -> Branch:
    stmt = select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Branch.deleted_at.is_(None))
    branch = db.scalar(stmt)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chi nhánh",
        )
    return branch


def create_branch(
    db: Session, current_user: User, payload: BranchCreateRequest
) -> BranchOut:
    _ensure_permission(db, current_user, BRANCH_CREATE_CODES)
    item = Branch(
        tenant_id=current_user.tenant_id,
        name=payload.name.strip(),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chi nhánh đã tồn tại trong tenant",
        )
    db.refresh(item)
    return BranchOut(
        id=item.id,
        tenant_id=item.tenant_id,
        name=item.name,
        deleted_at=item.deleted_at,
    )


def update_branch(
    db: Session, current_user: User, *, branch_id: int, payload: BranchUpdateRequest
) -> BranchOut:
    _ensure_permission(db, current_user, BRANCH_UPDATE_CODES)
    item = _get_branch(db, current_user.tenant_id, branch_id, include_deleted=False)
    if payload.name is not None:
        item.name = payload.name.strip()
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dữ liệu cập nhật chi nhánh bị trùng",
        )
    db.refresh(item)
    return BranchOut(
        id=item.id,
        tenant_id=item.tenant_id,
        name=item.name,
        deleted_at=item.deleted_at,
    )


def soft_delete_branch(
    db: Session, current_user: User, *, branch_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, BRANCH_DELETE_CODES)
    item = _get_branch(db, current_user.tenant_id, branch_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_branch(
    db: Session, current_user: User, *, branch_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, BRANCH_DELETE_CODES)
    item = _get_branch(db, current_user.tenant_id, branch_id, include_deleted=True)
    if item.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chi nhánh phải được xóa mềm trước khi xóa vĩnh viễn",
        )
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)
