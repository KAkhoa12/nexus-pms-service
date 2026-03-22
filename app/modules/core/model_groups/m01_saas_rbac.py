from __future__ import annotations

from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import (
    PermissionEffectEnum,
    PlanTypeEnum,
    TenantStatusEnum,
    TimestampSoftDeleteMixin,
    enum_col,
)


class SaasTenant(TimestampSoftDeleteMixin, Base):
    __tablename__ = "saas_tenants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_type: Mapped[PlanTypeEnum] = mapped_column(
        enum_col(PlanTypeEnum, "plan_type_enum"), nullable=False
    )
    status: Mapped[TenantStatusEnum] = mapped_column(
        enum_col(TenantStatusEnum, "tenant_status_enum"), nullable=False
    )

    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    roles: Mapped[List["Role"]] = relationship(back_populates="tenant")
    branches: Mapped[List["Branch"]] = relationship(back_populates="tenant")
    areas: Mapped[List["Area"]] = relationship(back_populates="tenant")
    buildings: Mapped[List["Building"]] = relationship(back_populates="tenant")
    room_types: Mapped[List["RoomType"]] = relationship(back_populates="tenant")
    rooms: Mapped[List["Room"]] = relationship(back_populates="tenant")
    renters: Mapped[List["Renter"]] = relationship(back_populates="tenant")
    leases: Mapped[List["Lease"]] = relationship(back_populates="tenant")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="tenant")
    subscriptions: Mapped[List["TenantSubscription"]] = relationship(
        back_populates="tenant"
    )
    teams: Mapped[List["Team"]] = relationship(back_populates="tenant")
    team_members: Mapped[List["TeamMember"]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:
        return f"SaasTenant(id={self.id}, name='{self.name}')"


class User(TimestampSoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="password", server_default="password"
    )
    google_sub: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship(back_populates="users")
    user_roles: Mapped[List["UserRole"]] = relationship(back_populates="user")
    permission_overrides: Mapped[List["UserPermissionOverride"]] = relationship(
        back_populates="user"
    )
    branch_accesses: Mapped[List["UserBranchAccess"]] = relationship(
        back_populates="user"
    )
    room_status_changes: Mapped[List["RoomStatusHistory"]] = relationship(
        back_populates="changed_by_user"
    )
    asset_logs: Mapped[List["AssetLog"]] = relationship(
        back_populates="created_by_user"
    )
    handover_sessions: Mapped[List["RoomHandoverSession"]] = relationship(
        back_populates="created_by_user"
    )
    maintenance_logs: Mapped[List["MaintenanceLog"]] = relationship(
        back_populates="created_by_user"
    )
    notifications_created: Mapped[List["Notification"]] = relationship(
        back_populates="created_by_user"
    )
    notification_recipients: Mapped[List["NotificationRecipient"]] = relationship(
        back_populates="user"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    teams_owned: Mapped[List["Team"]] = relationship(back_populates="owner_user")
    team_memberships: Mapped[List["TeamMember"]] = relationship(
        back_populates="user",
        foreign_keys="TeamMember.user_id",
    )
    team_invitations_sent: Mapped[List["TeamMember"]] = relationship(
        back_populates="invited_by_user",
        foreign_keys="TeamMember.invited_by_user_id",
    )
    user_subscriptions: Mapped[List["UserSubscription"]] = relationship(
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email='{self.email}')"


class Role(TimestampSoftDeleteMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="roles")
    role_permissions: Mapped[List["RolePermission"]] = relationship(
        back_populates="role"
    )
    user_roles: Mapped[List["UserRole"]] = relationship(back_populates="role")
    user_branch_accesses: Mapped[List["UserBranchAccess"]] = relationship(
        back_populates="role"
    )
    notifications: Mapped[List["Notification"]] = relationship(back_populates="role")
    team_members: Mapped[List["TeamMember"]] = relationship(back_populates="rbac_role")


class Permission(TimestampSoftDeleteMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_mean: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    role_permissions: Mapped[List["RolePermission"]] = relationship(
        back_populates="permission"
    )
    user_permission_overrides: Mapped[List["UserPermissionOverride"]] = relationship(
        back_populates="permission"
    )


class RolePermission(TimestampSoftDeleteMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_code", name="uq_role_permissions_role_permission"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_code: Mapped[str] = mapped_column(
        ForeignKey("permissions.code", ondelete="RESTRICT"), index=True, nullable=False
    )

    tenant: Mapped["SaasTenant"] = relationship()
    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(back_populates="role_permissions")


class UserRole(TimestampSoftDeleteMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )

    tenant: Mapped["SaasTenant"] = relationship()
    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class UserPermissionOverride(TimestampSoftDeleteMixin, Base):
    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "permission_code",
            name="uq_user_permission_overrides_user_permission",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_code: Mapped[str] = mapped_column(
        ForeignKey("permissions.code", ondelete="RESTRICT"), index=True, nullable=False
    )
    effect: Mapped[PermissionEffectEnum] = mapped_column(
        enum_col(PermissionEffectEnum, "permission_effect_enum"), nullable=False
    )

    tenant: Mapped["SaasTenant"] = relationship()
    user: Mapped["User"] = relationship(back_populates="permission_overrides")
    permission: Mapped["Permission"] = relationship(
        back_populates="user_permission_overrides"
    )


class Branch(TimestampSoftDeleteMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_branches_tenant_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="branches")
    areas: Mapped[List["Area"]] = relationship(back_populates="branch")
    rooms: Mapped[List["Room"]] = relationship(back_populates="branch")
    leases: Mapped[List["Lease"]] = relationship(back_populates="branch")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="branch")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="branch")
    user_accesses: Mapped[List["UserBranchAccess"]] = relationship(
        back_populates="branch"
    )
    notifications: Mapped[List["Notification"]] = relationship(back_populates="branch")


class Area(TimestampSoftDeleteMixin, Base):
    __tablename__ = "areas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "branch_id", "name", name="uq_areas_tenant_branch_name"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="areas")
    branch: Mapped["Branch"] = relationship(back_populates="areas")
    buildings: Mapped[List["Building"]] = relationship(back_populates="area")
    rooms: Mapped[List["Room"]] = relationship(back_populates="area")


class Building(TimestampSoftDeleteMixin, Base):
    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "area_id", "name", name="uq_buildings_tenant_area_name"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    area_id: Mapped[int] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_floors: Mapped[int] = mapped_column(Integer, nullable=False)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="buildings")
    area: Mapped["Area"] = relationship(back_populates="buildings")
    rooms: Mapped[List["Room"]] = relationship(back_populates="building")


class UserBranchAccess(TimestampSoftDeleteMixin, Base):
    __tablename__ = "user_branch_access"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "branch_id",
            "role_id",
            name="uq_user_branch_access_scope",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), index=True, nullable=True
    )

    tenant: Mapped["SaasTenant"] = relationship()
    user: Mapped["User"] = relationship(back_populates="branch_accesses")
    branch: Mapped["Branch"] = relationship(back_populates="user_accesses")
    role: Mapped[Optional["Role"]] = relationship(back_populates="user_branch_accesses")


__all__ = [
    "SaasTenant",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "UserPermissionOverride",
    "Branch",
    "Area",
    "Building",
    "UserBranchAccess",
]
