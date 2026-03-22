from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_admin, get_db
from app.core.config import settings
from app.core.response import (
    ApiResponse,
    PaginatedResult,
    build_paginated_result,
    success_response,
)
from app.modules.core.models import PlatformAdmin
from app.modules.developer_portal.schemas import (
    DeveloperAdminMeResponse,
    DeveloperLoginRequest,
    DeveloperOverviewOut,
    DeveloperPermissionDescriptionUpdateRequest,
    DeveloperPermissionOut,
    DeveloperTokenResponse,
    DeveloperUserOut,
    DeveloperUserPackageUpdateRequest,
    LandingSectionOut,
    LandingSectionUpsertRequest,
    SaasPackageOut,
    SaasPackageUpsertRequest,
)
from app.modules.developer_portal.service import (
    authenticate_platform_admin,
    build_developer_access_token,
    create_landing_section,
    create_package,
    get_developer_overview,
    list_developer_users,
    list_landing_sections,
    list_packages,
    list_permissions_for_developer,
    update_landing_section,
    update_package,
    update_permission_description,
    update_user_subscription,
)

router = APIRouter()


@router.post("/auth/login", response_model=ApiResponse[DeveloperTokenResponse])
def developer_login(
    payload: DeveloperLoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[DeveloperTokenResponse]:
    admin = authenticate_platform_admin(
        db,
        email=str(payload.email),
        password=payload.password,
    )
    token = DeveloperTokenResponse(
        access_token=build_developer_access_token(admin),
        expires_in=settings.DEVELOPER_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return success_response(token, message="Đăng nhập developer thành công")


@router.get("/auth/me", response_model=ApiResponse[DeveloperAdminMeResponse])
def developer_me(
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[DeveloperAdminMeResponse]:
    profile = DeveloperAdminMeResponse(
        id=current_admin.id,
        email=current_admin.email,
        full_name=current_admin.full_name,
        is_active=current_admin.is_active,
        last_login_at=current_admin.last_login_at,
    )
    return success_response(profile, message="Developer profile")


@router.get("/overview", response_model=ApiResponse[DeveloperOverviewOut])
def get_overview(
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[DeveloperOverviewOut]:
    result = get_developer_overview(db, current_admin)
    return success_response(result, message="System overview fetched successfully")


@router.get("/users", response_model=ApiResponse[PaginatedResult[DeveloperUserOut]])
def get_users(
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[PaginatedResult[DeveloperUserOut]]:
    users, total_items = list_developer_users(
        db,
        current_admin,
        page=page,
        items_per_page=items_per_page,
        search=search,
    )
    result = build_paginated_result(
        items=users,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Users fetched successfully")


@router.get(
    "/permissions",
    response_model=ApiResponse[PaginatedResult[DeveloperPermissionOut]],
)
def get_permissions(
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    module: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[PaginatedResult[DeveloperPermissionOut]]:
    permissions, total_items = list_permissions_for_developer(
        db,
        current_admin,
        page=page,
        items_per_page=items_per_page,
        search=search,
        module=module,
    )
    result = build_paginated_result(
        items=permissions,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Permissions fetched successfully")


@router.patch(
    "/permissions/{permission_code}/description",
    response_model=ApiResponse[DeveloperPermissionOut],
)
def edit_permission_description(
    permission_code: str,
    payload: DeveloperPermissionDescriptionUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[DeveloperPermissionOut]:
    result = update_permission_description(
        db,
        current_admin,
        permission_code=permission_code,
        payload=payload,
    )
    return success_response(result, message="Permission description updated")


@router.put(
    "/users/{user_id}/subscription", response_model=ApiResponse[DeveloperUserOut]
)
def set_user_subscription(
    user_id: int,
    payload: DeveloperUserPackageUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[DeveloperUserOut]:
    updated_user = update_user_subscription(
        db,
        current_admin,
        user_id=user_id,
        payload=payload,
    )
    return success_response(updated_user, message="User subscription updated")


@router.get("/plans", response_model=ApiResponse[PaginatedResult[SaasPackageOut]])
def get_plans(
    include_inactive: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[PaginatedResult[SaasPackageOut]]:
    plans, total_items = list_packages(
        db,
        current_admin,
        include_inactive=include_inactive,
        page=page,
        items_per_page=items_per_page,
    )
    result = build_paginated_result(
        items=plans,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Plans fetched successfully")


@router.post("/plans", response_model=ApiResponse[SaasPackageOut])
def add_plan(
    payload: SaasPackageUpsertRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[SaasPackageOut]:
    result = create_package(db, current_admin, payload)
    return success_response(result, message="Plan created successfully")


@router.put("/plans/{plan_id}", response_model=ApiResponse[SaasPackageOut])
def edit_plan(
    plan_id: int,
    payload: SaasPackageUpsertRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[SaasPackageOut]:
    result = update_package(db, current_admin, package_id=plan_id, payload=payload)
    return success_response(result, message="Plan updated successfully")


@router.get(
    "/landing-sections",
    response_model=ApiResponse[PaginatedResult[LandingSectionOut]],
)
def get_landing_content(
    page_slug: str | None = Query(default="home"),
    locale: str | None = Query(default="vi-VN"),
    published_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    items_per_page: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[PaginatedResult[LandingSectionOut]]:
    sections, total_items = list_landing_sections(
        db,
        current_admin,
        page_slug=page_slug,
        locale=locale,
        published_only=published_only,
        page=page,
        items_per_page=items_per_page,
    )
    result = build_paginated_result(
        items=sections,
        total_items=total_items,
        page=page,
        items_per_page=items_per_page,
    )
    return success_response(result, message="Landing sections fetched successfully")


@router.post("/landing-sections", response_model=ApiResponse[LandingSectionOut])
def add_landing_section(
    payload: LandingSectionUpsertRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[LandingSectionOut]:
    result = create_landing_section(db, current_admin, payload)
    return success_response(result, message="Landing section created successfully")


@router.put(
    "/landing-sections/{section_id}",
    response_model=ApiResponse[LandingSectionOut],
)
def edit_landing_section(
    section_id: int,
    payload: LandingSectionUpsertRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ApiResponse[LandingSectionOut]:
    result = update_landing_section(
        db, current_admin, section_id=section_id, payload=payload
    )
    return success_response(result, message="Landing section updated successfully")
