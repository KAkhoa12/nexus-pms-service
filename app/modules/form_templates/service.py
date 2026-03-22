from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.core.models import FormTemplate, User
from app.modules.form_templates.schemas import (
    FormTemplateCreateRequest,
    FormTemplateDeleteResult,
    FormTemplateOut,
    FormTemplateUpdateRequest,
)

MAX_ITEMS_PER_PAGE = 200


def _to_out(item: FormTemplate) -> FormTemplateOut:
    return FormTemplateOut(
        id=item.id,
        tenant_id=item.tenant_id,
        name=item.name,
        template_type=item.template_type,
        page_size=item.page_size,
        orientation=item.orientation,
        font_family=item.font_family,
        font_size=item.font_size,
        text_color=item.text_color,
        content_html=item.content_html,
        config_json=item.config_json,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
    )


def _apply_deleted_mode(stmt, deleted_mode: str):
    if deleted_mode == "active":
        return stmt.where(FormTemplate.deleted_at.is_(None))
    if deleted_mode == "trash":
        return stmt.where(FormTemplate.deleted_at.is_not(None))
    if deleted_mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode phải là active, trash hoặc all",
    )


def _get_template(
    db: Session, current_user: User, *, template_id: int, include_deleted: bool
) -> FormTemplate:
    stmt = select(FormTemplate).where(
        FormTemplate.id == template_id,
        FormTemplate.tenant_id == current_user.tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(FormTemplate.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biểu mẫu"
        )
    return item


def list_form_templates(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
) -> tuple[list[FormTemplateOut], int]:
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page phải lớn hơn hoặc bằng 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = select(FormTemplate).where(FormTemplate.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, deleted_mode)

    if search_key:
        keyword = f"%{search_key.strip()}%"
        stmt = stmt.where(
            or_(
                FormTemplate.name.ilike(keyword),
                FormTemplate.template_type.ilike(keyword),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(FormTemplate.updated_at.desc())
        .offset((page - 1) * items_per_page)
        .limit(items_per_page)
    ).all()

    return [_to_out(item) for item in items], int(total_items)


def get_form_template(
    db: Session, current_user: User, *, template_id: int
) -> FormTemplateOut:
    item = _get_template(
        db, current_user, template_id=template_id, include_deleted=True
    )
    return _to_out(item)


def create_form_template(
    db: Session, current_user: User, payload: FormTemplateCreateRequest
) -> FormTemplateOut:
    exists = db.scalar(
        select(FormTemplate).where(
            FormTemplate.tenant_id == current_user.tenant_id,
            FormTemplate.name == payload.name.strip(),
            FormTemplate.deleted_at.is_(None),
        )
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên biểu mẫu đã tồn tại",
        )

    item = FormTemplate(
        tenant_id=current_user.tenant_id,
        name=payload.name.strip(),
        template_type=payload.template_type,
        page_size=payload.page_size,
        orientation=payload.orientation,
        font_family=payload.font_family,
        font_size=payload.font_size,
        text_color=payload.text_color,
        content_html=payload.content_html,
        config_json=payload.config_json,
        is_active=payload.is_active,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def update_form_template(
    db: Session,
    current_user: User,
    *,
    template_id: int,
    payload: FormTemplateUpdateRequest,
) -> FormTemplateOut:
    item = _get_template(
        db, current_user, template_id=template_id, include_deleted=False
    )

    if payload.name is not None:
        next_name = payload.name.strip()
        exists = db.scalar(
            select(FormTemplate).where(
                FormTemplate.tenant_id == current_user.tenant_id,
                FormTemplate.name == next_name,
                FormTemplate.id != item.id,
                FormTemplate.deleted_at.is_(None),
            )
        )
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tên biểu mẫu đã tồn tại",
            )
        item.name = next_name

    if payload.template_type is not None:
        item.template_type = payload.template_type
    if payload.page_size is not None:
        item.page_size = payload.page_size
    if payload.orientation is not None:
        item.orientation = payload.orientation
    if payload.font_family is not None:
        item.font_family = payload.font_family
    if payload.font_size is not None:
        item.font_size = payload.font_size
    if payload.text_color is not None:
        item.text_color = payload.text_color
    if payload.content_html is not None:
        item.content_html = payload.content_html
    if payload.config_json is not None:
        item.config_json = payload.config_json
    if payload.is_active is not None:
        item.is_active = payload.is_active

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def soft_delete_form_template(
    db: Session, current_user: User, *, template_id: int
) -> FormTemplateDeleteResult:
    item = _get_template(
        db, current_user, template_id=template_id, include_deleted=False
    )
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return FormTemplateDeleteResult(deleted=True)


def hard_delete_form_template(
    db: Session, current_user: User, *, template_id: int
) -> FormTemplateDeleteResult:
    item = _get_template(
        db, current_user, template_id=template_id, include_deleted=True
    )
    if item.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biểu mẫu phải được xóa mềm trước khi xóa vĩnh viễn",
        )
    db.delete(item)
    db.commit()
    return FormTemplateDeleteResult(deleted=True)
