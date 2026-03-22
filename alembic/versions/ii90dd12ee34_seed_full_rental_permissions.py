"""seed full rental-management permissions

Revision ID: ii90dd12ee34
Revises: hh89cc01dd23
Create Date: 2026-03-16 21:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ii90dd12ee34"
down_revision: Union[str, Sequence[str], None] = "hh89cc01dd23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS: list[tuple[str, str, str]] = [
    ("area:view", "areas", "Xem khu vuc"),
    ("area:create", "areas", "Tao khu vuc"),
    ("area:update", "areas", "Cap nhat khu vuc"),
    ("area:delete", "areas", "Xoa khu vuc"),
    ("areas:view", "areas", "Xem danh sach khu vuc"),
    ("areas:create", "areas", "Them moi khu vuc"),
    ("areas:update", "areas", "Cap nhat khu vuc"),
    ("areas:delete", "areas", "Xoa mem khu vuc"),
    ("branch:view", "branches", "Xem chi nhanh"),
    ("branch:create", "branches", "Tao chi nhanh"),
    ("branch:update", "branches", "Cap nhat chi nhanh"),
    ("branch:delete", "branches", "Xoa chi nhanh"),
    ("branches:view", "branches", "Xem danh sach chi nhanh"),
    ("branches:create", "branches", "Them moi chi nhanh"),
    ("branches:update", "branches", "Cap nhat chi nhanh"),
    ("branches:delete", "branches", "Xoa mem chi nhanh"),
    ("building:view", "buildings", "Xem toa nha"),
    ("building:create", "buildings", "Tao toa nha"),
    ("building:update", "buildings", "Cap nhat toa nha"),
    ("building:delete", "buildings", "Xoa toa nha"),
    ("buildings:view", "buildings", "Xem danh sach toa nha"),
    ("buildings:create", "buildings", "Them moi toa nha"),
    ("buildings:update", "buildings", "Cap nhat toa nha"),
    ("buildings:delete", "buildings", "Xoa mem toa nha"),
    ("room_type:view", "room_types", "Xem loai phong"),
    ("room_type:create", "room_types", "Tao loai phong"),
    ("room_type:update", "room_types", "Cap nhat loai phong"),
    ("room_type:delete", "room_types", "Xoa loai phong"),
    ("room_types:view", "room_types", "Xem danh sach loai phong"),
    ("room_types:create", "room_types", "Them moi loai phong"),
    ("room_types:update", "room_types", "Cap nhat loai phong"),
    ("room_types:delete", "room_types", "Xoa mem loai phong"),
    ("room:view", "rooms", "Xem phong"),
    ("room:create", "rooms", "Tao phong"),
    ("room:update", "rooms", "Cap nhat phong"),
    ("room:delete", "rooms", "Xoa phong"),
    ("rooms:view", "rooms", "Xem danh sach phong"),
    ("rooms:create", "rooms", "Them moi phong"),
    ("rooms:update", "rooms", "Cap nhat phong"),
    ("rooms:delete", "rooms", "Xoa mem phong"),
    ("renter:view", "renters", "Xem khach thue"),
    ("renter:create", "renters", "Tao khach thue"),
    ("renter:update", "renters", "Cap nhat khach thue"),
    ("renter:delete", "renters", "Xoa khach thue"),
    ("renters:view", "renters", "Xem danh sach khach thue"),
    ("renters:create", "renters", "Them moi khach thue"),
    ("renters:update", "renters", "Cap nhat khach thue"),
    ("renters:delete", "renters", "Xoa mem khach thue"),
    ("renter_member:view", "renter_members", "Xem thanh vien khach thue"),
    ("renter_member:create", "renter_members", "Them thanh vien khach thue"),
    ("renter_member:update", "renter_members", "Cap nhat thanh vien khach thue"),
    ("renter_member:delete", "renter_members", "Xoa thanh vien khach thue"),
    ("renter_members:view", "renter_members", "Xem danh sach thanh vien khach thue"),
    ("renter_members:create", "renter_members", "Them moi thanh vien khach thue"),
    ("renter_members:update", "renter_members", "Cap nhat thanh vien khach thue"),
    ("renter_members:delete", "renter_members", "Xoa mem thanh vien khach thue"),
    ("invoice:view", "invoices", "Xem hoa don"),
    ("invoice:create", "invoices", "Tao hoa don"),
    ("invoice:update", "invoices", "Cap nhat hoa don"),
    ("invoice:delete", "invoices", "Xoa hoa don"),
    ("invoices:view", "invoices", "Xem danh sach hoa don"),
    ("invoices:create", "invoices", "Them moi hoa don"),
    ("invoices:update", "invoices", "Cap nhat hoa don"),
    ("invoices:delete", "invoices", "Xoa mem hoa don"),
    ("deposit:view", "deposits", "Xem tien coc"),
    ("deposit:create", "deposits", "Tao tien coc"),
    ("deposit:update", "deposits", "Cap nhat tien coc"),
    ("deposit:delete", "deposits", "Xoa tien coc"),
    ("deposits:view", "deposits", "Xem danh sach tien coc"),
    ("deposits:create", "deposits", "Them moi tien coc"),
    ("deposits:update", "deposits", "Cap nhat tien coc"),
    ("deposits:delete", "deposits", "Xoa mem tien coc"),
    ("user:view", "users", "Xem nguoi dung"),
    ("user:create", "users", "Tao nguoi dung"),
    ("user:update", "users", "Cap nhat nguoi dung"),
    ("user:delete", "users", "Xoa nguoi dung"),
    ("user:mangage", "users", "Quyen quan ly tong hop nguoi dung (legacy typo)"),
    ("user:permision:view", "users", "Xem quyen nguoi dung (legacy typo)"),
    ("users:view", "users", "Xem danh sach nguoi dung"),
    ("users:create", "users", "Tao nguoi dung"),
    ("users:update", "users", "Cap nhat nguoi dung"),
    ("users:delete", "users", "Xoa mem nguoi dung"),
    ("users:manage", "users", "Quan ly toan bo nguoi dung"),
    ("users:permissions:view", "users", "Xem danh sach quyen nguoi dung"),
    ("users:permissions:manage", "users", "Quan ly toan bo quyen nguoi dung"),
    ("users:permissions:create", "users", "Them quyen override cho user"),
    ("users:permissions:update", "users", "Cap nhat quyen override cho user"),
    ("users:permissions:delete", "users", "Xoa quyen override cho user"),
    ("employees:create", "users", "Tao nhan vien"),
    ("form_templates:view", "forms", "Xem bieu mau"),
    ("form_templates:create", "forms", "Tao bieu mau"),
    ("form_templates:update", "forms", "Cap nhat bieu mau"),
    ("form_templates:delete", "forms", "Xoa bieu mau"),
    ("teams:view", "teams", "Xem thong tin team"),
    ("teams:create", "teams", "Tao team moi"),
    ("teams:members:manage", "teams", "Moi, cap nhat role, kick thanh vien team"),
    ("platform:developer:access", "platform", "Truy cap trang quan tri nen tang"),
    ("platform:plans:view", "platform", "Xem danh sach goi dich vu"),
    ("platform:plans:update", "platform", "Cap nhat goi dich vu"),
    ("platform:landing:view", "platform", "Xem noi dung landing page"),
    ("platform:landing:update", "platform", "Cap nhat noi dung landing page"),
]


def _upsert_permission(
    bind: sa.Connection,
    *,
    code: str,
    module: str,
    description: str,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module, description, created_at, updated_at, deleted_at)
            SELECT :code, :module, :description, NOW(), NOW(), NULL
            WHERE NOT EXISTS (
                SELECT 1
                FROM permissions
                WHERE code = :code
            )
            """
        ),
        {
            "code": code,
            "module": module,
            "description": description,
        },
    )
    bind.execute(
        sa.text(
            """
            UPDATE permissions
            SET
                module = :module,
                description = :description,
                deleted_at = NULL,
                updated_at = NOW()
            WHERE code = :code
            """
        ),
        {
            "code": code,
            "module": module,
            "description": description,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("permissions"):
        return

    for code, module, description in PERMISSIONS:
        _upsert_permission(
            bind,
            code=code,
            module=module,
            description=description,
        )


def downgrade() -> None:
    # Keep seeded permissions for backward compatibility with existing RBAC assignments.
    pass
