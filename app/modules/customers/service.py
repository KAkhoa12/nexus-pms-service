from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import (
    case,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Session

from app.modules.auth.service import AuthContext, get_user_auth_context
from app.modules.core.models import Lease, LeaseStatusEnum, Renter, RenterMember
from app.modules.customers.schemas import (
    CustomerCompanionCreateRequest,
    CustomerCreateRequest,
    CustomerDetailOut,
    CustomerLeaseState,
    CustomerListItemOut,
    CustomerPrimaryRenterOut,
    CustomerType,
    CustomerUploadOut,
)
from app.modules.ops_shared.schemas import (
    RenterCreateRequest,
    RenterMemberCreateRequest,
)
from app.modules.ops_shared.service import (
    create_renter as _create_renter,
)
from app.modules.ops_shared.service import (
    create_renter_member as _create_renter_member,
)
from app.services.minio_storage import (
    MinioStorageError,
    get_chat_object_stream,
    upload_chat_bytes,
)
from app.utils.naming import random_name_with_timestamp

MANAGE_CODES = {"user:mangage", "users:manage"}
RENTER_VIEW_CODES = {"renters:view", "renter:view"}
RENTER_CREATE_CODES = {"renters:create", "renter:create"}
RENTER_MEMBER_VIEW_CODES = {"renter_members:view", "renter_member:view", "renters:view"}
RENTER_MEMBER_CREATE_CODES = {
    "renter_members:create",
    "renter_member:create",
    "renters:update",
}

MAX_ITEMS_PER_PAGE = 200
CUSTOMER_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
CUSTOMER_OBJECT_PREFIX = "customers"
ALLOWED_CUSTOMER_TYPE_FILTERS = {"all", "renter", "member"}
ALLOWED_RENT_STATE_FILTERS = {"all", "not_rented", "active", "past"}


def _ensure_pagination(page: int, items_per_page: int) -> tuple[int, int]:
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


def _ensure_deleted_mode(value: str) -> str:
    normalized = (value or "active").strip().lower()
    if normalized in {"active", "trash", "all"}:
        return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode chỉ nhận: active, trash hoặc all",
    )


def _ensure_customer_type_filter(value: str) -> str:
    normalized = (value or "all").strip().lower()
    if normalized in ALLOWED_CUSTOMER_TYPE_FILTERS:
        return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="customer_type chỉ nhận: all, renter hoặc member",
    )


def _ensure_rent_state_filter(value: str) -> str:
    normalized = (value or "all").strip().lower()
    if normalized in ALLOWED_RENT_STATE_FILTERS:
        return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="rent_state chỉ nhận: all, not_rented, active hoặc past",
    )


def _has_any_permission(context: AuthContext, codes: set[str]) -> bool:
    if context.has_full_access:
        return True
    if context.permissions.intersection(MANAGE_CODES):
        return True
    return bool(context.permissions.intersection(codes))


def _ensure_permission(context: AuthContext, codes: set[str]) -> None:
    if _has_any_permission(context, codes):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền thực hiện thao tác này",
    )


def _build_customer_item_from_renter(
    item: Renter, *, lease_state: CustomerLeaseState
) -> CustomerListItemOut:
    return CustomerListItemOut(
        id=item.id,
        customer_type="renter",
        full_name=item.full_name,
        phone=item.phone,
        email=item.email,
        identity_type=item.identity_type,
        id_number=item.id_number,
        avatar_url=item.avatar_url,
        date_of_birth=item.date_of_birth,
        address=item.address,
        relation=None,
        renter_id=None,
        primary_renter_name=None,
        lease_state=lease_state,
        deleted_at=item.deleted_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_customer_item_from_member(
    item: RenterMember,
    primary_renter_name: str | None,
    *,
    lease_state: CustomerLeaseState,
) -> CustomerListItemOut:
    return CustomerListItemOut(
        id=item.id,
        customer_type="member",
        full_name=item.full_name,
        phone=item.phone,
        email=item.email,
        identity_type=item.identity_type,
        id_number=item.id_number,
        avatar_url=item.avatar_url,
        date_of_birth=item.date_of_birth,
        address=item.address,
        relation=item.relation,
        renter_id=item.renter_id,
        primary_renter_name=primary_renter_name,
        lease_state=lease_state,
        deleted_at=item.deleted_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_primary_renter_out(item: Renter) -> CustomerPrimaryRenterOut:
    return CustomerPrimaryRenterOut(
        id=item.id,
        full_name=item.full_name,
        phone=item.phone,
        email=item.email,
        identity_type=item.identity_type,
        id_number=item.id_number,
        avatar_url=item.avatar_url,
        date_of_birth=item.date_of_birth,
        address=item.address,
    )


def _apply_deleted_filter(model, deleted_mode: str):
    if deleted_mode == "active":
        return model.deleted_at.is_(None)
    if deleted_mode == "trash":
        return model.deleted_at.is_not(None)
    return None


def _compute_renter_lease_state_map(
    db: Session,
    *,
    tenant_id: int,
) -> dict[int, CustomerLeaseState]:
    rows = db.execute(
        select(
            Lease.renter_id.label("renter_id"),
            func.sum(
                case(
                    (Lease.status == LeaseStatusEnum.ACTIVE, 1),
                    else_=0,
                )
            ).label("active_count"),
            func.count(Lease.id).label("total_count"),
        )
        .where(
            Lease.tenant_id == tenant_id,
            Lease.deleted_at.is_(None),
        )
        .group_by(Lease.renter_id)
    ).all()

    state_map: dict[int, CustomerLeaseState] = {}
    for row in rows:
        if row.renter_id is None:
            continue
        renter_id = int(row.renter_id)
        active_count = int(row.active_count or 0)
        total_count = int(row.total_count or 0)
        if active_count > 0:
            state_map[renter_id] = "ACTIVE"
        elif total_count > 0:
            state_map[renter_id] = "PAST"
        else:
            state_map[renter_id] = "NOT_RENTED"
    return state_map


def _match_rent_state_filter(
    lease_state: CustomerLeaseState,
    rent_state_filter: str,
) -> bool:
    if rent_state_filter == "all":
        return True
    if rent_state_filter == "active":
        return lease_state == "ACTIVE"
    if rent_state_filter == "past":
        return lease_state == "PAST"
    if rent_state_filter == "not_rented":
        return lease_state == "NOT_RENTED"
    return True


def _resolve_lease_state_for_renter(
    state_map: dict[int, CustomerLeaseState],
    *,
    renter_id: int | None,
) -> CustomerLeaseState:
    if renter_id is None:
        return "NOT_RENTED"
    return state_map.get(renter_id, "NOT_RENTED")


def _normalize_upload_suffix(file_name: str, content_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix and len(suffix) <= 12:
        return suffix

    content_type = (content_type or "").lower()
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/gif":
        return ".gif"
    return ".bin"


def _is_image_upload(content_type: str | None, file_name: str) -> bool:
    if (content_type or "").lower().startswith("image/"):
        return True
    suffix = Path(file_name).suffix.lower()
    return suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _build_customer_object_name(
    *,
    tenant_id: int,
    user_id: int,
    file_name: str,
    content_type: str | None,
) -> str:
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y/%m/%d")
    suffix = _normalize_upload_suffix(file_name, content_type)
    random_part = random_name_with_timestamp(f"u{user_id}")
    return (
        f"tenant-{tenant_id}/{CUSTOMER_OBJECT_PREFIX}/{date_part}/{random_part}{suffix}"
    )


def _build_customer_file_url(object_name: str) -> str:
    return f"/api/v1/customers/files/{object_name}"


def ensure_customer_file_access(*, tenant_id: int, object_name: str) -> None:
    expected_prefix = f"tenant-{tenant_id}/{CUSTOMER_OBJECT_PREFIX}/"
    if not object_name.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer file access denied",
        )


def _extract_object_name_from_customer_url(raw: str) -> str | None:
    normalized = str(raw or "").strip()
    if not normalized:
        return None
    if normalized.startswith("tenant-"):
        return normalized
    marker = "/api/v1/customers/files/"
    if marker in normalized:
        try:
            parsed = urlparse(normalized)
            path = parsed.path if parsed.path else normalized
        except Exception:
            path = normalized
        if marker in path:
            return unquote(path.split(marker, 1)[1].lstrip("/"))
    return None


def _to_customer_file_reference(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    object_name = _extract_object_name_from_customer_url(normalized)
    return object_name or normalized


def list_customers(
    db: Session,
    current_user,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None = None,
    customer_type: str = "all",
    rent_state: str = "all",
) -> tuple[list[CustomerListItemOut], int]:
    context = get_user_auth_context(db, current_user)
    can_view_renter = _has_any_permission(context, RENTER_VIEW_CODES)
    can_view_member = _has_any_permission(context, RENTER_MEMBER_VIEW_CODES)

    if not can_view_renter and not can_view_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem khách hàng",
        )

    page, items_per_page = _ensure_pagination(page, items_per_page)
    normalized_deleted_mode = _ensure_deleted_mode(deleted_mode)
    normalized_customer_type = _ensure_customer_type_filter(customer_type)
    normalized_rent_state = _ensure_rent_state_filter(rent_state)
    normalized_search_key = (search_key or "").strip()
    search_pattern = f"%{normalized_search_key}%" if normalized_search_key else None

    lease_state_map = _compute_renter_lease_state_map(
        db,
        tenant_id=current_user.tenant_id,
    )

    all_items: list[CustomerListItemOut] = []

    if can_view_renter and normalized_customer_type in {"all", "renter"}:
        renter_stmt = select(Renter).where(Renter.tenant_id == current_user.tenant_id)
        deleted_filter = _apply_deleted_filter(Renter, normalized_deleted_mode)
        if deleted_filter is not None:
            renter_stmt = renter_stmt.where(deleted_filter)
        if search_pattern:
            renter_stmt = renter_stmt.where(
                or_(
                    Renter.full_name.ilike(search_pattern),
                    Renter.phone.ilike(search_pattern),
                    Renter.email.ilike(search_pattern),
                    Renter.id_number.ilike(search_pattern),
                )
            )
        renter_rows = list(db.scalars(renter_stmt).all())
        for renter in renter_rows:
            lease_state = _resolve_lease_state_for_renter(
                lease_state_map,
                renter_id=renter.id,
            )
            if not _match_rent_state_filter(lease_state, normalized_rent_state):
                continue
            all_items.append(
                _build_customer_item_from_renter(
                    renter,
                    lease_state=lease_state,
                )
            )

    if can_view_member and normalized_customer_type in {"all", "member"}:
        member_stmt = (
            select(RenterMember, Renter.full_name.label("primary_renter_name"))
            .join(Renter, Renter.id == RenterMember.renter_id)
            .where(
                RenterMember.tenant_id == current_user.tenant_id,
                Renter.tenant_id == current_user.tenant_id,
            )
        )
        deleted_filter = _apply_deleted_filter(RenterMember, normalized_deleted_mode)
        if deleted_filter is not None:
            member_stmt = member_stmt.where(deleted_filter)
        if search_pattern:
            member_stmt = member_stmt.where(
                or_(
                    RenterMember.full_name.ilike(search_pattern),
                    RenterMember.phone.ilike(search_pattern),
                    RenterMember.email.ilike(search_pattern),
                    RenterMember.id_number.ilike(search_pattern),
                    Renter.full_name.ilike(search_pattern),
                )
            )
        member_rows = db.execute(member_stmt).all()
        for member, primary_renter_name in member_rows:
            lease_state = _resolve_lease_state_for_renter(
                lease_state_map,
                renter_id=member.renter_id,
            )
            if not _match_rent_state_filter(lease_state, normalized_rent_state):
                continue
            all_items.append(
                _build_customer_item_from_member(
                    member,
                    primary_renter_name,
                    lease_state=lease_state,
                )
            )

    all_items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    total_items = len(all_items)
    start = (page - 1) * items_per_page
    end = start + items_per_page
    return all_items[start:end], total_items


def _get_renter(
    db: Session, *, tenant_id: int, renter_id: int, include_deleted: bool = True
) -> Renter:
    stmt = select(Renter).where(
        Renter.id == renter_id,
        Renter.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(Renter.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách thuê",
        )
    return item


def _get_member(
    db: Session, *, tenant_id: int, member_id: int, include_deleted: bool = True
) -> RenterMember:
    stmt = select(RenterMember).where(
        RenterMember.id == member_id,
        RenterMember.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(RenterMember.deleted_at.is_(None))
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách thuê cùng",
        )
    return item


def get_customer_detail(
    db: Session,
    current_user,
    *,
    customer_type: CustomerType,
    customer_id: int,
) -> CustomerDetailOut:
    context = get_user_auth_context(db, current_user)
    can_view_renter = _has_any_permission(context, RENTER_VIEW_CODES)
    can_view_member = _has_any_permission(context, RENTER_MEMBER_VIEW_CODES)

    if customer_type == "renter":
        _ensure_permission(context, RENTER_VIEW_CODES)
        renter = _get_renter(
            db, tenant_id=current_user.tenant_id, renter_id=customer_id
        )
        lease_state_map = _compute_renter_lease_state_map(
            db,
            tenant_id=current_user.tenant_id,
        )
        renter_lease_state = _resolve_lease_state_for_renter(
            lease_state_map,
            renter_id=renter.id,
        )
        customer = _build_customer_item_from_renter(
            renter,
            lease_state=renter_lease_state,
        )

        companions: list[CustomerListItemOut] = []
        if can_view_member:
            member_rows = db.scalars(
                select(RenterMember)
                .where(
                    RenterMember.tenant_id == current_user.tenant_id,
                    RenterMember.renter_id == renter.id,
                )
                .order_by(RenterMember.created_at.asc(), RenterMember.id.asc())
            ).all()
            companions = [
                _build_customer_item_from_member(
                    item,
                    renter.full_name,
                    lease_state=renter_lease_state,
                )
                for item in member_rows
            ]

        return CustomerDetailOut(
            customer=customer,
            primary_renter=_build_primary_renter_out(renter),
            companions=companions,
        )

    _ensure_permission(context, RENTER_MEMBER_VIEW_CODES)
    member = _get_member(db, tenant_id=current_user.tenant_id, member_id=customer_id)
    renter = _get_renter(
        db, tenant_id=current_user.tenant_id, renter_id=member.renter_id
    )
    lease_state_map = _compute_renter_lease_state_map(
        db,
        tenant_id=current_user.tenant_id,
    )
    renter_lease_state = _resolve_lease_state_for_renter(
        lease_state_map,
        renter_id=renter.id,
    )
    customer = _build_customer_item_from_member(
        member,
        renter.full_name,
        lease_state=renter_lease_state,
    )

    companions: list[CustomerListItemOut] = []
    if can_view_member:
        member_rows = db.scalars(
            select(RenterMember)
            .where(
                RenterMember.tenant_id == current_user.tenant_id,
                RenterMember.renter_id == renter.id,
            )
            .order_by(RenterMember.created_at.asc(), RenterMember.id.asc())
        ).all()
        companions = [
            _build_customer_item_from_member(
                item,
                renter.full_name,
                lease_state=renter_lease_state,
            )
            for item in member_rows
        ]

    primary_renter = _build_primary_renter_out(renter) if can_view_renter else None
    return CustomerDetailOut(
        customer=customer,
        primary_renter=primary_renter,
        companions=companions,
    )


def create_customer(
    db: Session,
    current_user,
    payload: CustomerCreateRequest,
) -> CustomerListItemOut:
    context = get_user_auth_context(db, current_user)

    if payload.customer_type == "renter":
        _ensure_permission(context, RENTER_CREATE_CODES)
        created = _create_renter(
            db,
            current_user,
            RenterCreateRequest(
                full_name=payload.full_name,
                phone=payload.phone,
                identity_type=payload.identity_type,
                id_number=payload.id_number,
                email=payload.email,
                avatar_url=_to_customer_file_reference(payload.avatar_url),
                date_of_birth=payload.date_of_birth,
                address=payload.address,
            ),
        )
        renter = _get_renter(db, tenant_id=current_user.tenant_id, renter_id=created.id)
        return _build_customer_item_from_renter(
            renter,
            lease_state=_resolve_lease_state_for_renter(
                _compute_renter_lease_state_map(
                    db,
                    tenant_id=current_user.tenant_id,
                ),
                renter_id=renter.id,
            ),
        )

    _ensure_permission(context, RENTER_MEMBER_CREATE_CODES)
    if payload.renter_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="renter_id là bắt buộc khi tạo khách thuê cùng",
        )
    created = _create_renter_member(
        db,
        current_user,
        RenterMemberCreateRequest(
            renter_id=payload.renter_id,
            full_name=payload.full_name,
            phone=payload.phone,
            identity_type=payload.identity_type,
            id_number=payload.id_number,
            email=payload.email,
            avatar_url=_to_customer_file_reference(payload.avatar_url),
            date_of_birth=payload.date_of_birth,
            address=payload.address,
            relation=payload.relation,
        ),
    )
    member = _get_member(db, tenant_id=current_user.tenant_id, member_id=created.id)
    renter = _get_renter(
        db, tenant_id=current_user.tenant_id, renter_id=member.renter_id
    )
    return _build_customer_item_from_member(
        member,
        renter.full_name,
        lease_state=_resolve_lease_state_for_renter(
            _compute_renter_lease_state_map(
                db,
                tenant_id=current_user.tenant_id,
            ),
            renter_id=renter.id,
        ),
    )


def add_companion(
    db: Session,
    current_user,
    *,
    customer_type: CustomerType,
    customer_id: int,
    payload: CustomerCompanionCreateRequest,
) -> CustomerListItemOut:
    context = get_user_auth_context(db, current_user)
    _ensure_permission(context, RENTER_MEMBER_CREATE_CODES)

    if customer_type == "renter":
        renter = _get_renter(
            db,
            tenant_id=current_user.tenant_id,
            renter_id=customer_id,
            include_deleted=False,
        )
    else:
        member = _get_member(
            db,
            tenant_id=current_user.tenant_id,
            member_id=customer_id,
            include_deleted=False,
        )
        renter = _get_renter(
            db,
            tenant_id=current_user.tenant_id,
            renter_id=member.renter_id,
            include_deleted=False,
        )

    created = _create_renter_member(
        db,
        current_user,
        RenterMemberCreateRequest(
            renter_id=renter.id,
            full_name=payload.full_name,
            phone=payload.phone,
            identity_type=payload.identity_type,
            id_number=payload.id_number,
            email=payload.email,
            avatar_url=_to_customer_file_reference(payload.avatar_url),
            date_of_birth=payload.date_of_birth,
            address=payload.address,
            relation=payload.relation,
        ),
    )
    created_member = _get_member(
        db,
        tenant_id=current_user.tenant_id,
        member_id=created.id,
    )
    return _build_customer_item_from_member(
        created_member,
        renter.full_name,
        lease_state=_resolve_lease_state_for_renter(
            _compute_renter_lease_state_map(
                db,
                tenant_id=current_user.tenant_id,
            ),
            renter_id=renter.id,
        ),
    )


async def upload_customer_avatar(
    *,
    current_user,
    upload_file: UploadFile,
) -> CustomerUploadOut:
    if upload_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload file is required",
        )

    original_file_name = upload_file.filename or "customer.bin"
    content = await upload_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(content) > CUSTOMER_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large (max 10MB)",
        )

    object_name = _build_customer_object_name(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        file_name=original_file_name,
        content_type=upload_file.content_type,
    )
    try:
        upload_chat_bytes(
            object_name=object_name,
            content=content,
            content_type=upload_file.content_type,
        )
    except MinioStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot upload file to MinIO",
        ) from exc

    file_url = _build_customer_file_url(object_name)
    return CustomerUploadOut(
        object_name=object_name,
        file_name=original_file_name,
        file_url=file_url,
        access_url=file_url,
        mime_type=upload_file.content_type or None,
        size_bytes=len(content),
        is_image=_is_image_upload(upload_file.content_type, original_file_name),
    )


def get_customer_file_stream(
    *,
    current_user,
    object_name: str,
):
    ensure_customer_file_access(
        tenant_id=current_user.tenant_id,
        object_name=object_name,
    )
    try:
        stream = get_chat_object_stream(object_name)
    except MinioStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer file not found",
        ) from exc
    return stream.object_data, stream.content_type, stream.content_length
