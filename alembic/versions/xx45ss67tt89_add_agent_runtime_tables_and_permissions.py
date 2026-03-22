"""add agent runtime tables and permissions

Revision ID: xx45ss67tt89
Revises: ww34rr56ss78
Create Date: 2026-03-20 23:55:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "xx45ss67tt89"
down_revision: Union[str, Sequence[str], None] = "ww34rr56ss78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AGENT_PERMISSIONS: list[tuple[str, str, str]] = [
    ("agents:query", "Truy vấn AI agent read-only", "Trợ lý AI"),
    ("agents:reporting:kpi:view", "Xem KPI vận hành qua AI", "Trợ lý AI"),
    ("agents:billing:overdue:view", "Xem hóa đơn quá hạn qua AI", "Trợ lý AI"),
    ("agents:knowledge:search", "Tra cứu tri thức nội bộ qua AI", "Trợ lý AI"),
    (
        "agents:notifications:draft:create",
        "Tạo nháp thông báo bằng AI (chưa commit)",
        "Trợ lý AI",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_checkpoints"):
        op.create_table(
            "agent_checkpoints",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.BigInteger(),
                sa.ForeignKey("saas_tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("request_id", sa.String(length=64), nullable=False),
            sa.Column("thread_id", sa.String(length=128), nullable=False),
            sa.Column("checkpoint_ns", sa.String(length=255), nullable=False),
            sa.Column("graph_name", sa.String(length=64), nullable=False),
            sa.Column("node_name", sa.String(length=64), nullable=False),
            sa.Column("execution_mode", sa.String(length=32), nullable=False),
            sa.Column("state_json", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_agent_checkpoints_tenant_thread_created",
            "agent_checkpoints",
            ["tenant_id", "user_id", "thread_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_agent_checkpoints_request",
            "agent_checkpoints",
            ["request_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_checkpoints_tenant_id"),
            "agent_checkpoints",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_checkpoints_user_id"),
            "agent_checkpoints",
            ["user_id"],
            unique=False,
        )

    if not inspector.has_table("agent_tool_audit_logs"):
        op.create_table(
            "agent_tool_audit_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.BigInteger(),
                sa.ForeignKey("saas_tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("request_id", sa.String(length=64), nullable=False),
            sa.Column("thread_id", sa.String(length=128), nullable=False),
            sa.Column("graph_name", sa.String(length=64), nullable=False),
            sa.Column("node_name", sa.String(length=64), nullable=False),
            sa.Column("tool_name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("input_json", sa.Text(), nullable=True),
            sa.Column("output_json", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_agent_tool_audit_logs_tenant_created",
            "agent_tool_audit_logs",
            ["tenant_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_agent_tool_audit_logs_thread",
            "agent_tool_audit_logs",
            ["thread_id", "created_at"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_tool_audit_logs_tenant_id"),
            "agent_tool_audit_logs",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_tool_audit_logs_user_id"),
            "agent_tool_audit_logs",
            ["user_id"],
            unique=False,
        )

    if not inspector.has_table("agent_knowledge_documents"):
        op.create_table(
            "agent_knowledge_documents",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "tenant_id",
                sa.BigInteger(),
                sa.ForeignKey("saas_tenants.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tags_json", sa.Text(), nullable=True),
            sa.Column(
                "source_type",
                sa.String(length=64),
                nullable=False,
                server_default="manual",
            ),
            sa.Column("source_ref", sa.String(length=255), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_agent_knowledge_documents_tenant_active",
            "agent_knowledge_documents",
            ["tenant_id", "is_active"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_knowledge_documents_tenant_id"),
            "agent_knowledge_documents",
            ["tenant_id"],
            unique=False,
        )

    if inspector.has_table("permissions"):
        columns = {column["name"] for column in inspector.get_columns("permissions")}
        has_module_mean = "module_mean" in columns
        for code, description, module_mean in AGENT_PERMISSIONS:
            if has_module_mean:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO permissions
                            (code, module, module_mean, description, created_at, updated_at, deleted_at)
                        SELECT
                            :code, 'agents', :module_mean, :description, NOW(), NOW(), NULL
                        WHERE NOT EXISTS (
                            SELECT 1 FROM permissions WHERE code = :code
                        )
                        """
                    ),
                    {
                        "code": code,
                        "description": description,
                        "module_mean": module_mean,
                    },
                )
                bind.execute(
                    sa.text(
                        """
                        UPDATE permissions
                        SET module = 'agents',
                            module_mean = :module_mean,
                            description = :description,
                            deleted_at = NULL,
                            updated_at = NOW()
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": code,
                        "description": description,
                        "module_mean": module_mean,
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO permissions
                            (code, module, description, created_at, updated_at, deleted_at)
                        SELECT
                            :code, 'agents', :description, NOW(), NOW(), NULL
                        WHERE NOT EXISTS (
                            SELECT 1 FROM permissions WHERE code = :code
                        )
                        """
                    ),
                    {
                        "code": code,
                        "description": description,
                    },
                )
                bind.execute(
                    sa.text(
                        """
                        UPDATE permissions
                        SET module = 'agents',
                            description = :description,
                            deleted_at = NULL,
                            updated_at = NOW()
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": code,
                        "description": description,
                    },
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("agent_tool_audit_logs"):
        op.drop_table("agent_tool_audit_logs")
    if inspector.has_table("agent_checkpoints"):
        op.drop_table("agent_checkpoints")
    if inspector.has_table("agent_knowledge_documents"):
        op.drop_table("agent_knowledge_documents")

    # Keep permissions on downgrade to avoid breaking assigned roles.
