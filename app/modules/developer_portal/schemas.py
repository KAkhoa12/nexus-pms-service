from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.modules.core.models import SubscriptionBillingCycleEnum


class DeveloperLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class DeveloperTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DeveloperAdminMeResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    last_login_at: datetime | None


class PackageSubscriberCountOut(BaseModel):
    package_id: int
    package_code: str
    package_name: str
    subscriber_count: int


class DeveloperOverviewOut(BaseModel):
    total_users: int
    active_users: int
    total_teams: int
    total_paid_subscriptions: int
    total_revenue: Decimal
    mrr_estimate: Decimal
    currency: str
    last_user_registered_at: datetime | None
    package_distribution: list[PackageSubscriberCountOut]


class DeveloperUserSubscriptionOut(BaseModel):
    id: int
    package_id: int
    package_code: str
    package_name: str
    status: str
    billing_cycle: str
    price_amount: Decimal
    currency: str
    started_at: datetime
    ended_at: datetime | None
    auto_renew: bool
    note: str | None


class DeveloperUserOut(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    subscription: DeveloperUserSubscriptionOut | None


class DeveloperUserPackageUpdateRequest(BaseModel):
    package_id: int | None = Field(default=None, ge=1)
    package_code: str | None = Field(default=None, min_length=2, max_length=32)
    billing_cycle: SubscriptionBillingCycleEnum = SubscriptionBillingCycleEnum.MONTHLY
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_package_target(self) -> "DeveloperUserPackageUpdateRequest":
        if self.package_id is None and not self.package_code:
            raise ValueError("package_id or package_code is required")
        return self


class DeveloperPermissionOut(BaseModel):
    code: str
    module: str
    module_mean: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class DeveloperPermissionDescriptionUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=255)


class SaasPackageFeatureInput(BaseModel):
    feature_key: str = Field(min_length=2, max_length=64)
    feature_name: str = Field(min_length=2, max_length=255)
    feature_description: str | None = Field(default=None, max_length=255)
    is_included: bool = True
    limit_value: str | None = Field(default=None, max_length=64)
    sort_order: int = Field(default=0, ge=0)


class SaasPackageFeatureOut(BaseModel):
    id: int
    feature_key: str
    feature_name: str
    feature_description: str | None
    is_included: bool
    limit_value: str | None
    sort_order: int


class SaasPackageUpsertRequest(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=128)
    tagline: str | None = Field(default=None, max_length=255)
    description: str | None = None
    monthly_price: Decimal = Field(ge=0)
    yearly_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="VND", min_length=2, max_length=8)
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=0)
    max_users: int | None = Field(default=None, ge=1)
    max_rooms: int | None = Field(default=None, ge=1)
    ai_task_management_enabled: bool = False
    ai_quota_monthly: int | None = Field(default=None, ge=1)
    features: list[SaasPackageFeatureInput] = Field(default_factory=list)


class SaasPackageOut(BaseModel):
    id: int
    code: str
    name: str
    tagline: str | None
    description: str | None
    monthly_price: Decimal
    yearly_price: Decimal | None
    currency: str
    is_active: bool
    is_featured: bool
    sort_order: int
    max_users: int | None
    max_rooms: int | None
    ai_task_management_enabled: bool
    ai_quota_monthly: int | None
    created_at: datetime
    updated_at: datetime
    features: list[SaasPackageFeatureOut]


class LandingSectionUpsertRequest(BaseModel):
    page_slug: str = Field(default="home", min_length=1, max_length=64)
    locale: str = Field(default="vi-VN", min_length=2, max_length=10)
    section_key: str = Field(min_length=2, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    subtitle: str | None = None
    body_text: str | None = None
    content_json: str | None = None
    cta_label: str | None = Field(default=None, max_length=128)
    cta_url: str | None = Field(default=None, max_length=255)
    is_published: bool = True
    sort_order: int = Field(default=0, ge=0)


class LandingSectionOut(BaseModel):
    id: int
    page_slug: str
    locale: str
    section_key: str
    title: str | None
    subtitle: str | None
    body_text: str | None
    content_json: str | None
    cta_label: str | None
    cta_url: str | None
    is_published: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
