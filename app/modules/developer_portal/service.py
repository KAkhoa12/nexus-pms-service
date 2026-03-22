from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.modules.core.models import (
    LandingPageSection,
    Permission,
    PlatformAdmin,
    SaasPackage,
    SubscriptionBillingCycleEnum,
    SubscriptionStatusEnum,
    User,
    UserSubscription,
)
from app.modules.developer_portal import repository
from app.modules.developer_portal.schemas import (
    DeveloperOverviewOut,
    DeveloperPermissionDescriptionUpdateRequest,
    DeveloperPermissionOut,
    DeveloperUserOut,
    DeveloperUserPackageUpdateRequest,
    DeveloperUserSubscriptionOut,
    LandingSectionOut,
    LandingSectionUpsertRequest,
    PackageSubscriberCountOut,
    SaasPackageFeatureOut,
    SaasPackageOut,
    SaasPackageUpsertRequest,
)

MAX_ITEMS_PER_PAGE = 200


def _ensure_active_admin(current_admin: PlatformAdmin) -> None:
    if not current_admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer account is inactive",
        )


def _to_feature_out(item) -> SaasPackageFeatureOut:
    return SaasPackageFeatureOut(
        id=item.id,
        feature_key=item.feature_key,
        feature_name=item.feature_name,
        feature_description=item.feature_description,
        is_included=item.is_included,
        limit_value=item.limit_value,
        sort_order=item.sort_order,
    )


def _to_package_out(item: SaasPackage, feature_map: dict[int, list]) -> SaasPackageOut:
    features = feature_map.get(item.id, [])
    return SaasPackageOut(
        id=item.id,
        code=item.code,
        name=item.name,
        tagline=item.tagline,
        description=item.description,
        monthly_price=item.monthly_price,
        yearly_price=item.yearly_price,
        currency=item.currency,
        is_active=item.is_active,
        is_featured=item.is_featured,
        sort_order=item.sort_order,
        max_users=item.max_users,
        max_rooms=item.max_rooms,
        ai_task_management_enabled=item.ai_task_management_enabled,
        ai_quota_monthly=item.ai_quota_monthly,
        created_at=item.created_at,
        updated_at=item.updated_at,
        features=[_to_feature_out(feature) for feature in features],
    )


def _to_permission_out(item: Permission) -> DeveloperPermissionOut:
    return DeveloperPermissionOut(
        code=item.code,
        module=item.module,
        module_mean=item.module_mean,
        description=item.description,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_landing_out(item: LandingPageSection) -> LandingSectionOut:
    return LandingSectionOut(
        id=item.id,
        page_slug=item.page_slug,
        locale=item.locale,
        section_key=item.section_key,
        title=item.title,
        subtitle=item.subtitle,
        body_text=item.body_text,
        content_json=item.content_json,
        cta_label=item.cta_label,
        cta_url=item.cta_url,
        is_published=item.is_published,
        sort_order=item.sort_order,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_subscription_out(
    row: tuple[UserSubscription, SaasPackage] | None,
) -> DeveloperUserSubscriptionOut | None:
    if row is None:
        return None
    subscription, package = row
    return DeveloperUserSubscriptionOut(
        id=subscription.id,
        package_id=package.id,
        package_code=package.code,
        package_name=package.name,
        status=subscription.status.value,
        billing_cycle=subscription.billing_cycle.value,
        price_amount=subscription.price_amount,
        currency=subscription.currency,
        started_at=subscription.started_at,
        ended_at=subscription.ended_at,
        auto_renew=subscription.auto_renew,
        note=subscription.note,
    )


def _to_user_out(
    user: User, row: tuple[UserSubscription, SaasPackage] | None
) -> DeveloperUserOut:
    return DeveloperUserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        subscription=_to_subscription_out(row),
    )


def build_developer_access_token(admin: PlatformAdmin) -> str:
    return create_access_token(
        subject=str(admin.id),
        extra_claims={
            "scope": "developer_portal",
            "email": admin.email,
        },
        expires_minutes=settings.DEVELOPER_ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def authenticate_platform_admin(
    db: Session,
    *,
    email: str,
    password: str,
) -> PlatformAdmin:
    normalized_email = email.strip().lower()
    admin = repository.get_platform_admin_by_email(db, email=normalized_email)
    if admin is None or not verify_password(password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu developer không đúng",
        )
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản developer đang bị khóa",
        )

    admin.last_login_at = datetime.now(timezone.utc)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def get_developer_overview(
    db: Session,
    current_admin: PlatformAdmin,
) -> DeveloperOverviewOut:
    _ensure_active_admin(current_admin)
    package_distribution = [
        PackageSubscriberCountOut(
            package_id=package.id,
            package_code=package.code,
            package_name=package.name,
            subscriber_count=subscriber_count,
        )
        for package, subscriber_count in repository.list_package_subscriber_counts(db)
    ]

    return DeveloperOverviewOut(
        total_users=repository.count_total_users(db),
        active_users=repository.count_active_users(db),
        total_teams=repository.count_total_teams(db),
        total_paid_subscriptions=repository.count_paid_active_subscriptions(db),
        total_revenue=repository.sum_total_revenue(db),
        mrr_estimate=repository.sum_mrr_estimate(db),
        currency="VND",
        last_user_registered_at=repository.get_last_user_registered_at(db),
        package_distribution=package_distribution,
    )


def list_developer_users(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    page: int,
    items_per_page: int,
    search: str | None,
) -> tuple[list[DeveloperUserOut], int]:
    _ensure_active_admin(current_admin)
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page must be between 1 and {MAX_ITEMS_PER_PAGE}",
        )

    rows, total_items = repository.list_users(
        db,
        page=page,
        items_per_page=items_per_page,
        search=search,
    )
    items = [
        _to_user_out(
            user,
            repository.get_latest_active_subscription_for_user(db, user_id=user.id),
        )
        for user in rows
    ]
    return items, total_items


def list_permissions_for_developer(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    page: int,
    items_per_page: int,
    search: str | None,
    module: str | None,
) -> tuple[list[DeveloperPermissionOut], int]:
    _ensure_active_admin(current_admin)
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page must be between 1 and {MAX_ITEMS_PER_PAGE}",
        )

    rows, total_items = repository.list_permissions(
        db,
        page=page,
        items_per_page=items_per_page,
        search=search,
        module=module,
    )
    return [_to_permission_out(item) for item in rows], total_items


def update_permission_description(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    permission_code: str,
    payload: DeveloperPermissionDescriptionUpdateRequest,
) -> DeveloperPermissionOut:
    _ensure_active_admin(current_admin)
    permission = repository.get_permission_by_code(db, permission_code=permission_code)
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    permission.description = (payload.description or "").strip() or None
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return _to_permission_out(permission)


def update_user_subscription(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    user_id: int,
    payload: DeveloperUserPackageUpdateRequest,
) -> DeveloperUserOut:
    _ensure_active_admin(current_admin)

    user = repository.get_user_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    package = None
    if payload.package_id is not None:
        package = repository.get_package_by_id(db, package_id=payload.package_id)
    elif payload.package_code:
        package = repository.get_package_by_code(
            db,
            code=payload.package_code.strip().upper(),
        )

    if package is None or package.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    if not package.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Package is inactive",
        )

    now = datetime.now(timezone.utc)
    active_subscriptions = repository.list_active_subscriptions_for_user(
        db, user_id=user.id
    )
    for subscription in active_subscriptions:
        subscription.status = SubscriptionStatusEnum.CANCELLED
        subscription.ended_at = now
        subscription.auto_renew = False
        previous_note = (subscription.note or "").strip()
        cancel_note = (
            f"Cancelled by platform admin {current_admin.email} at {now.isoformat()}"
        )
        subscription.note = (
            f"{previous_note}\n{cancel_note}".strip() if previous_note else cancel_note
        )
        db.add(subscription)

    if payload.billing_cycle == SubscriptionBillingCycleEnum.YEARLY:
        price_amount = package.yearly_price
        if price_amount is None:
            price_amount = package.monthly_price * Decimal("12")
    else:
        price_amount = package.monthly_price

    admin_note = f"Assigned by platform admin {current_admin.email}"
    custom_note = (payload.note or "").strip()
    note = f"{custom_note} ({admin_note})" if custom_note else admin_note

    new_subscription = UserSubscription(
        user_id=user.id,
        package_id=package.id,
        status=SubscriptionStatusEnum.ACTIVE,
        billing_cycle=payload.billing_cycle,
        price_amount=price_amount,
        currency=package.currency,
        started_at=now,
        ended_at=None,
        auto_renew=True,
        note=note,
    )
    db.add(new_subscription)
    db.commit()

    latest_subscription = repository.get_latest_active_subscription_for_user(
        db,
        user_id=user.id,
    )
    if latest_subscription is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign subscription",
        )

    db.refresh(user)
    return _to_user_out(user, latest_subscription)


def list_packages(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    include_inactive: bool,
    page: int,
    items_per_page: int,
) -> tuple[list[SaasPackageOut], int]:
    _ensure_active_admin(current_admin)
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page must be between 1 and {MAX_ITEMS_PER_PAGE}",
        )

    rows, total_items = repository.list_packages(
        db,
        include_inactive=include_inactive,
        page=page,
        items_per_page=items_per_page,
    )
    feature_map = repository.list_package_features(
        db, package_ids=[row.id for row in rows]
    )
    return [_to_package_out(row, feature_map) for row in rows], total_items


def create_package(
    db: Session, current_admin: PlatformAdmin, payload: SaasPackageUpsertRequest
) -> SaasPackageOut:
    _ensure_active_admin(current_admin)
    normalized_code = payload.code.strip().upper()
    if repository.get_package_by_code(db, code=normalized_code) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package code already exists",
        )

    package = SaasPackage(
        code=normalized_code,
        name=payload.name.strip(),
        tagline=payload.tagline,
        description=payload.description,
        monthly_price=payload.monthly_price,
        yearly_price=payload.yearly_price,
        currency=payload.currency.strip().upper(),
        is_active=payload.is_active,
        is_featured=payload.is_featured,
        sort_order=payload.sort_order,
        max_users=payload.max_users,
        max_rooms=payload.max_rooms,
        ai_task_management_enabled=payload.ai_task_management_enabled,
        ai_quota_monthly=(
            payload.ai_quota_monthly if payload.ai_task_management_enabled else None
        ),
    )
    db.add(package)
    db.flush()
    repository.replace_package_features(
        db, package_id=package.id, features=payload.features
    )
    db.commit()
    db.refresh(package)
    feature_map = repository.list_package_features(db, package_ids=[package.id])
    return _to_package_out(package, feature_map)


def update_package(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    package_id: int,
    payload: SaasPackageUpsertRequest,
) -> SaasPackageOut:
    _ensure_active_admin(current_admin)
    package = repository.get_package_by_id(db, package_id=package_id)
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    normalized_code = payload.code.strip().upper()
    if (
        repository.get_package_by_code(db, code=normalized_code, exclude_id=package.id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package code already exists",
        )

    package.code = normalized_code
    package.name = payload.name.strip()
    package.tagline = payload.tagline
    package.description = payload.description
    package.monthly_price = payload.monthly_price
    package.yearly_price = payload.yearly_price
    package.currency = payload.currency.strip().upper()
    package.is_active = payload.is_active
    package.is_featured = payload.is_featured
    package.sort_order = payload.sort_order
    package.max_users = payload.max_users
    package.max_rooms = payload.max_rooms
    package.ai_task_management_enabled = payload.ai_task_management_enabled
    package.ai_quota_monthly = (
        payload.ai_quota_monthly if payload.ai_task_management_enabled else None
    )

    db.add(package)
    db.flush()
    repository.replace_package_features(
        db, package_id=package.id, features=payload.features
    )
    db.commit()
    db.refresh(package)
    feature_map = repository.list_package_features(db, package_ids=[package.id])
    return _to_package_out(package, feature_map)


def list_landing_sections(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    page_slug: str | None,
    locale: str | None,
    published_only: bool,
    page: int,
    items_per_page: int,
) -> tuple[list[LandingSectionOut], int]:
    _ensure_active_admin(current_admin)
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1",
        )
    if items_per_page < 1 or items_per_page > MAX_ITEMS_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"items_per_page must be between 1 and {MAX_ITEMS_PER_PAGE}",
        )

    rows, total_items = repository.list_landing_sections(
        db,
        page_slug=page_slug,
        locale=locale,
        published_only=published_only,
        page=page,
        items_per_page=items_per_page,
    )
    return [_to_landing_out(row) for row in rows], total_items


def create_landing_section(
    db: Session,
    current_admin: PlatformAdmin,
    payload: LandingSectionUpsertRequest,
) -> LandingSectionOut:
    _ensure_active_admin(current_admin)
    if (
        repository.get_landing_section_by_key(
            db,
            page_slug=payload.page_slug.strip(),
            locale=payload.locale.strip(),
            section_key=payload.section_key.strip(),
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Landing section key already exists",
        )

    section = LandingPageSection(
        page_slug=payload.page_slug.strip(),
        locale=payload.locale.strip(),
        section_key=payload.section_key.strip(),
        title=payload.title,
        subtitle=payload.subtitle,
        body_text=payload.body_text,
        content_json=payload.content_json,
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
        is_published=payload.is_published,
        sort_order=payload.sort_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return _to_landing_out(section)


def update_landing_section(
    db: Session,
    current_admin: PlatformAdmin,
    *,
    section_id: int,
    payload: LandingSectionUpsertRequest,
) -> LandingSectionOut:
    _ensure_active_admin(current_admin)
    section = repository.get_landing_section_by_id(db, section_id=section_id)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Landing section not found",
        )

    if (
        repository.get_landing_section_by_key(
            db,
            page_slug=payload.page_slug.strip(),
            locale=payload.locale.strip(),
            section_key=payload.section_key.strip(),
            exclude_id=section.id,
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Landing section key already exists",
        )

    section.page_slug = payload.page_slug.strip()
    section.locale = payload.locale.strip()
    section.section_key = payload.section_key.strip()
    section.title = payload.title
    section.subtitle = payload.subtitle
    section.body_text = payload.body_text
    section.content_json = payload.content_json
    section.cta_label = payload.cta_label
    section.cta_url = payload.cta_url
    section.is_published = payload.is_published
    section.sort_order = payload.sort_order

    db.add(section)
    db.commit()
    db.refresh(section)
    return _to_landing_out(section)
