"""add platform admins table for developer portal login

Revision ID: hh89cc01dd23
Revises: gg78bb90cc12
Create Date: 2026-03-16 14:05:00.000000

"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hh89cc01dd23"
down_revision: Union[str, Sequence[str], None] = "gg78bb90cc12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 210000
DEFAULT_ADMIN_EMAIL = "developer@quanlyphongtro.local"
DEFAULT_ADMIN_PASSWORD = "Admin123@"
DEFAULT_ADMIN_NAME = "System Developer Admin"


def _pbkdf2_hash(
    password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS
) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _make_pbkdf2_password_hash(
    password: str, iterations: int = PBKDF2_ITERATIONS
) -> str:
    salt = os.urandom(16)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8")
    digest_b64 = _pbkdf2_hash(password, salt, iterations)
    return f"{PBKDF2_SCHEME}${iterations}${salt_b64}${digest_b64}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("platform_admins"):
        op.create_table(
            "platform_admins",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_platform_admins_email"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("platform_admins"):
        indexes = {index["name"] for index in inspector.get_indexes("platform_admins")}
        if "ix_platform_admins_active" not in indexes:
            op.create_index(
                "ix_platform_admins_active",
                "platform_admins",
                ["is_active"],
                unique=False,
            )

        bind.execute(
            sa.text(
                """
                INSERT INTO platform_admins (
                    email,
                    full_name,
                    password_hash,
                    is_active,
                    last_login_at,
                    created_at,
                    updated_at
                )
                SELECT
                    :email,
                    :full_name,
                    :password_hash,
                    1,
                    NULL,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM platform_admins
                    WHERE email = :email
                      AND deleted_at IS NULL
                )
                """
            ),
            {
                "email": DEFAULT_ADMIN_EMAIL,
                "full_name": DEFAULT_ADMIN_NAME,
                "password_hash": _make_pbkdf2_password_hash(DEFAULT_ADMIN_PASSWORD),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("platform_admins"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("platform_admins")}
    if "ix_platform_admins_active" in indexes:
        op.drop_index("ix_platform_admins_active", table_name="platform_admins")
    op.drop_table("platform_admins")
