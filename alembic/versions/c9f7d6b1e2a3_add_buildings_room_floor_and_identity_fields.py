"""add buildings, room floor and renter identity fields

Revision ID: c9f7d6b1e2a3
Revises: 054123e0ca74
Create Date: 2026-03-05 16:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f7d6b1e2a3"
down_revision: Union[str, Sequence[str], None] = "054123e0ca74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, module, description)
        SELECT 'buildings:view', 'buildings', 'Xem danh sach toa nha'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'buildings:view')
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, module, description)
        SELECT 'buildings:create', 'buildings', 'Them moi toa nha'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'buildings:create')
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, module, description)
        SELECT 'buildings:update', 'buildings', 'Cap nhat toa nha'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'buildings:update')
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, module, description)
        SELECT 'buildings:delete', 'buildings', 'Xoa mem toa nha'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'buildings:delete')
        """
    )

    op.create_table(
        "buildings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("area_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("total_floors", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "area_id",
            "name",
            name="uq_buildings_tenant_area_name",
        ),
    )
    op.create_index(
        op.f("ix_buildings_tenant_id"), "buildings", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_buildings_area_id"), "buildings", ["area_id"], unique=False
    )

    op.add_column("rooms", sa.Column("building_id", sa.BigInteger(), nullable=True))
    op.add_column("rooms", sa.Column("floor_number", sa.Integer(), nullable=True))

    op.execute(
        """
        INSERT INTO buildings (tenant_id, area_id, name, total_floors, created_at, updated_at)
        SELECT a.tenant_id, a.id, 'Toa mac dinh', 1, NOW(), NOW()
        FROM areas a
        WHERE NOT EXISTS (
            SELECT 1
            FROM buildings b
            WHERE b.tenant_id = a.tenant_id
              AND b.area_id = a.id
              AND b.name = 'Toa mac dinh'
        )
        """
    )

    op.execute(
        """
        UPDATE rooms r
        JOIN buildings b
          ON b.tenant_id = r.tenant_id
         AND b.area_id = r.area_id
         AND b.name = 'Toa mac dinh'
        SET r.building_id = b.id
        WHERE r.building_id IS NULL
        """
    )
    op.execute("UPDATE rooms SET floor_number = 1 WHERE floor_number IS NULL")

    op.create_index(
        op.f("ix_rooms_building_id"), "rooms", ["building_id"], unique=False
    )
    op.create_foreign_key(
        "fk_rooms_building_id_buildings",
        "rooms",
        "buildings",
        ["building_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "rooms", "building_id", existing_type=sa.BigInteger(), nullable=False
    )
    op.alter_column("rooms", "floor_number", existing_type=sa.Integer(), nullable=False)

    op.add_column(
        "renters", sa.Column("identity_type", sa.String(length=32), nullable=True)
    )
    op.add_column("renters", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "renters", sa.Column("avatar_url", sa.String(length=1024), nullable=True)
    )
    op.add_column("renters", sa.Column("address", sa.String(length=255), nullable=True))

    op.add_column(
        "renter_members",
        sa.Column("identity_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "renter_members", sa.Column("id_number", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "renter_members", sa.Column("email", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "renter_members", sa.Column("avatar_url", sa.String(length=1024), nullable=True)
    )
    op.add_column(
        "renter_members",
        sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "renter_members", sa.Column("address", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("renter_members", "address")
    op.drop_column("renter_members", "date_of_birth")
    op.drop_column("renter_members", "avatar_url")
    op.drop_column("renter_members", "email")
    op.drop_column("renter_members", "id_number")
    op.drop_column("renter_members", "identity_type")

    op.drop_column("renters", "address")
    op.drop_column("renters", "avatar_url")
    op.drop_column("renters", "email")
    op.drop_column("renters", "identity_type")

    op.drop_constraint("fk_rooms_building_id_buildings", "rooms", type_="foreignkey")
    op.drop_index(op.f("ix_rooms_building_id"), table_name="rooms")
    op.drop_column("rooms", "floor_number")
    op.drop_column("rooms", "building_id")

    op.drop_index(op.f("ix_buildings_area_id"), table_name="buildings")
    op.drop_index(op.f("ix_buildings_tenant_id"), table_name="buildings")
    op.drop_table("buildings")
    op.execute(
        "DELETE FROM permissions WHERE code IN ('buildings:view', 'buildings:create', 'buildings:update', 'buildings:delete')"
    )
