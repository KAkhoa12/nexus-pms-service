from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import (
    ApiResponse,
    PaginatedResult,
    build_paginated_result,
    success_response,
)
from app.modules.core.models import User
from app.modules.invoices.schemas import (
    InvoiceCreateRequest,
    InvoiceOut,
    InvoiceUpdateRequest,
    SoftDeleteResult,
)
from app.modules.invoices.service import (
    create_invoice,
    hard_delete_invoice,
    list_invoices,
    soft_delete_invoice,
    update_invoice,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[PaginatedResult[InvoiceOut]])
def get_invoices(
    deleted_mode: str = Query(default="active", description="active | trash | all"),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedResult[InvoiceOut]]:
    items, total_items = list_invoices(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )
    result = build_paginated_result(
        items=items,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Invoices fetched successfully")


@router.post("", response_model=ApiResponse[InvoiceOut])
def add_invoice(
    payload: InvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[InvoiceOut]:
    result = create_invoice(db, current_user, payload)
    return success_response(result, message="Invoice created successfully")


@router.put("/{invoice_id}", response_model=ApiResponse[InvoiceOut])
def edit_invoice(
    invoice_id: int,
    payload: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[InvoiceOut]:
    result = update_invoice(db, current_user, invoice_id=invoice_id, payload=payload)
    return success_response(result, message="Invoice updated successfully")


@router.delete("/{invoice_id}", response_model=ApiResponse[SoftDeleteResult])
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = soft_delete_invoice(db, current_user, invoice_id=invoice_id)
    return success_response(result, message="Invoice soft deleted")


@router.delete("/{invoice_id}/hard", response_model=ApiResponse[SoftDeleteResult])
def delete_invoice_forever(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SoftDeleteResult]:
    result = hard_delete_invoice(db, current_user, invoice_id=invoice_id)
    return success_response(result, message="Invoice permanently deleted")
