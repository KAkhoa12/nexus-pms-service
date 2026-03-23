from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.modules.core.models import (
    CollabNotification,
    CollabNotificationRecipient,
    Invoice,
    InvoiceItem,
    InvoiceStatusEnum,
    Lease,
    LeaseStatusEnum,
    Renter,
    Room,
    RoomCurrentStatusEnum,
    RoomStatusHistory,
    ServiceFee,
    User,
)
from app.modules.leases.schemas import (
    LeaseCreateRequest,
    LeaseDeleteResult,
    LeaseDetailOut,
    LeaseInstallmentItemOut,
    LeaseInstallmentOut,
    LeaseInstallmentUpdateRequest,
    LeaseOut,
    LeaseRenterSummaryOut,
    LeaseRoomSummaryOut,
    LeaseSelectedServiceFeeRequest,
    LeaseUpdateRequest,
)
from app.modules.ops_shared.service import _ensure_permission

MAX_ITEMS_PER_PAGE = 200
LEASE_VIEW_CODES = {"leases:view", "lease:view", "leases:manage"}
LEASE_CREATE_CODES = {"leases:create", "lease:create", "leases:manage"}
LEASE_UPDATE_CODES = {"leases:update", "lease:update", "leases:manage"}
LEASE_DELETE_CODES = {"leases:delete", "lease:delete", "leases:manage"}
LEASE_NOTIFICATION_TYPE_SYSTEM = "SYSTEM"


def _to_out(item: Lease) -> LeaseOut:
    return LeaseOut(
        id=item.id,
        tenant_id=item.tenant_id,
        branch_id=item.branch_id,
        room_id=item.room_id,
        room_code=item.room.code if item.room is not None else None,
        renter_id=item.renter_id,
        renter_full_name=item.renter.full_name if item.renter is not None else None,
        renter_phone=item.renter.phone if item.renter is not None else None,
        created_by_user_id=item.created_by_user_id,
        lease_years=item.lease_years,
        handover_at=item.handover_at,
        start_date=item.start_date,
        end_date=item.end_date,
        rent_price=item.rent_price,
        pricing_mode=item.pricing_mode,
        status=item.status,
        content=item.content,
        content_html=item.content_html,
        security_deposit_amount=item.security_deposit_amount,
        security_deposit_paid_amount=item.security_deposit_paid_amount,
        security_deposit_payment_method=item.security_deposit_payment_method,
        security_deposit_paid_at=item.security_deposit_paid_at,
        security_deposit_note=item.security_deposit_note,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
    )


def _to_lease_installment_out(db: Session, invoice: Invoice) -> LeaseInstallmentOut:
    invoice_items = list(
        db.scalars(
            select(InvoiceItem)
            .where(
                InvoiceItem.invoice_id == invoice.id,
                InvoiceItem.deleted_at.is_(None),
            )
            .order_by(InvoiceItem.id.asc())
        ).all()
    )
    return LeaseInstallmentOut(
        id=invoice.id,
        installment_no=invoice.installment_no,
        installment_total=invoice.installment_total,
        period_month=invoice.period_month,
        due_date=invoice.due_date,
        reminder_at=invoice.reminder_at,
        total_amount=invoice.total_amount,
        paid_amount=invoice.paid_amount,
        status=invoice.status,
        content=invoice.content,
        content_html=invoice.content_html,
        items=[
            LeaseInstallmentItemOut(
                id=item.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )
            for item in invoice_items
        ],
    )


def _apply_deleted_mode(stmt, deleted_mode: str):
    mode = (deleted_mode or "active").strip().lower()
    if mode == "active":
        return stmt.where(Lease.deleted_at.is_(None))
    if mode == "trash":
        return stmt.where(Lease.deleted_at.is_not(None))
    if mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode phải là active, trash hoặc all",
    )


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _add_months_preserve_day(value: datetime, months: int) -> datetime:
    month_index = (value.month - 1) + months
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    max_day = monthrange(year, month)[1]
    day = min(value.day, max_day)
    return value.replace(year=year, month=month, day=day)


def _build_due_dates(start_date: datetime, total_installments: int) -> list[datetime]:
    if total_installments <= 0:
        return []
    return [
        _add_months_preserve_day(start_date, month_offset)
        for month_offset in range(1, total_installments + 1)
    ]


def _service_fee_applies_for_installment(fee: ServiceFee, installment_no: int) -> bool:
    cycle = (fee.billing_cycle or "MONTHLY").upper()
    if cycle == "ONE_TIME":
        return installment_no == 1
    if cycle == "CUSTOM_MONTHS":
        interval = int(fee.cycle_interval_months or 1)
        return ((installment_no - 1) % max(interval, 1)) == 0
    return True


def _generate_invoices_for_lease(
    db: Session,
    *,
    current_user: AuthenticatedUser,
    lease: Lease,
    reminder_days: int,
    selected_service_fees: list[LeaseSelectedServiceFeeRequest] | None = None,
) -> None:
    total_installments = int(lease.lease_years) * 12
    if total_installments <= 0:
        return

    # Kỳ thanh toán bắt đầu từ tháng kế tiếp ngày bàn giao/bắt đầu hợp đồng.
    # Ví dụ: start_date 20/03 => kỳ 1 due_date 20/04.
    due_dates = _build_due_dates(lease.start_date, total_installments)
    period_months = [due_date.strftime("%Y-%m") for due_date in due_dates]
    existing_periods = set(
        db.scalars(
            select(Invoice.period_month).where(
                Invoice.tenant_id == current_user.tenant_id,
                Invoice.room_id == lease.room_id,
                Invoice.deleted_at.is_(None),
                Invoice.period_month.in_(period_months),
            )
        ).all()
    )
    if existing_periods:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Đã tồn tại hóa đơn của phòng trong một số kỳ: "
                + ", ".join(sorted(existing_periods))
            ),
        )

    selected_map: dict[int, LeaseSelectedServiceFeeRequest] = {}
    if selected_service_fees is not None:
        selected_items = list(selected_service_fees)
        for item in selected_items:
            if item.service_fee_id in selected_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Danh sách phí dịch vụ bị trùng",
                )
            selected_map[item.service_fee_id] = item
        selected_ids = list(selected_map.keys())
        if selected_ids:
            service_fees = list(
                db.scalars(
                    select(ServiceFee).where(
                        ServiceFee.tenant_id == current_user.tenant_id,
                        ServiceFee.deleted_at.is_(None),
                        ServiceFee.is_active.is_(True),
                        ServiceFee.id.in_(selected_ids),
                    )
                ).all()
            )
            found_ids = {fee.id for fee in service_fees}
            missing_ids = [fee_id for fee_id in selected_ids if fee_id not in found_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Không tìm thấy phí dịch vụ hợp lệ với id: "
                        + ", ".join(str(item) for item in missing_ids)
                    ),
                )
        else:
            service_fees = []
    else:
        service_fees = list(
            db.scalars(
                select(ServiceFee).where(
                    ServiceFee.tenant_id == current_user.tenant_id,
                    ServiceFee.deleted_at.is_(None),
                    ServiceFee.is_active.is_(True),
                )
            ).all()
        )
    reminder_delta = timedelta(days=max(reminder_days, 0))
    now_utc = datetime.now(timezone.utc)
    reminder_recipients = list(
        db.scalars(
            select(User.id).where(
                User.tenant_id == current_user.tenant_id,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        ).all()
    )
    remaining_deposit_credit = Decimal(
        lease.security_deposit_paid_amount or Decimal("0")
    )

    for index, due_date in enumerate(due_dates, start=1):
        line_items: list[InvoiceItem] = []
        subtotal = Decimal("0")
        rent_amount = Decimal(lease.rent_price or Decimal("0"))
        if rent_amount > 0:
            subtotal += rent_amount
            line_items.append(
                InvoiceItem(
                    tenant_id=current_user.tenant_id,
                    description=f"Tiền thuê phòng kỳ {index}/{total_installments}",
                    quantity=Decimal("1"),
                    unit_price=rent_amount,
                    amount=rent_amount,
                )
            )

        for fee in service_fees:
            if not _service_fee_applies_for_installment(fee, index):
                continue
            selected = selected_map.get(fee.id)
            quantity = Decimal(
                selected.quantity
                if selected is not None
                else fee.default_quantity or Decimal("1")
            )
            if quantity <= 0:
                continue
            unit_price = (
                Decimal(selected.unit_price)
                if selected is not None and selected.unit_price is not None
                else Decimal(fee.default_price or Decimal("0"))
            )
            if unit_price <= 0:
                continue
            fee_amount = unit_price * quantity
            if fee_amount <= 0:
                continue
            subtotal += fee_amount
            line_items.append(
                InvoiceItem(
                    tenant_id=current_user.tenant_id,
                    description=f"Phí dịch vụ: {fee.name}",
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=fee_amount,
                )
            )

        applied_deposit_credit = Decimal("0")
        if index == 1 and remaining_deposit_credit > 0:
            applied_deposit_credit = min(remaining_deposit_credit, subtotal)
            remaining_deposit_credit -= applied_deposit_credit
            if applied_deposit_credit > 0:
                line_items.append(
                    InvoiceItem(
                        tenant_id=current_user.tenant_id,
                        description="Khấu trừ tiền cọc đã thanh toán",
                        quantity=Decimal("1"),
                        unit_price=-applied_deposit_credit,
                        amount=-applied_deposit_credit,
                    )
                )
                subtotal -= applied_deposit_credit

        reminder_at = due_date - reminder_delta
        invoice = Invoice(
            tenant_id=current_user.tenant_id,
            branch_id=lease.branch_id,
            room_id=lease.room_id,
            renter_id=lease.renter_id,
            lease_id=lease.id,
            installment_no=index,
            installment_total=total_installments,
            period_month=due_date.strftime("%Y-%m"),
            due_date=due_date,
            reminder_at=reminder_at,
            total_amount=max(subtotal, Decimal("0")),
            paid_amount=Decimal("0"),
            status=InvoiceStatusEnum.UNPAID,
            content=f"Hóa đơn kỳ {index}/{total_installments} cho hợp đồng #{lease.id}",
            content_html="",
        )
        db.add(invoice)
        db.flush()

        for line in line_items:
            line.invoice_id = invoice.id
            db.add(line)

        published_at = reminder_at if reminder_at > now_utc else now_utc
        notification = CollabNotification(
            tenant_id=current_user.tenant_id,
            team_id=None,
            title=f"Sắp đến hạn đóng tiền kỳ {index}/{total_installments}",
            body=(
                f"Phòng #{lease.room_id} cần thanh toán trước ngày "
                f"{due_date.strftime('%d/%m/%Y')}. Tổng tiền: {max(subtotal, Decimal('0'))}."
            ),
            notification_type=LEASE_NOTIFICATION_TYPE_SYSTEM,
            created_by_user_id=current_user.id,
            published_at=published_at,
        )
        db.add(notification)
        db.flush()
        for recipient_id in reminder_recipients:
            db.add(
                CollabNotificationRecipient(
                    tenant_id=current_user.tenant_id,
                    notification_id=notification.id,
                    user_id=recipient_id,
                    read_at=None,
                )
            )


def _get_room(db: Session, *, tenant_id: int, room_id: int) -> Room:
    item = db.scalar(
        select(Room).where(
            Room.id == room_id,
            Room.tenant_id == tenant_id,
            Room.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng"
        )
    return item


def _get_renter(db: Session, *, tenant_id: int, renter_id: int) -> Renter:
    item = db.scalar(
        select(Renter).where(
            Renter.id == renter_id,
            Renter.tenant_id == tenant_id,
            Renter.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách thuê",
        )
    return item


def _get_lease(db: Session, *, tenant_id: int, lease_id: int, include_deleted: bool):
    stmt = select(Lease).where(Lease.id == lease_id, Lease.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Lease.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hợp đồng thuê"
        )
    return item


def _apply_room_status_change(
    db: Session,
    *,
    room: Room,
    new_status: RoomCurrentStatusEnum,
    current_user: AuthenticatedUser,
    note: str,
) -> None:
    old_status = room.current_status
    if old_status == new_status:
        return
    room.current_status = new_status
    db.add(
        RoomStatusHistory(
            tenant_id=room.tenant_id,
            room_id=room.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_user_id=current_user.id,
            note=note,
        )
    )
    db.add(room)


def list_leases(
    db: Session,
    *,
    current_user: AuthenticatedUser,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    room_id: int | None,
    renter_id: int | None,
    status_filter: LeaseStatusEnum | None,
    search_key: str | None,
) -> tuple[list[LeaseOut], int]:
    _ensure_permission(db, current_user, LEASE_VIEW_CODES)
    if page < 1:
        raise HTTPException(status_code=400, detail="page phải >= 1")
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=400,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = select(Lease).where(Lease.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, deleted_mode)

    if room_id is not None:
        stmt = stmt.where(Lease.room_id == room_id)
    if renter_id is not None:
        stmt = stmt.where(Lease.renter_id == renter_id)
    if status_filter is not None:
        stmt = stmt.where(Lease.status == status_filter)
    if search_key and search_key.strip():
        keyword = f"%{search_key.strip()}%"
        stmt = (
            stmt.join(Renter, Renter.id == Lease.renter_id)
            .join(Room, Room.id == Lease.room_id)
            .where(
                or_(
                    Renter.full_name.ilike(keyword),
                    Renter.phone.ilike(keyword),
                    Room.code.ilike(keyword),
                    cast(Lease.id, String).ilike(keyword),
                )
            )
        )

    total_items = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(Lease.created_at.desc(), Lease.id.desc())
        .offset((page - 1) * items_per_page)
        .limit(items_per_page)
    ).all()
    return [_to_out(item) for item in rows], total_items


def get_lease(
    db: Session, *, current_user: AuthenticatedUser, lease_id: int
) -> LeaseOut:
    _ensure_permission(db, current_user, LEASE_VIEW_CODES)
    item = _get_lease(
        db,
        tenant_id=current_user.tenant_id,
        lease_id=lease_id,
        include_deleted=True,
    )
    return _to_out(item)


def get_lease_detail(
    db: Session, *, current_user: AuthenticatedUser, lease_id: int
) -> LeaseDetailOut:
    _ensure_permission(db, current_user, LEASE_VIEW_CODES)
    lease = _get_lease(
        db,
        tenant_id=current_user.tenant_id,
        lease_id=lease_id,
        include_deleted=True,
    )
    renter = lease.renter
    room = lease.room

    installment_rows = list(
        db.scalars(
            select(Invoice)
            .where(
                Invoice.tenant_id == current_user.tenant_id,
                Invoice.lease_id == lease.id,
                Invoice.deleted_at.is_(None),
            )
            .order_by(
                Invoice.installment_no.asc(),
                Invoice.due_date.asc(),
                Invoice.id.asc(),
            )
        ).all()
    )

    return LeaseDetailOut(
        lease=_to_out(lease),
        renter=(
            LeaseRenterSummaryOut(
                id=renter.id,
                full_name=renter.full_name,
                phone=renter.phone,
                email=renter.email,
            )
            if renter is not None
            else None
        ),
        room=(
            LeaseRoomSummaryOut(
                id=room.id,
                code=room.code,
                branch_id=room.branch_id,
                area_id=room.area_id,
                building_id=room.building_id,
                floor_number=room.floor_number,
                current_status=(
                    room.current_status.value
                    if hasattr(room.current_status, "value")
                    else str(room.current_status)
                ),
            )
            if room is not None
            else None
        ),
        installments=[_to_lease_installment_out(db, row) for row in installment_rows],
    )


def update_lease_installment(
    db: Session,
    *,
    current_user: AuthenticatedUser,
    lease_id: int,
    invoice_id: int,
    payload: LeaseInstallmentUpdateRequest,
) -> LeaseInstallmentOut:
    _ensure_permission(db, current_user, LEASE_UPDATE_CODES)
    _get_lease(
        db,
        tenant_id=current_user.tenant_id,
        lease_id=lease_id,
        include_deleted=False,
    )

    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == current_user.tenant_id,
            Invoice.lease_id == lease_id,
            Invoice.deleted_at.is_(None),
        )
    )
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỳ thanh toán của hợp đồng",
        )

    if payload.due_date is not None:
        invoice.due_date = payload.due_date
    if payload.reminder_at is not None:
        invoice.reminder_at = payload.reminder_at
    if payload.status is not None:
        invoice.status = payload.status
    if payload.content is not None:
        invoice.content = payload.content
    if payload.content_html is not None:
        invoice.content_html = payload.content_html

    if payload.items is not None:
        now_utc = datetime.now(timezone.utc)
        existing_items = list(
            db.scalars(
                select(InvoiceItem).where(
                    InvoiceItem.invoice_id == invoice.id,
                    InvoiceItem.deleted_at.is_(None),
                )
            ).all()
        )
        for item in existing_items:
            item.deleted_at = now_utc
            db.add(item)

        next_total = Decimal("0")
        for row in payload.items:
            amount = Decimal(row.quantity) * Decimal(row.unit_price)
            next_total += amount
            db.add(
                InvoiceItem(
                    tenant_id=current_user.tenant_id,
                    invoice_id=invoice.id,
                    fee_type_id=None,
                    description=row.description.strip(),
                    quantity=Decimal(row.quantity),
                    unit_price=Decimal(row.unit_price),
                    amount=amount,
                )
            )
        invoice.total_amount = next_total
        if invoice.paid_amount > next_total:
            invoice.paid_amount = next_total

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return _to_lease_installment_out(db, invoice)


def create_lease(
    db: Session, *, current_user: AuthenticatedUser, payload: LeaseCreateRequest
) -> LeaseOut:
    _ensure_permission(db, current_user, LEASE_CREATE_CODES)
    room = _get_room(db, tenant_id=current_user.tenant_id, room_id=payload.room_id)
    _get_renter(db, tenant_id=current_user.tenant_id, renter_id=payload.renter_id)
    if room.branch_id != payload.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chi nhánh của hợp đồng không khớp với phòng",
        )

    if room.current_status not in {
        RoomCurrentStatusEnum.VACANT,
        RoomCurrentStatusEnum.DEPOSITED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ tạo hợp đồng cho phòng trống hoặc đã đặt cọc",
        )
    existed_active_lease = db.scalar(
        select(Lease).where(
            Lease.tenant_id == current_user.tenant_id,
            Lease.room_id == payload.room_id,
            Lease.deleted_at.is_(None),
            Lease.status == LeaseStatusEnum.ACTIVE,
        )
    )
    if existed_active_lease is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng này đã có hợp đồng thuê đang hiệu lực",
        )

    base_start = payload.start_date or payload.handover_at
    lease_years = payload.lease_years
    end_date = payload.end_date or _add_years(base_start, lease_years)
    if end_date <= base_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày kết thúc phải lớn hơn ngày bắt đầu",
        )

    security_amount = Decimal(payload.security_deposit_amount)
    security_paid = (
        Decimal(payload.security_deposit_paid_amount)
        if payload.security_deposit_paid_amount is not None
        else security_amount
    )
    if security_paid > security_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tiền cọc đã thanh toán không được lớn hơn tiền cọc",
        )
    if security_paid > 0 and payload.security_deposit_payment_method is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn phương thức đặt cọc",
        )

    item = Lease(
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        room_id=payload.room_id,
        renter_id=payload.renter_id,
        created_by_user_id=current_user.id,
        lease_years=lease_years,
        handover_at=payload.handover_at,
        start_date=base_start,
        end_date=end_date,
        rent_price=payload.rent_price,
        pricing_mode=payload.pricing_mode,
        status=payload.status,
        content=payload.content or "",
        content_html=payload.content_html or "",
        security_deposit_amount=security_amount,
        security_deposit_paid_amount=security_paid,
        security_deposit_payment_method=payload.security_deposit_payment_method,
        security_deposit_paid_at=payload.security_deposit_paid_at
        or (datetime.now(timezone.utc) if security_paid > 0 else None),
        security_deposit_note=payload.security_deposit_note or "",
    )
    db.add(item)
    db.flush()

    if payload.mark_room_as_deposited:
        _apply_room_status_change(
            db,
            room=room,
            new_status=RoomCurrentStatusEnum.DEPOSITED,
            current_user=current_user,
            note=f"Tạo hợp đồng thuê #{item.id if item.id else 'new'}",
        )

    if payload.auto_generate_invoices:
        _generate_invoices_for_lease(
            db,
            current_user=current_user,
            lease=item,
            reminder_days=payload.invoice_reminder_days,
            selected_service_fees=payload.selected_service_fees,
        )

    db.commit()
    db.refresh(item)
    return _to_out(item)


def update_lease(
    db: Session,
    *,
    current_user: AuthenticatedUser,
    lease_id: int,
    payload: LeaseUpdateRequest,
) -> LeaseOut:
    _ensure_permission(db, current_user, LEASE_UPDATE_CODES)
    item = _get_lease(
        db,
        tenant_id=current_user.tenant_id,
        lease_id=lease_id,
        include_deleted=False,
    )

    if payload.lease_years is not None:
        item.lease_years = payload.lease_years
    if payload.handover_at is not None:
        item.handover_at = payload.handover_at
    if payload.start_date is not None:
        item.start_date = payload.start_date
    if payload.end_date is not None:
        item.end_date = payload.end_date
    if item.end_date is not None and item.end_date <= item.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày kết thúc phải lớn hơn ngày bắt đầu",
        )

    if payload.rent_price is not None:
        item.rent_price = payload.rent_price
    if payload.pricing_mode is not None:
        item.pricing_mode = payload.pricing_mode
    if payload.status is not None:
        item.status = payload.status
    if payload.content is not None:
        item.content = payload.content
    if payload.content_html is not None:
        item.content_html = payload.content_html
    if payload.security_deposit_amount is not None:
        item.security_deposit_amount = payload.security_deposit_amount
    if payload.security_deposit_paid_amount is not None:
        item.security_deposit_paid_amount = payload.security_deposit_paid_amount
    if (
        item.security_deposit_paid_amount is not None
        and item.security_deposit_amount is not None
        and item.security_deposit_paid_amount > item.security_deposit_amount
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tiền cọc đã thanh toán không được lớn hơn tiền cọc",
        )
    if payload.security_deposit_payment_method is not None:
        item.security_deposit_payment_method = payload.security_deposit_payment_method
    if payload.security_deposit_paid_at is not None:
        item.security_deposit_paid_at = payload.security_deposit_paid_at
    if payload.security_deposit_note is not None:
        item.security_deposit_note = payload.security_deposit_note

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def soft_delete_lease(
    db: Session, *, current_user: AuthenticatedUser, lease_id: int
) -> LeaseDeleteResult:
    _ensure_permission(db, current_user, LEASE_DELETE_CODES)
    item = _get_lease(
        db,
        tenant_id=current_user.tenant_id,
        lease_id=lease_id,
        include_deleted=False,
    )
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return LeaseDeleteResult(deleted=True)
