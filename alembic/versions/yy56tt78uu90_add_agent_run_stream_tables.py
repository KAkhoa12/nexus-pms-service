"""add agent run stream tables

Revision ID: yy56tt78uu90
Revises: xx45ss67tt89
Create Date: 2026-03-21 12:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "yy56tt78uu90"
down_revision: Union[str, Sequence[str], None] = "xx45ss67tt89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(length=64), nullable=False, unique=True),
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
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("workspace_key", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("execution_mode", sa.String(length=32), nullable=False),
            sa.Column("model_tier", sa.String(length=32), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "locale",
                sa.String(length=16),
                nullable=False,
                server_default="vi-VN",
            ),
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("partial_answer", sa.Text(), nullable=True),
            sa.Column("final_answer", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("runtime_context_json", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        )

        op.create_index(
            op.f("ix_agent_runs_thread_id"),
            "agent_runs",
            ["thread_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_runs_status"),
            "agent_runs",
            ["status"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_runs_user_id"),
            "agent_runs",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_agent_runs_tenant_id"),
            "agent_runs",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_runs_tenant_user_status_created",
            "agent_runs",
            ["tenant_id", "user_id", "status", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_agent_runs_thread_created",
            "agent_runs",
            ["thread_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_agent_runs_workspace_status",
            "agent_runs",
            ["workspace_key", "status"],
            unique=False,
        )

    if not inspector.has_table("agent_run_events"):
        op.create_table(
            "agent_run_events",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_pk_id",
                sa.BigInteger(),
                sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            op.f("ix_agent_run_events_run_pk_id"),
            "agent_run_events",
            ["run_pk_id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_run_events_run_event",
            "agent_run_events",
            ["run_pk_id", "id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_run_events_created",
            "agent_run_events",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("agent_run_events"):
        op.drop_table("agent_run_events")

    if inspector.has_table("agent_runs"):
        op.drop_table("agent_runs")
