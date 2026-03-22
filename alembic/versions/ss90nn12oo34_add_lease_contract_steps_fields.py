"""add lease contract step fields

Revision ID: ss90nn12oo34
Revises: rr89mm01nn23
Create Date: 2026-03-18 22:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ss90nn12oo34"
down_revision: Union[str, Sequence[str], None] = "rr89mm01nn23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "leases"):
        return

    if not _has_column(inspector, "leases", "lease_years"):
        op.add_column(
            "leases",
            sa.Column("lease_years", sa.Integer(), nullable=False, server_default="1"),
        )
        bind.execute(
            sa.text(
                """
                UPDATE leases
                SET lease_years = CASE
                    WHEN start_date IS NULL THEN 1
                    WHEN end_date IS NULL THEN 1
                    WHEN TIMESTAMPDIFF(YEAR, start_date, end_date) <= 0 THEN 1
                    ELSE TIMESTAMPDIFF(YEAR, start_date, end_date)
                END
                """
            )
        )

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "leases", "handover_at"):
        op.add_column(
            "leases",
            sa.Column("handover_at", sa.DateTime(timezone=True), nullable=True),
        )
        bind.execute(
            sa.text(
                """
                UPDATE leases
                SET handover_at = start_date
                WHERE handover_at IS NULL
                """
            )
        )

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "leases", "security_deposit_payment_method"):
        op.add_column(
            "leases",
            sa.Column(
                "security_deposit_payment_method",
                sa.Enum(
                    "CASH", "BANK", "QR", name="lease_security_deposit_method_enum"
                ),
                nullable=True,
            ),
        )
        if _has_table(inspector, "deposits") and _has_column(
            inspector, "deposits", "method"
        ):
            bind.execute(
                sa.text(
                    """
                    UPDATE leases l
                    LEFT JOIN (
                        SELECT d1.lease_id, d1.method
                        FROM deposits d1
                        JOIN (
                            SELECT lease_id, MAX(paid_at) AS max_paid_at
                            FROM deposits
                            WHERE lease_id IS NOT NULL AND deleted_at IS NULL
                            GROUP BY lease_id
                        ) latest
                            ON latest.lease_id = d1.lease_id
                           AND latest.max_paid_at = d1.paid_at
                        WHERE d1.deleted_at IS NULL
                    ) dm
                        ON dm.lease_id = l.id
                    SET l.security_deposit_payment_method = dm.method
                    WHERE l.security_deposit_payment_method IS NULL
                    """
                )
            )
        bind.execute(
            sa.text(
                """
                UPDATE leases
                SET security_deposit_payment_method = 'CASH'
                WHERE security_deposit_payment_method IS NULL
                  AND COALESCE(security_deposit_paid_amount, 0) > 0
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "leases"):
        return

    if _has_column(inspector, "leases", "security_deposit_payment_method"):
        op.drop_column("leases", "security_deposit_payment_method")
    if _has_column(inspector, "leases", "handover_at"):
        op.drop_column("leases", "handover_at")
    if _has_column(inspector, "leases", "lease_years"):
        op.drop_column("leases", "lease_years")
