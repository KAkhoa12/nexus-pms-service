from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.core.models import User
from app.modules.ops_shared.schemas import (
    RenterMemberCreateRequest,
    RenterMemberOut,
    RenterMemberUpdateRequest,
    SoftDeleteResult,
)
from app.modules.ops_shared.service import (
    create_renter_member as _create_renter_member,
)
from app.modules.ops_shared.service import (
    hard_delete_renter_member as _hard_delete_renter_member,
)
from app.modules.ops_shared.service import (
    list_renter_members as _list_renter_members,
)
from app.modules.ops_shared.service import (
    soft_delete_renter_member as _soft_delete_renter_member,
)
from app.modules.ops_shared.service import (
    update_renter_member as _update_renter_member,
)


def list_renter_members(
    db: Session,
    current_user: User,
    *,
    deleted_mode: str,
    page: int,
    items_per_page: int,
) -> tuple[list[RenterMemberOut], int]:
    return _list_renter_members(
        db,
        current_user,
        deleted_mode=deleted_mode,
        page=page,
        items_per_page=items_per_page,
    )


def create_renter_member(
    db: Session, current_user: User, payload: RenterMemberCreateRequest
) -> RenterMemberOut:
    return _create_renter_member(db, current_user, payload)


def update_renter_member(
    db: Session,
    current_user: User,
    *,
    member_id: int,
    payload: RenterMemberUpdateRequest,
) -> RenterMemberOut:
    return _update_renter_member(db, current_user, member_id=member_id, payload=payload)


def soft_delete_renter_member(
    db: Session, current_user: User, *, member_id: int
) -> SoftDeleteResult:
    return _soft_delete_renter_member(db, current_user, member_id=member_id)


def hard_delete_renter_member(
    db: Session, current_user: User, *, member_id: int
) -> SoftDeleteResult:
    return _hard_delete_renter_member(db, current_user, member_id=member_id)
