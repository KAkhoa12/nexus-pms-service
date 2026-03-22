from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.modules.auth.google_service import GoogleIdentity
from app.modules.auth.models import RevokedToken
from app.modules.auth.schemas import RegisterEmployeeRequest
from app.modules.core.models import (
    Permission,
    PermissionEffectEnum,
    PlanTypeEnum,
    Role,
    RolePermission,
    SaasPackage,
    SaasPackageFeature,
    SaasTenant,
    SubscriptionBillingCycleEnum,
    SubscriptionStatusEnum,
    Team,
    TeamMember,
    TeamMemberRoleEnum,
    TenantStatusEnum,
    User,
    UserPermissionOverride,
    UserPreference,
    UserRole,
    UserSubscription,
)
from app.utils.validators import password_strength_errors

FULL_ACCESS_ROLE_NAMES = {"OWNER", "SUPER_ADMIN", "TENANT_ADMIN", "ADMIN"}
CREATE_EMPLOYEE_PERMISSION_CODES = {"employees:create", "users:create"}
WILDCARD_PERMISSION_CODES = {"*", "all:*", "admin:*"}
ACTIVE_SUBSCRIPTION_STATUSES = {
    SubscriptionStatusEnum.TRIAL,
    SubscriptionStatusEnum.ACTIVE,
}
SUNSET_THEME_FEATURE_CODE = "SUNSET_THEME"
AI_TASK_FEATURE_CODE = "AI_TASK_MANAGEMENT"
INTERNAL_CHAT_FEATURE_CODE = "INTERNAL_CHAT"
AI_CHAT_FEATURE_CODE = "AI_CHAT_ASSISTANT"
AURORA_THEME_FEATURE_CODE = "PRO_AURORA_THEME"
ALLOWED_THEME_MODES = {"light", "dark", "sunset", "aurora"}
_UNSET = object()


@dataclass
class EffectivePackageContext:
    code: str
    name: str
    source: str
    team_id: int | None
    feature_codes: set[str]
    ai_task_management_enabled: bool
    internal_chat_enabled: bool
    can_use_sunset_theme: bool


@dataclass
class AuthContext:
    roles: set[str]
    permissions: set[str]

    @property
    def has_full_access(self) -> bool:
        return bool(self.roles.intersection(FULL_ACCESS_ROLE_NAMES)) or bool(
            self.permissions.intersection(WILDCARD_PERMISSION_CODES)
        )

    @property
    def can_create_employee(self) -> bool:
        return self.has_full_access or bool(
            self.permissions.intersection(CREATE_EMPLOYEE_PERMISSION_CODES)
        )


def _ensure_full_permissions_for_role(db: Session, *, role: Role) -> bool:
    permission_codes = set(
        db.scalars(
            select(Permission.code).where(
                Permission.deleted_at.is_(None),
            )
        ).all()
    )
    if not permission_codes:
        return False

    existing_rows = db.scalars(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
        )
    ).all()
    existing_by_code = {row.permission_code: row for row in existing_rows}

    changed = False
    for code in permission_codes:
        row = existing_by_code.get(code)
        if row is None:
            db.add(
                RolePermission(
                    tenant_id=role.tenant_id,
                    role_id=role.id,
                    permission_code=code,
                )
            )
            changed = True
            continue

        if row.deleted_at is not None:
            row.deleted_at = None
            db.add(row)
            changed = True

    return changed


def _ensure_full_access_role_permissions_for_user(db: Session, *, user: User) -> bool:
    roles = db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user.id,
            UserRole.deleted_at.is_(None),
            Role.deleted_at.is_(None),
        )
    ).all()

    changed = False
    for role in roles:
        if role.name.upper() not in FULL_ACCESS_ROLE_NAMES:
            continue
        if _ensure_full_permissions_for_role(db, role=role):
            changed = True
    return changed


def _get_active_subscription_for_user(
    db: Session, *, user_id: int
) -> tuple[UserSubscription, SaasPackage] | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserSubscription, SaasPackage)
        .join(SaasPackage, SaasPackage.id == UserSubscription.package_id)
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
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return row[0], row[1]


def _get_best_team_package_for_user(
    db: Session, *, user_id: int
) -> tuple[int, UserSubscription, SaasPackage] | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(Team.id, UserSubscription, SaasPackage)
        .join(
            TeamMember,
            TeamMember.team_id == Team.id,
        )
        .join(
            UserSubscription,
            UserSubscription.user_id == Team.owner_user_id,
        )
        .join(SaasPackage, SaasPackage.id == UserSubscription.package_id)
        .where(
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
            TeamMember.user_id == user_id,
            TeamMember.deleted_at.is_(None),
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
            Team.id.asc(),
        )
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return int(row[0]), row[1], row[2]


def _get_team_package_for_user(
    db: Session,
    *,
    user_id: int,
    team_id: int,
) -> tuple[UserSubscription, SaasPackage] | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserSubscription, SaasPackage)
        .join(Team, Team.owner_user_id == UserSubscription.user_id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(SaasPackage, SaasPackage.id == UserSubscription.package_id)
        .where(
            Team.id == team_id,
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
            TeamMember.user_id == user_id,
            TeamMember.deleted_at.is_(None),
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
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return row[0], row[1]


def _ensure_active_free_subscription(db: Session, user: User) -> None:
    active_subscription = _get_active_subscription_for_user(db, user_id=user.id)
    if active_subscription is not None:
        return

    package = db.scalar(
        select(SaasPackage).where(
            SaasPackage.code == "FREE",
            SaasPackage.deleted_at.is_(None),
        )
    )
    if package is None:
        return

    db.add(
        UserSubscription(
            user_id=user.id,
            package_id=package.id,
            status=SubscriptionStatusEnum.ACTIVE,
            billing_cycle=SubscriptionBillingCycleEnum.MONTHLY,
            price_amount=0,
            currency="VND",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            auto_renew=True,
            note="Default FREE package",
        )
    )


def _ensure_admin_role_assignment(db: Session, user: User) -> None:
    admin_role = db.scalar(
        select(Role).where(
            Role.tenant_id == user.tenant_id,
            Role.name == "ADMIN",
            Role.deleted_at.is_(None),
        )
    )
    if admin_role is None:
        admin_role = Role(
            tenant_id=user.tenant_id,
            name="ADMIN",
            description="Default admin role for tenant owner",
        )
        db.add(admin_role)
        db.flush()

    user_role = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == admin_role.id,
        )
    )
    if user_role is None:
        db.add(
            UserRole(
                tenant_id=user.tenant_id,
                user_id=user.id,
                role_id=admin_role.id,
            )
        )
    elif user_role.deleted_at is not None:
        user_role.deleted_at = None
        db.add(user_role)

    _ensure_full_permissions_for_role(db, role=admin_role)


def _get_default_role_ids_for_tenant(db: Session, *, tenant_id: int) -> list[int]:
    role_ids = list(
        db.scalars(
            select(Role.id).where(
                Role.tenant_id == tenant_id,
                Role.deleted_at.is_(None),
            )
        ).all()
    )
    if role_ids:
        return role_ids

    admin_role = Role(
        tenant_id=tenant_id,
        name="ADMIN",
        description="Default admin role",
    )
    db.add(admin_role)
    db.flush()
    _ensure_full_permissions_for_role(db, role=admin_role)
    return [admin_role.id]


def _get_team_workspace_membership(
    db: Session, *, user: User
) -> tuple[TeamMemberRoleEnum, int | None] | None:
    workspace_key = str(getattr(user, "workspace_key", "personal") or "personal")
    if not workspace_key.startswith("team:"):
        return None
    team_id_raw = workspace_key.split(":", 1)[1]
    if not team_id_raw.isdigit():
        return None
    team_id = int(team_id_raw)

    row = db.execute(
        select(TeamMember.member_role, TeamMember.rbac_role_id)
        .join(Team, Team.id == TeamMember.team_id)
        .where(
            TeamMember.user_id == user.id,
            TeamMember.team_id == team_id,
            TeamMember.deleted_at.is_(None),
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
        )
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def _build_workspace_name(identity: GoogleIdentity) -> str:
    base = (identity.name or identity.email.split("@")[0]).strip()
    base = base or "Workspace"
    if len(base) > 120:
        base = base[:120].rstrip()
    return f"{base} Workspace"


def _normalize_theme_mode(theme_mode: str | None) -> str | None:
    if theme_mode is None:
        return None
    normalized = theme_mode.strip().lower()
    if not normalized:
        return None
    if normalized not in ALLOWED_THEME_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="theme_mode is invalid",
        )
    return normalized


def _normalize_workspace_key(
    db: Session, *, user: User, workspace_key: str | None
) -> str | None:
    if workspace_key is None:
        return None
    normalized = workspace_key.strip()
    if not normalized:
        return None
    if normalized == "personal":
        return "personal"
    if not normalized.startswith("team:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_key is invalid",
        )

    team_id_raw = normalized.split(":", 1)[1]
    if not team_id_raw.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_key is invalid",
        )
    team_id = int(team_id_raw)
    is_member = db.scalar(
        select(TeamMember.id)
        .join(Team, Team.id == TeamMember.team_id)
        .where(
            TeamMember.user_id == user.id,
            TeamMember.team_id == team_id,
            TeamMember.deleted_at.is_(None),
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
        )
    )
    if is_member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_key does not belong to current user",
        )
    return normalized


def _workspace_supports_theme_mode(
    db: Session,
    *,
    user_id: int,
    workspace_key: str | None,
    theme_mode: str | None,
) -> bool:
    if theme_mode not in {"sunset", "aurora"}:
        return True

    package: SaasPackage | None = None
    normalized_workspace = workspace_key or "personal"
    if normalized_workspace.startswith("team:"):
        team_id_raw = normalized_workspace.split(":", 1)[1]
        if team_id_raw.isdigit():
            team_package = _get_team_package_for_user(
                db,
                user_id=user_id,
                team_id=int(team_id_raw),
            )
            if team_package is not None:
                package = team_package[1]

    if package is None:
        personal = _get_active_subscription_for_user(db, user_id=user_id)
        if personal is not None:
            package = personal[1]

    if package is None:
        package = db.scalar(
            select(SaasPackage).where(
                SaasPackage.code == "FREE",
                SaasPackage.deleted_at.is_(None),
            )
        )
    if package is None:
        return False

    feature_codes = set(
        db.scalars(
            select(SaasPackageFeature.feature_key).where(
                SaasPackageFeature.package_id == package.id,
                SaasPackageFeature.deleted_at.is_(None),
                SaasPackageFeature.is_included.is_(True),
            )
        ).all()
    )

    if theme_mode == "sunset":
        return package.code in {"PRO", "BUSINESS"} or (
            SUNSET_THEME_FEATURE_CODE in feature_codes
        )
    return AURORA_THEME_FEATURE_CODE in feature_codes


def _get_user_preference_row(db: Session, *, user_id: int) -> UserPreference | None:
    return db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


def get_user_preferences(db: Session, user: User) -> tuple[str | None, str | None]:
    row = _get_user_preference_row(db, user_id=user.id)
    if row is None:
        return None, None
    changed = False
    if row.workspace_key:
        try:
            normalized_workspace_key = _normalize_workspace_key(
                db,
                user=user,
                workspace_key=row.workspace_key,
            )
            if normalized_workspace_key != row.workspace_key:
                row.workspace_key = normalized_workspace_key
                changed = True
        except HTTPException:
            row.workspace_key = "personal"
            changed = True

    if not _workspace_supports_theme_mode(
        db,
        user_id=user.id,
        workspace_key=row.workspace_key,
        theme_mode=row.theme_mode,
    ):
        row.theme_mode = "light"
        changed = True

    if changed:
        db.add(row)
        db.commit()
        db.refresh(row)
    return row.theme_mode, row.workspace_key


def update_user_preferences(
    db: Session,
    user: User,
    *,
    theme_mode: str | None | object = _UNSET,
    workspace_key: str | None | object = _UNSET,
) -> tuple[str | None, str | None]:
    if theme_mode is _UNSET and workspace_key is _UNSET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preference field provided",
        )

    row = _get_user_preference_row(db, user_id=user.id)
    if row is None:
        row = UserPreference(user_id=user.id, theme_mode=None, workspace_key=None)
        db.add(row)
        db.flush()

    if theme_mode is not _UNSET:
        row.theme_mode = _normalize_theme_mode(theme_mode)
    if workspace_key is not _UNSET:
        row.workspace_key = _normalize_workspace_key(
            db,
            user=user,
            workspace_key=workspace_key,
        )

    if not _workspace_supports_theme_mode(
        db,
        user_id=user.id,
        workspace_key=row.workspace_key,
        theme_mode=row.theme_mode,
    ):
        row.theme_mode = "light"

    db.add(row)
    db.commit()
    db.refresh(row)
    return row.theme_mode, row.workspace_key


def authenticate_google_user(db: Session, identity: GoogleIdentity) -> User:
    user_by_sub = db.scalar(
        select(User).where(
            User.google_sub == identity.sub,
            User.deleted_at.is_(None),
        )
    )
    if user_by_sub is not None:
        if not user_by_sub.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )
        user_by_sub.email = identity.email
        if identity.name:
            user_by_sub.full_name = identity.name.strip()[:255]
        user_by_sub.avatar_url = identity.picture
        user_by_sub.auth_provider = "google"
        user_by_sub.google_sub = identity.sub
        _ensure_full_access_role_permissions_for_user(db, user=user_by_sub)
        _ensure_active_free_subscription(db, user_by_sub)
        db.add(user_by_sub)
        db.commit()
        db.refresh(user_by_sub)
        return user_by_sub

    user_by_email = db.scalar(
        select(User).where(
            User.email == identity.email,
            User.deleted_at.is_(None),
        )
    )
    if user_by_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists. Please use password login or account-link flow.",
        )

    tenant = SaasTenant(
        name=_build_workspace_name(identity),
        plan_type=PlanTypeEnum.BASIC,
        status=TenantStatusEnum.ACTIVE,
    )
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=identity.email,
        full_name=(identity.name or identity.email.split("@")[0])[:255],
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        auth_provider="google",
        google_sub=identity.sub,
        avatar_url=identity.picture,
        is_active=True,
    )
    db.add(user)
    db.flush()

    _ensure_admin_role_assignment(db, user)
    _ensure_full_access_role_permissions_for_user(db, user=user)
    _ensure_active_free_subscription(db, user)
    db.commit()
    db.refresh(user)
    return user


def resolve_effective_package_context(
    db: Session, user: User
) -> EffectivePackageContext:
    workspace_key = str(getattr(user, "workspace_key", "personal") or "personal")
    personal = _get_active_subscription_for_user(db, user_id=user.id)

    chosen_package: SaasPackage | None = None
    source = "default"
    team_id: int | None = None

    if workspace_key.startswith("team:"):
        team_id_raw = workspace_key.split(":", 1)[1]
        if team_id_raw.isdigit():
            team_id = int(team_id_raw)
            team_package = _get_team_package_for_user(
                db,
                user_id=user.id,
                team_id=team_id,
            )
            if team_package is not None:
                chosen_package = team_package[1]
                source = "team"
            else:
                team_id = None

    if chosen_package is None and personal is not None:
        chosen_package = personal[1]
        source = "personal"

    if chosen_package is None:
        chosen_package = db.scalar(
            select(SaasPackage).where(
                SaasPackage.code == "FREE",
                SaasPackage.deleted_at.is_(None),
            )
        )

    if chosen_package is None:
        return EffectivePackageContext(
            code="FREE",
            name="Goi Free",
            source="default",
            team_id=None,
            feature_codes=set(),
            ai_task_management_enabled=False,
            internal_chat_enabled=False,
            can_use_sunset_theme=False,
        )

    feature_codes = set(
        db.scalars(
            select(SaasPackageFeature.feature_key).where(
                SaasPackageFeature.package_id == chosen_package.id,
                SaasPackageFeature.deleted_at.is_(None),
                SaasPackageFeature.is_included.is_(True),
            )
        ).all()
    )

    ai_task_enabled = (
        chosen_package.ai_task_management_enabled
        or AI_TASK_FEATURE_CODE in feature_codes
    )
    internal_chat_enabled = (
        INTERNAL_CHAT_FEATURE_CODE in feature_codes
        or AI_CHAT_FEATURE_CODE in feature_codes
    )
    can_use_sunset_theme = (
        SUNSET_THEME_FEATURE_CODE in feature_codes
        or chosen_package.code in {"PRO", "BUSINESS"}
    )

    return EffectivePackageContext(
        code=chosen_package.code,
        name=chosen_package.name,
        source=source,
        team_id=team_id,
        feature_codes=feature_codes,
        ai_task_management_enabled=ai_task_enabled,
        internal_chat_enabled=internal_chat_enabled,
        can_use_sunset_theme=can_use_sunset_theme,
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    stmt = select(User).where(
        User.email == email,
        User.deleted_at.is_(None),
    )
    users = db.scalars(stmt).all()
    if not users:
        return None
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email exists in multiple tenants. Please contact admin to disambiguate.",
        )

    user = users[0]
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    if _ensure_full_access_role_permissions_for_user(db, user=user):
        db.commit()
        db.refresh(user)
    return user


def build_access_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        extra_claims={"tenant_id": user.tenant_id, "email": user.email},
    )


def build_refresh_token(user: User) -> str:
    return create_refresh_token(
        subject=str(user.id),
        extra_claims={"tenant_id": user.tenant_id, "email": user.email},
    )


def get_user_auth_context(db: Session, user: User) -> AuthContext:
    workspace_membership = _get_team_workspace_membership(db, user=user)
    if workspace_membership is not None:
        member_role, rbac_role_id = workspace_membership

        if member_role == TeamMemberRoleEnum.MANAGER:
            return AuthContext(roles={"ADMIN"}, permissions={"*"})

        if rbac_role_id is None:
            return AuthContext(roles=set(), permissions=set())

        role_name = db.scalar(
            select(Role.name).where(
                Role.id == rbac_role_id,
                Role.tenant_id == user.tenant_id,
                Role.deleted_at.is_(None),
            )
        )
        if role_name is None:
            return AuthContext(roles=set(), permissions=set())

        permissions = set(
            db.scalars(
                select(RolePermission.permission_code).where(
                    RolePermission.role_id == rbac_role_id,
                    RolePermission.tenant_id == user.tenant_id,
                    RolePermission.deleted_at.is_(None),
                )
            ).all()
        )
        return AuthContext(roles={str(role_name)}, permissions=permissions)

    role_stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user.id,
            UserRole.tenant_id == user.tenant_id,
            UserRole.deleted_at.is_(None),
            Role.tenant_id == user.tenant_id,
            Role.deleted_at.is_(None),
        )
    )
    roles = set(db.scalars(role_stmt).all())

    permission_stmt = (
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(
            UserRole.user_id == user.id,
            UserRole.tenant_id == user.tenant_id,
            UserRole.deleted_at.is_(None),
            RolePermission.tenant_id == user.tenant_id,
            RolePermission.deleted_at.is_(None),
        )
    )
    permissions = set(db.scalars(permission_stmt).all())

    override_stmt = select(
        UserPermissionOverride.permission_code, UserPermissionOverride.effect
    ).where(
        UserPermissionOverride.user_id == user.id,
        UserPermissionOverride.tenant_id == user.tenant_id,
        UserPermissionOverride.deleted_at.is_(None),
    )
    for permission_code, effect in db.execute(override_stmt).all():
        if effect == PermissionEffectEnum.DENY:
            permissions.discard(permission_code)
        else:
            permissions.add(permission_code)

    return AuthContext(roles=roles, permissions=permissions)


def ensure_can_create_employee(db: Session, current_user: User) -> AuthContext:
    context = get_user_auth_context(db, current_user)
    if not context.can_create_employee:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create employees",
        )
    return context


def create_employee(
    db: Session, current_user: User, payload: RegisterEmployeeRequest
) -> User:
    password_errors = password_strength_errors(payload.password)
    if password_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password is too weak",
                "errors": password_errors,
            },
        )

    existing_stmt = select(User).where(
        User.tenant_id == current_user.tenant_id,
        User.email == payload.email,
        User.deleted_at.is_(None),
    )
    existing = db.scalar(existing_stmt)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists in tenant",
        )

    assigned_role_ids = payload.role_ids
    if assigned_role_ids:
        role_stmt = select(Role).where(
            Role.id.in_(assigned_role_ids),
            Role.tenant_id == current_user.tenant_id,
            Role.deleted_at.is_(None),
        )
        roles = db.scalars(role_stmt).all()
        role_ids_found = {role.id for role in roles}
        if len(role_ids_found) != len(set(assigned_role_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more role_ids are invalid",
            )
    else:
        assigned_role_ids = _get_default_role_ids_for_tenant(
            db, tenant_id=current_user.tenant_id
        )

    user = User(
        tenant_id=current_user.tenant_id,
        email=str(payload.email),
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        auth_provider="password",
        google_sub=None,
        avatar_url=None,
        is_active=True,
    )
    db.add(user)
    db.flush()

    for role_id in assigned_role_ids:
        db.add(
            UserRole(
                tenant_id=current_user.tenant_id,
                user_id=user.id,
                role_id=role_id,
            )
        )

    _ensure_full_access_role_permissions_for_user(db, user=user)

    db.commit()
    db.refresh(user)
    return user


def is_refresh_token_revoked(db: Session, refresh_token: str) -> bool:
    token_hash = hash_token(refresh_token)
    stmt = select(RevokedToken.id).where(RevokedToken.token_hash == token_hash)
    return db.scalar(stmt) is not None


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    payload = decode_refresh_token(refresh_token)
    user_id = int(payload.get("sub", "0"))
    tenant_id = int(payload.get("tenant_id", "0"))
    expires_at = datetime.fromtimestamp(int(payload.get("exp", "0")), tz=timezone.utc)

    token_hash = hash_token(refresh_token)
    exists_stmt = select(RevokedToken.id).where(RevokedToken.token_hash == token_hash)
    if db.scalar(exists_stmt) is not None:
        return

    db.add(
        RevokedToken(
            tenant_id=tenant_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()


def cleanup_expired_revoked_tokens(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
    db.commit()
