from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import TimestampSoftDeleteMixin


class CollabNotification(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    recipients: Mapped[list["CollabNotificationRecipient"]] = relationship(
        back_populates="notification"
    )


class CollabNotificationRecipient(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_notification_recipients"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_collab_notification_recipients_notification_user",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("collab_notifications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notification: Mapped["CollabNotification"] = relationship(
        back_populates="recipients"
    )


class CollabTask(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="TODO")
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completion_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignees: Mapped[list["CollabTaskAssignee"]] = relationship(back_populates="task")
    attachments: Mapped[list["CollabTaskAttachment"]] = relationship(
        back_populates="task"
    )


class CollabTaskAssignee(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_task_assignees"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "user_id",
            name="uq_collab_task_assignees_task_user",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("collab_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    task: Mapped["CollabTask"] = relationship(back_populates="assignees")


class CollabTaskAttachment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_task_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("collab_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task: Mapped["CollabTask"] = relationship(back_populates="attachments")


class CollabChatChannel(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_chat_channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    members: Mapped[list["CollabChatChannelMember"]] = relationship(
        back_populates="channel"
    )
    messages: Mapped[list["CollabChatMessage"]] = relationship(back_populates="channel")
    typing_states: Mapped[list["CollabChatTypingState"]] = relationship(
        back_populates="channel"
    )


class CollabChatChannelMember(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_chat_channel_members"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_collab_chat_channel_members_channel_user",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("collab_chat_channels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    last_read_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    channel: Mapped["CollabChatChannel"] = relationship(back_populates="members")


class CollabChatMessage(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("collab_chat_channels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sender_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    message_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="TEXT"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    channel: Mapped["CollabChatChannel"] = relationship(back_populates="messages")
    attachments: Mapped[list["CollabChatMessageAttachment"]] = relationship(
        back_populates="message"
    )


class CollabChatMessageAttachment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_chat_message_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("collab_chat_messages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message: Mapped["CollabChatMessage"] = relationship(back_populates="attachments")


class CollabChatTypingState(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_chat_typing_states"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_collab_chat_typing_states_channel_user",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("collab_chat_channels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    is_typing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_typed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    channel: Mapped["CollabChatChannel"] = relationship(back_populates="typing_states")


class CollabAiSession(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_ai_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    messages: Mapped[list["CollabAiMessage"]] = relationship(back_populates="session")


class CollabAiMessage(TimestampSoftDeleteMixin, Base):
    __tablename__ = "collab_ai_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("collab_ai_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["CollabAiSession"] = relationship(back_populates="messages")


__all__ = [
    "CollabNotification",
    "CollabNotificationRecipient",
    "CollabTask",
    "CollabTaskAssignee",
    "CollabTaskAttachment",
    "CollabChatChannel",
    "CollabChatChannelMember",
    "CollabChatMessage",
    "CollabChatMessageAttachment",
    "CollabChatTypingState",
    "CollabAiSession",
    "CollabAiMessage",
]
