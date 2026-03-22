"""seed lease permissions for contract module

Revision ID: tt01oo23pp45
Revises: ss90nn12oo34
Create Date: 2026-03-18 23:15:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "tt01oo23pp45"
down_revision: Union[str, Sequence[str], None] = "ss90nn12oo34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEASE_PERMISSIONS: list[tuple[str, str]] = [
    ("lease:view", "Xem hợp đồng thuê"),
    ("lease:create", "Tạo hợp đồng thuê"),
    ("lease:update", "Cập nhật hợp đồng thuê"),
    ("lease:delete", "Xóa hợp đồng thuê"),
    ("lease:delete:soft", "Xóa mềm hợp đồng thuê"),
    ("lease:delete:hard", "Xóa vĩnh viễn hợp đồng thuê"),
    ("leases:view", "Xem danh sách hợp đồng thuê"),
    ("leases:create", "Thêm mới hợp đồng thuê"),
    ("leases:update", "Cập nhật hợp đồng thuê"),
    ("leases:delete", "Xóa mềm hợp đồng thuê"),
    ("leases:delete:soft", "Xóa mềm hợp đồng thuê"),
    ("leases:delete:hard", "Xóa vĩnh viễn hợp đồng thuê"),
    ("leases:manage", "Quản lý toàn bộ hợp đồng thuê"),
]


def _upsert_permission(
    bind: sa.Connection,
    *,
    code: str,
    description: str,
    has_module_mean: bool,
) -> None:
    if has_module_mean:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, module, module_mean, description, created_at, updated_at, deleted_at)
                SELECT :code, 'leases', 'Hợp đồng thuê', :description, NOW(), NOW(), NULL
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM permissions
                    WHERE code = :code
                )
                """
            ),
            {"code": code, "description": description},
        )
        bind.execute(
            sa.text(
                """
                UPDATE permissions
                SET module = 'leases',
                    module_mean = 'Hợp đồng thuê',
                    description = :description,
                    deleted_at = NULL,
                    updated_at = NOW()
                WHERE code = :code
                """
            ),
            {"code": code, "description": description},
        )
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module, description, created_at, updated_at, deleted_at)
            SELECT :code, 'leases', :description, NOW(), NOW(), NULL
            WHERE NOT EXISTS (
                SELECT 1
                FROM permissions
                WHERE code = :code
            )
            """
        ),
        {"code": code, "description": description},
    )
    bind.execute(
        sa.text(
            """
            UPDATE permissions
            SET module = 'leases',
                description = :description,
                deleted_at = NULL,
                updated_at = NOW()
            WHERE code = :code
            """
        ),
        {"code": code, "description": description},
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("permissions"):
        return

    columns = {column["name"] for column in inspector.get_columns("permissions")}
    has_module_mean = "module_mean" in columns

    for code, description in LEASE_PERMISSIONS:
        _upsert_permission(
            bind,
            code=code,
            description=description,
            has_module_mean=has_module_mean,
        )


def downgrade() -> None:
    # Keep seeded permissions to avoid breaking existing role assignments.
    pass
