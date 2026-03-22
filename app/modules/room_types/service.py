from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    RoomTypeCreateRequest,
    RoomTypeOut,
    RoomTypeUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_room_type as _create_room_type,
)
from app.modules.ops_shared.service import (
    hard_delete_room_type as _hard_delete_room_type,
)
from app.modules.ops_shared.service import (
    list_room_types as _list_room_types,
)
from app.modules.ops_shared.service import (
    soft_delete_room_type as _soft_delete_room_type,
)
from app.modules.ops_shared.service import (
    update_room_type as _update_room_type,
)


def list_room_types(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[RoomTypeOut], int]:
    return _list_room_types(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )


def create_room_type(
    db: Session, current_user: User, payload: RoomTypeCreateRequest
) -> RoomTypeOut:
    return _create_room_type(db, current_user, payload)


def update_room_type(
    db: Session,
    current_user: User,
    *,
    room_type_id: int,
    payload: RoomTypeUpdateRequest,
) -> RoomTypeOut:
    return _update_room_type(
        db, current_user, room_type_id=room_type_id, payload=payload
    )


def soft_delete_room_type(
    db: Session, current_user: User, *, room_type_id: int
) -> SoftDeleteResult:
    return _soft_delete_room_type(db, current_user, room_type_id=room_type_id)


def hard_delete_room_type(
    db: Session, current_user: User, *, room_type_id: int
) -> SoftDeleteResult:
    return _hard_delete_room_type(db, current_user, room_type_id=room_type_id)
