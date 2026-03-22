"""add lease invoice schedule fields

Revision ID: vv23qq45rr67
Revises: uu12pp34qq56
Create Date: 2026-03-20 11:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "vv23qq45rr67"
down_revision: str | None = "uu12pp34qq56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("lease_id", sa.BigInteger(), nullable=True))
    op.add_column("invoices", sa.Column("installment_no", sa.Integer(), nullable=True))
    op.add_column(
        "invoices", sa.Column("installment_total", sa.Integer(), nullable=True)
    )
    op.add_column(
        "invoices", sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_index("ix_invoices_lease_id", "invoices", ["lease_id"], unique=False)
    op.create_index(
        "ix_invoices_reminder_at", "invoices", ["reminder_at"], unique=False
    )
    op.create_foreign_key(
        "fk_invoices_lease_id_leases",
        "invoices",
        "leases",
        ["lease_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "service_fees",
        sa.Column(
            "default_quantity",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("service_fees", "default_quantity")
    op.drop_constraint("fk_invoices_lease_id_leases", "invoices", type_="foreignkey")
    op.drop_index("ix_invoices_reminder_at", table_name="invoices")
    op.drop_index("ix_invoices_lease_id", table_name="invoices")

    op.drop_column("invoices", "reminder_at")
    op.drop_column("invoices", "installment_total")
    op.drop_column("invoices", "installment_no")
    op.drop_column("invoices", "lease_id")
