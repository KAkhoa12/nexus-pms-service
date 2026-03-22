"""remove estimated_value from assets

Revision ID: ww34rr56ss78
Revises: vv23qq45rr67
Create Date: 2026-03-20 18:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ww34rr56ss78"
down_revision: Union[str, Sequence[str], None] = "vv23qq45rr67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("assets"):
        return
    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "estimated_value" in columns:
        op.drop_column("assets", "estimated_value")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("assets"):
        return
    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "estimated_value" not in columns:
        op.add_column(
            "assets",
            sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        )
