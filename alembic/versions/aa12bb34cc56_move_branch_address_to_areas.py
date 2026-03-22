"""move branch address to areas

Revision ID: aa12bb34cc56
Revises: f3a4b5c6d7e8
Create Date: 2026-03-13 20:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa12bb34cc56"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("areas") and not _has_column(inspector, "areas", "address"):
        op.add_column(
            "areas", sa.Column("address", sa.String(length=255), nullable=True)
        )

    inspector = sa.inspect(bind)
    has_branches_address = inspector.has_table("branches") and _has_column(
        inspector, "branches", "address"
    )
    has_areas_address = inspector.has_table("areas") and _has_column(
        inspector, "areas", "address"
    )

    if has_branches_address and has_areas_address:
        op.execute(
            sa.text(
                """
                UPDATE areas a
                JOIN branches b ON b.id = a.branch_id
                SET a.address = b.address
                WHERE a.address IS NULL AND b.address IS NOT NULL
                """
            )
        )

    if has_branches_address:
        op.drop_column("branches", "address")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("branches") and not _has_column(
        inspector, "branches", "address"
    ):
        op.add_column(
            "branches",
            sa.Column("address", sa.String(length=255), nullable=True),
        )

    inspector = sa.inspect(bind)
    has_branches_address = inspector.has_table("branches") and _has_column(
        inspector, "branches", "address"
    )
    has_areas_address = inspector.has_table("areas") and _has_column(
        inspector, "areas", "address"
    )

    if has_branches_address and has_areas_address:
        op.execute(
            sa.text(
                """
                UPDATE branches b
                SET b.address = (
                    SELECT a.address
                    FROM areas a
                    WHERE a.branch_id = b.id
                      AND a.address IS NOT NULL
                    ORDER BY a.id ASC
                    LIMIT 1
                )
                WHERE b.address IS NULL
                """
            )
        )
        op.drop_column("areas", "address")
