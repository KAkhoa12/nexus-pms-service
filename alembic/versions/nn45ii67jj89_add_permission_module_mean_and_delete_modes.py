"""add module_mean to permissions and seed soft/hard delete variants

Revision ID: nn45ii67jj89
Revises: mm34hh56ii78
Create Date: 2026-03-17 22:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "nn45ii67jj89"
down_revision: Union[str, Sequence[str], None] = "mm34hh56ii78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODULE_MEAN_MAP: dict[str, str] = {
    "areas": "Khu vực",
    "branches": "Chi nhánh",
    "buildings": "Tòa nhà",
    "room_types": "Loại phòng",
    "rooms": "Phòng",
    "renters": "Khách thuê",
    "renter_members": "Thành viên khách thuê",
    "invoices": "Hóa đơn",
    "deposits": "Đặt cọc",
    "users": "Người dùng",
    "forms": "Biểu mẫu",
    "teams": "Nhóm làm việc",
    "platform": "Nền tảng",
    "collaboration": "Cộng tác",
}


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

    column_names = {col["name"] for col in inspector.get_columns("permissions")}
    if "module_mean" not in column_names:
        op.add_column(
            "permissions",
            sa.Column("module_mean", sa.String(length=128), nullable=True),
        )

    for module, module_mean in MODULE_MEAN_MAP.items():
        bind.execute(
            sa.text(
                """
                UPDATE permissions
                SET module_mean = :module_mean, updated_at = NOW()
                WHERE module = :module
                """
            ),
            {"module": module, "module_mean": module_mean},
        )

    bind.execute(
        sa.text(
            """
            UPDATE permissions
            SET description = REPLACE(description, 'Cập nhập', 'Cập nhật'),
                updated_at = NOW()
            WHERE description LIKE '%Cập nhập%'
            """
        )
    )

    delete_rows = bind.execute(
        sa.text(
            """
            SELECT code, module, COALESCE(module_mean, module) AS module_mean, COALESCE(description, code) AS description
            FROM permissions
            WHERE deleted_at IS NULL
              AND code LIKE :delete_suffix
              AND code NOT LIKE '%:delete:soft'
              AND code NOT LIKE '%:delete:hard'
            """
        ),
        {"delete_suffix": "%:delete"},
    ).mappings()

    for row in delete_rows:
        base_code = str(row["code"])
        module = str(row["module"])
        module_mean = str(row["module_mean"])
        base_description = str(row["description"])

        _upsert_permission(
            bind,
            code=f"{base_code}:soft",
            module=module,
            module_mean=module_mean,
            description=f"Xóa mềm ({base_description})",
        )
        _upsert_permission(
            bind,
            code=f"{base_code}:hard",
            module=module,
            module_mean=module_mean,
            description=f"Xóa vĩnh viễn ({base_description})",
        )


def downgrade() -> None:
    # Keep seeded permissions and module_mean to avoid breaking RBAC assignments.
    pass
