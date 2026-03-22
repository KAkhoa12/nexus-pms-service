"""add service fees and customer appointments tables

Revision ID: oo56jj78kk90
Revises: nn45ii67jj89
Create Date: 2026-03-18 11:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "oo56jj78kk90"
down_revision: Union[str, Sequence[str], None] = "nn45ii67jj89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _ensure_index(bind: sa.Connection, *, table_name: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("service_fees"):
        op.create_table(
            "service_fees",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("unit", sa.String(length=64), nullable=True),
            sa.Column("default_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_service_fees_tenant_code"),
            *_timestamp_columns(),
        )
    _ensure_index(bind, table_name="service_fees", index_name="ix_service_fees_tenant_id", columns=["tenant_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("customer_appointments"):
        op.create_table(
            "customer_appointments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("branch_id", sa.BigInteger(), nullable=True),
            sa.Column("room_id", sa.BigInteger(), nullable=True),
            sa.Column("contact_name", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=32), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'SCHEDULED'")),
            sa.Column("source", sa.String(length=64), nullable=True),
            sa.Column("assigned_user_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
            *_timestamp_columns(),
        )
    _ensure_index(bind, table_name="customer_appointments", index_name="ix_customer_appointments_tenant_id", columns=["tenant_id"])
    _ensure_index(bind, table_name="customer_appointments", index_name="ix_customer_appointments_phone", columns=["phone"])
    _ensure_index(bind, table_name="customer_appointments", index_name="ix_customer_appointments_branch_id", columns=["branch_id"])
    _ensure_index(bind, table_name="customer_appointments", index_name="ix_customer_appointments_room_id", columns=["room_id"])
    _ensure_index(bind, table_name="customer_appointments", index_name="ix_customer_appointments_assigned_user_id", columns=["assigned_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("customer_appointments"):
        op.drop_table("customer_appointments")
    if inspector.has_table("service_fees"):
        op.drop_table("service_fees")
