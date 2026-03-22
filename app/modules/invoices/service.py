from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    InvoiceCreateRequest,
    InvoiceOut,
    InvoiceUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_invoice as _create_invoice,
)
from app.modules.ops_shared.service import (
    hard_delete_invoice as _hard_delete_invoice,
)
from app.modules.ops_shared.service import (
    list_invoices as _list_invoices,
)
from app.modules.ops_shared.service import (
    soft_delete_invoice as _soft_delete_invoice,
)
from app.modules.ops_shared.service import (
    update_invoice as _update_invoice,
)


def list_invoices(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[InvoiceOut], int]:
    return _list_invoices(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )


def create_invoice(
    db: Session, current_user: User, payload: InvoiceCreateRequest
) -> InvoiceOut:
    return _create_invoice(db, current_user, payload)


def update_invoice(
    db: Session, current_user: User, *, invoice_id: int, payload: InvoiceUpdateRequest
) -> InvoiceOut:
    return _update_invoice(db, current_user, invoice_id=invoice_id, payload=payload)


def soft_delete_invoice(
    db: Session, current_user: User, *, invoice_id: int
) -> SoftDeleteResult:
    return _soft_delete_invoice(db, current_user, invoice_id=invoice_id)


def hard_delete_invoice(
    db: Session, current_user: User, *, invoice_id: int
) -> SoftDeleteResult:
    return _hard_delete_invoice(db, current_user, invoice_id=invoice_id)
