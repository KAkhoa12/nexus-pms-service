from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    AreaCreateRequest,
    AreaOut,
    AreaUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_area as _create_area,
)
from app.modules.ops_shared.service import (
    hard_delete_area as _hard_delete_area,
)
from app.modules.ops_shared.service import (
    list_areas as _list_areas,
)
from app.modules.ops_shared.service import (
    soft_delete_area as _soft_delete_area,
)
from app.modules.ops_shared.service import (
    update_area as _update_area,
)


def list_areas(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
    branch_id: int | None,
    search_key: str | None,
) -> tuple[list[AreaOut], int]:
    return _list_areas(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
        branch_id=branch_id,
        search_key=search_key,
    )


def create_area(db: Session, current_user: User, payload: AreaCreateRequest) -> AreaOut:
    return _create_area(db, current_user, payload)


def update_area(
    db: Session, current_user: User, *, area_id: int, payload: AreaUpdateRequest
) -> AreaOut:
    return _update_area(db, current_user, area_id=area_id, payload=payload)


def soft_delete_area(
    db: Session, current_user: User, *, area_id: int
) -> SoftDeleteResult:
    return _soft_delete_area(db, current_user, area_id=area_id)


def hard_delete_area(
    db: Session, current_user: User, *, area_id: int
) -> SoftDeleteResult:
    return _hard_delete_area(db, current_user, area_id=area_id)
