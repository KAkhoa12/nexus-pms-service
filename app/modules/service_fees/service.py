from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.core.models import ServiceFee
from app.modules.service_fees.schemas import (
    ServiceFeeCreateRequest,
    ServiceFeeDeleteResult,
    ServiceFeeOut,
    ServiceFeeUpdateRequest,
)

MAX_ITEMS_PER_PAGE = 500
BILLING_CYCLES = {"MONTHLY", "ONE_TIME", "CUSTOM_MONTHS"}
CHARGE_MODES = {"FIXED", "USAGE"}


def _normalize_billing_config(
    *,
    billing_cycle: str | None,
    cycle_interval_months: int | None,
) -> tuple[str, int | None]:
    normalized_cycle = (billing_cycle or "MONTHLY").strip().upper()
    if normalized_cycle not in BILLING_CYCLES:
        raise HTTPException(
            status_code=400,
            detail="billing_cycle không hợp lệ. Hỗ trợ: MONTHLY, ONE_TIME, CUSTOM_MONTHS",
        )
    if normalized_cycle == "MONTHLY":
        return ("MONTHLY", 1)
    if normalized_cycle == "ONE_TIME":
        return ("ONE_TIME", None)
    # CUSTOM_MONTHS
    if cycle_interval_months is None or cycle_interval_months < 1:
        raise HTTPException(
            status_code=400,
            detail="cycle_interval_months phải >= 1 khi billing_cycle=CUSTOM_MONTHS",
        )
    return ("CUSTOM_MONTHS", int(cycle_interval_months))


def _normalize_charge_mode(charge_mode: str | None) -> str:
    normalized = (charge_mode or "FIXED").strip().upper()
    if normalized not in CHARGE_MODES:
        raise HTTPException(
            status_code=400,
            detail="charge_mode không hợp lệ. Hỗ trợ: FIXED, USAGE",
        )
    return normalized


def _to_out(item: ServiceFee) -> ServiceFeeOut:
    return ServiceFeeOut(
        id=item.id,
        tenant_id=item.tenant_id,
        code=item.code,
        name=item.name,
        unit=item.unit,
        default_quantity=item.default_quantity,
        default_price=item.default_price,
        billing_cycle=item.billing_cycle,
        cycle_interval_months=item.cycle_interval_months,
        charge_mode=item.charge_mode,
        description=item.description,
        is_active=item.is_active,
    )


def _apply_deleted_mode(stmt, deleted_mode: str):
    mode = (deleted_mode or "active").strip().lower()
    if mode == "active":
        return stmt.where(ServiceFee.deleted_at.is_(None))
    if mode == "trash":
        return stmt.where(ServiceFee.deleted_at.is_not(None))
    if mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode phải là active, trash hoặc all",
    )


def _get_item(db: Session, *, tenant_id: int, item_id: int, include_deleted: bool):
    stmt = select(ServiceFee).where(
        ServiceFee.id == item_id, ServiceFee.tenant_id == tenant_id
    )
    if not include_deleted:
        stmt = stmt.where(ServiceFee.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phí thu")
    return item


def list_service_fees(
    db: Session,
    *,
    tenant_id: int,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
    billing_cycle: str | None,
    charge_mode: str | None,
) -> tuple[list[ServiceFeeOut], int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page phải >= 1")
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=400,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = select(ServiceFee).where(ServiceFee.tenant_id == tenant_id)
    stmt = _apply_deleted_mode(stmt, deleted_mode)
    if billing_cycle and billing_cycle.strip():
        stmt = stmt.where(ServiceFee.billing_cycle == billing_cycle.strip().upper())
    if charge_mode and charge_mode.strip():
        stmt = stmt.where(ServiceFee.charge_mode == charge_mode.strip().upper())
    if search_key and search_key.strip():
        keyword = f"%{search_key.strip()}%"
        stmt = stmt.where(
            or_(
                ServiceFee.code.ilike(keyword),
                ServiceFee.name.ilike(keyword),
                ServiceFee.unit.ilike(keyword),
                ServiceFee.billing_cycle.ilike(keyword),
                ServiceFee.charge_mode.ilike(keyword),
                ServiceFee.description.ilike(keyword),
            )
        )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.order_by(ServiceFee.id.desc())
            .offset((page - 1) * items_per_page)
            .limit(items_per_page)
        ).all()
    )
    return [_to_out(item) for item in rows], total


def create_service_fee(
    db: Session, *, tenant_id: int, payload: ServiceFeeCreateRequest
) -> ServiceFeeOut:
    billing_cycle, cycle_interval_months = _normalize_billing_config(
        billing_cycle=payload.billing_cycle,
        cycle_interval_months=payload.cycle_interval_months,
    )
    charge_mode = _normalize_charge_mode(payload.charge_mode)
    provided_code = (payload.code or "").strip().upper()
    # Temporary code required for INSERT because column is NOT NULL.
    provisional_code = (
        provided_code
        if provided_code
        else f"AUTO-{tenant_id}-{uuid4().hex[:12].upper()}"
    )
    if provided_code:
        exists = db.scalar(
            select(ServiceFee.id).where(
                ServiceFee.tenant_id == tenant_id,
                ServiceFee.code == provided_code,
                ServiceFee.deleted_at.is_(None),
            )
        )
        if exists is not None:
            raise HTTPException(status_code=409, detail="Mã phí đã tồn tại")

    item = ServiceFee(
        tenant_id=tenant_id,
        code=provisional_code,
        name=payload.name.strip(),
        unit=(payload.unit or "").strip() or None,
        default_quantity=payload.default_quantity,
        default_price=payload.default_price,
        billing_cycle=billing_cycle,
        cycle_interval_months=cycle_interval_months,
        charge_mode=charge_mode,
        description=(payload.description or "").strip() or None,
        is_active=payload.is_active,
    )
    db.add(item)
    db.flush()
    if not provided_code:
        item.code = str(item.id)
        db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def update_service_fee(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
    payload: ServiceFeeUpdateRequest,
) -> ServiceFeeOut:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=False)
    next_billing_cycle = (
        payload.billing_cycle
        if payload.billing_cycle is not None
        else item.billing_cycle
    )
    next_interval = (
        payload.cycle_interval_months
        if payload.cycle_interval_months is not None
        else item.cycle_interval_months
    )

    # code is system-generated by ID, so it is not editable in update flow.
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.unit is not None:
        item.unit = payload.unit.strip() or None
    if payload.default_quantity is not None:
        item.default_quantity = payload.default_quantity
    if payload.default_price is not None:
        item.default_price = payload.default_price
    if payload.billing_cycle is not None or payload.cycle_interval_months is not None:
        billing_cycle, cycle_interval_months = _normalize_billing_config(
            billing_cycle=next_billing_cycle,
            cycle_interval_months=next_interval,
        )
        item.billing_cycle = billing_cycle
        item.cycle_interval_months = cycle_interval_months
    if payload.charge_mode is not None:
        item.charge_mode = _normalize_charge_mode(payload.charge_mode)
    if payload.description is not None:
        item.description = payload.description.strip() or None
    if payload.is_active is not None:
        item.is_active = payload.is_active

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def soft_delete_service_fee(
    db: Session, *, tenant_id: int, item_id: int
) -> ServiceFeeDeleteResult:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return ServiceFeeDeleteResult(deleted=True)


def hard_delete_service_fee(
    db: Session, *, tenant_id: int, item_id: int
) -> ServiceFeeDeleteResult:
    item = _get_item(db, tenant_id=tenant_id, item_id=item_id, include_deleted=True)
    db.delete(item)
    db.commit()
    return ServiceFeeDeleteResult(deleted=True)
