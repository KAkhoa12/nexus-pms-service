"""add saas packages and landing sections

Revision ID: ee56ff78aa90
Revises: dd45ee67ff89
Create Date: 2026-03-15 22:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee56ff78aa90"
down_revision: Union[str, Sequence[str], None] = "dd45ee67ff89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_permission(
    bind: sa.Connection, code: str, module: str, description: str
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module, description)
            SELECT :code, :module, :description
            WHERE NOT EXISTS (
                SELECT 1
                FROM permissions
                WHERE code = :code
            )
            """
        ),
        {
            "code": code,
            "module": module,
            "description": description,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("saas_packages"):
        op.create_table(
            "saas_packages",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("tagline", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "monthly_price",
                sa.Numeric(precision=18, scale=2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("yearly_price", sa.Numeric(precision=18, scale=2), nullable=True),
            sa.Column(
                "currency",
                sa.String(length=8),
                nullable=False,
                server_default="VND",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_users", sa.Integer(), nullable=True),
            sa.Column("max_rooms", sa.Integer(), nullable=True),
            sa.Column(
                "ai_task_management_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("ai_quota_monthly", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_saas_packages_code"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("saas_packages"):
        package_indexes = {
            index["name"] for index in inspector.get_indexes("saas_packages")
        }
        if "ix_saas_packages_is_active" not in package_indexes:
            op.create_index(
                "ix_saas_packages_is_active",
                "saas_packages",
                ["is_active"],
                unique=False,
            )
        if "ix_saas_packages_active_sort" not in package_indexes:
            op.create_index(
                "ix_saas_packages_active_sort",
                "saas_packages",
                ["is_active", "sort_order"],
                unique=False,
            )

    if not inspector.has_table("saas_package_features"):
        op.create_table(
            "saas_package_features",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("package_id", sa.BigInteger(), nullable=False),
            sa.Column("feature_key", sa.String(length=64), nullable=False),
            sa.Column("feature_name", sa.String(length=255), nullable=False),
            sa.Column("feature_description", sa.String(length=255), nullable=True),
            sa.Column("is_included", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("limit_value", sa.String(length=64), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["package_id"], ["saas_packages.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "package_id",
                "feature_key",
                name="uq_saas_package_features_package_feature_key",
            ),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("saas_package_features"):
        feature_indexes = {
            index["name"] for index in inspector.get_indexes("saas_package_features")
        }
        if "ix_saas_package_features_package_id" not in feature_indexes:
            op.create_index(
                "ix_saas_package_features_package_id",
                "saas_package_features",
                ["package_id"],
                unique=False,
            )

    if not inspector.has_table("tenant_subscriptions"):
        op.create_table(
            "tenant_subscriptions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("package_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "TRIAL",
                    "ACTIVE",
                    "EXPIRED",
                    "CANCELLED",
                    name="subscription_status_enum",
                ),
                nullable=False,
            ),
            sa.Column(
                "billing_cycle",
                sa.Enum("MONTHLY", "YEARLY", name="subscription_billing_cycle_enum"),
                nullable=False,
            ),
            sa.Column(
                "price_amount",
                sa.Numeric(precision=18, scale=2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "currency",
                sa.String(length=8),
                nullable=False,
                server_default="VND",
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["package_id"], ["saas_packages.id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("tenant_subscriptions"):
        subscription_indexes = {
            index["name"] for index in inspector.get_indexes("tenant_subscriptions")
        }
        if "ix_tenant_subscriptions_tenant_id" not in subscription_indexes:
            op.create_index(
                "ix_tenant_subscriptions_tenant_id",
                "tenant_subscriptions",
                ["tenant_id"],
                unique=False,
            )
        if "ix_tenant_subscriptions_package_id" not in subscription_indexes:
            op.create_index(
                "ix_tenant_subscriptions_package_id",
                "tenant_subscriptions",
                ["package_id"],
                unique=False,
            )
        if "ix_tenant_subscriptions_tenant_status" not in subscription_indexes:
            op.create_index(
                "ix_tenant_subscriptions_tenant_status",
                "tenant_subscriptions",
                ["tenant_id", "status"],
                unique=False,
            )

    if not inspector.has_table("landing_page_sections"):
        op.create_table(
            "landing_page_sections",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column(
                "page_slug", sa.String(length=64), nullable=False, server_default="home"
            ),
            sa.Column(
                "locale", sa.String(length=10), nullable=False, server_default="vi-VN"
            ),
            sa.Column("section_key", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("subtitle", sa.Text(), nullable=True),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.Column("content_json", sa.Text(), nullable=True),
            sa.Column("cta_label", sa.String(length=128), nullable=True),
            sa.Column("cta_url", sa.String(length=255), nullable=True),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "page_slug",
                "locale",
                "section_key",
                name="uq_landing_page_sections_key",
            ),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("landing_page_sections"):
        landing_indexes = {
            index["name"] for index in inspector.get_indexes("landing_page_sections")
        }
        if "ix_landing_page_sections_publish_sort" not in landing_indexes:
            op.create_index(
                "ix_landing_page_sections_publish_sort",
                "landing_page_sections",
                ["page_slug", "locale", "is_published", "sort_order"],
                unique=False,
            )

    if inspector.has_table("permissions"):
        _ensure_permission(
            bind,
            code="platform:developer:access",
            module="platform",
            description="Truy cap trang quan tri nen tang",
        )
        _ensure_permission(
            bind,
            code="platform:plans:view",
            module="platform",
            description="Xem danh sach goi dich vu",
        )
        _ensure_permission(
            bind,
            code="platform:plans:update",
            module="platform",
            description="Cap nhat goi dich vu",
        )
        _ensure_permission(
            bind,
            code="platform:landing:view",
            module="platform",
            description="Xem noi dung landing page",
        )
        _ensure_permission(
            bind,
            code="platform:landing:update",
            module="platform",
            description="Cap nhat noi dung landing page",
        )

    if inspector.has_table("saas_packages"):
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_packages (
                    code,
                    name,
                    tagline,
                    description,
                    monthly_price,
                    yearly_price,
                    currency,
                    is_active,
                    is_featured,
                    sort_order,
                    max_users,
                    max_rooms,
                    ai_task_management_enabled,
                    ai_quota_monthly,
                    created_at,
                    updated_at
                )
                SELECT
                    'FREE',
                    'Goi Free',
                    'Bat dau nhanh cho chu tro nho',
                    'Quan ly phong tro co ban cho ca nhan va ho kinh doanh.',
                    0,
                    0,
                    'VND',
                    1,
                    0,
                    1,
                    3,
                    50,
                    0,
                    NULL,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM saas_packages WHERE code = 'FREE'
                )
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_packages (
                    code,
                    name,
                    tagline,
                    description,
                    monthly_price,
                    yearly_price,
                    currency,
                    is_active,
                    is_featured,
                    sort_order,
                    max_users,
                    max_rooms,
                    ai_task_management_enabled,
                    ai_quota_monthly,
                    created_at,
                    updated_at
                )
                SELECT
                    'PRO',
                    'Goi Pro',
                    'Tang truong voi AI quan ly cong viec',
                    'Day du nghiep vu quan ly phong tro va tro ly AI cho van hanh.',
                    299000,
                    2990000,
                    'VND',
                    1,
                    1,
                    2,
                    NULL,
                    NULL,
                    1,
                    5000,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM saas_packages WHERE code = 'PRO'
                )
                """
            )
        )

    if inspector.has_table("saas_package_features"):
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_package_features (
                    package_id,
                    feature_key,
                    feature_name,
                    feature_description,
                    is_included,
                    limit_value,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    p.id,
                    'ROOM_MANAGEMENT',
                    'Quan ly phong tro',
                    'Quan ly phong, nguoi thue, hop dong, hoa don co ban',
                    1,
                    NULL,
                    1,
                    NOW(),
                    NOW()
                FROM saas_packages p
                WHERE p.code = 'FREE'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM saas_package_features f
                      WHERE f.package_id = p.id
                        AND f.feature_key = 'ROOM_MANAGEMENT'
                  )
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_package_features (
                    package_id,
                    feature_key,
                    feature_name,
                    feature_description,
                    is_included,
                    limit_value,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    p.id,
                    'AI_TASK_MANAGEMENT',
                    'AI quan ly cong viec',
                    'Tu dong tao va nhac viec theo van hanh nha tro',
                    0,
                    'Khong ho tro',
                    2,
                    NOW(),
                    NOW()
                FROM saas_packages p
                WHERE p.code = 'FREE'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM saas_package_features f
                      WHERE f.package_id = p.id
                        AND f.feature_key = 'AI_TASK_MANAGEMENT'
                  )
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_package_features (
                    package_id,
                    feature_key,
                    feature_name,
                    feature_description,
                    is_included,
                    limit_value,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    p.id,
                    'ROOM_MANAGEMENT',
                    'Quan ly phong tro',
                    'Day du module quan ly phong tro da tenant',
                    1,
                    NULL,
                    1,
                    NOW(),
                    NOW()
                FROM saas_packages p
                WHERE p.code = 'PRO'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM saas_package_features f
                      WHERE f.package_id = p.id
                        AND f.feature_key = 'ROOM_MANAGEMENT'
                  )
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO saas_package_features (
                    package_id,
                    feature_key,
                    feature_name,
                    feature_description,
                    is_included,
                    limit_value,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    p.id,
                    'AI_TASK_MANAGEMENT',
                    'AI quan ly cong viec',
                    'Bao gom AI assignment, nhac viec va tong hop cong viec',
                    1,
                    '5000 request/thang',
                    2,
                    NOW(),
                    NOW()
                FROM saas_packages p
                WHERE p.code = 'PRO'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM saas_package_features f
                      WHERE f.package_id = p.id
                        AND f.feature_key = 'AI_TASK_MANAGEMENT'
                  )
                """
            )
        )

    if inspector.has_table("landing_page_sections"):
        bind.execute(
            sa.text(
                """
                INSERT INTO landing_page_sections (
                    page_slug,
                    locale,
                    section_key,
                    title,
                    subtitle,
                    body_text,
                    content_json,
                    cta_label,
                    cta_url,
                    is_published,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    'home',
                    'vi-VN',
                    'hero',
                    'Nen tang SaaS quan ly phong tro va van hanh AI',
                    'Danh cho chu tro ca nhan den doanh nghiep',
                    'Bat dau voi goi Free de quan ly phong tro. Nang cap Pro khi can AI quan ly cong viec.',
                    '{"highlight":"Free + Pro","theme":"sunset-teal"}',
                    'Dang ky dung thu',
                    '/dashboard/login',
                    1,
                    1,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM landing_page_sections
                    WHERE page_slug = 'home'
                      AND locale = 'vi-VN'
                      AND section_key = 'hero'
                )
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO landing_page_sections (
                    page_slug,
                    locale,
                    section_key,
                    title,
                    subtitle,
                    body_text,
                    content_json,
                    cta_label,
                    cta_url,
                    is_published,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    'home',
                    'vi-VN',
                    'pricing',
                    'Hai goi dich vu ro rang cho tung giai doan',
                    'Free cho van hanh co ban, Pro cho tang truong voi AI',
                    'Bang gia co the thay doi trong dashboard developer.',
                    '{"plans":["FREE","PRO"]}',
                    'Xem bang gia',
                    '/#pricing',
                    1,
                    2,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM landing_page_sections
                    WHERE page_slug = 'home'
                      AND locale = 'vi-VN'
                      AND section_key = 'pricing'
                )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("permissions"):
        bind.execute(
            sa.text(
                """
                DELETE FROM permissions
                WHERE code IN (
                    'platform:developer:access',
                    'platform:plans:view',
                    'platform:plans:update',
                    'platform:landing:view',
                    'platform:landing:update'
                )
                """
            )
        )

    if inspector.has_table("landing_page_sections"):
        landing_indexes = {
            index["name"] for index in inspector.get_indexes("landing_page_sections")
        }
        if "ix_landing_page_sections_publish_sort" in landing_indexes:
            op.drop_index(
                "ix_landing_page_sections_publish_sort",
                table_name="landing_page_sections",
            )
        op.drop_table("landing_page_sections")

    inspector = sa.inspect(bind)
    if inspector.has_table("tenant_subscriptions"):
        subscription_indexes = {
            index["name"] for index in inspector.get_indexes("tenant_subscriptions")
        }
        if "ix_tenant_subscriptions_tenant_status" in subscription_indexes:
            op.drop_index(
                "ix_tenant_subscriptions_tenant_status",
                table_name="tenant_subscriptions",
            )
        if "ix_tenant_subscriptions_package_id" in subscription_indexes:
            op.drop_index(
                "ix_tenant_subscriptions_package_id",
                table_name="tenant_subscriptions",
            )
        if "ix_tenant_subscriptions_tenant_id" in subscription_indexes:
            op.drop_index(
                "ix_tenant_subscriptions_tenant_id",
                table_name="tenant_subscriptions",
            )
        op.drop_table("tenant_subscriptions")

    inspector = sa.inspect(bind)
    if inspector.has_table("saas_package_features"):
        feature_indexes = {
            index["name"] for index in inspector.get_indexes("saas_package_features")
        }
        if "ix_saas_package_features_package_id" in feature_indexes:
            op.drop_index(
                "ix_saas_package_features_package_id",
                table_name="saas_package_features",
            )
        op.drop_table("saas_package_features")

    inspector = sa.inspect(bind)
    if inspector.has_table("saas_packages"):
        package_indexes = {
            index["name"] for index in inspector.get_indexes("saas_packages")
        }
        if "ix_saas_packages_active_sort" in package_indexes:
            op.drop_index("ix_saas_packages_active_sort", table_name="saas_packages")
        if "ix_saas_packages_is_active" in package_indexes:
            op.drop_index("ix_saas_packages_is_active", table_name="saas_packages")
        op.drop_table("saas_packages")
