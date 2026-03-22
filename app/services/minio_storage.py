from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.utils.naming import random_name_with_timestamp


class MinioStorageError(RuntimeError):
    pass


@dataclass
class MinioObjectStream:
    object_data: object
    content_type: str | None
    content_length: int | None


_minio_client: Minio | None = None
_bucket_checked = False


def _get_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        access_key = settings.MINIO_ACCESS_KEY or settings.MINIO_ROOT_USER
        secret_key = settings.MINIO_SECRET_KEY or settings.MINIO_ROOT_PASSWORD
        _minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=access_key,
            secret_key=secret_key,
            secure=settings.MINIO_SECURE,
        )
    return _minio_client


def _ensure_bucket() -> None:
    global _bucket_checked
    if _bucket_checked:
        return

    client = _get_client()
    bucket = settings.MINIO_CHAT_BUCKET
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error as exc:
        raise MinioStorageError(f"MinIO bucket check failed: {exc}") from exc
    _bucket_checked = True


def _normalize_suffix(file_name: str, content_type: str | None) -> str:
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
    if content_type == "application/pdf":
        return ".pdf"
    return ".bin"


def build_chat_object_name(
    *,
    tenant_id: int,
    user_id: int,
    file_name: str,
    content_type: str | None,
) -> str:
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y/%m/%d")
    suffix = _normalize_suffix(file_name, content_type)
    random_part = random_name_with_timestamp(f"u{user_id}")
    return f"tenant-{tenant_id}/chat/{date_part}/{random_part}{suffix}"


def upload_chat_bytes(
    *,
    object_name: str,
    content: bytes,
    content_type: str | None,
) -> None:
    _ensure_bucket()
    client = _get_client()
    try:
        client.put_object(
            bucket_name=settings.MINIO_CHAT_BUCKET,
            object_name=object_name,
            data=BytesIO(content),
            length=len(content),
            content_type=content_type or "application/octet-stream",
        )
    except S3Error as exc:
        raise MinioStorageError(f"MinIO upload failed: {exc}") from exc


def get_chat_object_stream(object_name: str) -> MinioObjectStream:
    _ensure_bucket()
    client = _get_client()
    try:
        stat = client.stat_object(settings.MINIO_CHAT_BUCKET, object_name)
        obj = client.get_object(settings.MINIO_CHAT_BUCKET, object_name)
        return MinioObjectStream(
            object_data=obj,
            content_type=getattr(stat, "content_type", None),
            content_length=getattr(stat, "size", None),
        )
    except S3Error as exc:
        raise MinioStorageError(f"MinIO object read failed: {exc}") from exc
