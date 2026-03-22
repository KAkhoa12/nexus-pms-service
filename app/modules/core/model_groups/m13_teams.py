from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import (
    SubscriptionBillingCycleEnum,
    SubscriptionStatusEnum,
    TeamMemberRoleEnum,
    TimestampSoftDeleteMixin,
    enum_col,
)


class Team(TimestampSoftDeleteMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_teams_tenant_name"),
        Index("ix_teams_tenant_active", "tenant_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship(back_populates="teams")
    owner_user: Mapped["User"] = relationship(
        back_populates="teams_owned", foreign_keys=[owner_user_id]
    )
    members: Mapped[List["TeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(TimestampSoftDeleteMixin, Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        Index("ix_team_members_team_role", "team_id", "member_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invited_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    member_role: Mapped[TeamMemberRoleEnum] = mapped_column(
        enum_col(TeamMemberRoleEnum, "team_member_role_enum"),
        nullable=False,
        default=TeamMemberRoleEnum.MEMBER,
        server_default=TeamMemberRoleEnum.MEMBER.value,
    )
    rbac_role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )

    team: Mapped["Team"] = relationship(back_populates="members")
    tenant: Mapped["SaasTenant"] = relationship(back_populates="team_members")
    user: Mapped["User"] = relationship(
        back_populates="team_memberships", foreign_keys=[user_id]
    )
    invited_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="team_invitations_sent", foreign_keys=[invited_by_user_id]
    )
    rbac_role: Mapped[Optional["Role"]] = relationship(back_populates="team_members")


class UserSubscription(TimestampSoftDeleteMixin, Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (Index("ix_user_subscriptions_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    package_id: Mapped[int] = mapped_column(
        ForeignKey("saas_packages.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[SubscriptionStatusEnum] = mapped_column(
        enum_col(SubscriptionStatusEnum, "subscription_status_enum"),
        nullable=False,
    )
    billing_cycle: Mapped[SubscriptionBillingCycleEnum] = mapped_column(
        enum_col(SubscriptionBillingCycleEnum, "subscription_billing_cycle_enum"),
        nullable=False,
        default=SubscriptionBillingCycleEnum.MONTHLY,
        server_default=SubscriptionBillingCycleEnum.MONTHLY.value,
    )
    price_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="VND", server_default="VND"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="user_subscriptions")
    package: Mapped["SaasPackage"] = relationship(back_populates="user_subscriptions")


__all__ = ["Team", "TeamMember", "UserSubscription"]
