"""seed permissions for service_fees and customer_appointments

Revision ID: pp67kk89ll01
Revises: oo56jj78kk90
Create Date: 2026-03-18 12:20:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "pp67kk89ll01"
down_revision: Union[str, Sequence[str], None] = "oo56jj78kk90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS: list[tuple[str, str, str, str]] = [
    (
        "service_fees:view",
        "service_fees",
        "Phí thu",
        "Xem danh sách phí thu",
    ),
    (
        "service_fees:create",
        "service_fees",
        "Phí thu",
        "Thêm mới phí thu",
    ),
    (
        "service_fees:update",
        "service_fees",
        "Phí thu",
        "Cập nhật phí thu",
    ),
    (
        "service_fees:delete",
        "service_fees",
        "Phí thu",
        "Xóa phí thu",
    ),
    (
        "service_fees:delete:soft",
        "service_fees",
        "Phí thu",
        "Xóa mềm phí thu",
    ),
    (
        "service_fees:delete:hard",
        "service_fees",
        "Phí thu",
        "Xóa vĩnh viễn phí thu",
    ),
    (
        "customer_appointments:view",
        "customer_appointments",
        "Khách hẹn",
        "Xem danh sách khách hẹn",
    ),
    (
        "customer_appointments:create",
        "customer_appointments",
        "Khách hẹn",
        "Thêm mới khách hẹn",
    ),
    (
        "customer_appointments:update",
        "customer_appointments",
        "Khách hẹn",
        "Cập nhật khách hẹn",
    ),
    (
        "customer_appointments:delete",
        "customer_appointments",
        "Khách hẹn",
        "Xóa khách hẹn",
    ),
    (
        "customer_appointments:delete:soft",
        "customer_appointments",
        "Khách hẹn",
        "Xóa mềm khách hẹn",
    ),
    (
        "customer_appointments:delete:hard",
        "customer_appointments",
        "Khách hẹn",
        "Xóa vĩnh viễn khách hẹn",
    ),
]


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
                SELECT 1
                FROM permissions
                WHERE code = :code
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("permissions"):
        return

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
    # Keep seeded permissions for compatibility with assigned RBAC roles.
    pass
