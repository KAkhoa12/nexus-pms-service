"""move deposit to leases and add room maintenance status

Revision ID: rr89mm01nn23
Revises: qq78ll90mm12
Create Date: 2026-03-18 20:35:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "rr89mm01nn23"
down_revision: Union[str, Sequence[str], None] = "qq78ll90mm12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    return column_name in columns


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    return index_name in indexes


def _has_foreign_key(
    inspector: sa.Inspector, table_name: str, constraint_name: str
) -> bool:
    constraints = {
        fk.get("name")
        for fk in inspector.get_foreign_keys(table_name)
        if fk.get("name") is not None
    }
    return constraint_name in constraints


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "leases"):
        if not _has_column(inspector, "leases", "created_by_user_id"):
            op.add_column(
                "leases",
                sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            )
        inspector = sa.inspect(bind)
        if not _has_foreign_key(
            inspector,
            "leases",
            "fk_leases_created_by_user_id_users",
        ):
            op.create_foreign_key(
                "fk_leases_created_by_user_id_users",
                "leases",
                "users",
                ["created_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
        inspector = sa.inspect(bind)
        if not _has_index(inspector, "leases", "ix_leases_created_by_user_id"):
            op.create_index(
                "ix_leases_created_by_user_id",
                "leases",
                ["created_by_user_id"],
                unique=False,
            )
        if not _has_column(inspector, "leases", "security_deposit_amount"):
            op.add_column(
                "leases",
                sa.Column(
                    "security_deposit_amount",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )
        if not _has_column(inspector, "leases", "security_deposit_paid_amount"):
            op.add_column(
                "leases",
                sa.Column(
                    "security_deposit_paid_amount",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )
        if not _has_column(inspector, "leases", "security_deposit_paid_at"):
            op.add_column(
                "leases",
                sa.Column(
                    "security_deposit_paid_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )
        if not _has_column(inspector, "leases", "security_deposit_note"):
            op.add_column(
                "leases",
                sa.Column(
                    "security_deposit_note",
                    sa.Text(),
                    nullable=False,
                    server_default="",
                ),
            )

        if _has_table(inspector, "deposits") and _has_column(
            inspector, "deposits", "lease_id"
        ):
            bind.execute(
                sa.text(
                    """
                    UPDATE leases l
                    LEFT JOIN (
                        SELECT
                            lease_id,
                            SUM(amount) AS total_amount,
                            MAX(paid_at) AS last_paid_at
                        FROM deposits
                        WHERE lease_id IS NOT NULL AND deleted_at IS NULL
                        GROUP BY lease_id
                    ) d ON d.lease_id = l.id
                    SET
                        l.security_deposit_amount = COALESCE(d.total_amount, 0),
                        l.security_deposit_paid_amount = COALESCE(d.total_amount, 0),
                        l.security_deposit_paid_at = d.last_paid_at,
                        l.security_deposit_note = CASE
                            WHEN COALESCE(d.total_amount, 0) > 0 THEN 'Migrated from deposits'
                            ELSE l.security_deposit_note
                        END
                    """
                )
            )

    if _has_table(inspector, "rooms") and _has_column(
        inspector, "rooms", "current_status"
    ):
        bind.execute(
            sa.text(
                """
                ALTER TABLE rooms
                MODIFY COLUMN current_status
                ENUM('VACANT','DEPOSITED','RENTED','MAINTENANCE')
                NOT NULL
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "rooms") and _has_column(
        inspector, "rooms", "current_status"
    ):
        bind.execute(
            sa.text(
                """
                UPDATE rooms
                SET current_status = 'VACANT'
                WHERE current_status = 'MAINTENANCE'
                """
            )
        )
        bind.execute(
            sa.text(
                """
                ALTER TABLE rooms
                MODIFY COLUMN current_status
                ENUM('VACANT','DEPOSITED','RENTED')
                NOT NULL
                """
            )
        )

    if _has_table(inspector, "leases"):
        if _has_column(inspector, "leases", "created_by_user_id"):
            if _has_index(inspector, "leases", "ix_leases_created_by_user_id"):
                op.drop_index("ix_leases_created_by_user_id", table_name="leases")
            inspector = sa.inspect(bind)
            if _has_foreign_key(
                inspector,
                "leases",
                "fk_leases_created_by_user_id_users",
            ):
                op.drop_constraint(
                    "fk_leases_created_by_user_id_users",
                    "leases",
                    type_="foreignkey",
                )
            op.drop_column("leases", "created_by_user_id")
        if _has_column(inspector, "leases", "security_deposit_note"):
            op.drop_column("leases", "security_deposit_note")
        if _has_column(inspector, "leases", "security_deposit_paid_at"):
            op.drop_column("leases", "security_deposit_paid_at")
        if _has_column(inspector, "leases", "security_deposit_paid_amount"):
            op.drop_column("leases", "security_deposit_paid_amount")
        if _has_column(inspector, "leases", "security_deposit_amount"):
            op.drop_column("leases", "security_deposit_amount")
