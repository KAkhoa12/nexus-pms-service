from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CollaborationAttachmentInput(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_url: str = Field(min_length=1, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=128)
    size_bytes: int | None = Field(default=None, ge=0)


class CollaborationAttachmentOut(BaseModel):
    id: int
    file_name: str
    file_url: str
    mime_type: str | None
    size_bytes: int | None


class NotificationCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    notification_type: str = Field(
        default="ALL_USERS",
        description="SYSTEM | ALL_USERS | SELECTED_USERS",
    )
    team_id: int | None = Field(default=None, ge=1)
    recipient_user_ids: list[int] = Field(default_factory=list)


class NotificationOut(BaseModel):
    id: int
    team_id: int | None
    title: str
    body: str
    notification_type: str
    created_by_user_id: int | None
    published_at: datetime
    is_read: bool
    read_at: datetime | None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    team_id: int | None = Field(default=None, ge=1)
    priority: str = Field(default="MEDIUM")
    due_at: datetime | None = None
    assignee_user_ids: list[int] = Field(default_factory=list)
    attachments: list[CollaborationAttachmentInput] = Field(default_factory=list)


class TaskStatusUpdateRequest(BaseModel):
    status: str = Field(description="TODO | IN_PROGRESS | DONE | CANCELLED")
    completion_report: str | None = None
    attachments: list[CollaborationAttachmentInput] = Field(default_factory=list)


class TaskOut(BaseModel):
    id: int
    team_id: int | None
    title: str
    description: str | None
    priority: str
    status: str
    assigned_by_user_id: int | None
    due_at: datetime | None
    completed_at: datetime | None
    completion_report: str | None
    assignee_user_ids: list[int]
    attachments: list[CollaborationAttachmentOut]
    created_at: datetime
    updated_at: datetime


class ChatChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    team_id: int | None = Field(default=None, ge=1)
    is_group: bool = True
    member_user_ids: list[int] = Field(default_factory=list)


class ChatChannelOut(BaseModel):
    id: int
    team_id: int | None
    name: str
    is_group: bool
    is_active: bool
    member_user_ids: list[int]
    unread_count: int = 0
    last_message_id: int | None = None
    last_message_content: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(default="")
    message_type: str = Field(default="TEXT")
    reply_to_message_id: int | None = Field(default=None, ge=1)
    attachments: list[CollaborationAttachmentInput] = Field(default_factory=list)


class ChatMessageOut(BaseModel):
    id: int
    channel_id: int
    sender_user_id: int | None
    message_type: str
    content: str
    reply_to_message_id: int | None
    attachments: list[CollaborationAttachmentOut]
    created_at: datetime


class ChatUploadOut(BaseModel):
    file_name: str
    file_url: str
    mime_type: str | None
    size_bytes: int
    is_image: bool


class ChatTypingUpdateRequest(BaseModel):
    is_typing: bool = True


class ChatTypingOut(BaseModel):
    user_id: int
    full_name: str
    avatar_url: str | None
    is_typing: bool
    last_typed_at: datetime | None
    expires_at: datetime | None


class PresenceHeartbeatRequest(BaseModel):
    is_online: bool = True


class PresenceOut(BaseModel):
    user_id: int
    is_online: bool
    updated_at: datetime | None


class AiSessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    team_id: int | None = Field(default=None, ge=1)


class AiSessionOut(BaseModel):
    id: int
    team_id: int | None
    user_id: int
    title: str
    is_active: bool
    last_message_at: datetime | None
    created_at: datetime


class AiMessageCreateRequest(BaseModel):
    role: str = Field(default="user", description="system | user | assistant")
    content: str = Field(min_length=1)
    token_usage: int | None = Field(default=None, ge=0)


class AiMessageOut(BaseModel):
    id: int
    role: str
    content: str
    token_usage: int | None
    created_at: datetime
