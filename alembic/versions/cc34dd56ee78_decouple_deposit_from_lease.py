"""decouple deposit from lease

Revision ID: cc34dd56ee78
Revises: bb23cc45dd67
Create Date: 2026-03-14 18:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc34dd56ee78"
down_revision: Union[str, Sequence[str], None] = "bb23cc45dd67"
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

    if not _has_column(inspector, "deposits", "room_id"):
        op.add_column("deposits", sa.Column("room_id", sa.BigInteger(), nullable=True))

    inspector = sa.inspect(bind)
    if _has_column(inspector, "deposits", "room_id") and _has_column(
        inspector, "deposits", "lease_id"
    ):
        op.execute(
            sa.text(
                """
                UPDATE deposits d
                JOIN leases l ON l.id = d.lease_id
                SET d.room_id = l.room_id
                WHERE d.room_id IS NULL
                """
            )
        )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "deposits", "lease_id"):
        for fk_name in _find_fk_names(inspector, "deposits", "lease_id"):
            op.drop_constraint(fk_name, "deposits", type_="foreignkey")
        op.alter_column(
            "deposits",
            "lease_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
        op.create_foreign_key(
            "fk_deposits_lease_id_leases",
            "deposits",
            "leases",
            ["lease_id"],
            ["id"],
            ondelete="SET NULL",
        )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "deposits", "room_id"):
        null_count = bind.execute(
            sa.text("SELECT COUNT(*) FROM deposits WHERE room_id IS NULL")
        ).scalar()
        if int(null_count or 0) > 0:
            raise RuntimeError(
                "Không thể migrate deposits.room_id do còn dữ liệu null sau khi map từ lease"
            )

        op.alter_column(
            "deposits",
            "room_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        existing_indexes = {
            index["name"] for index in inspector.get_indexes("deposits")
        }
        if "ix_deposits_room_id" not in existing_indexes:
            op.create_index(
                "ix_deposits_room_id", "deposits", ["room_id"], unique=False
            )

        inspector = sa.inspect(bind)
        room_fk_names = _find_fk_names(inspector, "deposits", "room_id")
        if not room_fk_names:
            op.create_foreign_key(
                "fk_deposits_room_id_rooms",
                "deposits",
                "rooms",
                ["room_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("deposits"):
        return

    if _has_column(inspector, "deposits", "lease_id"):
        # Map lại lease_id theo room_id nếu bị null.
        op.execute(
            sa.text(
                """
                UPDATE deposits d
                SET d.lease_id = (
                    SELECT l.id
                    FROM leases l
                    WHERE l.room_id = d.room_id
                      AND l.deleted_at IS NULL
                    ORDER BY l.id DESC
                    LIMIT 1
                )
                WHERE d.lease_id IS NULL
                """
            )
        )

        inspector = sa.inspect(bind)
        for fk_name in _find_fk_names(inspector, "deposits", "lease_id"):
            op.drop_constraint(fk_name, "deposits", type_="foreignkey")
        op.alter_column(
            "deposits",
            "lease_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        op.create_foreign_key(
            "fk_deposits_lease_id_leases",
            "deposits",
            "leases",
            ["lease_id"],
            ["id"],
            ondelete="CASCADE",
        )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "deposits", "room_id"):
        for fk_name in _find_fk_names(inspector, "deposits", "room_id"):
            op.drop_constraint(fk_name, "deposits", type_="foreignkey")
        existing_indexes = {
            index["name"] for index in inspector.get_indexes("deposits")
        }
        if "ix_deposits_room_id" in existing_indexes:
            op.drop_index("ix_deposits_room_id", table_name="deposits")
        op.drop_column("deposits", "room_id")
