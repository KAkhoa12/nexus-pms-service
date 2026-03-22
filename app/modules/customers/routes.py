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
from app.modules.customers.schemas import (
    CustomerCompanionCreateRequest,
    CustomerCreateRequest,
    CustomerDetailOut,
    CustomerListItemOut,
    CustomerType,
    CustomerUploadOut,
)
from app.modules.customers.service import (
    add_companion,
    create_customer,
    get_customer_detail,
    get_customer_file_stream,
    list_customers,
    upload_customer_avatar,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[CustomerListItemOut]])
def get_customers(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    search_key: str | None = Query(default=None),
    customer_type: str = Query(default="all", description="all | renter | member"),
    rent_state: str = Query(
        default="all",
        description="all | not_rented | active | past",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[PaginatedResult[CustomerListItemOut]]:
    items, total_items = list_customers(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        search_key=search_key,
        customer_type=customer_type,
        rent_state=rent_state,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Lấy danh sách khách hàng thành công")


@router.get(
    "/{customer_type}/{customer_id}",
    response_model=ApiResponse[CustomerDetailOut],
)
def get_customer_detail_route(
    customer_type: CustomerType,
    customer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerDetailOut]:
    result = get_customer_detail(
        db,
        current_user,
        customer_type=customer_type,
        customer_id=customer_id,
    )
    return success_response(result, message="Lấy chi tiết khách hàng thành công")


@router.post("", response_model=ApiResponse[CustomerListItemOut])
def create_customer_route(
    payload: CustomerCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerListItemOut]:
    result = create_customer(db, current_user, payload)
    return success_response(result, message="Tạo khách hàng thành công")


@router.post(
    "/{customer_type}/{customer_id}/companions",
    response_model=ApiResponse[CustomerListItemOut],
)
def create_customer_companion_route(
    customer_type: CustomerType,
    customer_id: int,
    payload: CustomerCompanionCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerListItemOut]:
    result = add_companion(
        db,
        current_user,
        customer_type=customer_type,
        customer_id=customer_id,
        payload=payload,
    )
    return success_response(result, message="Thêm người thuê cùng thành công")


@router.post("/uploads", response_model=ApiResponse[CustomerUploadOut])
async def upload_customer_avatar_route(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
) -> ApiResponse[CustomerUploadOut]:
    result = await upload_customer_avatar(current_user=current_user, upload_file=file)
    return success_response(result, message="Tải ảnh khách hàng thành công")


@router.get("/files/{object_name:path}")
def get_customer_file_route(
    object_name: str,
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    object_data, content_type, content_length = get_customer_file_stream(
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
