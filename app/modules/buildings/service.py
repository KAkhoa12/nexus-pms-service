from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.buildings.schemas import (
    BuildingCreateRequest,
    BuildingOut,
    BuildingUpdateRequest,
    SoftDeleteResult,
)
from app.modules.core.models import User
from app.modules.ops_shared.service import (
    create_building as _create_building,
)
from app.modules.ops_shared.service import (
    hard_delete_building as _hard_delete_building,
)
from app.modules.ops_shared.service import (
    list_buildings as _list_buildings,
)
from app.modules.ops_shared.service import (
    soft_delete_building as _soft_delete_building,
)
from app.modules.ops_shared.service import (
    update_building as _update_building,
)


def list_buildings(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[BuildingOut], int]:
    return _list_buildings(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )


def create_building(
    db: Session, current_user: User, payload: BuildingCreateRequest
) -> BuildingOut:
    return _create_building(db, current_user, payload)


def update_building(
    db: Session, current_user: User, *, building_id: int, payload: BuildingUpdateRequest
) -> BuildingOut:
    return _update_building(db, current_user, building_id=building_id, payload=payload)


def soft_delete_building(
    db: Session, current_user: User, *, building_id: int
) -> SoftDeleteResult:
    return _soft_delete_building(db, current_user, building_id=building_id)


def hard_delete_building(
    db: Session, current_user: User, *, building_id: int
) -> SoftDeleteResult:
    return _hard_delete_building(db, current_user, building_id=building_id)
