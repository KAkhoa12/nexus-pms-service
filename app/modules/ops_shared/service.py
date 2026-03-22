from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.service import get_user_auth_context
from app.modules.core.models import (
    Area,
    Branch,
    Building,
    Deposit,
    DepositStatusEnum,
    FeeType,
    Invoice,
    InvoiceItem,
    Lease,
    Renter,
    RenterMember,
    Room,
    RoomCurrentStatusEnum,
    RoomType,
    User,
)
from app.modules.ops_shared.schemas import (
    AreaCreateRequest,
    AreaOut,
    AreaUpdateRequest,
    BuildingCreateRequest,
    BuildingOut,
    BuildingUpdateRequest,
    DepositCreateRequest,
    DepositOut,
    DepositUpdateRequest,
    InvoiceCreateRequest,
    InvoiceItemOut,
    InvoiceOut,
    InvoiceUpdateRequest,
    RenterCreateRequest,
    RenterMemberCreateRequest,
    RenterMemberOut,
    RenterMemberUpdateRequest,
    RenterOut,
    RenterUpdateRequest,
    RoomCreateRequest,
    RoomOut,
    RoomTypeCreateRequest,
    RoomTypeOut,
    RoomTypeUpdateRequest,
    RoomUpdateRequest,
    SoftDeleteResult,
)

MANAGE_CODES = {"user:mangage", "users:manage"}
AREA_VIEW_CODES = {"areas:view", "area:view"}
AREA_CREATE_CODES = {"areas:create", "area:create"}
AREA_UPDATE_CODES = {"areas:update", "area:update"}
AREA_DELETE_CODES = {"areas:delete", "area:delete"}

BUILDING_VIEW_CODES = {"buildings:view", "building:view"}
BUILDING_CREATE_CODES = {"buildings:create", "building:create"}
BUILDING_UPDATE_CODES = {"buildings:update", "building:update"}
BUILDING_DELETE_CODES = {"buildings:delete", "building:delete"}

ROOM_TYPE_VIEW_CODES = {"room_types:view", "room_type:view"}
ROOM_TYPE_CREATE_CODES = {"room_types:create", "room_type:create"}
ROOM_TYPE_UPDATE_CODES = {"room_types:update", "room_type:update"}
ROOM_TYPE_DELETE_CODES = {"room_types:delete", "room_type:delete"}

ROOM_VIEW_CODES = {"rooms:view", "room:view"}
ROOM_CREATE_CODES = {"rooms:create", "room:create"}
ROOM_UPDATE_CODES = {"rooms:update", "room:update"}
ROOM_DELETE_CODES = {"rooms:delete", "room:delete"}

RENTER_VIEW_CODES = {"renters:view", "renter:view"}
RENTER_CREATE_CODES = {"renters:create", "renter:create"}
RENTER_UPDATE_CODES = {"renters:update", "renter:update"}
RENTER_DELETE_CODES = {"renters:delete", "renter:delete"}

RENTER_MEMBER_VIEW_CODES = {"renter_members:view", "renter_member:view", "renters:view"}
RENTER_MEMBER_CREATE_CODES = {
    "renter_members:create",
    "renter_member:create",
    "renters:update",
}
RENTER_MEMBER_UPDATE_CODES = {
    "renter_members:update",
    "renter_member:update",
    "renters:update",
}
RENTER_MEMBER_DELETE_CODES = {
    "renter_members:delete",
    "renter_member:delete",
    "renters:delete",
}

INVOICE_VIEW_CODES = {"invoices:view", "invoice:view"}
INVOICE_CREATE_CODES = {"invoices:create", "invoice:create"}
INVOICE_UPDATE_CODES = {"invoices:update", "invoice:update"}
INVOICE_DELETE_CODES = {"invoices:delete", "invoice:delete"}

DEPOSIT_VIEW_CODES = {"deposits:view", "deposit:view", "rooms:view", "room:view"}
DEPOSIT_CREATE_CODES = {
    "deposits:create",
    "deposit:create",
    "rooms:update",
    "room:update",
}
DEPOSIT_UPDATE_CODES = {
    "deposits:update",
    "deposit:update",
    "rooms:update",
    "room:update",
}
DEPOSIT_DELETE_CODES = {
    "deposits:delete",
    "deposit:delete",
    "rooms:delete",
    "room:delete",
}

DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20
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


def _apply_deleted_mode(stmt: Select, model: type, deleted_mode: str) -> Select:
    if deleted_mode == "active":
        return stmt.where(model.deleted_at.is_(None))
    if deleted_mode == "trash":
        return stmt.where(model.deleted_at.is_not(None))
    if deleted_mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode chỉ nhận: active, trash hoặc all",
    )


def _commit_or_409(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _normalize_pagination(page: int, items_per_page: int) -> tuple[int, int]:
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
    return page, items_per_page


def _paginate_scalars(
    db: Session, stmt: Select, *, page: int, items_per_page: int
) -> tuple[list, int]:
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    items = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return items, total_items


def _get_branch(db: Session, tenant_id: int, branch_id: int) -> Branch:
    stmt = select(Branch).where(
        Branch.id == branch_id,
        Branch.tenant_id == tenant_id,
        Branch.deleted_at.is_(None),
    )
    branch = db.scalar(stmt)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh"
        )
    return branch


def _get_area(
    db: Session, tenant_id: int, area_id: int, include_deleted: bool = False
) -> Area:
    stmt = select(Area).where(Area.id == area_id, Area.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Area.deleted_at.is_(None))
    area = db.scalar(stmt)
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khu vực"
        )
    return area


def _get_building(
    db: Session, tenant_id: int, building_id: int, include_deleted: bool = False
) -> Building:
    stmt = select(Building).where(
        Building.id == building_id,
        Building.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(Building.deleted_at.is_(None))
    building = db.scalar(stmt)
    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tòa nhà",
        )
    return building


def _get_room_type(
    db: Session, tenant_id: int, room_type_id: int, include_deleted: bool = False
) -> RoomType:
    stmt = select(RoomType).where(
        RoomType.id == room_type_id, RoomType.tenant_id == tenant_id
    )
    if not include_deleted:
        stmt = stmt.where(RoomType.deleted_at.is_(None))
    room_type = db.scalar(stmt)
    if room_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy loại phòng"
        )
    return room_type


def _get_room(
    db: Session, tenant_id: int, room_id: int, include_deleted: bool = False
) -> Room:
    stmt = select(Room).where(Room.id == room_id, Room.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Room.deleted_at.is_(None))
    room = db.scalar(stmt)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng"
        )
    return room


def _get_lease(
    db: Session, tenant_id: int, lease_id: int, include_deleted: bool = False
) -> Lease:
    stmt = select(Lease).where(Lease.id == lease_id, Lease.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Lease.deleted_at.is_(None))
    lease = db.scalar(stmt)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hợp đồng"
        )
    return lease


def _get_renter(
    db: Session, tenant_id: int, renter_id: int, include_deleted: bool = False
) -> Renter:
    stmt = select(Renter).where(Renter.id == renter_id, Renter.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(Renter.deleted_at.is_(None))
    renter = db.scalar(stmt)
    if renter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người thuê"
        )
    return renter


def _get_renter_member(
    db: Session, tenant_id: int, member_id: int, include_deleted: bool = False
) -> RenterMember:
    stmt = select(RenterMember).where(
        RenterMember.id == member_id,
        RenterMember.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(RenterMember.deleted_at.is_(None))
    member = db.scalar(stmt)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người đi cùng",
        )
    return member


def _get_invoice(
    db: Session, tenant_id: int, invoice_id: int, include_deleted: bool = False
) -> Invoice:
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(Invoice.deleted_at.is_(None))
    invoice = db.scalar(stmt)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hóa đơn"
        )
    return invoice


def _get_deposit(
    db: Session, tenant_id: int, deposit_id: int, include_deleted: bool = False
) -> Deposit:
    stmt = select(Deposit).where(
        Deposit.id == deposit_id, Deposit.tenant_id == tenant_id
    )
    if not include_deleted:
        stmt = stmt.where(Deposit.deleted_at.is_(None))
    deposit = db.scalar(stmt)
    if deposit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiếu đặt cọc",
        )
    return deposit


def _require_soft_deleted(item: object, name: str) -> None:
    deleted_at = getattr(item, "deleted_at", None)
    if deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} phải được xóa mềm trước khi xóa vĩnh viễn",
        )


def _get_fee_type(db: Session, tenant_id: int, fee_type_id: int) -> FeeType:
    stmt = select(FeeType).where(
        FeeType.id == fee_type_id,
        FeeType.tenant_id == tenant_id,
        FeeType.deleted_at.is_(None),
    )
    fee_type = db.scalar(stmt)
    if fee_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy loại phí"
        )
    return fee_type


def _build_area_out(area: Area) -> AreaOut:
    return AreaOut(
        id=area.id,
        tenant_id=area.tenant_id,
        branch_id=area.branch_id,
        name=area.name,
        address=area.address,
        deleted_at=area.deleted_at,
    )


def _area_name_exists_in_branch(
    db: Session,
    *,
    tenant_id: int,
    branch_id: int,
    name: str,
    exclude_area_id: int | None = None,
) -> bool:
    normalized_name = name.strip().lower()
    stmt = select(Area.id).where(
        Area.tenant_id == tenant_id,
        Area.branch_id == branch_id,
        func.lower(func.trim(Area.name)) == normalized_name,
    )
    if exclude_area_id is not None:
        stmt = stmt.where(Area.id != exclude_area_id)
    return db.scalar(stmt) is not None


def _build_building_out(building: Building) -> BuildingOut:
    return BuildingOut(
        id=building.id,
        tenant_id=building.tenant_id,
        area_id=building.area_id,
        name=building.name,
        total_floors=building.total_floors,
        deleted_at=building.deleted_at,
    )


def _build_room_type_out(room_type: RoomType) -> RoomTypeOut:
    return RoomTypeOut(
        id=room_type.id,
        tenant_id=room_type.tenant_id,
        name=room_type.name,
        base_price=room_type.base_price,
        pricing_mode=room_type.pricing_mode,
        default_occupancy=room_type.default_occupancy,
        max_occupancy=room_type.max_occupancy,
        deleted_at=room_type.deleted_at,
    )


def _build_room_out(room: Room) -> RoomOut:
    return RoomOut(
        id=room.id,
        tenant_id=room.tenant_id,
        branch_id=room.branch_id,
        area_id=room.area_id,
        building_id=room.building_id,
        room_type_id=room.room_type_id,
        floor_number=room.floor_number,
        code=room.code,
        current_status=room.current_status,
        current_price=room.current_price,
        deleted_at=room.deleted_at,
    )


def _build_renter_out(renter: Renter) -> RenterOut:
    return RenterOut(
        id=renter.id,
        tenant_id=renter.tenant_id,
        full_name=renter.full_name,
        phone=renter.phone,
        identity_type=renter.identity_type,
        id_number=renter.id_number,
        email=renter.email,
        avatar_url=renter.avatar_url,
        date_of_birth=renter.date_of_birth,
        address=renter.address,
        deleted_at=renter.deleted_at,
    )


def _build_renter_member_out(member: RenterMember) -> RenterMemberOut:
    return RenterMemberOut(
        id=member.id,
        tenant_id=member.tenant_id,
        renter_id=member.renter_id,
        full_name=member.full_name,
        phone=member.phone,
        identity_type=member.identity_type,
        id_number=member.id_number,
        email=member.email,
        avatar_url=member.avatar_url,
        date_of_birth=member.date_of_birth,
        address=member.address,
        relation=member.relation,
        deleted_at=member.deleted_at,
    )


def _build_invoice_out(db: Session, invoice: Invoice) -> InvoiceOut:
    item_stmt = (
        select(InvoiceItem)
        .where(
            InvoiceItem.invoice_id == invoice.id,
            InvoiceItem.deleted_at.is_(None),
        )
        .order_by(InvoiceItem.id.asc())
    )
    items = list(db.scalars(item_stmt).all())
    return InvoiceOut(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        branch_id=invoice.branch_id,
        room_id=invoice.room_id,
        renter_id=invoice.renter_id,
        lease_id=invoice.lease_id,
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
        deleted_at=invoice.deleted_at,
        items=[
            InvoiceItemOut(
                id=item.id,
                tenant_id=item.tenant_id,
                invoice_id=item.invoice_id,
                fee_type_id=item.fee_type_id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
                deleted_at=item.deleted_at,
            )
            for item in items
        ],
    )


def _build_deposit_out(deposit: Deposit) -> DepositOut:
    room = deposit.room
    lease = deposit.lease
    return DepositOut(
        id=deposit.id,
        tenant_id=deposit.tenant_id,
        lease_id=deposit.lease_id,
        room_id=deposit.room_id,
        renter_id=deposit.renter_id
        if deposit.renter_id is not None
        else (lease.renter_id if lease is not None else None),
        branch_id=room.branch_id,
        amount=deposit.amount,
        method=deposit.method,
        status=deposit.status,
        paid_at=deposit.paid_at,
        content_html=deposit.content_html,
        deleted_at=deposit.deleted_at,
    )


def list_room_types(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
) -> tuple[list[RoomTypeOut], int]:
    _ensure_permission(db, current_user, ROOM_TYPE_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(RoomType).where(RoomType.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, RoomType, deleted_mode).order_by(
        RoomType.id.desc()
    )
    room_types, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_room_type_out(item) for item in room_types], total_items


def create_room_type(
    db: Session, current_user: User, payload: RoomTypeCreateRequest
) -> RoomTypeOut:
    _ensure_permission(db, current_user, ROOM_TYPE_CREATE_CODES)
    item = RoomType(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        base_price=payload.base_price,
        pricing_mode=payload.pricing_mode,
        default_occupancy=payload.default_occupancy,
        max_occupancy=payload.max_occupancy,
    )
    db.add(item)
    db.flush()
    _commit_or_409(db, "Room type already exists in tenant")
    db.refresh(item)
    return _build_room_type_out(item)


def update_room_type(
    db: Session,
    current_user: User,
    *,
    room_type_id: int,
    payload: RoomTypeUpdateRequest,
) -> RoomTypeOut:
    _ensure_permission(db, current_user, ROOM_TYPE_UPDATE_CODES)
    item = _get_room_type(
        db, current_user.tenant_id, room_type_id, include_deleted=False
    )
    if payload.name is not None:
        item.name = payload.name
    if payload.base_price is not None:
        item.base_price = payload.base_price
    if payload.pricing_mode is not None:
        item.pricing_mode = payload.pricing_mode
    if payload.default_occupancy is not None:
        item.default_occupancy = payload.default_occupancy
    if payload.max_occupancy is not None:
        item.max_occupancy = payload.max_occupancy
    db.add(item)
    _commit_or_409(db, "Room type update conflicts with existing data")
    db.refresh(item)
    return _build_room_type_out(item)


def soft_delete_room_type(
    db: Session, current_user: User, *, room_type_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, ROOM_TYPE_DELETE_CODES)
    item = _get_room_type(
        db, current_user.tenant_id, room_type_id, include_deleted=False
    )
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_room_type(
    db: Session, current_user: User, *, room_type_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, ROOM_TYPE_DELETE_CODES)
    item = _get_room_type(
        db, current_user.tenant_id, room_type_id, include_deleted=True
    )
    _require_soft_deleted(item, "Loại phòng")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_areas(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
    branch_id: int | None = None,
    search_key: str | None = None,
) -> tuple[list[AreaOut], int]:
    _ensure_permission(db, current_user, AREA_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = (
        select(Area)
        .join(Branch, Branch.id == Area.branch_id)
        .where(
            Area.tenant_id == current_user.tenant_id,
            Branch.tenant_id == current_user.tenant_id,
        )
    )
    if branch_id is not None:
        stmt = stmt.where(Area.branch_id == branch_id)
    if search_key:
        keyword = search_key.strip().lower()
        if keyword:
            like_pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    func.lower(Area.name).like(like_pattern),
                    func.lower(func.coalesce(Area.address, "")).like(like_pattern),
                    func.lower(Branch.name).like(like_pattern),
                )
            )
    stmt = _apply_deleted_mode(stmt, Area, deleted_mode).order_by(Area.id.desc())
    areas, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_area_out(item) for item in areas], total_items


def create_area(db: Session, current_user: User, payload: AreaCreateRequest) -> AreaOut:
    _ensure_permission(db, current_user, AREA_CREATE_CODES)
    _get_branch(db, current_user.tenant_id, payload.branch_id)
    normalized_name = payload.name.strip()
    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên khu vực không được để trống",
        )
    if _area_name_exists_in_branch(
        db,
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        name=normalized_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên khu vực đã tồn tại trong chi nhánh này",
        )
    item = Area(
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        name=normalized_name,
        address=payload.address.strip() if payload.address else None,
    )
    db.add(item)
    db.flush()
    _commit_or_409(db, "Khu vực đã tồn tại trong chi nhánh")
    db.refresh(item)
    return _build_area_out(item)


def update_area(
    db: Session, current_user: User, *, area_id: int, payload: AreaUpdateRequest
) -> AreaOut:
    _ensure_permission(db, current_user, AREA_UPDATE_CODES)
    item = _get_area(db, current_user.tenant_id, area_id, include_deleted=False)
    next_branch_id = (
        payload.branch_id if payload.branch_id is not None else item.branch_id
    )
    if payload.branch_id is not None:
        _get_branch(db, current_user.tenant_id, payload.branch_id)
        item.branch_id = payload.branch_id
    if payload.name is not None:
        normalized_name = payload.name.strip()
        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên khu vực không được để trống",
            )
        item.name = normalized_name
    if payload.address is not None:
        item.address = payload.address.strip() or None
    if payload.name is not None or payload.branch_id is not None:
        if _area_name_exists_in_branch(
            db,
            tenant_id=current_user.tenant_id,
            branch_id=next_branch_id,
            name=item.name,
            exclude_area_id=item.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tên khu vực đã tồn tại trong chi nhánh này",
            )
    db.add(item)
    _commit_or_409(db, "Dữ liệu cập nhật khu vực bị trùng")
    db.refresh(item)
    return _build_area_out(item)


def soft_delete_area(
    db: Session, current_user: User, *, area_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, AREA_DELETE_CODES)
    item = _get_area(db, current_user.tenant_id, area_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_area(
    db: Session, current_user: User, *, area_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, AREA_DELETE_CODES)
    item = _get_area(db, current_user.tenant_id, area_id, include_deleted=True)
    _require_soft_deleted(item, "Khu vực")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_buildings(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
) -> tuple[list[BuildingOut], int]:
    _ensure_permission(db, current_user, BUILDING_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(Building).where(Building.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, Building, deleted_mode).order_by(
        Building.id.desc()
    )
    buildings, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_building_out(item) for item in buildings], total_items


def create_building(
    db: Session, current_user: User, payload: BuildingCreateRequest
) -> BuildingOut:
    _ensure_permission(db, current_user, BUILDING_CREATE_CODES)
    _get_area(db, current_user.tenant_id, payload.area_id, include_deleted=False)
    item = Building(
        tenant_id=current_user.tenant_id,
        area_id=payload.area_id,
        name=payload.name,
        total_floors=payload.total_floors,
    )
    db.add(item)
    db.flush()
    _commit_or_409(db, "Building already exists in area")
    db.refresh(item)
    return _build_building_out(item)


def update_building(
    db: Session, current_user: User, *, building_id: int, payload: BuildingUpdateRequest
) -> BuildingOut:
    _ensure_permission(db, current_user, BUILDING_UPDATE_CODES)
    item = _get_building(db, current_user.tenant_id, building_id, include_deleted=False)
    if payload.area_id is not None:
        _get_area(db, current_user.tenant_id, payload.area_id, include_deleted=False)
        item.area_id = payload.area_id
    if payload.name is not None:
        item.name = payload.name
    if payload.total_floors is not None:
        item.total_floors = payload.total_floors
    db.add(item)
    _commit_or_409(db, "Building update conflicts with existing data")
    db.refresh(item)
    return _build_building_out(item)


def soft_delete_building(
    db: Session, current_user: User, *, building_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, BUILDING_DELETE_CODES)
    item = _get_building(db, current_user.tenant_id, building_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_building(
    db: Session, current_user: User, *, building_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, BUILDING_DELETE_CODES)
    item = _get_building(db, current_user.tenant_id, building_id, include_deleted=True)
    _require_soft_deleted(item, "Tòa nhà")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_rooms(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
    search_key: str | None = None,
) -> tuple[list[RoomOut], int]:
    _ensure_permission(db, current_user, ROOM_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(Room).where(Room.tenant_id == current_user.tenant_id)
    if search_key:
        keyword = search_key.strip().lower()
        if keyword:
            like_pattern = f"%{keyword}%"
            stmt = stmt.where(func.lower(Room.code).like(like_pattern))
    stmt = _apply_deleted_mode(stmt, Room, deleted_mode).order_by(Room.id.desc())
    rooms, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_room_out(item) for item in rooms], total_items


def create_room(db: Session, current_user: User, payload: RoomCreateRequest) -> RoomOut:
    _ensure_permission(db, current_user, ROOM_CREATE_CODES)
    _get_branch(db, current_user.tenant_id, payload.branch_id)
    area = _get_area(db, current_user.tenant_id, payload.area_id, include_deleted=False)
    building = _get_building(
        db, current_user.tenant_id, payload.building_id, include_deleted=False
    )
    _get_room_type(
        db, current_user.tenant_id, payload.room_type_id, include_deleted=False
    )
    if area.branch_id != payload.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khu vực không thuộc chi nhánh đã chọn",
        )
    if building.area_id != payload.area_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tòa nhà không thuộc khu vực đã chọn",
        )
    if payload.floor_number > building.total_floors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tầng vượt quá tổng số tầng của tòa nhà",
        )

    item = Room(
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        area_id=payload.area_id,
        building_id=payload.building_id,
        room_type_id=payload.room_type_id,
        floor_number=payload.floor_number,
        code=payload.code,
        current_status=payload.current_status,
        current_price=payload.current_price,
    )
    db.add(item)
    db.flush()
    _commit_or_409(db, "Mã phòng đã tồn tại trong tenant")
    db.refresh(item)
    return _build_room_out(item)


def update_room(
    db: Session, current_user: User, *, room_id: int, payload: RoomUpdateRequest
) -> RoomOut:
    _ensure_permission(db, current_user, ROOM_UPDATE_CODES)
    item = _get_room(db, current_user.tenant_id, room_id, include_deleted=False)

    next_branch_id = (
        payload.branch_id if payload.branch_id is not None else item.branch_id
    )
    next_area_id = payload.area_id if payload.area_id is not None else item.area_id
    next_building_id = (
        payload.building_id if payload.building_id is not None else item.building_id
    )
    next_floor_number = (
        payload.floor_number if payload.floor_number is not None else item.floor_number
    )
    if payload.branch_id is not None:
        _get_branch(db, current_user.tenant_id, payload.branch_id)
    if payload.area_id is not None:
        _get_area(db, current_user.tenant_id, payload.area_id, include_deleted=False)
    if payload.building_id is not None:
        _get_building(
            db, current_user.tenant_id, payload.building_id, include_deleted=False
        )
    if payload.room_type_id is not None:
        _get_room_type(
            db, current_user.tenant_id, payload.room_type_id, include_deleted=False
        )
    area = _get_area(db, current_user.tenant_id, next_area_id, include_deleted=False)
    building = _get_building(
        db, current_user.tenant_id, next_building_id, include_deleted=False
    )
    if area.branch_id != next_branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khu vực không thuộc chi nhánh đã chọn",
        )
    if building.area_id != next_area_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tòa nhà không thuộc khu vực đã chọn",
        )
    if next_floor_number > building.total_floors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tầng vượt quá tổng số tầng của tòa nhà",
        )

    if payload.branch_id is not None:
        item.branch_id = payload.branch_id
    if payload.area_id is not None:
        item.area_id = payload.area_id
    if payload.building_id is not None:
        item.building_id = payload.building_id
    if payload.room_type_id is not None:
        item.room_type_id = payload.room_type_id
    if payload.floor_number is not None:
        item.floor_number = payload.floor_number
    if payload.code is not None:
        item.code = payload.code
    if payload.current_status is not None:
        item.current_status = payload.current_status
    if payload.current_price is not None:
        item.current_price = payload.current_price

    db.add(item)
    _commit_or_409(db, "Dữ liệu cập nhật phòng bị trùng")
    db.refresh(item)
    return _build_room_out(item)


def soft_delete_room(
    db: Session, current_user: User, *, room_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, ROOM_DELETE_CODES)
    item = _get_room(db, current_user.tenant_id, room_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_room(
    db: Session, current_user: User, *, room_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, ROOM_DELETE_CODES)
    item = _get_room(db, current_user.tenant_id, room_id, include_deleted=True)
    _require_soft_deleted(item, "Phòng")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_renters(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
) -> tuple[list[RenterOut], int]:
    _ensure_permission(db, current_user, RENTER_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(Renter).where(Renter.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, Renter, deleted_mode).order_by(Renter.id.desc())
    renters, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_renter_out(item) for item in renters], total_items


def create_renter(
    db: Session, current_user: User, payload: RenterCreateRequest
) -> RenterOut:
    _ensure_permission(db, current_user, RENTER_CREATE_CODES)
    item = Renter(
        tenant_id=current_user.tenant_id,
        full_name=payload.full_name,
        phone=payload.phone,
        identity_type=payload.identity_type,
        id_number=payload.id_number,
        email=payload.email,
        avatar_url=payload.avatar_url,
        date_of_birth=payload.date_of_birth,
        address=payload.address,
    )
    db.add(item)
    db.flush()
    db.commit()
    db.refresh(item)
    return _build_renter_out(item)


def update_renter(
    db: Session, current_user: User, *, renter_id: int, payload: RenterUpdateRequest
) -> RenterOut:
    _ensure_permission(db, current_user, RENTER_UPDATE_CODES)
    item = _get_renter(db, current_user.tenant_id, renter_id, include_deleted=False)
    if payload.full_name is not None:
        item.full_name = payload.full_name
    if payload.phone is not None:
        item.phone = payload.phone
    if payload.identity_type is not None:
        item.identity_type = payload.identity_type
    if payload.id_number is not None:
        item.id_number = payload.id_number
    if payload.email is not None:
        item.email = payload.email
    if payload.avatar_url is not None:
        item.avatar_url = payload.avatar_url
    if payload.date_of_birth is not None:
        item.date_of_birth = payload.date_of_birth
    if payload.address is not None:
        item.address = payload.address
    db.add(item)
    db.commit()
    db.refresh(item)
    return _build_renter_out(item)


def soft_delete_renter(
    db: Session, current_user: User, *, renter_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, RENTER_DELETE_CODES)
    item = _get_renter(db, current_user.tenant_id, renter_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_renter(
    db: Session, current_user: User, *, renter_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, RENTER_DELETE_CODES)
    item = _get_renter(db, current_user.tenant_id, renter_id, include_deleted=True)
    _require_soft_deleted(item, "Người thuê")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_renter_members(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
) -> tuple[list[RenterMemberOut], int]:
    _ensure_permission(db, current_user, RENTER_MEMBER_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(RenterMember).where(RenterMember.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, RenterMember, deleted_mode).order_by(
        RenterMember.id.desc()
    )
    members, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_renter_member_out(item) for item in members], total_items


def create_renter_member(
    db: Session, current_user: User, payload: RenterMemberCreateRequest
) -> RenterMemberOut:
    _ensure_permission(db, current_user, RENTER_MEMBER_CREATE_CODES)
    _get_renter(db, current_user.tenant_id, payload.renter_id, include_deleted=False)
    item = RenterMember(
        tenant_id=current_user.tenant_id,
        renter_id=payload.renter_id,
        full_name=payload.full_name,
        phone=payload.phone,
        identity_type=payload.identity_type,
        id_number=payload.id_number,
        email=payload.email,
        avatar_url=payload.avatar_url,
        date_of_birth=payload.date_of_birth,
        address=payload.address,
        relation=payload.relation,
    )
    db.add(item)
    db.flush()
    db.commit()
    db.refresh(item)
    return _build_renter_member_out(item)


def update_renter_member(
    db: Session,
    current_user: User,
    *,
    member_id: int,
    payload: RenterMemberUpdateRequest,
) -> RenterMemberOut:
    _ensure_permission(db, current_user, RENTER_MEMBER_UPDATE_CODES)
    item = _get_renter_member(
        db, current_user.tenant_id, member_id, include_deleted=False
    )

    if payload.renter_id is not None:
        _get_renter(
            db, current_user.tenant_id, payload.renter_id, include_deleted=False
        )
        item.renter_id = payload.renter_id
    if payload.full_name is not None:
        item.full_name = payload.full_name
    if payload.phone is not None:
        item.phone = payload.phone
    if payload.identity_type is not None:
        item.identity_type = payload.identity_type
    if payload.id_number is not None:
        item.id_number = payload.id_number
    if payload.email is not None:
        item.email = payload.email
    if payload.avatar_url is not None:
        item.avatar_url = payload.avatar_url
    if payload.date_of_birth is not None:
        item.date_of_birth = payload.date_of_birth
    if payload.address is not None:
        item.address = payload.address
    if payload.relation is not None:
        item.relation = payload.relation

    db.add(item)
    db.commit()
    db.refresh(item)
    return _build_renter_member_out(item)


def soft_delete_renter_member(
    db: Session, current_user: User, *, member_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, RENTER_MEMBER_DELETE_CODES)
    item = _get_renter_member(
        db, current_user.tenant_id, member_id, include_deleted=False
    )
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_renter_member(
    db: Session, current_user: User, *, member_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, RENTER_MEMBER_DELETE_CODES)
    item = _get_renter_member(
        db, current_user.tenant_id, member_id, include_deleted=True
    )
    _require_soft_deleted(item, "Người đi cùng")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_invoices(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
) -> tuple[list[InvoiceOut], int]:
    _ensure_permission(db, current_user, INVOICE_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(Invoice).where(Invoice.tenant_id == current_user.tenant_id)
    stmt = _apply_deleted_mode(stmt, Invoice, deleted_mode).order_by(Invoice.id.desc())
    invoices, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_invoice_out(db, item) for item in invoices], total_items


def create_invoice(
    db: Session, current_user: User, payload: InvoiceCreateRequest
) -> InvoiceOut:
    _ensure_permission(db, current_user, INVOICE_CREATE_CODES)
    _get_branch(db, current_user.tenant_id, payload.branch_id)
    room = _get_room(db, current_user.tenant_id, payload.room_id, include_deleted=False)
    renter = _get_renter(
        db, current_user.tenant_id, payload.renter_id, include_deleted=False
    )
    lease = (
        _get_lease(db, current_user.tenant_id, payload.lease_id, include_deleted=False)
        if payload.lease_id is not None
        else None
    )
    if room.branch_id != payload.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phòng không thuộc chi nhánh đã chọn",
        )
    if lease is not None:
        if lease.room_id != room.id or lease.renter_id != renter.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hợp đồng không khớp với phòng/người thuê của hóa đơn",
            )
    if payload.items:
        for item in payload.items:
            if item.fee_type_id is not None:
                _get_fee_type(db, current_user.tenant_id, item.fee_type_id)

    invoice = Invoice(
        tenant_id=current_user.tenant_id,
        branch_id=payload.branch_id,
        room_id=room.id,
        renter_id=renter.id,
        lease_id=payload.lease_id,
        installment_no=payload.installment_no,
        installment_total=payload.installment_total,
        period_month=payload.period_month,
        due_date=payload.due_date,
        reminder_at=payload.reminder_at,
        total_amount=payload.total_amount,
        paid_amount=payload.paid_amount,
        status=payload.status,
        content=payload.content,
        content_html=payload.content_html,
    )
    db.add(invoice)
    db.flush()

    for item in payload.items:
        db.add(
            InvoiceItem(
                tenant_id=current_user.tenant_id,
                invoice_id=invoice.id,
                fee_type_id=item.fee_type_id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )
        )

    db.flush()
    _commit_or_409(db, "Invoice already exists for this room and period")
    db.refresh(invoice)
    return _build_invoice_out(db, invoice)


def update_invoice(
    db: Session, current_user: User, *, invoice_id: int, payload: InvoiceUpdateRequest
) -> InvoiceOut:
    _ensure_permission(db, current_user, INVOICE_UPDATE_CODES)
    invoice = _get_invoice(
        db, current_user.tenant_id, invoice_id, include_deleted=False
    )

    next_branch_id = (
        payload.branch_id if payload.branch_id is not None else invoice.branch_id
    )
    next_room_id = payload.room_id if payload.room_id is not None else invoice.room_id
    next_renter_id = (
        payload.renter_id if payload.renter_id is not None else invoice.renter_id
    )
    next_lease_id = (
        payload.lease_id if payload.lease_id is not None else invoice.lease_id
    )

    _get_branch(db, current_user.tenant_id, next_branch_id)
    room = _get_room(db, current_user.tenant_id, next_room_id, include_deleted=False)
    renter = _get_renter(
        db, current_user.tenant_id, next_renter_id, include_deleted=False
    )
    lease = (
        _get_lease(db, current_user.tenant_id, next_lease_id, include_deleted=False)
        if next_lease_id is not None
        else None
    )
    if room.branch_id != next_branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phòng không thuộc chi nhánh đã chọn",
        )
    if lease is not None:
        if lease.room_id != room.id or lease.renter_id != renter.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hợp đồng không khớp với phòng/người thuê của hóa đơn",
            )

    if payload.branch_id is not None:
        invoice.branch_id = payload.branch_id
    if payload.room_id is not None:
        invoice.room_id = payload.room_id
    if payload.renter_id is not None:
        invoice.renter_id = payload.renter_id
    if payload.lease_id is not None:
        invoice.lease_id = payload.lease_id
    if payload.installment_no is not None:
        invoice.installment_no = payload.installment_no
    if payload.installment_total is not None:
        invoice.installment_total = payload.installment_total
    if payload.period_month is not None:
        invoice.period_month = payload.period_month
    if payload.due_date is not None:
        invoice.due_date = payload.due_date
    if payload.reminder_at is not None:
        invoice.reminder_at = payload.reminder_at
    if payload.total_amount is not None:
        invoice.total_amount = payload.total_amount
    if payload.paid_amount is not None:
        invoice.paid_amount = payload.paid_amount
    if payload.status is not None:
        invoice.status = payload.status
    if payload.content is not None:
        invoice.content = payload.content
    if payload.content_html is not None:
        invoice.content_html = payload.content_html

    if payload.items is not None:
        if payload.items:
            for item in payload.items:
                if item.fee_type_id is not None:
                    _get_fee_type(db, current_user.tenant_id, item.fee_type_id)
        now = datetime.now(timezone.utc)
        active_items_stmt = select(InvoiceItem).where(
            InvoiceItem.invoice_id == invoice.id,
            InvoiceItem.deleted_at.is_(None),
        )
        active_items = list(db.scalars(active_items_stmt).all())
        for current_item in active_items:
            current_item.deleted_at = now
            db.add(current_item)
        for item in payload.items:
            db.add(
                InvoiceItem(
                    tenant_id=current_user.tenant_id,
                    invoice_id=invoice.id,
                    fee_type_id=item.fee_type_id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                )
            )

    db.add(invoice)
    db.flush()
    _commit_or_409(db, "Invoice update conflicts with existing data")
    db.refresh(invoice)
    return _build_invoice_out(db, invoice)


def soft_delete_invoice(
    db: Session, current_user: User, *, invoice_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, INVOICE_DELETE_CODES)
    invoice = _get_invoice(
        db, current_user.tenant_id, invoice_id, include_deleted=False
    )
    invoice.deleted_at = datetime.now(timezone.utc)
    db.add(invoice)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_invoice(
    db: Session, current_user: User, *, invoice_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, INVOICE_DELETE_CODES)
    invoice = _get_invoice(db, current_user.tenant_id, invoice_id, include_deleted=True)
    _require_soft_deleted(invoice, "Hóa đơn")
    db.delete(invoice)
    db.commit()
    return SoftDeleteResult(deleted=True)


def list_deposits(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int = DEFAULT_PAGE,
    items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
    room_id: int | None = None,
    lease_id: int | None = None,
) -> tuple[list[DepositOut], int]:
    _ensure_permission(db, current_user, DEPOSIT_VIEW_CODES)
    page, items_per_page = _normalize_pagination(page, items_per_page)
    stmt = select(Deposit).where(Deposit.tenant_id == current_user.tenant_id)
    if room_id is not None:
        stmt = stmt.where(Deposit.room_id == room_id)
    if lease_id is not None:
        stmt = stmt.where(Deposit.lease_id == lease_id)
    stmt = _apply_deleted_mode(stmt, Deposit, deleted_mode).order_by(Deposit.id.desc())
    deposits, total_items = _paginate_scalars(
        db, stmt, page=page, items_per_page=items_per_page
    )
    return [_build_deposit_out(item) for item in deposits], total_items


def create_deposit(
    db: Session, current_user: User, payload: DepositCreateRequest
) -> DepositOut:
    _ensure_permission(db, current_user, DEPOSIT_CREATE_CODES)
    room = _get_room(db, current_user.tenant_id, payload.room_id, include_deleted=False)
    if payload.renter_id is not None:
        _get_renter(
            db, current_user.tenant_id, payload.renter_id, include_deleted=False
        )

    lease_id: int | None = None
    if payload.lease_id is not None:
        lease = _get_lease(
            db, current_user.tenant_id, payload.lease_id, include_deleted=False
        )
        if lease.room_id != payload.room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hợp đồng không thuộc phòng đã chọn",
            )
        lease_id = lease.id

    item = Deposit(
        tenant_id=current_user.tenant_id,
        room_id=payload.room_id,
        renter_id=payload.renter_id,
        lease_id=lease_id,
        amount=payload.amount,
        method=payload.method,
        status=payload.status,
        paid_at=payload.paid_at or datetime.now(timezone.utc),
        content_html=payload.content_html,
    )
    db.add(item)
    if payload.status == DepositStatusEnum.HELD:
        room.current_status = RoomCurrentStatusEnum.DEPOSITED
        db.add(room)
    db.flush()
    _commit_or_409(db, "Dữ liệu đặt cọc bị trùng")
    db.refresh(item)
    return _build_deposit_out(item)


def update_deposit(
    db: Session,
    current_user: User,
    *,
    deposit_id: int,
    payload: DepositUpdateRequest,
) -> DepositOut:
    _ensure_permission(db, current_user, DEPOSIT_UPDATE_CODES)
    item = _get_deposit(db, current_user.tenant_id, deposit_id, include_deleted=False)
    if payload.renter_id is not None:
        _get_renter(
            db, current_user.tenant_id, payload.renter_id, include_deleted=False
        )
        item.renter_id = payload.renter_id
    if payload.lease_id is not None:
        lease = _get_lease(
            db, current_user.tenant_id, payload.lease_id, include_deleted=False
        )
        if lease.room_id != item.room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hợp đồng không thuộc phòng của phiếu đặt cọc",
            )
        item.lease_id = lease.id
    if payload.amount is not None:
        item.amount = payload.amount
    if payload.method is not None:
        item.method = payload.method
    if payload.status is not None:
        item.status = payload.status
    if payload.paid_at is not None:
        item.paid_at = payload.paid_at
    if payload.content_html is not None:
        item.content_html = payload.content_html
    db.add(item)
    _commit_or_409(db, "Dữ liệu cập nhật đặt cọc bị trùng")
    db.refresh(item)
    return _build_deposit_out(item)


def get_deposit(db: Session, current_user: User, *, deposit_id: int) -> DepositOut:
    _ensure_permission(db, current_user, DEPOSIT_VIEW_CODES)
    item = _get_deposit(db, current_user.tenant_id, deposit_id, include_deleted=False)
    return _build_deposit_out(item)


def soft_delete_deposit(
    db: Session, current_user: User, *, deposit_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, DEPOSIT_DELETE_CODES)
    item = _get_deposit(db, current_user.tenant_id, deposit_id, include_deleted=False)
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return SoftDeleteResult(deleted=True)


def hard_delete_deposit(
    db: Session, current_user: User, *, deposit_id: int
) -> SoftDeleteResult:
    _ensure_permission(db, current_user, DEPOSIT_DELETE_CODES)
    item = _get_deposit(db, current_user.tenant_id, deposit_id, include_deleted=True)
    _require_soft_deleted(item, "Phiếu đặt cọc")
    db.delete(item)
    db.commit()
    return SoftDeleteResult(deleted=True)
