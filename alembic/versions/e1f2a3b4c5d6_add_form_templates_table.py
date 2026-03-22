"""add form_templates table

Revision ID: e1f2a3b4c5d6
Revises: c9f7d6b1e2a3
Create Date: 2026-03-11 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "c9f7d6b1e2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("form_templates"):
        op.create_table(
            "form_templates",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "template_type",
                sa.String(length=32),
                server_default="GENERAL",
                nullable=False,
            ),
            sa.Column(
                "page_size", sa.String(length=16), server_default="A4", nullable=False
            ),
            sa.Column(
                "orientation",
                sa.String(length=16),
                server_default="portrait",
                nullable=False,
            ),
            sa.Column(
                "font_family",
                sa.String(length=64),
                server_default="Arial",
                nullable=False,
            ),
            sa.Column("font_size", sa.Integer(), server_default="14", nullable=False),
            sa.Column(
                "text_color",
                sa.String(length=16),
                server_default="#111827",
                nullable=False,
            ),
            sa.Column("content_html", sa.Text(), server_default="", nullable=False),
            sa.Column("config_json", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
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
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "name", name="uq_form_templates_tenant_name"
            ),
        )

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("form_templates")
    }
    tenant_idx_name = op.f("ix_form_templates_tenant_id")
    if tenant_idx_name not in existing_indexes:
        op.create_index(
            tenant_idx_name,
            "form_templates",
            ["tenant_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("form_templates"):
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("form_templates")
    }
    tenant_idx_name = op.f("ix_form_templates_tenant_id")
    if tenant_idx_name in existing_indexes:
        op.drop_index(tenant_idx_name, table_name="form_templates")
    op.drop_table("form_templates")
