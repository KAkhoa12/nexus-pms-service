"""add user preferences table for theme and workspace settings

Revision ID: jj01ee23ff45
Revises: ii90dd12ee34
Create Date: 2026-03-17 00:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "jj01ee23ff45"
down_revision: Union[str, Sequence[str], None] = "ii90dd12ee34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("user_preferences"):
        op.create_table(
            "user_preferences",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("theme_mode", sa.String(length=20), nullable=True),
            sa.Column("workspace_key", sa.String(length=64), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("user_preferences"):
        indexes = {index["name"] for index in inspector.get_indexes("user_preferences")}
        if "ix_user_preferences_user_id" not in indexes:
            op.create_index(
                "ix_user_preferences_user_id",
                "user_preferences",
                ["user_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("user_preferences"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("user_preferences")}
    if "ix_user_preferences_user_id" in indexes:
        op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
