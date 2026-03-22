from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.core.models import (
    LandingPageSection,
    Permission,
    PlatformAdmin,
    SaasPackage,
    SaasPackageFeature,
    SubscriptionBillingCycleEnum,
    SubscriptionStatusEnum,
    Team,
    User,
    UserSubscription,
)
from app.modules.developer_portal.schemas import SaasPackageFeatureInput

ACTIVE_SUBSCRIPTION_STATUSES = {
    SubscriptionStatusEnum.TRIAL,
    SubscriptionStatusEnum.ACTIVE,
}


def get_platform_admin_by_email(db: Session, *, email: str) -> PlatformAdmin | None:
    stmt = select(PlatformAdmin).where(
        PlatformAdmin.email == email,
        PlatformAdmin.deleted_at.is_(None),
    )
    return db.scalar(stmt)


def list_packages(
    db: Session,
    *,
    include_inactive: bool,
    page: int,
    items_per_page: int,
) -> tuple[list[SaasPackage], int]:
    stmt = select(SaasPackage).where(SaasPackage.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(SaasPackage.is_active.is_(True))
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(SaasPackage.sort_order.asc(), SaasPackage.id.asc())
    rows = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return rows, total_items


def get_package_by_id(
    db: Session, *, package_id: int, include_deleted: bool = False
) -> SaasPackage | None:
    stmt = select(SaasPackage).where(SaasPackage.id == package_id)
    if not include_deleted:
        stmt = stmt.where(SaasPackage.deleted_at.is_(None))
    return db.scalar(stmt)


def get_package_by_code(
    db: Session, *, code: str, exclude_id: int | None = None
) -> SaasPackage | None:
    stmt = select(SaasPackage).where(
        SaasPackage.code == code,
        SaasPackage.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(SaasPackage.id != exclude_id)
    return db.scalar(stmt)


def list_package_features(
    db: Session, *, package_ids: list[int]
) -> dict[int, list[SaasPackageFeature]]:
    if not package_ids:
        return {}
    stmt = (
        select(SaasPackageFeature)
        .where(
            SaasPackageFeature.package_id.in_(package_ids),
            SaasPackageFeature.deleted_at.is_(None),
        )
        .order_by(
            SaasPackageFeature.package_id.asc(),
            SaasPackageFeature.sort_order.asc(),
            SaasPackageFeature.id.asc(),
        )
    )
    result: dict[int, list[SaasPackageFeature]] = {
        package_id: [] for package_id in package_ids
    }
    for item in db.scalars(stmt).all():
        result.setdefault(item.package_id, []).append(item)
    return result


def list_permissions(
    db: Session,
    *,
    page: int,
    items_per_page: int,
    search: str | None,
    module: str | None,
) -> tuple[list[Permission], int]:
    stmt = select(Permission).where(Permission.deleted_at.is_(None))
    if module:
        stmt = stmt.where(Permission.module == module.strip())
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Permission.code.ilike(keyword),
                Permission.module.ilike(keyword),
                Permission.module_mean.ilike(keyword),
                Permission.description.ilike(keyword),
            )
        )
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(Permission.module.asc(), Permission.code.asc())
    rows = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return rows, total_items


def get_permission_by_code(db: Session, *, permission_code: str) -> Permission | None:
    return db.scalar(
        select(Permission).where(
            Permission.code == permission_code,
            Permission.deleted_at.is_(None),
        )
    )


def replace_package_features(
    db: Session, *, package_id: int, features: list[SaasPackageFeatureInput]
) -> None:
    db.query(SaasPackageFeature).filter(
        SaasPackageFeature.package_id == package_id
    ).delete()
    for item in features:
        db.add(
            SaasPackageFeature(
                package_id=package_id,
                feature_key=item.feature_key,
                feature_name=item.feature_name,
                feature_description=item.feature_description,
                is_included=item.is_included,
                limit_value=item.limit_value,
                sort_order=item.sort_order,
            )
        )
    db.flush()


def list_landing_sections(
    db: Session,
    *,
    page_slug: str | None,
    locale: str | None,
    published_only: bool,
    page: int,
    items_per_page: int,
) -> tuple[list[LandingPageSection], int]:
    stmt = select(LandingPageSection).where(LandingPageSection.deleted_at.is_(None))
    if page_slug:
        stmt = stmt.where(LandingPageSection.page_slug == page_slug)
    if locale:
        stmt = stmt.where(LandingPageSection.locale == locale)
    if published_only:
        stmt = stmt.where(LandingPageSection.is_published.is_(True))
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(
        LandingPageSection.sort_order.asc(), LandingPageSection.id.asc()
    )
    rows = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return rows, total_items


def get_landing_section_by_id(
    db: Session, *, section_id: int, include_deleted: bool = False
) -> LandingPageSection | None:
    stmt = select(LandingPageSection).where(LandingPageSection.id == section_id)
    if not include_deleted:
        stmt = stmt.where(LandingPageSection.deleted_at.is_(None))
    return db.scalar(stmt)


def get_landing_section_by_key(
    db: Session,
    *,
    page_slug: str,
    locale: str,
    section_key: str,
    exclude_id: int | None = None,
) -> LandingPageSection | None:
    stmt = select(LandingPageSection).where(
        LandingPageSection.page_slug == page_slug,
        LandingPageSection.locale == locale,
        LandingPageSection.section_key == section_key,
        LandingPageSection.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(LandingPageSection.id != exclude_id)
    return db.scalar(stmt)


def count_total_users(db: Session) -> int:
    return int(
        db.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0
    )


def count_active_users(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        or 0
    )


def count_total_teams(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(Team.id)).where(
                Team.deleted_at.is_(None),
                Team.is_active.is_(True),
            )
        )
        or 0
    )


def get_last_user_registered_at(db: Session):
    return db.scalar(select(func.max(User.created_at)).where(User.deleted_at.is_(None)))


def sum_total_revenue(db: Session) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(UserSubscription.price_amount), 0)).where(
            UserSubscription.deleted_at.is_(None),
            UserSubscription.price_amount > 0,
        )
    ) or Decimal("0")


def sum_mrr_estimate(db: Session) -> Decimal:
    now = datetime.now(timezone.utc)
    monthly_equivalent = case(
        (
            UserSubscription.billing_cycle == SubscriptionBillingCycleEnum.YEARLY,
            UserSubscription.price_amount / 12,
        ),
        else_=UserSubscription.price_amount,
    )

    return db.scalar(
        select(func.coalesce(func.sum(monthly_equivalent), 0)).where(
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
        )
    ) or Decimal("0")


def count_paid_active_subscriptions(db: Session) -> int:
    now = datetime.now(timezone.utc)
    return int(
        db.scalar(
            select(func.count(UserSubscription.id)).where(
                UserSubscription.deleted_at.is_(None),
                UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
                UserSubscription.price_amount > 0,
                or_(
                    UserSubscription.ended_at.is_(None),
                    UserSubscription.ended_at >= now,
                ),
            )
        )
        or 0
    )


def list_package_subscriber_counts(db: Session) -> list[tuple[SaasPackage, int]]:
    now = datetime.now(timezone.utc)
    latest_active_subscription = (
        select(
            UserSubscription.user_id.label("user_id"),
            func.max(UserSubscription.id).label("subscription_id"),
        )
        .where(
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
        )
        .group_by(UserSubscription.user_id)
        .subquery()
    )

    stmt = (
        select(SaasPackage, func.count(latest_active_subscription.c.user_id))
        .select_from(latest_active_subscription)
        .join(
            UserSubscription,
            UserSubscription.id == latest_active_subscription.c.subscription_id,
        )
        .join(SaasPackage, SaasPackage.id == UserSubscription.package_id)
        .where(SaasPackage.deleted_at.is_(None))
        .group_by(SaasPackage.id)
        .order_by(SaasPackage.sort_order.asc(), SaasPackage.id.asc())
    )
    return [(row[0], int(row[1] or 0)) for row in db.execute(stmt).all()]


def list_users(
    db: Session,
    *,
    page: int,
    items_per_page: int,
    search: str | None,
) -> tuple[list[User], int]:
    stmt = select(User).where(User.deleted_at.is_(None))
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(keyword),
                User.full_name.ilike(keyword),
            )
        )
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = int(db.scalar(total_stmt) or 0)
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    rows = list(
        db.scalars(stmt.offset((page - 1) * items_per_page).limit(items_per_page)).all()
    )
    return rows, total_items


def get_user_by_id(db: Session, *, user_id: int) -> User | None:
    return db.scalar(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )


def list_active_subscriptions_for_user(
    db: Session, *, user_id: int
) -> list[UserSubscription]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.deleted_at.is_(None),
            UserSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                UserSubscription.ended_at.is_(None),
                UserSubscription.ended_at >= now,
            ),
        )
        .order_by(UserSubscription.started_at.desc(), UserSubscription.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_latest_active_subscription_for_user(
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
        )
        .order_by(UserSubscription.started_at.desc(), UserSubscription.id.desc())
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return row[0], row[1]


__all__ = [
    "get_platform_admin_by_email",
    "list_permissions",
    "get_permission_by_code",
    "list_packages",
    "get_package_by_id",
    "get_package_by_code",
    "list_package_features",
    "replace_package_features",
    "list_landing_sections",
    "get_landing_section_by_id",
    "get_landing_section_by_key",
    "count_total_users",
    "count_active_users",
    "count_total_teams",
    "get_last_user_registered_at",
    "sum_total_revenue",
    "sum_mrr_estimate",
    "count_paid_active_subscriptions",
    "list_package_subscriber_counts",
    "list_users",
    "get_user_by_id",
    "list_active_subscriptions_for_user",
    "get_latest_active_subscription_for_user",
]
