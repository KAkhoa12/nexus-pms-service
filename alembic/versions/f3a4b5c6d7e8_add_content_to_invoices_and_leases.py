"""add content to invoices and leases

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-03-11 19:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("invoices") and not _has_column(
        inspector, "invoices", "content"
    ):
        op.add_column(
            "invoices",
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
        )

    if inspector.has_table("leases") and not _has_column(
        inspector, "leases", "content"
    ):
        op.add_column(
            "leases",
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("invoices") and _has_column(
        inspector, "invoices", "content"
    ):
        op.drop_column("invoices", "content")

    if inspector.has_table("leases") and _has_column(inspector, "leases", "content"):
        op.drop_column("leases", "content")
