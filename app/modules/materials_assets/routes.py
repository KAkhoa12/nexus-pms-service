from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import (
    ApiResponse,
    PaginatedResult,
    build_paginated_result,
    success_response,
)
from app.modules.materials_assets.schemas import (
    DeleteResult,
    MaterialAssetCreateRequest,
    MaterialAssetOut,
    MaterialAssetTypeCreateRequest,
    MaterialAssetTypeOut,
    MaterialAssetTypeUpdateRequest,
    MaterialAssetUpdateRequest,
    MaterialAssetUploadOut,
)
from app.modules.materials_assets.service import (
    create_asset_type,
    create_material_asset,
    get_material_asset_file_stream,
    hard_delete_asset_type,
    hard_delete_material_asset,
    list_asset_types,
    list_material_assets,
    soft_delete_asset_type,
    soft_delete_material_asset,
    update_asset_type,
    update_material_asset,
    upload_material_asset_image,
)

router = APIRouter()


@router.get("/types", response_model=ApiResponse[PaginatedResult[MaterialAssetTypeOut]])
def get_asset_types(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=50, ge=1, le=500),
    search_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[MaterialAssetTypeOut]]:
    items, total_items = list_asset_types(
        db,
        tenant_id=current_user.tenant_id,
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
    return success_response(result, message="Lấy danh sách loại tài sản thành công")


@router.post("/types", response_model=ApiResponse[MaterialAssetTypeOut])
def add_asset_type(
    payload: MaterialAssetTypeCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[MaterialAssetTypeOut]:
    item = create_asset_type(db, tenant_id=current_user.tenant_id, payload=payload)
    return success_response(item, message="Tạo loại tài sản thành công")


@router.put("/types/{type_id}", response_model=ApiResponse[MaterialAssetTypeOut])
def edit_asset_type(
    type_id: int,
    payload: MaterialAssetTypeUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[MaterialAssetTypeOut]:
    item = update_asset_type(
        db,
        tenant_id=current_user.tenant_id,
        item_id=type_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật loại tài sản thành công")


@router.delete("/types/{type_id}", response_model=ApiResponse[DeleteResult])
def delete_asset_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[DeleteResult]:
    result = soft_delete_asset_type(
        db,
        tenant_id=current_user.tenant_id,
        item_id=type_id,
    )
    return success_response(result, message="Xóa mềm loại tài sản thành công")


@router.delete("/types/{type_id}/hard", response_model=ApiResponse[DeleteResult])
def delete_asset_type_hard(
    type_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[DeleteResult]:
    result = hard_delete_asset_type(
        db,
        tenant_id=current_user.tenant_id,
        item_id=type_id,
    )
    return success_response(result, message="Xóa vĩnh viễn loại tài sản thành công")


@router.get("", response_model=ApiResponse[PaginatedResult[MaterialAssetOut]])
def get_material_assets(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=500),
    search_key: str | None = Query(default=None),
    room_id: int | None = Query(default=None, ge=1),
    renter_id: int | None = Query(default=None, ge=1),
    owner_scope: str | None = Query(default=None),
    asset_type_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[MaterialAssetOut]]:
    items, total_items = list_material_assets(
        db,
        tenant_id=current_user.tenant_id,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        search_key=search_key,
        room_id=room_id,
        renter_id=renter_id,
        owner_scope=owner_scope,
        asset_type_id=asset_type_id,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách tài sản vật tư thành công")


@router.post("", response_model=ApiResponse[MaterialAssetOut])
def add_material_asset(
    payload: MaterialAssetCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[MaterialAssetOut]:
    item = create_material_asset(db, tenant_id=current_user.tenant_id, payload=payload)
    return success_response(item, message="Tạo tài sản vật tư thành công")


@router.post("/uploads", response_model=ApiResponse[MaterialAssetUploadOut])
async def add_material_asset_upload(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
) -> ApiResponse[MaterialAssetUploadOut]:
    item = await upload_material_asset_image(
        current_user=current_user,
        upload_file=file,
    )
    return success_response(item, message="Tải ảnh tài sản thành công")


@router.get("/files/{object_name:path}")
def get_material_asset_file(
    object_name: str,
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    object_data, content_type, content_length = get_material_asset_file_stream(
        current_user=current_user,
        object_name=object_name,
    )

    def _iterator():
        try:
            for chunk in object_data.stream(32 * 1024):
                yield chunk
        finally:
            object_data.close()
            object_data.release_conn()

    headers: dict[str, str] = {}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    return StreamingResponse(
        _iterator(),
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


@router.put("/{asset_id}", response_model=ApiResponse[MaterialAssetOut])
def edit_material_asset(
    asset_id: int,
    payload: MaterialAssetUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[MaterialAssetOut]:
    item = update_material_asset(
        db,
        tenant_id=current_user.tenant_id,
        item_id=asset_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật tài sản vật tư thành công")


@router.delete("/{asset_id}", response_model=ApiResponse[DeleteResult])
def delete_material_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[DeleteResult]:
    result = soft_delete_material_asset(
        db,
        tenant_id=current_user.tenant_id,
        item_id=asset_id,
    )
    return success_response(result, message="Xóa mềm tài sản vật tư thành công")


@router.delete("/{asset_id}/hard", response_model=ApiResponse[DeleteResult])
def delete_material_asset_hard(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[DeleteResult]:
    result = hard_delete_material_asset(
        db,
        tenant_id=current_user.tenant_id,
        item_id=asset_id,
    )
    return success_response(result, message="Xóa vĩnh viễn tài sản vật tư thành công")
