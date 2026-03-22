"""seed collaboration permissions for business chat and notifications

Revision ID: mm34hh56ii78
Revises: ll23gg45hh67
Create Date: 2026-03-17 17:15:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mm34hh56ii78"
down_revision: Union[str, Sequence[str], None] = "ll23gg45hh67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS: list[tuple[str, str, str]] = [
    (
        "collaboration:notifications:view",
        "collaboration",
        "Xem danh sach thong bao noi bo",
    ),
    (
        "collaboration:notifications:create",
        "collaboration",
        "Tao thong bao gui 1 nhieu hoac toan bo nguoi dung",
    ),
    ("notifications:create", "collaboration", "Legacy alias tao thong bao"),
    ("collaboration:chat:view", "collaboration", "Xem kenh chat noi bo"),
    ("collaboration:chat:channel:create", "collaboration", "Tao kenh chat"),
    ("collaboration:chat:message:send", "collaboration", "Gui tin nhan chat"),
    ("collaboration:chat:file:upload", "collaboration", "Tai file chat len MinIO"),
    (
        "collaboration:chat:typing:update",
        "collaboration",
        "Cap nhat typing indicator",
    ),
    ("collaboration:tasks:view", "collaboration", "Xem task trong workspace"),
    ("collaboration:tasks:create", "collaboration", "Tao task trong workspace"),
    (
        "collaboration:tasks:update",
        "collaboration",
        "Cap nhat trang thai va bao cao task",
    ),
    (
        "collaboration:ai:sessions:view",
        "collaboration",
        "Xem session chatbot AI trong workspace",
    ),
    (
        "collaboration:ai:sessions:create",
        "collaboration",
        "Tao session chatbot AI trong workspace",
    ),
    (
        "collaboration:ai:messages:create",
        "collaboration",
        "Them hoi thoai vao session chatbot AI",
    ),
]


def _upsert_permission(
    bind: sa.Connection,
    *,
    code: str,
    module: str,
    description: str,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module, description, created_at, updated_at, deleted_at)
            SELECT :code, :module, :description, NOW(), NOW(), NULL
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
    bind.execute(
        sa.text(
            """
            UPDATE permissions
            SET
                module = :module,
                description = :description,
                deleted_at = NULL,
                updated_at = NOW()
            WHERE code = :code
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
    if not inspector.has_table("permissions"):
        return

    for code, module, description in PERMISSIONS:
        _upsert_permission(
            bind,
            code=code,
            module=module,
            description=description,
        )


def downgrade() -> None:
    # Keep seeded permissions for compatibility with current RBAC assignments.
    pass
