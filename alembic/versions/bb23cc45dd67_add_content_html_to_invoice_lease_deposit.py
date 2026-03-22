"""add content_html to invoices leases deposits

Revision ID: bb23cc45dd67
Revises: aa12bb34cc56
Create Date: 2026-03-14 16:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb23cc45dd67"
down_revision: Union[str, Sequence[str], None] = "aa12bb34cc56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("invoices") and not _has_column(
        inspector, "invoices", "content_html"
    ):
        op.add_column(
            "invoices",
            sa.Column("content_html", sa.Text(), nullable=False, server_default=""),
        )

    if inspector.has_table("leases") and not _has_column(
        inspector, "leases", "content_html"
    ):
        op.add_column(
            "leases",
            sa.Column("content_html", sa.Text(), nullable=False, server_default=""),
        )

    if inspector.has_table("deposits") and not _has_column(
        inspector, "deposits", "content_html"
    ):
        op.add_column(
            "deposits",
            sa.Column("content_html", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("deposits") and _has_column(
        inspector, "deposits", "content_html"
    ):
        op.drop_column("deposits", "content_html")

    if inspector.has_table("leases") and _has_column(
        inspector, "leases", "content_html"
    ):
        op.drop_column("leases", "content_html")

    if inspector.has_table("invoices") and _has_column(
        inspector, "invoices", "content_html"
    ):
        op.drop_column("invoices", "content_html")
