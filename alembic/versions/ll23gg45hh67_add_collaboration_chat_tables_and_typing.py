"""add collaboration chat tables and typing state

Revision ID: ll23gg45hh67
Revises: kk12ff34gg56
Create Date: 2026-03-17 23:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ll23gg45hh67"
down_revision: Union[str, Sequence[str], None] = "kk12ff34gg56"
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


def _ensure_index(
    bind: sa.Connection,
    *,
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("collab_notifications"):
        op.create_table(
            "collab_notifications",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("team_id", sa.BigInteger(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("notification_type", sa.String(length=32), nullable=False),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_notifications",
        index_name="ix_collab_notifications_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_notifications",
        index_name="ix_collab_notifications_team_id",
        columns=["team_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_notifications",
        index_name="ix_collab_notifications_created_by_user_id",
        columns=["created_by_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_notification_recipients"):
        op.create_table(
            "collab_notification_recipients",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("notification_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["notification_id"], ["collab_notifications.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "notification_id",
                "user_id",
                name="uq_collab_notification_recipients_notification_user",
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_notification_recipients",
        index_name="ix_collab_notification_recipients_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_notification_recipients",
        index_name="ix_collab_notification_recipients_notification_id",
        columns=["notification_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_notification_recipients",
        index_name="ix_collab_notification_recipients_user_id",
        columns=["user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_tasks"):
        op.create_table(
            "collab_tasks",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("team_id", sa.BigInteger(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("priority", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("assigned_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completion_report", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_tasks",
        index_name="ix_collab_tasks_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_tasks",
        index_name="ix_collab_tasks_team_id",
        columns=["team_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_tasks",
        index_name="ix_collab_tasks_assigned_by_user_id",
        columns=["assigned_by_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_task_assignees"):
        op.create_table(
            "collab_task_assignees",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("task_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["task_id"], ["collab_tasks.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "task_id",
                "user_id",
                name="uq_collab_task_assignees_task_user",
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_task_assignees",
        index_name="ix_collab_task_assignees_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_task_assignees",
        index_name="ix_collab_task_assignees_task_id",
        columns=["task_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_task_assignees",
        index_name="ix_collab_task_assignees_user_id",
        columns=["user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_task_attachments"):
        op.create_table(
            "collab_task_attachments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("task_id", sa.BigInteger(), nullable=False),
            sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=1024), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["task_id"], ["collab_tasks.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_task_attachments",
        index_name="ix_collab_task_attachments_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_task_attachments",
        index_name="ix_collab_task_attachments_task_id",
        columns=["task_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_task_attachments",
        index_name="ix_collab_task_attachments_uploaded_by_user_id",
        columns=["uploaded_by_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_chat_channels"):
        op.create_table(
            "collab_chat_channels",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("team_id", sa.BigInteger(), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "is_group", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_chat_channels",
        index_name="ix_collab_chat_channels_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_channels",
        index_name="ix_collab_chat_channels_team_id",
        columns=["team_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_channels",
        index_name="ix_collab_chat_channels_created_by_user_id",
        columns=["created_by_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_chat_channel_members"):
        op.create_table(
            "collab_chat_channel_members",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("last_read_message_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["channel_id"], ["collab_chat_channels.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "channel_id",
                "user_id",
                name="uq_collab_chat_channel_members_channel_user",
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_chat_channel_members",
        index_name="ix_collab_chat_channel_members_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_channel_members",
        index_name="ix_collab_chat_channel_members_channel_id",
        columns=["channel_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_channel_members",
        index_name="ix_collab_chat_channel_members_user_id",
        columns=["user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_chat_messages"):
        op.create_table(
            "collab_chat_messages",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("sender_user_id", sa.BigInteger(), nullable=True),
            sa.Column("message_type", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("reply_to_message_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["channel_id"], ["collab_chat_channels.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["sender_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_chat_messages",
        index_name="ix_collab_chat_messages_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_messages",
        index_name="ix_collab_chat_messages_channel_id",
        columns=["channel_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_messages",
        index_name="ix_collab_chat_messages_sender_user_id",
        columns=["sender_user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_chat_message_attachments"):
        op.create_table(
            "collab_chat_message_attachments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("message_id", sa.BigInteger(), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=1024), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["message_id"], ["collab_chat_messages.id"], ondelete="CASCADE"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_chat_message_attachments",
        index_name="ix_collab_chat_message_attachments_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_message_attachments",
        index_name="ix_collab_chat_message_attachments_message_id",
        columns=["message_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_chat_typing_states"):
        op.create_table(
            "collab_chat_typing_states",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "is_typing", sa.Boolean(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("last_typed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["channel_id"], ["collab_chat_channels.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "channel_id",
                "user_id",
                name="uq_collab_chat_typing_states_channel_user",
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_chat_typing_states",
        index_name="ix_collab_chat_typing_states_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_typing_states",
        index_name="ix_collab_chat_typing_states_channel_id",
        columns=["channel_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_chat_typing_states",
        index_name="ix_collab_chat_typing_states_user_id",
        columns=["user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_ai_sessions"):
        op.create_table(
            "collab_ai_sessions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("team_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_ai_sessions",
        index_name="ix_collab_ai_sessions_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_ai_sessions",
        index_name="ix_collab_ai_sessions_team_id",
        columns=["team_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_ai_sessions",
        index_name="ix_collab_ai_sessions_user_id",
        columns=["user_id"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("collab_ai_messages"):
        op.create_table(
            "collab_ai_messages",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("session_id", sa.BigInteger(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("token_usage", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["saas_tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["session_id"], ["collab_ai_sessions.id"], ondelete="CASCADE"
            ),
            *_timestamp_columns(),
        )
    _ensure_index(
        bind,
        table_name="collab_ai_messages",
        index_name="ix_collab_ai_messages_tenant_id",
        columns=["tenant_id"],
    )
    _ensure_index(
        bind,
        table_name="collab_ai_messages",
        index_name="ix_collab_ai_messages_session_id",
        columns=["session_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in [
        "collab_ai_messages",
        "collab_ai_sessions",
        "collab_chat_typing_states",
        "collab_chat_message_attachments",
        "collab_chat_messages",
        "collab_chat_channel_members",
        "collab_chat_channels",
        "collab_task_attachments",
        "collab_task_assignees",
        "collab_tasks",
        "collab_notification_recipients",
        "collab_notifications",
    ]:
        if inspector.has_table(table_name):
            op.drop_table(table_name)
            inspector = sa.inspect(bind)
