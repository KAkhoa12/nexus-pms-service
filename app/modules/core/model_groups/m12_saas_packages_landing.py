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
    Integer,
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
    TimestampSoftDeleteMixin,
    enum_col,
)


class SaasPackage(TimestampSoftDeleteMixin, Base):
    __tablename__ = "saas_packages"
    __table_args__ = (
        UniqueConstraint("code", name="uq_saas_packages_code"),
        Index("ix_saas_packages_active_sort", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    yearly_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="VND", server_default="VND"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_task_management_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    ai_quota_monthly: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    features: Mapped[List["SaasPackageFeature"]] = relationship(
        back_populates="package"
    )
    subscriptions: Mapped[List["TenantSubscription"]] = relationship(
        back_populates="package"
    )
    user_subscriptions: Mapped[List["UserSubscription"]] = relationship(
        back_populates="package"
    )


class SaasPackageFeature(TimestampSoftDeleteMixin, Base):
    __tablename__ = "saas_package_features"
    __table_args__ = (
        UniqueConstraint(
            "package_id",
            "feature_key",
            name="uq_saas_package_features_package_feature_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("saas_packages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(255), nullable=False)
    feature_description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    is_included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    limit_value: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    package: Mapped["SaasPackage"] = relationship(back_populates="features")


class TenantSubscription(TimestampSoftDeleteMixin, Base):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        Index("ix_tenant_subscriptions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
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

    tenant: Mapped["SaasTenant"] = relationship(back_populates="subscriptions")
    package: Mapped["SaasPackage"] = relationship(back_populates="subscriptions")


class LandingPageSection(TimestampSoftDeleteMixin, Base):
    __tablename__ = "landing_page_sections"
    __table_args__ = (
        UniqueConstraint(
            "page_slug",
            "locale",
            "section_key",
            name="uq_landing_page_sections_key",
        ),
        Index(
            "ix_landing_page_sections_publish_sort",
            "page_slug",
            "locale",
            "is_published",
            "sort_order",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_slug: Mapped[str] = mapped_column(
        String(64), nullable=False, default="home", server_default="home"
    )
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="vi-VN", server_default="vi-VN"
    )
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cta_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cta_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


__all__ = [
    "SaasPackage",
    "SaasPackageFeature",
    "TenantSubscription",
    "LandingPageSection",
]
