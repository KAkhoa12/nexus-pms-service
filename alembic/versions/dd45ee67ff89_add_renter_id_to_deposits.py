"""add renter_id to deposits

Revision ID: dd45ee67ff89
Revises: cc34dd56ee78
Create Date: 2026-03-14 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd45ee67ff89"
down_revision: Union[str, Sequence[str], None] = "cc34dd56ee78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _find_fk_names(
    inspector: sa.Inspector, table_name: str, column_name: str
) -> list[str]:
    names: list[str] = []
    for fk in inspector.get_foreign_keys(table_name):
        cols = fk.get("constrained_columns") or []
        name = fk.get("name")
        if cols == [column_name] and name:
            names.append(name)
    return names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("deposits"):
        return

    if not _has_column(inspector, "deposits", "renter_id"):
        op.add_column(
            "deposits", sa.Column("renter_id", sa.BigInteger(), nullable=True)
        )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "deposits", "renter_id") and _has_column(
        inspector, "deposits", "lease_id"
    ):
        op.execute(
            sa.text(
                """
                UPDATE deposits d
                JOIN leases l ON l.id = d.lease_id
                SET d.renter_id = l.renter_id
                WHERE d.renter_id IS NULL AND d.lease_id IS NOT NULL
                """
            )
        )

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("deposits")}
    if "ix_deposits_renter_id" not in existing_indexes:
        op.create_index(
            "ix_deposits_renter_id", "deposits", ["renter_id"], unique=False
        )

    inspector = sa.inspect(bind)
    fk_names = _find_fk_names(inspector, "deposits", "renter_id")
    if not fk_names:
        op.create_foreign_key(
            "fk_deposits_renter_id_renters",
            "deposits",
            "renters",
            ["renter_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("deposits"):
        return

    if _has_column(inspector, "deposits", "renter_id"):
        for fk_name in _find_fk_names(inspector, "deposits", "renter_id"):
            op.drop_constraint(fk_name, "deposits", type_="foreignkey")
        existing_indexes = {
            index["name"] for index in inspector.get_indexes("deposits")
        }
        if "ix_deposits_renter_id" in existing_indexes:
            op.drop_index("ix_deposits_renter_id", table_name="deposits")
        op.drop_column("deposits", "renter_id")
