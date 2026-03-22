"""remove mysql vector storage artifacts for ai collaboration

Revision ID: kk12ff34gg56
Revises: jj01ee23ff45
Create Date: 2026-03-17 20:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "kk12ff34gg56"
down_revision: Union[str, Sequence[str], None] = "jj01ee23ff45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("collab_ai_vector_documents"):
        op.drop_table("collab_ai_vector_documents")

    inspector = sa.inspect(bind)
    if inspector.has_table("collab_ai_sessions"):
        columns = {item["name"] for item in inspector.get_columns("collab_ai_sessions")}
        if "vector_namespace" in columns:
            op.drop_column("collab_ai_sessions", "vector_namespace")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("collab_ai_sessions"):
        columns = {item["name"] for item in inspector.get_columns("collab_ai_sessions")}
        if "vector_namespace" not in columns:
            op.add_column(
                "collab_ai_sessions",
                sa.Column("vector_namespace", sa.String(length=255), nullable=True),
            )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_ai_vector_documents"):
        op.create_table(
            "collab_ai_vector_documents",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("session_id", sa.BigInteger(), nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("source_ref_id", sa.String(length=128), nullable=True),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("embedding_provider", sa.String(length=64), nullable=True),
            sa.Column("vector_id", sa.String(length=255), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["saas_tenants.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["collab_ai_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_collab_ai_vector_documents_tenant_id",
            "collab_ai_vector_documents",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            "ix_collab_ai_vector_documents_session_id",
            "collab_ai_vector_documents",
            ["session_id"],
            unique=False,
        )
