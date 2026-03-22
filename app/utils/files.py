from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.utils.naming import random_name_with_timestamp

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assetss"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


def _ensure_assets_dir() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _build_safe_target_path(file_name: str) -> Path:
    target = (ASSETS_DIR / file_name).resolve()
    base = ASSETS_DIR.resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Invalid file path")
    return target


def _resolve_extension(upload_file: UploadFile) -> str:
    file_suffix = Path(upload_file.filename or "").suffix.lower()
    if file_suffix in ALLOWED_IMAGE_EXTENSIONS:
        return file_suffix

    content_type = (upload_file.content_type or "").lower()
    mapped = CONTENT_TYPE_TO_EXTENSION.get(content_type)
    if mapped:
        return mapped

    raise ValueError("Unsupported image format")


async def upload_image(upload_file: UploadFile, prefix: str = "img") -> str:
    """
    Save image into app/assetss and return relative file path.
    """
    if not upload_file:
        raise ValueError("No file provided")

    content_type = (upload_file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise ValueError("File is not an image")

    extension = _resolve_extension(upload_file)
    file_name = f"{random_name_with_timestamp(prefix)}{extension}"

    _ensure_assets_dir()
    target_path = _build_safe_target_path(file_name)

    content = await upload_file.read()
    if not content:
        raise ValueError("Image file is empty")

    target_path.write_bytes(content)
    return f"app/assetss/{file_name}"


def delete_image(path_or_name: str) -> bool:
    """
    Delete image from app/assetss. Returns True if removed, else False.
    """
    if not path_or_name:
        return False

    file_name = Path(path_or_name).name
    target_path = _build_safe_target_path(file_name)

    if not target_path.exists() or not target_path.is_file():
        return False

    target_path.unlink()
    return True
