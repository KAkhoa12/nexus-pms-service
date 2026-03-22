from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.modules.core.models import (
    Permission,
    PlanTypeEnum,
    Role,
    RolePermission,
    SaasPackage,
    SaasPackageFeature,
    SaasTenant,
    SubscriptionStatusEnum,
    Team,
    TeamMember,
    TeamMemberRoleEnum,
    TenantStatusEnum,
    User,
    UserPreference,
    UserRole,
    UserSubscription,
)
from app.modules.teams.schemas import (
    TeamActionResult,
    TeamCreateRequest,
    TeamMemberCandidateOut,
    TeamMemberInviteRequest,
    TeamMemberOut,
    TeamMemberRoleUpdateRequest,
    TeamOut,
)

ACTIVE_SUBSCRIPTION_STATUSES = {
    SubscriptionStatusEnum.TRIAL,
    SubscriptionStatusEnum.ACTIVE,
}
SUNSET_THEME_FEATURE_CODE = "SUNSET_THEME"
AURORA_THEME_FEATURE_CODE = "PRO_AURORA_THEME"


def _normalize_theme_for_personal_package(
    db: Session,
    *,
    user_id: int,
    current_theme_mode: str | None,
) -> str | None:
    if current_theme_mode not in {"sunset", "aurora"}:
        return current_theme_mode

    now = datetime.now(timezone.utc)
    row = db.execute(
        select(SaasPackage.code, SaasPackage.id)
        .join(UserSubscription, UserSubscription.package_id == SaasPackage.id)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
            SaasPackage.deleted_at.is_(None),
            SaasPackage.is_active.is_(True),
        )
        .order_by(
            SaasPackage.sort_order.desc(),
            UserSubscription.started_at.desc(),
            UserSubscription.id.desc(),
        )
    ).first()
    if row is None:
        return "light"

    package_code = str(row[0])
    package_id = int(row[1])
    feature_codes = set(
        db.scalars(
            select(SaasPackageFeature.feature_key).where(
                SaasPackageFeature.package_id == package_id,
                SaasPackageFeature.deleted_at.is_(None),
                SaasPackageFeature.is_included.is_(True),
            )
        ).all()
    )
    can_use_sunset = package_code in {"PRO", "BUSINESS"} or (
        SUNSET_THEME_FEATURE_CODE in feature_codes
    )
    can_use_aurora = AURORA_THEME_FEATURE_CODE in feature_codes

    if current_theme_mode == "sunset" and can_use_sunset:
        return current_theme_mode
    if current_theme_mode == "aurora" and can_use_aurora:
        return current_theme_mode
    return "light"


def _reset_workspace_preference_if_team_selected(
    db: Session,
    *,
    user_id: int,
    team_id: int,
) -> None:
    row = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if row is None:
        return
    if row.workspace_key != f"team:{team_id}":
        return
    row.workspace_key = "personal"
    row.theme_mode = _normalize_theme_for_personal_package(
        db,
        user_id=user_id,
        current_theme_mode=row.theme_mode,
    )
    db.add(row)


def _ensure_team_owner(db: Session, *, team_id: int, current_user: User) -> Team:
    team = _ensure_team_manager(db, team_id=team_id, current_user=current_user)
    if team.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team owner can delete workspace",
        )
    return team


def _to_member_out(member: TeamMember, user: User) -> TeamMemberOut:
    return TeamMemberOut(
        id=member.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        member_role=member.member_role.value,
        rbac_role_id=member.rbac_role_id,
        invited_by_user_id=member.invited_by_user_id,
        created_at=member.created_at,
    )


def _ensure_can_create_team(db: Session, *, current_user: User) -> None:
    now = datetime.now(timezone.utc)
    has_business_subscription = db.scalar(
        select(SaasPackage.id)
        .join(UserSubscription, UserSubscription.package_id == SaasPackage.id)
        .where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
            SaasPackage.deleted_at.is_(None),
            SaasPackage.is_active.is_(True),
            SaasPackage.code == "BUSINESS",
        )
        .order_by(
            UserSubscription.started_at.desc(),
            UserSubscription.id.desc(),
        )
    )
    if has_business_subscription is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only personal BUSINESS package can create workspace team",
        )


def _get_owner_package(db: Session, *, owner_user_id: int) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(SaasPackage.code, SaasPackage.name)
        .join(UserSubscription, UserSubscription.package_id == SaasPackage.id)
        .where(
            UserSubscription.user_id == owner_user_id,
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
            SaasPackage.deleted_at.is_(None),
            SaasPackage.is_active.is_(True),
        )
        .order_by(
            SaasPackage.sort_order.desc(),
            UserSubscription.started_at.desc(),
            UserSubscription.id.desc(),
        )
    ).first()
    if row is None:
        return "FREE", "Goi Free"
    return str(row[0]), str(row[1])


def _ensure_team_manager(db: Session, *, team_id: int, current_user: User) -> Team:
    team = db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
        )
    )
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == current_user.id,
            TeamMember.deleted_at.is_(None),
        )
    )
    if membership is None or membership.member_role != TeamMemberRoleEnum.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team manager can manage members",
        )
    return team


def _ensure_role_belongs_tenant(db: Session, *, tenant_id: int, role_id: int) -> None:
    role = db.scalar(
        select(Role).where(
            Role.id == role_id,
            Role.tenant_id == tenant_id,
            Role.deleted_at.is_(None),
        )
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RBAC role is invalid",
        )


def _create_workspace_tenant(db: Session, *, team_name: str) -> SaasTenant:
    normalized_name = team_name.strip() or "Workspace"
    display_name = f"{normalized_name} Workspace"
    if len(display_name) > 255:
        display_name = display_name[:255].rstrip()
    tenant = SaasTenant(
        name=display_name,
        plan_type=PlanTypeEnum.BASIC,
        status=TenantStatusEnum.ACTIVE,
    )
    db.add(tenant)
    db.flush()
    return tenant


def _ensure_admin_role_permissions_for_tenant(
    db: Session, *, tenant_id: int
) -> Role | None:
    admin_role = db.scalar(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.name == "ADMIN",
        )
    )
    if admin_role is None:
        admin_role = Role(
            tenant_id=tenant_id,
            name="ADMIN",
            description="Workspace manager role",
        )
        db.add(admin_role)
        db.flush()
    elif admin_role.deleted_at is not None:
        admin_role.deleted_at = None
        db.add(admin_role)

    permission_codes = list(
        db.scalars(
            select(Permission.code).where(
                Permission.deleted_at.is_(None),
            )
        ).all()
    )
    if not permission_codes:
        return admin_role

    existing_rows = db.scalars(
        select(RolePermission).where(
            RolePermission.role_id == admin_role.id,
        )
    ).all()
    existing_by_code = {row.permission_code: row for row in existing_rows}

    for code in permission_codes:
        row = existing_by_code.get(code)
        if row is None:
            db.add(
                RolePermission(
                    tenant_id=tenant_id,
                    role_id=admin_role.id,
                    permission_code=code,
                )
            )
            continue
        if row.deleted_at is not None:
            row.deleted_at = None
            db.add(row)
    return admin_role


def _load_team_members(db: Session, *, team_id: int) -> list[TeamMemberOut]:
    rows = db.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(
            TeamMember.team_id == team_id,
            TeamMember.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(
            TeamMember.member_role.desc(),
            User.full_name.asc(),
            User.id.asc(),
        )
    ).all()
    return [_to_member_out(member, user) for member, user in rows]


def _get_role_names_for_users(
    db: Session, *, user_ids: list[int]
) -> dict[int, list[str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.user_id.in_(user_ids),
            UserRole.deleted_at.is_(None),
            Role.deleted_at.is_(None),
        )
    ).all()
    result: dict[int, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, role_name in rows:
        result.setdefault(int(user_id), []).append(str(role_name))
    return result


def _to_team_out(db: Session, team: Team, owner: User) -> TeamOut:
    package_code, package_name = _get_owner_package(db, owner_user_id=owner.id)
    return TeamOut(
        id=team.id,
        tenant_id=team.tenant_id,
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        owner_user_id=owner.id,
        owner_email=owner.email,
        owner_full_name=owner.full_name,
        owner_package_code=package_code,
        owner_package_name=package_name,
        members=_load_team_members(db, team_id=team.id),
    )


def create_team(db: Session, current_user: User, payload: TeamCreateRequest) -> TeamOut:
    _ensure_can_create_team(db, current_user=current_user)
    normalized_name = payload.name.strip()

    existing = db.scalar(
        select(Team).where(
            Team.owner_user_id == current_user.id,
            func.lower(func.trim(Team.name)) == normalized_name.lower(),
            Team.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team name already exists",
        )

    workspace_tenant = _create_workspace_tenant(db, team_name=normalized_name)
    admin_role = _ensure_admin_role_permissions_for_tenant(
        db, tenant_id=workspace_tenant.id
    )
    team = Team(
        tenant_id=workspace_tenant.id,
        owner_user_id=current_user.id,
        name=normalized_name,
        description=(payload.description or None),
        is_active=True,
    )
    db.add(team)
    db.flush()

    db.add(
        TeamMember(
            team_id=team.id,
            tenant_id=workspace_tenant.id,
            user_id=current_user.id,
            invited_by_user_id=current_user.id,
            member_role=TeamMemberRoleEnum.MANAGER,
            rbac_role_id=admin_role.id if admin_role is not None else None,
        )
    )

    db.commit()
    db.refresh(team)
    return _to_team_out(db, team, current_user)


def list_my_teams(db: Session, current_user: User) -> list[TeamOut]:
    rows = db.execute(
        select(Team, User)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(User, User.id == Team.owner_user_id)
        .where(
            Team.deleted_at.is_(None),
            TeamMember.user_id == current_user.id,
            TeamMember.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(Team.name.asc(), Team.id.asc())
    ).all()
    return [_to_team_out(db, team, owner) for team, owner in rows]


def invite_member(
    db: Session,
    current_user: User,
    *,
    team_id: int,
    payload: TeamMemberInviteRequest,
) -> TeamMemberOut:
    team = _ensure_team_manager(db, team_id=team_id, current_user=current_user)

    user = db.scalar(
        select(User).where(
            User.email == str(payload.email).lower(),
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invited user not found",
        )

    role_id = payload.rbac_role_id
    if role_id is not None:
        _ensure_role_belongs_tenant(db, tenant_id=team.tenant_id, role_id=role_id)

    member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id,
        )
    )
    if member is not None and member.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists in team",
        )

    if member is None:
        member = TeamMember(
            team_id=team_id,
            tenant_id=team.tenant_id,
            user_id=user.id,
            invited_by_user_id=current_user.id,
            member_role=TeamMemberRoleEnum.MEMBER,
            rbac_role_id=role_id,
        )
    else:
        member.deleted_at = None
        member.invited_by_user_id = current_user.id
        member.member_role = TeamMemberRoleEnum.MEMBER
        member.rbac_role_id = role_id

    db.add(member)

    db.commit()
    db.refresh(member)
    return _to_member_out(member, user)


def update_member_rbac_role(
    db: Session,
    current_user: User,
    *,
    team_id: int,
    member_user_id: int,
    payload: TeamMemberRoleUpdateRequest,
) -> TeamMemberOut:
    team = _ensure_team_manager(db, team_id=team_id, current_user=current_user)
    _ensure_role_belongs_tenant(
        db, tenant_id=team.tenant_id, role_id=payload.rbac_role_id
    )

    row = db.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == member_user_id,
            TeamMember.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )
    member, user = row

    member.rbac_role_id = payload.rbac_role_id
    db.add(member)
    db.commit()
    db.refresh(member)
    return _to_member_out(member, user)


def kick_member(
    db: Session,
    current_user: User,
    *,
    team_id: int,
    member_user_id: int,
) -> TeamActionResult:
    team = _ensure_team_manager(db, team_id=team_id, current_user=current_user)
    if member_user_id == team.owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team owner",
        )

    member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == member_user_id,
            TeamMember.deleted_at.is_(None),
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    member.deleted_at = datetime.now(timezone.utc)
    db.add(member)
    _reset_workspace_preference_if_team_selected(
        db,
        user_id=member_user_id,
        team_id=team_id,
    )
    db.commit()
    return TeamActionResult(success=True, message="Member removed from team")


def delete_team(
    db: Session,
    current_user: User,
    *,
    team_id: int,
) -> TeamActionResult:
    team = _ensure_team_owner(db, team_id=team_id, current_user=current_user)
    now = datetime.now(timezone.utc)

    member_user_ids = list(
        db.scalars(
            select(TeamMember.user_id).where(
                TeamMember.team_id == team.id,
                TeamMember.deleted_at.is_(None),
            )
        ).all()
    )

    memberships = db.scalars(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.deleted_at.is_(None),
        )
    ).all()
    for membership in memberships:
        membership.deleted_at = now
        db.add(membership)

    team.is_active = False
    team.deleted_at = now
    db.add(team)

    for user_id in member_user_ids:
        _reset_workspace_preference_if_team_selected(
            db,
            user_id=int(user_id),
            team_id=team.id,
        )

    db.commit()
    return TeamActionResult(success=True, message="Workspace team deleted")


def search_member_candidates(
    db: Session,
    current_user: User,
    *,
    team_id: int,
    query: str,
    limit: int = 30,
) -> list[TeamMemberCandidateOut]:
    _ensure_team_manager(db, team_id=team_id, current_user=current_user)
    normalized_query = query.strip()
    safe_limit = max(1, min(limit, 100))

    if len(normalized_query) < 2:
        return []

    member_user_ids = set(
        db.scalars(
            select(TeamMember.user_id).where(
                TeamMember.team_id == team_id,
                TeamMember.deleted_at.is_(None),
            )
        ).all()
    )

    like_query = f"%{normalized_query}%"
    stmt = select(User).where(
        User.deleted_at.is_(None),
        or_(
            User.email.ilike(like_query),
            User.full_name.ilike(like_query),
            cast(User.id, String).like(like_query),
        ),
    )

    users = list(
        db.scalars(
            stmt.order_by(User.full_name.asc(), User.id.asc()).limit(safe_limit)
        ).all()
    )
    role_map = _get_role_names_for_users(db, user_ids=[item.id for item in users])

    return [
        TeamMemberCandidateOut(
            user_id=item.id,
            email=item.email,
            full_name=item.full_name,
            roles=sorted(role_map.get(item.id, [])),
            is_active=bool(item.is_active),
            is_in_team=item.id in member_user_ids,
        )
        for item in users
    ]
