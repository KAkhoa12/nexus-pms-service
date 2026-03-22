"""add material assets management and extend service fees billing cycle

Revision ID: uu12pp34qq56
Revises: tt01oo23pp45
Create Date: 2026-03-19 23:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "uu12pp34qq56"
down_revision: Union[str, Sequence[str], None] = "tt01oo23pp45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _ensure_index(
    bind: sa.Connection,
    *,
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def _upsert_permission(
    bind: sa.Connection,
    *,
    code: str,
    module: str,
    module_mean: str | None,
    description: str,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module, module_mean, description, created_at, updated_at, deleted_at)
            SELECT :code, :module, :module_mean, :description, NOW(), NOW(), NULL
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE code = :code
            )
            """
        ),
        {
            "code": code,
            "module": module,
            "module_mean": module_mean,
            "description": description,
        },
    )
    bind.execute(
        sa.text(
            """
            UPDATE permissions
            SET
                module = :module,
                module_mean = :module_mean,
                description = :description,
                deleted_at = NULL,
                updated_at = NOW()
            WHERE code = :code
            """
        ),
        {
            "code": code,
            "module": module,
            "module_mean": module_mean,
            "description": description,
        },
    )


PERMISSIONS: list[tuple[str, str, str, str]] = [
    (
        "materials_assets:view",
        "materials_assets",
        "Tài sản vật tư",
        "Xem danh sách tài sản hoặc vật tư của khách thuê",
    ),
    (
        "materials_assets:create",
        "materials_assets",
        "Tài sản vật tư",
        "Thêm mới tài sản vật tư",
    ),
    (
        "materials_assets:update",
        "materials_assets",
        "Tài sản vật tư",
        "Cập nhật tài sản vật tư",
    ),
    (
        "materials_assets:delete",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa tài sản vật tư",
    ),
    (
        "materials_assets:delete:soft",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa mềm tài sản vật tư",
    ),
    (
        "materials_assets:delete:hard",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa vĩnh viễn tài sản vật tư",
    ),
    (
        "materials_asset_types:view",
        "materials_assets",
        "Tài sản vật tư",
        "Xem danh sách loại tài sản vật tư",
    ),
    (
        "materials_asset_types:create",
        "materials_assets",
        "Tài sản vật tư",
        "Thêm mới loại tài sản vật tư",
    ),
    (
        "materials_asset_types:update",
        "materials_assets",
        "Tài sản vật tư",
        "Cập nhật loại tài sản vật tư",
    ),
    (
        "materials_asset_types:delete",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa loại tài sản vật tư",
    ),
    (
        "materials_asset_types:delete:soft",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa mềm loại tài sản vật tư",
    ),
    (
        "materials_asset_types:delete:hard",
        "materials_assets",
        "Tài sản vật tư",
        "Xóa vĩnh viễn loại tài sản vật tư",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # service_fees extensions
    if not inspector.has_table("service_fees"):
        op.create_table(
            "service_fees",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("unit", sa.String(length=64), nullable=True),
            sa.Column("default_price", sa.Numeric(18, 2), nullable=True),
            sa.Column(
                "billing_cycle",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'MONTHLY'"),
            ),
            sa.Column("cycle_interval_months", sa.Integer(), nullable=True),
            sa.Column(
                "charge_mode",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'FIXED'"),
            ),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint(
                "tenant_id", "code", name="uq_service_fees_tenant_code"
            ),
            *_timestamp_columns(),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("service_fees")}
        if "billing_cycle" not in columns:
            op.add_column(
                "service_fees",
                sa.Column(
                    "billing_cycle",
                    sa.String(length=32),
                    nullable=False,
                    server_default=sa.text("'MONTHLY'"),
                ),
            )
        columns = {column["name"] for column in inspector.get_columns("service_fees")}
        if "cycle_interval_months" not in columns:
            op.add_column(
                "service_fees",
                sa.Column("cycle_interval_months", sa.Integer(), nullable=True),
            )
        columns = {column["name"] for column in inspector.get_columns("service_fees")}
        if "charge_mode" not in columns:
            op.add_column(
                "service_fees",
                sa.Column(
                    "charge_mode",
                    sa.String(length=32),
                    nullable=False,
                    server_default=sa.text("'FIXED'"),
                ),
            )
        bind.execute(
            sa.text(
                """
                UPDATE service_fees
                SET
                    billing_cycle = COALESCE(NULLIF(billing_cycle, ''), 'MONTHLY'),
                    charge_mode = COALESCE(NULLIF(charge_mode, ''), 'FIXED')
                """
            )
        )
        bind.execute(
            sa.text(
                """
                UPDATE service_fees
                SET cycle_interval_months = 1
                WHERE billing_cycle = 'MONTHLY'
                  AND (cycle_interval_months IS NULL OR cycle_interval_months < 1)
                """
            )
        )

    _ensure_index(
        bind,
        table_name="service_fees",
        index_name="ix_service_fees_tenant_id",
        columns=["tenant_id"],
    )

    # ensure legacy asset tables exist and extend to material-asset use case
    inspector = sa.inspect(bind)
    if not inspector.has_table("asset_types"):
        op.create_table(
            "asset_types",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("tenant_id", "name", name="uq_asset_types_tenant_name"),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="asset_types",
        index_name="ix_asset_types_tenant_id",
        columns=["tenant_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("room_id", sa.BigInteger(), nullable=False),
            sa.Column("renter_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_type_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "name",
                sa.String(length=255),
                nullable=False,
                server_default=sa.text("'Tài sản'"),
            ),
            sa.Column("identifier", sa.String(length=64), nullable=True),
            sa.Column(
                "quantity",
                sa.Numeric(12, 2),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("unit", sa.String(length=64), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'ACTIVE'"),
            ),
            sa.Column(
                "condition_status",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'GOOD'"),
            ),
            sa.Column("brand", sa.String(length=128), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("serial_number", sa.String(length=128), nullable=True),
            sa.Column("color", sa.String(length=64), nullable=True),
            sa.Column("plate_number", sa.String(length=64), nullable=True),
            sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("primary_image_url", sa.String(length=1024), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["renter_id"], ["renters.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["asset_type_id"], ["asset_types.id"], ondelete="RESTRICT"
            ),
            *_timestamp_columns(),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "name" not in columns:
            op.add_column(
                "assets",
                sa.Column(
                    "name",
                    sa.String(length=255),
                    nullable=False,
                    server_default=sa.text("'Tài sản'"),
                ),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "quantity" not in columns:
            op.add_column(
                "assets",
                sa.Column(
                    "quantity",
                    sa.Numeric(12, 2),
                    nullable=False,
                    server_default=sa.text("1"),
                ),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "unit" not in columns:
            op.add_column(
                "assets", sa.Column("unit", sa.String(length=64), nullable=True)
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "status" not in columns:
            op.add_column(
                "assets",
                sa.Column(
                    "status",
                    sa.String(length=32),
                    nullable=False,
                    server_default=sa.text("'ACTIVE'"),
                ),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "condition_status" not in columns:
            op.add_column(
                "assets",
                sa.Column(
                    "condition_status",
                    sa.String(length=32),
                    nullable=False,
                    server_default=sa.text("'GOOD'"),
                ),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "brand" not in columns:
            op.add_column(
                "assets", sa.Column("brand", sa.String(length=128), nullable=True)
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "model" not in columns:
            op.add_column(
                "assets", sa.Column("model", sa.String(length=128), nullable=True)
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "serial_number" not in columns:
            op.add_column(
                "assets",
                sa.Column("serial_number", sa.String(length=128), nullable=True),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "color" not in columns:
            op.add_column(
                "assets", sa.Column("color", sa.String(length=64), nullable=True)
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "plate_number" not in columns:
            op.add_column(
                "assets",
                sa.Column("plate_number", sa.String(length=64), nullable=True),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "estimated_value" not in columns:
            op.add_column(
                "assets",
                sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "acquired_at" not in columns:
            op.add_column(
                "assets",
                sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "metadata_json" not in columns:
            op.add_column(
                "assets", sa.Column("metadata_json", sa.Text(), nullable=True)
            )
        columns = {column["name"] for column in inspector.get_columns("assets")}
        if "primary_image_url" not in columns:
            op.add_column(
                "assets",
                sa.Column("primary_image_url", sa.String(length=1024), nullable=True),
            )

        bind.execute(
            sa.text(
                """
                UPDATE assets
                SET
                    name = COALESCE(NULLIF(name, ''), 'Tài sản'),
                    quantity = COALESCE(quantity, 1),
                    status = COALESCE(NULLIF(status, ''), 'ACTIVE'),
                    condition_status = COALESCE(NULLIF(condition_status, ''), 'GOOD')
                """
            )
        )

    _ensure_index(
        bind,
        table_name="assets",
        index_name="ix_assets_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind, table_name="assets", index_name="ix_assets_room_id", columns=["room_id"]
    )
    _ensure_index(
        bind,
        table_name="assets",
        index_name="ix_assets_renter_id",
        columns=["renter_id"],
    )
    _ensure_index(
        bind,
        table_name="assets",
        index_name="ix_assets_asset_type_id",
        columns=["asset_type_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("asset_logs"):
        op.create_table(
            "asset_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="asset_logs",
        index_name="ix_asset_logs_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="asset_logs",
        index_name="ix_asset_logs_asset_id",
        columns=["asset_id"],
    )
    _ensure_index(
        bind,
        table_name="asset_logs",
        index_name="ix_asset_logs_created_by_user_id",
        columns=["created_by_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("asset_images"):
        op.create_table(
            "asset_images",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("image_url", sa.String(length=1024), nullable=False),
            sa.Column("caption", sa.String(length=255), nullable=True),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_primary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="asset_images",
        index_name="ix_asset_images_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="asset_images",
        index_name="ix_asset_images_asset_id",
        columns=["asset_id"],
    )

    # Seed permissions
    inspector = sa.inspect(bind)
    if inspector.has_table("permissions"):
        columns = {col["name"] for col in inspector.get_columns("permissions")}
        if "module_mean" not in columns:
            op.add_column(
                "permissions",
                sa.Column("module_mean", sa.String(length=128), nullable=True),
            )
        for code, module, module_mean, description in PERMISSIONS:
            _upsert_permission(
                bind,
                code=code,
                module=module,
                module_mean=module_mean,
                description=description,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("asset_images"):
        op.drop_table("asset_images")

    # Keep columns on existing tables for backward compatibility.
    # Avoid dropping service_fees/assets columns to prevent data loss.
