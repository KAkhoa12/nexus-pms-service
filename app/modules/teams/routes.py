from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import ApiResponse, success_response
from app.modules.core.models import User
from app.modules.teams.schemas import (
    TeamActionResult,
    TeamCreateRequest,
    TeamMemberCandidateOut,
    TeamMemberInviteRequest,
    TeamMemberOut,
    TeamMemberRoleUpdateRequest,
    TeamOut,
)
from app.modules.teams.service import (
    create_team,
    delete_team,
    invite_member,
    kick_member,
    list_my_teams,
    search_member_candidates,
    update_member_rbac_role,
)

router = APIRouter()


@router.get("/me", response_model=ApiResponse[list[TeamOut]])
def get_my_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[TeamOut]]:
    items = list_my_teams(db, current_user)
    return success_response(items, message="Lấy danh sách team thành công")


@router.post("", response_model=ApiResponse[TeamOut])
def add_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TeamOut]:
    item = create_team(db, current_user, payload)
    return success_response(item, message="Tạo team thành công")


@router.post("/{team_id}/members", response_model=ApiResponse[TeamMemberOut])
def add_team_member(
    team_id: int,
    payload: TeamMemberInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TeamMemberOut]:
    item = invite_member(db, current_user, team_id=team_id, payload=payload)
    return success_response(item, message="Mời thành viên vào team thành công")


@router.get(
    "/{team_id}/member-candidates",
    response_model=ApiResponse[list[TeamMemberCandidateOut]],
)
def get_member_candidates(
    team_id: int,
    query: str = Query(default=""),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[TeamMemberCandidateOut]]:
    items = search_member_candidates(
        db,
        current_user,
        team_id=team_id,
        query=query,
        limit=limit,
    )
    return success_response(
        items, message="Lấy danh sách ứng viên thành viên thành công"
    )


@router.patch(
    "/{team_id}/members/{member_user_id}/rbac-role",
    response_model=ApiResponse[TeamMemberOut],
)
def edit_team_member_role(
    team_id: int,
    member_user_id: int,
    payload: TeamMemberRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TeamMemberOut]:
    item = update_member_rbac_role(
        db,
        current_user,
        team_id=team_id,
        member_user_id=member_user_id,
        payload=payload,
    )
    return success_response(item, message="Cập nhật RBAC role thành công")


@router.delete(
    "/{team_id}/members/{member_user_id}", response_model=ApiResponse[TeamActionResult]
)
def remove_team_member(
    team_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TeamActionResult]:
    result = kick_member(
        db,
        current_user,
        team_id=team_id,
        member_user_id=member_user_id,
    )
    return success_response(result, message=result.message)


@router.delete("/{team_id}", response_model=ApiResponse[TeamActionResult])
def remove_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TeamActionResult]:
    result = delete_team(db, current_user, team_id=team_id)
    return success_response(result, message=result.message)
