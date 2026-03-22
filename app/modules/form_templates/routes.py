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
from app.modules.form_templates.schemas import (
    FormTemplateCreateRequest,
    FormTemplateDeleteResult,
    FormTemplateOut,
    FormTemplateUpdateRequest,
)
from app.modules.form_templates.service import (
    create_form_template,
    get_form_template,
    hard_delete_form_template,
    list_form_templates,
    soft_delete_form_template,
    update_form_template,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[FormTemplateOut]])
def get_form_templates(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[FormTemplateOut]]:
    items, total_items = list_form_templates(
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
    return success_response(result, message="Lấy danh sách biểu mẫu thành công")


@router.get("/{template_id}", response_model=ApiResponse[FormTemplateOut])
def get_form_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FormTemplateOut]:
    item = get_form_template(db, current_user, template_id=template_id)
    return success_response(item, message="Lấy chi tiết biểu mẫu thành công")


@router.post("", response_model=ApiResponse[FormTemplateOut])
def add_form_template(
    payload: FormTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FormTemplateOut]:
    item = create_form_template(db, current_user, payload)
    return success_response(item, message="Tạo biểu mẫu thành công")


@router.put("/{template_id}", response_model=ApiResponse[FormTemplateOut])
def edit_form_template(
    template_id: int,
    payload: FormTemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FormTemplateOut]:
    item = update_form_template(
        db,
        current_user,
        template_id=template_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật biểu mẫu thành công")


@router.delete("/{template_id}", response_model=ApiResponse[FormTemplateDeleteResult])
def delete_form_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FormTemplateDeleteResult]:
    result = soft_delete_form_template(db, current_user, template_id=template_id)
    return success_response(result, message="Xóa mềm biểu mẫu thành công")


@router.delete(
    "/{template_id}/hard", response_model=ApiResponse[FormTemplateDeleteResult]
)
def delete_form_template_forever(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[FormTemplateDeleteResult]:
    result = hard_delete_form_template(db, current_user, template_id=template_id)
    return success_response(result, message="Xóa vĩnh viễn biểu mẫu thành công")
