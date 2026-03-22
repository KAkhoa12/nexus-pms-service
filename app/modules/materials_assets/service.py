from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.core.models import (
    Asset,
    AssetImage,
    AssetType,
    Lease,
    LeaseStatusEnum,
    Renter,
    Room,
    User,
)
from app.modules.materials_assets.schemas import (
    DeleteResult,
    MaterialAssetCreateRequest,
    MaterialAssetImageOut,
    MaterialAssetOut,
    MaterialAssetTypeCreateRequest,
    MaterialAssetTypeOut,
    MaterialAssetTypeUpdateRequest,
    MaterialAssetUpdateRequest,
    MaterialAssetUploadOut,
)
from app.services.minio_storage import (
    MinioStorageError,
    get_chat_object_stream,
    upload_chat_bytes,
)
from app.utils.naming import random_name_with_timestamp

MAX_ITEMS_PER_PAGE = 500
MATERIAL_ASSET_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
MATERIAL_ASSET_OBJECT_PREFIX = "materials-assets"


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


def _build_material_asset_object_name(
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
        f"tenant-{tenant_id}/{MATERIAL_ASSET_OBJECT_PREFIX}/{date_part}/"
        f"{random_part}{suffix}"
    )


def _build_material_asset_file_url(object_name: str) -> str:
    return f"/api/v1/materials-assets/files/{object_name}"


def ensure_material_asset_file_access(*, tenant_id: int, object_name: str) -> None:
    expected_prefix = f"tenant-{tenant_id}/{MATERIAL_ASSET_OBJECT_PREFIX}/"
    if not object_name.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Asset file access denied",
        )


def _extract_object_name_from_asset_url(raw: str) -> str | None:
    normalized = str(raw or "").strip()
    if not normalized:
        return None
    if normalized.startswith("tenant-"):
        return normalized
    marker = "/api/v1/materials-assets/files/"
    if marker in normalized:
        try:
            parsed = urlparse(normalized)
            path = parsed.path if parsed.path else normalized
        except Exception:
            path = normalized
        if marker in path:
            return unquote(path.split(marker, 1)[1].lstrip("/"))
    return None


def _apply_deleted_mode(stmt, model, deleted_mode: str):
    mode = (deleted_mode or "active").strip().lower()
    if mode == "active":
        return stmt.where(model.deleted_at.is_(None))
    if mode == "trash":
        return stmt.where(model.deleted_at.is_not(None))
    if mode == "all":
        return stmt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="deleted_mode phải là active, trash hoặc all",
    )


def _to_type_out(item: AssetType) -> MaterialAssetTypeOut:
    return MaterialAssetTypeOut(
        id=item.id,
        tenant_id=item.tenant_id,
        name=item.name,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
    )


def _to_asset_file_reference(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    object_name = _extract_object_name_from_asset_url(normalized)
    return object_name or normalized


def _to_image_out(image: AssetImage) -> MaterialAssetImageOut:
    return MaterialAssetImageOut(
        id=image.id,
        image_url=_to_asset_file_reference(image.image_url) or image.image_url,
        caption=image.caption,
        sort_order=image.sort_order,
        is_primary=image.is_primary,
        created_at=image.created_at,
        updated_at=image.updated_at,
        deleted_at=image.deleted_at,
    )


def _to_asset_out(item: Asset) -> MaterialAssetOut:
    ordered_images = sorted(
        [image for image in item.images if image.deleted_at is None],
        key=lambda image: (image.sort_order, image.id),
    )
    return MaterialAssetOut(
        id=item.id,
        tenant_id=item.tenant_id,
        room_id=item.room_id,
        renter_id=item.renter_id,
        asset_type_id=item.asset_type_id,
        name=item.name,
        identifier=item.identifier,
        quantity=item.quantity,
        unit=item.unit,
        status=item.status,
        condition_status=item.condition_status,
        acquired_at=item.acquired_at,
        metadata_json=item.metadata_json,
        note=item.note,
        primary_image_url=_to_asset_file_reference(item.primary_image_url),
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
        asset_type_name=item.asset_type.name if item.asset_type else None,
        room_code=item.room.code if item.room else None,
        renter_full_name=item.renter.full_name if item.renter else None,
        images=[_to_image_out(image) for image in ordered_images],
    )


def _normalize_image_urls(image_urls: list[str] | None) -> list[str]:
    if not image_urls:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in image_urls:
        object_name = _extract_object_name_from_asset_url(str(raw or "").strip())
        url = object_name or str(raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized[:30]


def _ensure_room(db: Session, *, tenant_id: int, room_id: int) -> None:
    exists = db.scalar(
        select(Room.id).where(
            Room.id == room_id,
            Room.tenant_id == tenant_id,
            Room.deleted_at.is_(None),
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Phòng không tồn tại")


def _resolve_room_id_for_asset(
    db: Session,
    *,
    tenant_id: int,
    renter_id: int,
    room_id: int | None,
) -> int:
    if room_id is not None:
        _ensure_room(db, tenant_id=tenant_id, room_id=room_id)
        return room_id

    active_room_id = db.scalar(
        select(Lease.room_id).where(
            Lease.tenant_id == tenant_id,
            Lease.renter_id == renter_id,
            Lease.deleted_at.is_(None),
            Lease.status == LeaseStatusEnum.ACTIVE,
        )
    )
    if active_room_id is not None:
        return int(active_room_id)

    latest_room_id = db.scalar(
        select(Lease.room_id)
        .where(
            Lease.tenant_id == tenant_id,
            Lease.renter_id == renter_id,
            Lease.deleted_at.is_(None),
        )
        .order_by(Lease.start_date.desc(), Lease.id.desc())
    )
    if latest_room_id is not None:
        return int(latest_room_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Không xác định được phòng của khách thuê. "
            "Vui lòng tạo hợp đồng thuê trước khi thêm tài sản."
        ),
    )


def _ensure_renter(db: Session, *, tenant_id: int, renter_id: int) -> None:
    exists = db.scalar(
        select(Renter.id).where(
            Renter.id == renter_id,
            Renter.tenant_id == tenant_id,
            Renter.deleted_at.is_(None),
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Khách thuê không tồn tại")


def _ensure_asset_type(db: Session, *, tenant_id: int, asset_type_id: int) -> AssetType:
    item = db.scalar(
        select(AssetType).where(
            AssetType.id == asset_type_id,
            AssetType.tenant_id == tenant_id,
            AssetType.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Loại tài sản không tồn tại")
    return item


def _replace_asset_images(
    db: Session,
    *,
    tenant_id: int,
    asset: Asset,
    image_urls: list[str],
    primary_image_url: str | None,
) -> None:
    db.execute(
        delete(AssetImage).where(
            AssetImage.tenant_id == tenant_id,
            AssetImage.asset_id == asset.id,
        )
    )

    final_urls = _normalize_image_urls(image_urls)
    primary_candidate = (primary_image_url or "").strip() or None
    primary = (
        _extract_object_name_from_asset_url(primary_candidate)
        if primary_candidate
        else None
    ) or primary_candidate
    if primary and primary not in final_urls:
        final_urls.insert(0, primary)
    if not primary and final_urls:
        primary = final_urls[0]
    asset.primary_image_url = primary

    for index, image_url in enumerate(final_urls):
        db.add(
            AssetImage(
                tenant_id=tenant_id,
                asset_id=asset.id,
                image_url=image_url,
                caption=None,
                sort_order=index,
                is_primary=image_url == primary,
            )
        )


def list_asset_types(
    db: Session,
    *,
    tenant_id: int,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
) -> tuple[list[MaterialAssetTypeOut], int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page phải >= 1")
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=400,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = select(AssetType).where(AssetType.tenant_id == tenant_id)
    stmt = _apply_deleted_mode(stmt, AssetType, deleted_mode)
    if search_key and search_key.strip():
        keyword = f"%{search_key.strip()}%"
        stmt = stmt.where(AssetType.name.ilike(keyword))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.order_by(AssetType.id.desc())
            .offset((page - 1) * items_per_page)
            .limit(items_per_page)
        ).all()
    )
    return ([_to_type_out(item) for item in rows], total)


def create_asset_type(
    db: Session, *, tenant_id: int, payload: MaterialAssetTypeCreateRequest
) -> MaterialAssetTypeOut:
    name = payload.name.strip()
    exists = db.scalar(
        select(AssetType.id).where(
            AssetType.tenant_id == tenant_id,
            AssetType.name == name,
            AssetType.deleted_at.is_(None),
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Loại tài sản đã tồn tại")

    item = AssetType(tenant_id=tenant_id, name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_type_out(item)


def update_asset_type(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
    payload: MaterialAssetTypeUpdateRequest,
) -> MaterialAssetTypeOut:
    item = db.scalar(
        select(AssetType).where(
            AssetType.id == item_id,
            AssetType.tenant_id == tenant_id,
            AssetType.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại tài sản")

    if payload.name is not None:
        next_name = payload.name.strip()
        exists = db.scalar(
            select(AssetType.id).where(
                AssetType.tenant_id == tenant_id,
                AssetType.name == next_name,
                AssetType.id != item.id,
                AssetType.deleted_at.is_(None),
            )
        )
        if exists is not None:
            raise HTTPException(status_code=409, detail="Loại tài sản đã tồn tại")
        item.name = next_name

    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_type_out(item)


def soft_delete_asset_type(
    db: Session, *, tenant_id: int, item_id: int
) -> DeleteResult:
    item = db.scalar(
        select(AssetType).where(
            AssetType.id == item_id,
            AssetType.tenant_id == tenant_id,
            AssetType.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại tài sản")

    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return DeleteResult(deleted=True)


def hard_delete_asset_type(
    db: Session, *, tenant_id: int, item_id: int
) -> DeleteResult:
    item = db.scalar(
        select(AssetType).where(
            AssetType.id == item_id,
            AssetType.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại tài sản")

    used = db.scalar(
        select(Asset.id).where(
            Asset.tenant_id == tenant_id,
            Asset.asset_type_id == item.id,
            Asset.deleted_at.is_(None),
        )
    )
    if used is not None:
        raise HTTPException(
            status_code=409,
            detail="Loại tài sản đang được sử dụng, không thể xóa vĩnh viễn",
        )

    db.delete(item)
    db.commit()
    return DeleteResult(deleted=True)


def list_material_assets(
    db: Session,
    *,
    tenant_id: int,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
    room_id: int | None,
    renter_id: int | None,
    asset_type_id: int | None,
) -> tuple[list[MaterialAssetOut], int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page phải >= 1")
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=400,
            detail=f"items_per_page phải nằm trong khoảng 1..{MAX_ITEMS_PER_PAGE}",
        )

    stmt = (
        select(Asset)
        .options(
            selectinload(Asset.images),
            selectinload(Asset.asset_type),
            selectinload(Asset.room),
            selectinload(Asset.renter),
        )
        .where(Asset.tenant_id == tenant_id)
    )
    stmt = _apply_deleted_mode(stmt, Asset, deleted_mode)

    if room_id is not None:
        stmt = stmt.where(Asset.room_id == room_id)
    if renter_id is not None:
        stmt = stmt.where(Asset.renter_id == renter_id)
    if asset_type_id is not None:
        stmt = stmt.where(Asset.asset_type_id == asset_type_id)

    if search_key and search_key.strip():
        keyword = f"%{search_key.strip()}%"
        stmt = (
            stmt.join(Room, Asset.room_id == Room.id)
            .join(Renter, Asset.renter_id == Renter.id)
            .join(AssetType, Asset.asset_type_id == AssetType.id)
            .where(
                or_(
                    Asset.name.ilike(keyword),
                    Asset.identifier.ilike(keyword),
                    Asset.metadata_json.ilike(keyword),
                    Asset.note.ilike(keyword),
                    Room.code.ilike(keyword),
                    Renter.full_name.ilike(keyword),
                    AssetType.name.ilike(keyword),
                )
            )
            .distinct()
        )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.order_by(Asset.id.desc())
            .offset((page - 1) * items_per_page)
            .limit(items_per_page)
        ).all()
    )
    return ([_to_asset_out(item) for item in rows], total)


def create_material_asset(
    db: Session, *, tenant_id: int, payload: MaterialAssetCreateRequest
) -> MaterialAssetOut:
    _ensure_renter(db, tenant_id=tenant_id, renter_id=payload.renter_id)
    _ensure_asset_type(db, tenant_id=tenant_id, asset_type_id=payload.asset_type_id)
    resolved_room_id = _resolve_room_id_for_asset(
        db,
        tenant_id=tenant_id,
        renter_id=payload.renter_id,
        room_id=payload.room_id,
    )

    item = Asset(
        tenant_id=tenant_id,
        room_id=resolved_room_id,
        renter_id=payload.renter_id,
        asset_type_id=payload.asset_type_id,
        name=payload.name.strip(),
        identifier=(payload.identifier or "").strip() or None,
        quantity=payload.quantity,
        unit=(payload.unit or "").strip() or None,
        status=payload.status.strip().upper(),
        condition_status=payload.condition_status.strip().upper(),
        acquired_at=payload.acquired_at,
        metadata_json=(payload.metadata_json or "").strip() or None,
        note=(payload.note or "").strip() or None,
        primary_image_url=(payload.primary_image_url or "").strip() or None,
    )
    db.add(item)
    db.flush()
    _replace_asset_images(
        db,
        tenant_id=tenant_id,
        asset=item,
        image_urls=payload.image_urls,
        primary_image_url=payload.primary_image_url,
    )
    db.commit()
    db.refresh(item)
    item = db.scalar(
        select(Asset)
        .options(
            selectinload(Asset.images),
            selectinload(Asset.asset_type),
            selectinload(Asset.room),
            selectinload(Asset.renter),
        )
        .where(Asset.id == item.id)
    )
    if item is None:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy tài sản sau khi tạo"
        )
    return _to_asset_out(item)


def update_material_asset(
    db: Session,
    *,
    tenant_id: int,
    item_id: int,
    payload: MaterialAssetUpdateRequest,
) -> MaterialAssetOut:
    item = db.scalar(
        select(Asset).where(
            Asset.id == item_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài sản")

    if payload.renter_id is not None:
        _ensure_renter(db, tenant_id=tenant_id, renter_id=payload.renter_id)
        item.renter_id = payload.renter_id
        if payload.room_id is None:
            item.room_id = _resolve_room_id_for_asset(
                db,
                tenant_id=tenant_id,
                renter_id=payload.renter_id,
                room_id=None,
            )
    if payload.room_id is not None:
        item.room_id = _resolve_room_id_for_asset(
            db,
            tenant_id=tenant_id,
            renter_id=item.renter_id,
            room_id=payload.room_id,
        )
    if payload.asset_type_id is not None:
        _ensure_asset_type(db, tenant_id=tenant_id, asset_type_id=payload.asset_type_id)
        item.asset_type_id = payload.asset_type_id
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.identifier is not None:
        item.identifier = payload.identifier.strip() or None
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.unit is not None:
        item.unit = payload.unit.strip() or None
    if payload.status is not None:
        item.status = payload.status.strip().upper()
    if payload.condition_status is not None:
        item.condition_status = payload.condition_status.strip().upper()
    if payload.acquired_at is not None:
        item.acquired_at = payload.acquired_at
    if payload.metadata_json is not None:
        item.metadata_json = payload.metadata_json.strip() or None
    if payload.note is not None:
        item.note = payload.note.strip() or None
    if payload.primary_image_url is not None:
        item.primary_image_url = payload.primary_image_url.strip() or None

    db.add(item)
    db.flush()
    if payload.image_urls is not None:
        _replace_asset_images(
            db,
            tenant_id=tenant_id,
            asset=item,
            image_urls=payload.image_urls,
            primary_image_url=payload.primary_image_url or item.primary_image_url,
        )
    db.commit()
    refreshed = db.scalar(
        select(Asset)
        .options(
            selectinload(Asset.images),
            selectinload(Asset.asset_type),
            selectinload(Asset.room),
            selectinload(Asset.renter),
        )
        .where(Asset.id == item.id)
    )
    if refreshed is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài sản sau khi cập nhật",
        )
    return _to_asset_out(refreshed)


async def upload_material_asset_image(
    *,
    current_user: User,
    upload_file: UploadFile,
) -> MaterialAssetUploadOut:
    if upload_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload file is required",
        )

    original_file_name = upload_file.filename or "asset.bin"
    content = await upload_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(content) > MATERIAL_ASSET_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large (max 10MB)",
        )

    object_name = _build_material_asset_object_name(
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

    file_url = _build_material_asset_file_url(object_name)
    return MaterialAssetUploadOut(
        object_name=object_name,
        file_name=original_file_name,
        file_url=file_url,
        access_url=file_url,
        mime_type=upload_file.content_type or None,
        size_bytes=len(content),
        is_image=_is_image_upload(upload_file.content_type, original_file_name),
    )


def get_material_asset_file_stream(
    *,
    current_user: User,
    object_name: str,
):
    ensure_material_asset_file_access(
        tenant_id=current_user.tenant_id,
        object_name=object_name,
    )
    try:
        stream = get_chat_object_stream(object_name)
    except MinioStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset file not found",
        ) from exc
    return stream.object_data, stream.content_type, stream.content_length


def soft_delete_material_asset(
    db: Session, *, tenant_id: int, item_id: int
) -> DeleteResult:
    item = db.scalar(
        select(Asset).where(
            Asset.id == item_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài sản")
    item.deleted_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return DeleteResult(deleted=True)


def hard_delete_material_asset(
    db: Session, *, tenant_id: int, item_id: int
) -> DeleteResult:
    item = db.scalar(
        select(Asset).where(
            Asset.id == item_id,
            Asset.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài sản")
    db.delete(item)
    db.commit()
    return DeleteResult(deleted=True)
