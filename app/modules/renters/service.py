from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    RenterCreateRequest,
    RenterOut,
    RenterUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_renter as _create_renter,
)
from app.modules.ops_shared.service import (
    hard_delete_renter as _hard_delete_renter,
)
from app.modules.ops_shared.service import (
    list_renters as _list_renters,
)
from app.modules.ops_shared.service import (
    soft_delete_renter as _soft_delete_renter,
)
from app.modules.ops_shared.service import (
    update_renter as _update_renter,
)


def list_renters(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[RenterOut], int]:
    return _list_renters(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )


def create_renter(
    db: Session, current_user: User, payload: RenterCreateRequest
) -> RenterOut:
    return _create_renter(db, current_user, payload)


def update_renter(
    db: Session, current_user: User, *, renter_id: int, payload: RenterUpdateRequest
) -> RenterOut:
    return _update_renter(db, current_user, renter_id=renter_id, payload=payload)


def soft_delete_renter(
    db: Session, current_user: User, *, renter_id: int
) -> SoftDeleteResult:
    return _soft_delete_renter(db, current_user, renter_id=renter_id)


def hard_delete_renter(
    db: Session, current_user: User, *, renter_id: int
) -> SoftDeleteResult:
    return _hard_delete_renter(db, current_user, renter_id=renter_id)
