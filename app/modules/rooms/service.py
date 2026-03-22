from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    RoomCreateRequest,
    RoomOut,
    RoomUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_room as _create_room,
)
from app.modules.ops_shared.service import (
    hard_delete_room as _hard_delete_room,
)
from app.modules.ops_shared.service import (
    list_rooms as _list_rooms,
)
from app.modules.ops_shared.service import (
    soft_delete_room as _soft_delete_room,
)
from app.modules.ops_shared.service import (
    update_room as _update_room,
)


def list_rooms(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    search_key: str | None,
) -> tuple[list[RoomOut], int]:
    return _list_rooms(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        search_key=search_key,
    )


def create_room(db: Session, current_user: User, payload: RoomCreateRequest) -> RoomOut:
    return _create_room(db, current_user, payload)


def update_room(
    db: Session, current_user: User, *, room_id: int, payload: RoomUpdateRequest
) -> RoomOut:
    return _update_room(db, current_user, room_id=room_id, payload=payload)


def soft_delete_room(
    db: Session, current_user: User, *, room_id: int
) -> SoftDeleteResult:
    return _soft_delete_room(db, current_user, room_id=room_id)


def hard_delete_room(
    db: Session, current_user: User, *, room_id: int
) -> SoftDeleteResult:
    return _hard_delete_room(db, current_user, room_id=room_id)
