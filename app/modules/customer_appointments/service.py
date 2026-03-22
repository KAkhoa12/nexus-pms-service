from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.core.models import CustomerAppointment
from app.modules.customer_appointments.schemas import (
    CustomerAppointmentCreateRequest,
    CustomerAppointmentDeleteResult,
    CustomerAppointmentOut,
    CustomerAppointmentUpdateRequest,
)

MAX_ITEMS_PER_PAGE = 500


def _to_out(item: CustomerAppointment) -> CustomerAppointmentOut:
    return CustomerAppointmentOut(
        id=item.id,
        tenant_id=item.tenant_id,
        branch_id=item.branch_id,
        room_id=item.room_id,
        contact_name=item.contact_name,
        phone=item.phone,
        email=item.email,
        note=item.note,
        start_at=item.start_at,
        end_at=item.end_at,
        status=item.status,
        source=item.source,
        assigned_user_id=item.assigned_user_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
    )


def _apply_deleted_mode(stmt, deleted_mode: str):
    mode = (deleted_mode or "active").strip().lower()
    if mode == "active":
        return stmt.where(CustomerAppointment.deleted_at.is_(None))
    if mode == "trash":
        return stmt.where(CustomerAppointment.deleted_at.is_not(None))
    if mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode phải là active, trash hoặc all",
    )


def _get_item(db: Session, *, tenant_id: int, item_id: int, include_deleted: bool):
    stmt = select(CustomerAppointment).where(
        CustomerAppointment.id == item_id,
        CustomerAppointment.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(CustomerAppointment.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hẹn",
        )
    return item


def list_customer_appointments(
    db: Session,
    *,
    tenant_id: int,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
) -> tuple[list[CustomerAppointmentOut], int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page phải >= 1")
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=400,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = select(CustomerAppointment).where(CustomerAppointment.tenant_id == tenant_id)
    stmt = _apply_deleted_mode(stmt, deleted_mode)

    if search_key and search_key.strip():
        keyword = f"%{search_key.strip()}%"
        stmt = stmt.where(
            or_(
                CustomerAppointment.contact_name.ilike(keyword),
                CustomerAppointment.phone.ilike(keyword),
                CustomerAppointment.email.ilike(keyword),
                CustomerAppointment.note.ilike(keyword),
            )
        )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.order_by(CustomerAppointment.start_at.desc(), CustomerAppointment.id.desc())
            .offset((page - 1) * items_per_page)
            .limit(items_per_page)
        ).all()
    )
    return [_to_out(item) for item in rows], total


def get_customer_appointment(db: Session, *, tenant_id: int, item_id: int) -> CustomerAppointmentOut:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=True)
    return _to_out(item)


def create_customer_appointment(
    db: Session,
    *,
    tenant_id: int,
    payload: CustomerAppointmentCreateRequest,
) -> CustomerAppointmentOut:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải lớn hơn bắt đầu")

    item = CustomerAppointment(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        room_id=payload.room_id,
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip() or None,
        note=(payload.note or "").strip() or None,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=payload.status.strip().upper(),
        source=(payload.source or "").strip() or None,
        assigned_user_id=payload.assigned_user_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def update_customer_appointment(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
    payload: CustomerAppointmentUpdateRequest,
) -> CustomerAppointmentOut:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=False)

    if payload.branch_id is not None:
        item.branch_id = payload.branch_id
    if payload.room_id is not None:
        item.room_id = payload.room_id
    if payload.contact_name is not None:
        item.contact_name = payload.contact_name.strip()
    if payload.phone is not None:
        item.phone = payload.phone.strip()
    if payload.email is not None:
        item.email = payload.email.strip() or None
    if payload.note is not None:
        item.note = payload.note.strip() or None
    if payload.start_at is not None:
        item.start_at = payload.start_at
    if payload.end_at is not None:
        item.end_at = payload.end_at
    if item.end_at <= item.start_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải lớn hơn bắt đầu")
    if payload.status is not None:
        item.status = payload.status.strip().upper()
    if payload.source is not None:
        item.source = payload.source.strip() or None
    if payload.assigned_user_id is not None:
        item.assigned_user_id = payload.assigned_user_id

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def soft_delete_customer_appointment(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
) -> CustomerAppointmentDeleteResult:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return CustomerAppointmentDeleteResult(deleted=True)


def hard_delete_customer_appointment(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
) -> CustomerAppointmentDeleteResult:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=True)
    db.delete(item)
    db.commit()
    return CustomerAppointmentDeleteResult(deleted=True)
