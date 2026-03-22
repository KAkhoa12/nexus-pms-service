"""add google auth, teams, user subscriptions and business package

Revision ID: ff67aa89bb01
Revises: ee56ff78aa90
Create Date: 2026-03-16 00:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff67aa89bb01"
down_revision: Union[str, Sequence[str], None] = "ee56ff78aa90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


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


def _ensure_feature(
    bind: sa.Connection,
    *,
    package_code: str,
    feature_key: str,
    feature_name: str,
    feature_description: str,
    is_included: bool,
    limit_value: str | None,
    sort_order: int,
) -> None:
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
                :feature_key,
                :feature_name,
                :feature_description,
                :is_included,
                :limit_value,
                :sort_order,
                NOW(),
                NOW()
            FROM saas_packages p
            WHERE p.code = :package_code
              AND p.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM saas_package_features f
                  WHERE f.package_id = p.id
                    AND f.feature_key = :feature_key
                    AND f.deleted_at IS NULL
              )
            """
        ),
        {
            "package_code": package_code,
            "feature_key": feature_key,
            "feature_name": feature_name,
            "feature_description": feature_description,
            "is_included": 1 if is_included else 0,
            "limit_value": limit_value,
            "sort_order": sort_order,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("users"):
        if not _has_column(inspector, "users", "auth_provider"):
            op.add_column(
                "users",
                sa.Column(
                    "auth_provider",
                    sa.String(length=32),
                    nullable=False,
                    server_default="password",
                ),
            )
        if not _has_column(inspector, "users", "google_sub"):
            op.add_column(
                "users",
                sa.Column("google_sub", sa.String(length=255), nullable=True),
            )
        if not _has_column(inspector, "users", "avatar_url"):
            op.add_column(
                "users",
                sa.Column("avatar_url", sa.Text(), nullable=True),
            )

    inspector = sa.inspect(bind)
    if inspector.has_table("users"):
        user_indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "uq_users_google_sub" not in user_indexes:
            op.create_index(
                "uq_users_google_sub",
                "users",
                ["google_sub"],
                unique=True,
            )

    if not inspector.has_table("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
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
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["owner_user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "name", name="uq_teams_tenant_name"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("teams"):
        team_indexes = {index["name"] for index in inspector.get_indexes("teams")}
        if "ix_teams_tenant_id" not in team_indexes:
            op.create_index("ix_teams_tenant_id", "teams", ["tenant_id"], unique=False)
        if "ix_teams_owner_user_id" not in team_indexes:
            op.create_index(
                "ix_teams_owner_user_id", "teams", ["owner_user_id"], unique=False
            )
        if "ix_teams_tenant_active" not in team_indexes:
            op.create_index(
                "ix_teams_tenant_active",
                "teams",
                ["tenant_id", "is_active"],
                unique=False,
            )

    if not inspector.has_table("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.BigInteger(), nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("invited_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "member_role",
                sa.Enum("MANAGER", "MEMBER", name="team_member_role_enum"),
                nullable=False,
                server_default="MEMBER",
            ),
            sa.Column("rbac_role_id", sa.BigInteger(), nullable=True),
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
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["invited_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["rbac_role_id"], ["roles.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("team_members"):
        member_indexes = {
            index["name"] for index in inspector.get_indexes("team_members")
        }
        if "ix_team_members_team_id" not in member_indexes:
            op.create_index(
                "ix_team_members_team_id", "team_members", ["team_id"], unique=False
            )
        if "ix_team_members_user_id" not in member_indexes:
            op.create_index(
                "ix_team_members_user_id", "team_members", ["user_id"], unique=False
            )
        if "ix_team_members_team_role" not in member_indexes:
            op.create_index(
                "ix_team_members_team_role",
                "team_members",
                ["team_id", "member_role"],
                unique=False,
            )

    if not inspector.has_table("user_subscriptions"):
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
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
                server_default="MONTHLY",
            ),
            sa.Column(
                "price_amount",
                sa.Numeric(precision=18, scale=2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "currency", sa.String(length=8), nullable=False, server_default="VND"
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
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["package_id"], ["saas_packages.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("user_subscriptions"):
        user_subscription_indexes = {
            index["name"] for index in inspector.get_indexes("user_subscriptions")
        }
        if "ix_user_subscriptions_user_id" not in user_subscription_indexes:
            op.create_index(
                "ix_user_subscriptions_user_id",
                "user_subscriptions",
                ["user_id"],
                unique=False,
            )
        if "ix_user_subscriptions_package_id" not in user_subscription_indexes:
            op.create_index(
                "ix_user_subscriptions_package_id",
                "user_subscriptions",
                ["package_id"],
                unique=False,
            )
        if "ix_user_subscriptions_user_status" not in user_subscription_indexes:
            op.create_index(
                "ix_user_subscriptions_user_status",
                "user_subscriptions",
                ["user_id", "status"],
                unique=False,
            )

    if inspector.has_table("permissions"):
        _ensure_permission(
            bind,
            code="teams:view",
            module="teams",
            description="Xem thong tin team",
        )
        _ensure_permission(
            bind,
            code="teams:create",
            module="teams",
            description="Tao team moi",
        )
        _ensure_permission(
            bind,
            code="teams:members:manage",
            module="teams",
            description="Moi, cap nhat role, kick thanh vien team",
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
                    'BUSINESS',
                    'Goi Business',
                    'Uu dai tu Pro va bo sung chat noi bo',
                    'Bao gom toan bo tinh nang Pro, chat voi he thong AI va chat user noi bo.',
                    599000,
                    5990000,
                    'VND',
                    1,
                    1,
                    3,
                    NULL,
                    NULL,
                    1,
                    15000,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM saas_packages
                    WHERE code = 'BUSINESS'
                )
                """
            )
        )

    if inspector.has_table("saas_package_features"):
        _ensure_feature(
            bind,
            package_code="FREE",
            feature_key="SUNSET_THEME",
            feature_name="Sunset Mint Theme",
            feature_description="Theme cao cap chi danh cho Pro tro len",
            is_included=False,
            limit_value="Khong ho tro",
            sort_order=10,
        )
        _ensure_feature(
            bind,
            package_code="PRO",
            feature_key="SUNSET_THEME",
            feature_name="Sunset Mint Theme",
            feature_description="Mo khoa theme Sunset Mint trong dashboard",
            is_included=True,
            limit_value=None,
            sort_order=10,
        )
        _ensure_feature(
            bind,
            package_code="BUSINESS",
            feature_key="ROOM_MANAGEMENT",
            feature_name="Quan ly phong tro",
            feature_description="Day du module quan ly phong tro da tenant",
            is_included=True,
            limit_value=None,
            sort_order=1,
        )
        _ensure_feature(
            bind,
            package_code="BUSINESS",
            feature_key="AI_TASK_MANAGEMENT",
            feature_name="AI quan ly cong viec",
            feature_description="Bao gom AI assignment, nhac viec va tong hop cong viec",
            is_included=True,
            limit_value="15000 request/thang",
            sort_order=2,
        )
        _ensure_feature(
            bind,
            package_code="BUSINESS",
            feature_key="SUNSET_THEME",
            feature_name="Sunset Mint Theme",
            feature_description="Mo khoa theme Sunset Mint trong dashboard",
            is_included=True,
            limit_value=None,
            sort_order=10,
        )
        _ensure_feature(
            bind,
            package_code="BUSINESS",
            feature_key="INTERNAL_CHAT",
            feature_name="Chat noi bo",
            feature_description="Chat giua cac user trong cung team/doanh nghiep",
            is_included=True,
            limit_value=None,
            sort_order=11,
        )
        _ensure_feature(
            bind,
            package_code="BUSINESS",
            feature_key="AI_CHAT_ASSISTANT",
            feature_name="Chat voi he thong AI",
            feature_description="Tro ly AI ho tro van hanh theo du lieu he thong",
            is_included=True,
            limit_value="4000 request/thang",
            sort_order=12,
        )

    if inspector.has_table("user_subscriptions") and inspector.has_table(
        "saas_packages"
    ):
        bind.execute(
            sa.text(
                """
                INSERT INTO user_subscriptions (
                    user_id,
                    package_id,
                    status,
                    billing_cycle,
                    price_amount,
                    currency,
                    started_at,
                    ended_at,
                    auto_renew,
                    note,
                    created_at,
                    updated_at
                )
                SELECT
                    u.id,
                    p.id,
                    'ACTIVE',
                    'MONTHLY',
                    0,
                    'VND',
                    NOW(),
                    NULL,
                    1,
                    'Default FREE package',
                    NOW(),
                    NOW()
                FROM users u
                JOIN saas_packages p
                  ON p.code = 'FREE'
                 AND p.deleted_at IS NULL
                WHERE u.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM user_subscriptions us
                      WHERE us.user_id = u.id
                        AND us.deleted_at IS NULL
                        AND us.status IN ('TRIAL', 'ACTIVE')
                        AND (us.ended_at IS NULL OR us.ended_at >= NOW())
                  )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_subscriptions"):
        user_subscription_indexes = {
            index["name"] for index in inspector.get_indexes("user_subscriptions")
        }
        if "ix_user_subscriptions_user_status" in user_subscription_indexes:
            op.drop_index(
                "ix_user_subscriptions_user_status", table_name="user_subscriptions"
            )
        if "ix_user_subscriptions_package_id" in user_subscription_indexes:
            op.drop_index(
                "ix_user_subscriptions_package_id", table_name="user_subscriptions"
            )
        if "ix_user_subscriptions_user_id" in user_subscription_indexes:
            op.drop_index(
                "ix_user_subscriptions_user_id", table_name="user_subscriptions"
            )
        op.drop_table("user_subscriptions")

    inspector = sa.inspect(bind)
    if inspector.has_table("team_members"):
        member_indexes = {
            index["name"] for index in inspector.get_indexes("team_members")
        }
        if "ix_team_members_team_role" in member_indexes:
            op.drop_index("ix_team_members_team_role", table_name="team_members")
        if "ix_team_members_user_id" in member_indexes:
            op.drop_index("ix_team_members_user_id", table_name="team_members")
        if "ix_team_members_team_id" in member_indexes:
            op.drop_index("ix_team_members_team_id", table_name="team_members")
        op.drop_table("team_members")

    inspector = sa.inspect(bind)
    if inspector.has_table("teams"):
        team_indexes = {index["name"] for index in inspector.get_indexes("teams")}
        if "ix_teams_tenant_active" in team_indexes:
            op.drop_index("ix_teams_tenant_active", table_name="teams")
        if "ix_teams_owner_user_id" in team_indexes:
            op.drop_index("ix_teams_owner_user_id", table_name="teams")
        if "ix_teams_tenant_id" in team_indexes:
            op.drop_index("ix_teams_tenant_id", table_name="teams")
        op.drop_table("teams")

    if inspector.has_table("permissions"):
        bind.execute(
            sa.text(
                """
                DELETE FROM permissions
                WHERE code IN ('teams:view', 'teams:create', 'teams:members:manage')
                """
            )
        )

    if inspector.has_table("saas_package_features"):
        bind.execute(
            sa.text(
                """
                DELETE f
                FROM saas_package_features f
                JOIN saas_packages p ON p.id = f.package_id
                WHERE p.code = 'BUSINESS'
                """
            )
        )
        bind.execute(
            sa.text(
                """
                DELETE f
                FROM saas_package_features f
                JOIN saas_packages p ON p.id = f.package_id
                WHERE f.feature_key = 'SUNSET_THEME'
                  AND p.code IN ('FREE', 'PRO')
                """
            )
        )

    if inspector.has_table("saas_packages"):
        bind.execute(sa.text("DELETE FROM saas_packages WHERE code = 'BUSINESS'"))

    inspector = sa.inspect(bind)
    if inspector.has_table("users"):
        user_indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "uq_users_google_sub" in user_indexes:
            op.drop_index("uq_users_google_sub", table_name="users")

        if _has_column(inspector, "users", "avatar_url"):
            op.drop_column("users", "avatar_url")
        if _has_column(inspector, "users", "google_sub"):
            op.drop_column("users", "google_sub")
        if _has_column(inspector, "users", "auth_provider"):
            op.drop_column("users", "auth_provider")
