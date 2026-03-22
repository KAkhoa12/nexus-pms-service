from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    DepositCreateRequest,
    DepositOut,
    DepositUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_deposit as _create_deposit,
)
from app.modules.ops_shared.service import (
    get_deposit as _get_deposit,
)
from app.modules.ops_shared.service import (
    hard_delete_deposit as _hard_delete_deposit,
)
from app.modules.ops_shared.service import (
    list_deposits as _list_deposits,
)
from app.modules.ops_shared.service import (
    soft_delete_deposit as _soft_delete_deposit,
)
from app.modules.ops_shared.service import (
    update_deposit as _update_deposit,
)


def list_deposits(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    room_id: int | None,
    lease_id: int | None,
) -> tuple[list[DepositOut], int]:
    return _list_deposits(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        room_id=room_id,
        lease_id=lease_id,
    )


def create_deposit(
    db: Session, current_user: User, payload: DepositCreateRequest
) -> DepositOut:
    return _create_deposit(db, current_user, payload)


def get_deposit(db: Session, current_user: User, *, deposit_id: int) -> DepositOut:
    return _get_deposit(db, current_user, deposit_id=deposit_id)


def update_deposit(
    db: Session,
    current_user: User,
    *,
    deposit_id: int,
    payload: DepositUpdateRequest,
) -> DepositOut:
    return _update_deposit(db, current_user, deposit_id=deposit_id, payload=payload)


def soft_delete_deposit(
    db: Session, current_user: User, *, deposit_id: int
) -> SoftDeleteResult:
    return _soft_delete_deposit(db, current_user, deposit_id=deposit_id)


def hard_delete_deposit(
    db: Session, current_user: User, *, deposit_id: int
) -> SoftDeleteResult:
    return _hard_delete_deposit(db, current_user, deposit_id=deposit_id)
