from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.collaboration.schemas import (
    AiMessageCreateRequest,
    AiMessageOut,
    AiSessionCreateRequest,
    AiSessionOut,
    ChatChannelCreateRequest,
    ChatChannelOut,
    ChatMessageCreateRequest,
    ChatMessageOut,
    ChatTypingOut,
    ChatTypingUpdateRequest,
    ChatUploadOut,
    CollaborationAttachmentOut,
    NotificationCreateRequest,
    NotificationOut,
    PresenceHeartbeatRequest,
    PresenceOut,
    TaskCreateRequest,
    TaskOut,
    TaskStatusUpdateRequest,
)
from app.modules.core.models import (
    CollabAiMessage,
    CollabAiSession,
    CollabChatChannel,
    CollabChatChannelMember,
    CollabChatMessage,
    CollabChatMessageAttachment,
    CollabChatTypingState,
    CollabNotification,
    CollabNotificationRecipient,
    CollabTask,
    CollabTaskAssignee,
    CollabTaskAttachment,
    Team,
    TeamMember,
    User,
)
from app.services.minio_storage import (
    MinioStorageError,
    build_chat_object_name,
    get_chat_object_stream,
    upload_chat_bytes,
)
from app.services.realtime_pubsub import (
    list_online_user_ids,
    publish_chat_message,
    publish_notification,
    publish_typing,
    update_presence,
)

CHAT_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


def _ensure_team_member_access(db: Session, *, user_id: int, team_id: int) -> None:
    exists = db.scalar(
        select(TeamMember.id)
        .join(Team, Team.id == TeamMember.team_id)
        .where(
            TeamMember.user_id == user_id,
            TeamMember.team_id == team_id,
            TeamMember.deleted_at.is_(None),
            Team.deleted_at.is_(None),
            Team.is_active.is_(True),
        )
    )
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team access denied",
        )


def _validate_user_ids(
    db: Session,
    *,
    tenant_id: int,
    user_ids: list[int],
) -> list[int]:
    normalized = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
    if not normalized:
        return []
    found = set(
        db.scalars(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.id.in_(normalized),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        ).all()
    )
    if found != set(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more users are invalid in this workspace",
        )
    return normalized


def _attachment_out_from_task(item: CollabTaskAttachment) -> CollaborationAttachmentOut:
    return CollaborationAttachmentOut(
        id=item.id,
        file_name=item.file_name,
        file_url=item.file_url,
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
    )


def _attachment_out_from_message(
    item: CollabChatMessageAttachment,
) -> CollaborationAttachmentOut:
    return CollaborationAttachmentOut(
        id=item.id,
        file_name=item.file_name,
        file_url=item.file_url,
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
    )


def _is_image_mime(content_type: str | None, file_name: str) -> bool:
    normalized = (content_type or "").lower()
    if normalized.startswith("image/"):
        return True
    file_name = file_name.lower()
    return any(
        file_name.endswith(extension)
        for extension in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    )


def _object_name_from_file_url(file_url: str) -> str:
    prefix = "/api/v1/collaboration/chat/files/"
    if not file_url.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat file URL",
        )
    return file_url[len(prefix) :]


def ensure_chat_file_access(current_user: User, *, object_name: str) -> None:
    if not object_name.startswith(f"tenant-{current_user.tenant_id}/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat file access denied",
        )


def get_chat_file_stream(
    current_user: User,
    *,
    object_name: str,
) -> tuple[object, str | None, int | None]:
    ensure_chat_file_access(current_user, object_name=object_name)
    try:
        stream = get_chat_object_stream(object_name)
    except MinioStorageError as exc:
        error_message = str(exc).lower()
        if "no such key" in error_message or "not found" in error_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot read file from MinIO",
        ) from exc
    return stream.object_data, stream.content_type, stream.content_length


def _ensure_attachment_urls_belong_to_tenant(
    current_user: User,
    *,
    attachments: list,
) -> None:
    for attachment in attachments:
        file_url = str(getattr(attachment, "file_url", ""))
        if file_url.startswith("/api/v1/collaboration/chat/files/"):
            object_name = _object_name_from_file_url(file_url)
            ensure_chat_file_access(current_user, object_name=object_name)


def _publish_chat_message_event(
    *,
    current_user: User,
    room_id: int,
    message_id: int,
    message_type: str,
) -> None:
    publish_chat_message(
        tenant_id=current_user.tenant_id,
        room_id=room_id,
        payload={
            "event": "chat_message",
            "tenant_id": current_user.tenant_id,
            "room_id": room_id,
            "message_id": message_id,
            "sender_user_id": current_user.id,
            "message_type": message_type,
            "created_at": datetime.now(timezone.utc),
        },
    )


def _publish_typing_event(
    *,
    current_user: User,
    room_id: int,
    is_typing: bool,
) -> None:
    publish_typing(
        tenant_id=current_user.tenant_id,
        room_id=room_id,
        payload={
            "event": "typing",
            "tenant_id": current_user.tenant_id,
            "room_id": room_id,
            "user_id": current_user.id,
            "is_typing": is_typing,
            "updated_at": datetime.now(timezone.utc),
        },
    )


def _publish_notification_event(
    *,
    tenant_id: int,
    user_id: int,
    notification_id: int,
    notification_type: str,
) -> None:
    publish_notification(
        tenant_id=tenant_id,
        user_id=user_id,
        payload={
            "event": "notification",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "notification_id": notification_id,
            "notification_type": notification_type,
            "created_at": datetime.now(timezone.utc),
        },
    )


async def upload_chat_attachment(
    *,
    current_user: User,
    upload_file: UploadFile,
) -> ChatUploadOut:
    if upload_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload file is required",
        )

    content = await upload_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(content) > CHAT_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large (max 10MB)",
        )

    object_name = build_chat_object_name(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        file_name=upload_file.filename or "file.bin",
        content_type=upload_file.content_type,
    )
    try:
        upload_chat_bytes(
            object_name=object_name,
            content=content,
            content_type=upload_file.content_type,
        )
    except MinioStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot upload file to MinIO",
        ) from exc

    file_url = f"/api/v1/collaboration/chat/files/{object_name}"
    return ChatUploadOut(
        file_name=upload_file.filename or "file.bin",
        file_url=file_url,
        mime_type=(upload_file.content_type or None),
        size_bytes=len(content),
        is_image=_is_image_mime(upload_file.content_type, upload_file.filename or ""),
    )


def create_notification(
    db: Session,
    current_user: User,
    payload: NotificationCreateRequest,
) -> NotificationOut:
    if payload.team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=payload.team_id)

    notification_type = payload.notification_type.strip().upper()
    if notification_type not in {"SYSTEM", "ALL_USERS", "SELECTED_USERS"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="notification_type must be SYSTEM, ALL_USERS or SELECTED_USERS",
        )

    notification = CollabNotification(
        tenant_id=current_user.tenant_id,
        team_id=payload.team_id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        notification_type=notification_type,
        created_by_user_id=current_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.flush()

    if notification_type == "SELECTED_USERS":
        recipient_ids = _validate_user_ids(
            db,
            tenant_id=current_user.tenant_id,
            user_ids=payload.recipient_user_ids,
        )
        if not recipient_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_user_ids is required for SELECTED_USERS",
            )
    else:
        if payload.team_id is not None:
            recipient_ids = list(
                db.scalars(
                    select(TeamMember.user_id).where(
                        TeamMember.team_id == payload.team_id,
                        TeamMember.deleted_at.is_(None),
                    )
                ).all()
            )
        else:
            recipient_ids = list(
                db.scalars(
                    select(User.id).where(
                        User.tenant_id == current_user.tenant_id,
                        User.deleted_at.is_(None),
                        User.is_active.is_(True),
                    )
                ).all()
            )

    for user_id in sorted({int(item) for item in recipient_ids}):
        db.add(
            CollabNotificationRecipient(
                tenant_id=current_user.tenant_id,
                notification_id=notification.id,
                user_id=user_id,
                read_at=None,
            )
        )

    db.commit()
    for user_id in sorted({int(item) for item in recipient_ids}):
        _publish_notification_event(
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            notification_id=notification.id,
            notification_type=notification.notification_type,
        )
    return NotificationOut(
        id=notification.id,
        team_id=notification.team_id,
        title=notification.title,
        body=notification.body,
        notification_type=notification.notification_type,
        created_by_user_id=notification.created_by_user_id,
        published_at=notification.published_at,
        is_read=False,
        read_at=None,
    )


def list_my_notifications(db: Session, current_user: User) -> list[NotificationOut]:
    now_utc = datetime.now(timezone.utc)
    rows = db.execute(
        select(CollabNotification, CollabNotificationRecipient)
        .join(
            CollabNotificationRecipient,
            CollabNotificationRecipient.notification_id == CollabNotification.id,
        )
        .where(
            CollabNotification.tenant_id == current_user.tenant_id,
            CollabNotification.deleted_at.is_(None),
            CollabNotification.published_at <= now_utc,
            CollabNotificationRecipient.user_id == current_user.id,
            CollabNotificationRecipient.deleted_at.is_(None),
        )
        .order_by(CollabNotification.published_at.desc(), CollabNotification.id.desc())
        .limit(300)
    ).all()
    return [
        NotificationOut(
            id=item.id,
            team_id=item.team_id,
            title=item.title,
            body=item.body,
            notification_type=item.notification_type,
            created_by_user_id=item.created_by_user_id,
            published_at=item.published_at,
            is_read=recipient.read_at is not None,
            read_at=recipient.read_at,
        )
        for item, recipient in rows
    ]


def mark_notification_read(
    db: Session,
    current_user: User,
    *,
    notification_id: int,
) -> NotificationOut:
    now_utc = datetime.now(timezone.utc)
    row = db.execute(
        select(CollabNotification, CollabNotificationRecipient)
        .join(
            CollabNotificationRecipient,
            CollabNotificationRecipient.notification_id == CollabNotification.id,
        )
        .where(
            CollabNotification.id == notification_id,
            CollabNotification.tenant_id == current_user.tenant_id,
            CollabNotification.deleted_at.is_(None),
            CollabNotification.published_at <= now_utc,
            CollabNotificationRecipient.user_id == current_user.id,
            CollabNotificationRecipient.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification, recipient = row
    recipient.read_at = datetime.now(timezone.utc)
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    return NotificationOut(
        id=notification.id,
        team_id=notification.team_id,
        title=notification.title,
        body=notification.body,
        notification_type=notification.notification_type,
        created_by_user_id=notification.created_by_user_id,
        published_at=notification.published_at,
        is_read=True,
        read_at=recipient.read_at,
    )


def _to_task_out(
    db: Session,
    *,
    task: CollabTask,
) -> TaskOut:
    assignee_user_ids = list(
        db.scalars(
            select(CollabTaskAssignee.user_id).where(
                CollabTaskAssignee.task_id == task.id,
                CollabTaskAssignee.deleted_at.is_(None),
            )
        ).all()
    )
    attachments = list(
        db.scalars(
            select(CollabTaskAttachment).where(
                CollabTaskAttachment.task_id == task.id,
                CollabTaskAttachment.deleted_at.is_(None),
            )
        ).all()
    )
    return TaskOut(
        id=task.id,
        team_id=task.team_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        assigned_by_user_id=task.assigned_by_user_id,
        due_at=task.due_at,
        completed_at=task.completed_at,
        completion_report=task.completion_report,
        assignee_user_ids=assignee_user_ids,
        attachments=[_attachment_out_from_task(item) for item in attachments],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def create_task(db: Session, current_user: User, payload: TaskCreateRequest) -> TaskOut:
    if payload.team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=payload.team_id)

    assignee_user_ids = _validate_user_ids(
        db,
        tenant_id=current_user.tenant_id,
        user_ids=payload.assignee_user_ids or [current_user.id],
    )

    task = CollabTask(
        tenant_id=current_user.tenant_id,
        team_id=payload.team_id,
        title=payload.title.strip(),
        description=payload.description,
        priority=payload.priority.strip().upper(),
        status="TODO",
        assigned_by_user_id=current_user.id,
        due_at=payload.due_at,
        completed_at=None,
        completion_report=None,
    )
    db.add(task)
    db.flush()

    for assignee_user_id in assignee_user_ids:
        db.add(
            CollabTaskAssignee(
                tenant_id=current_user.tenant_id,
                task_id=task.id,
                user_id=assignee_user_id,
            )
        )
    for attachment in payload.attachments:
        db.add(
            CollabTaskAttachment(
                tenant_id=current_user.tenant_id,
                task_id=task.id,
                uploaded_by_user_id=current_user.id,
                file_name=attachment.file_name,
                file_url=attachment.file_url,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
            )
        )
    db.commit()
    db.refresh(task)
    return _to_task_out(db, task=task)


def list_tasks(
    db: Session,
    current_user: User,
    *,
    team_id: int | None,
) -> list[TaskOut]:
    stmt = select(CollabTask).where(
        CollabTask.tenant_id == current_user.tenant_id,
        CollabTask.deleted_at.is_(None),
    )
    if team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=team_id)
        stmt = stmt.where(CollabTask.team_id == team_id)

    assignee_subquery = (
        select(CollabTaskAssignee.task_id)
        .where(
            CollabTaskAssignee.user_id == current_user.id,
            CollabTaskAssignee.deleted_at.is_(None),
        )
        .subquery()
    )
    stmt = stmt.where(
        or_(
            CollabTask.assigned_by_user_id == current_user.id,
            CollabTask.id.in_(select(assignee_subquery.c.task_id)),
        )
    )
    tasks = list(
        db.scalars(
            stmt.order_by(CollabTask.updated_at.desc(), CollabTask.id.desc()).limit(200)
        ).all()
    )
    return [_to_task_out(db, task=item) for item in tasks]


def update_task_status(
    db: Session,
    current_user: User,
    *,
    task_id: int,
    payload: TaskStatusUpdateRequest,
) -> TaskOut:
    task = db.scalar(
        select(CollabTask).where(
            CollabTask.id == task_id,
            CollabTask.tenant_id == current_user.tenant_id,
            CollabTask.deleted_at.is_(None),
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    is_assignee = db.scalar(
        select(CollabTaskAssignee.id).where(
            CollabTaskAssignee.task_id == task.id,
            CollabTaskAssignee.user_id == current_user.id,
            CollabTaskAssignee.deleted_at.is_(None),
        )
    )
    if task.assigned_by_user_id != current_user.id and is_assignee is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Task access denied",
        )

    next_status = payload.status.strip().upper()
    if next_status not in {"TODO", "IN_PROGRESS", "DONE", "CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task status",
        )

    task.status = next_status
    task.completion_report = payload.completion_report
    task.completed_at = datetime.now(timezone.utc) if next_status == "DONE" else None
    db.add(task)
    db.flush()

    for attachment in payload.attachments:
        db.add(
            CollabTaskAttachment(
                tenant_id=current_user.tenant_id,
                task_id=task.id,
                uploaded_by_user_id=current_user.id,
                file_name=attachment.file_name,
                file_url=attachment.file_url,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
            )
        )

    db.commit()
    db.refresh(task)
    return _to_task_out(db, task=task)


def _to_channel_out(
    db: Session,
    *,
    channel: CollabChatChannel,
    viewer_user_id: int,
) -> ChatChannelOut:
    member_user_ids = list(
        db.scalars(
            select(CollabChatChannelMember.user_id).where(
                CollabChatChannelMember.channel_id == channel.id,
                CollabChatChannelMember.deleted_at.is_(None),
            )
        ).all()
    )
    viewer_member = db.scalar(
        select(CollabChatChannelMember).where(
            CollabChatChannelMember.channel_id == channel.id,
            CollabChatChannelMember.user_id == viewer_user_id,
            CollabChatChannelMember.deleted_at.is_(None),
        )
    )
    last_message = db.scalar(
        select(CollabChatMessage)
        .where(
            CollabChatMessage.channel_id == channel.id,
            CollabChatMessage.deleted_at.is_(None),
        )
        .order_by(CollabChatMessage.created_at.desc(), CollabChatMessage.id.desc())
        .limit(1)
    )
    unread_count = 0
    if viewer_member is not None:
        unread_stmt = select(func.count(CollabChatMessage.id)).where(
            CollabChatMessage.channel_id == channel.id,
            CollabChatMessage.deleted_at.is_(None),
            CollabChatMessage.sender_user_id != viewer_user_id,
        )
        if viewer_member.last_read_message_id is not None:
            unread_stmt = unread_stmt.where(
                CollabChatMessage.id > int(viewer_member.last_read_message_id)
            )
        unread_count = int(db.scalar(unread_stmt) or 0)

    return ChatChannelOut(
        id=channel.id,
        team_id=channel.team_id,
        name=channel.name,
        is_group=channel.is_group,
        is_active=channel.is_active,
        member_user_ids=member_user_ids,
        unread_count=unread_count,
        last_message_id=last_message.id if last_message is not None else None,
        last_message_content=(
            last_message.content if last_message is not None else None
        ),
        last_message_at=(last_message.created_at if last_message is not None else None),
        created_at=channel.created_at,
    )


def _get_channel_member_ids(db: Session, *, channel_id: int) -> list[int]:
    return list(
        db.scalars(
            select(CollabChatChannelMember.user_id).where(
                CollabChatChannelMember.channel_id == channel_id,
                CollabChatChannelMember.deleted_at.is_(None),
            )
        ).all()
    )


def _find_existing_direct_channel(
    db: Session,
    *,
    tenant_id: int,
    team_id: int | None,
    member_user_ids: list[int],
) -> CollabChatChannel | None:
    target_members = {int(user_id) for user_id in member_user_ids}
    if len(target_members) != 2:
        return None

    stmt = select(CollabChatChannel).where(
        CollabChatChannel.tenant_id == tenant_id,
        CollabChatChannel.is_group.is_(False),
        CollabChatChannel.is_active.is_(True),
        CollabChatChannel.deleted_at.is_(None),
    )
    if team_id is None:
        stmt = stmt.where(CollabChatChannel.team_id.is_(None))
    else:
        stmt = stmt.where(CollabChatChannel.team_id == team_id)

    channels = list(
        db.scalars(stmt.order_by(CollabChatChannel.id.asc()).limit(200)).all()
    )
    matched_channels: list[CollabChatChannel] = []
    for channel in channels:
        channel_members = set(_get_channel_member_ids(db, channel_id=channel.id))
        if channel_members == target_members:
            matched_channels.append(channel)
    if not matched_channels:
        return None
    return min(matched_channels, key=lambda item: int(item.id))


def create_chat_channel(
    db: Session,
    current_user: User,
    payload: ChatChannelCreateRequest,
) -> ChatChannelOut:
    if payload.team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=payload.team_id)
        valid_team_member_ids = set(
            db.scalars(
                select(TeamMember.user_id).where(
                    TeamMember.team_id == payload.team_id,
                    TeamMember.deleted_at.is_(None),
                )
            ).all()
        )
        requested_member_ids = sorted(
            {int(user_id) for user_id in [current_user.id, *payload.member_user_ids]}
        )
        invalid_member_ids = [
            user_id
            for user_id in requested_member_ids
            if user_id not in valid_team_member_ids
        ]
        if invalid_member_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more users are not members of this team",
            )
        member_user_ids = requested_member_ids
    else:
        member_user_ids = _validate_user_ids(
            db,
            tenant_id=current_user.tenant_id,
            user_ids=[current_user.id, *payload.member_user_ids],
        )
    if not payload.is_group and len(member_user_ids) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct chat must include exactly 2 members",
        )

    if not payload.is_group:
        existing_direct = _find_existing_direct_channel(
            db,
            tenant_id=current_user.tenant_id,
            team_id=payload.team_id,
            member_user_ids=member_user_ids,
        )
        if existing_direct is not None:
            return _to_channel_out(
                db,
                channel=existing_direct,
                viewer_user_id=current_user.id,
            )

    channel = CollabChatChannel(
        tenant_id=current_user.tenant_id,
        team_id=payload.team_id,
        name=payload.name.strip(),
        is_group=payload.is_group,
        is_active=True,
        created_by_user_id=current_user.id,
    )
    db.add(channel)
    db.flush()

    for member_user_id in member_user_ids:
        db.add(
            CollabChatChannelMember(
                tenant_id=current_user.tenant_id,
                channel_id=channel.id,
                user_id=member_user_id,
                last_read_message_id=None,
            )
        )

    db.commit()
    db.refresh(channel)
    return _to_channel_out(db, channel=channel, viewer_user_id=current_user.id)


def list_my_chat_channels(db: Session, current_user: User) -> list[ChatChannelOut]:
    channels = list(
        db.scalars(
            select(CollabChatChannel)
            .join(
                CollabChatChannelMember,
                CollabChatChannelMember.channel_id == CollabChatChannel.id,
            )
            .where(
                CollabChatChannel.tenant_id == current_user.tenant_id,
                CollabChatChannel.deleted_at.is_(None),
                CollabChatChannel.is_active.is_(True),
                CollabChatChannelMember.user_id == current_user.id,
                CollabChatChannelMember.deleted_at.is_(None),
            )
            .order_by(CollabChatChannel.updated_at.desc(), CollabChatChannel.id.desc())
            .limit(200)
        ).all()
    )
    group_channels: list[ChatChannelOut] = []
    direct_channels_by_key: dict[str, ChatChannelOut] = {}
    for channel in channels:
        channel_out = _to_channel_out(
            db,
            channel=channel,
            viewer_user_id=current_user.id,
        )
        if not channel_out.is_group:
            unique_members = sorted(
                {int(user_id) for user_id in channel_out.member_user_ids}
            )
            direct_key = f"{channel_out.team_id or 0}:{','.join(str(item) for item in unique_members)}"
            existing = direct_channels_by_key.get(direct_key)
            if existing is None or int(channel_out.id) < int(existing.id):
                direct_channels_by_key[direct_key] = channel_out
            continue
        group_channels.append(channel_out)

    direct_channels = sorted(
        direct_channels_by_key.values(),
        key=lambda item: (
            item.last_message_at or item.created_at,
            item.id,
        ),
        reverse=True,
    )
    return [*group_channels, *direct_channels]


def _ensure_channel_member(
    db: Session,
    *,
    channel_id: int,
    current_user: User,
) -> CollabChatChannel:
    channel = db.scalar(
        select(CollabChatChannel).where(
            CollabChatChannel.id == channel_id,
            CollabChatChannel.tenant_id == current_user.tenant_id,
            CollabChatChannel.deleted_at.is_(None),
            CollabChatChannel.is_active.is_(True),
        )
    )
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat channel not found",
        )
    member = db.scalar(
        select(CollabChatChannelMember.id).where(
            CollabChatChannelMember.channel_id == channel.id,
            CollabChatChannelMember.user_id == current_user.id,
            CollabChatChannelMember.deleted_at.is_(None),
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat channel access denied",
        )
    if channel.is_group:
        return channel

    member_user_ids = _get_channel_member_ids(db, channel_id=channel.id)
    canonical_channel = _find_existing_direct_channel(
        db,
        tenant_id=current_user.tenant_id,
        team_id=channel.team_id,
        member_user_ids=member_user_ids,
    )
    if canonical_channel is None:
        return channel
    return canonical_channel


def send_chat_message(
    db: Session,
    current_user: User,
    *,
    channel_id: int,
    payload: ChatMessageCreateRequest,
) -> ChatMessageOut:
    channel = _ensure_channel_member(
        db,
        channel_id=channel_id,
        current_user=current_user,
    )
    if not payload.content.strip() and not payload.attachments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content or attachment is required",
        )
    _ensure_attachment_urls_belong_to_tenant(
        current_user,
        attachments=payload.attachments,
    )

    message = CollabChatMessage(
        tenant_id=current_user.tenant_id,
        channel_id=channel.id,
        sender_user_id=current_user.id,
        message_type=payload.message_type.strip().upper(),
        content=payload.content,
        reply_to_message_id=payload.reply_to_message_id,
    )
    db.add(message)
    db.flush()

    for attachment in payload.attachments:
        db.add(
            CollabChatMessageAttachment(
                tenant_id=current_user.tenant_id,
                message_id=message.id,
                file_name=attachment.file_name,
                file_url=attachment.file_url,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
            )
        )
    db.commit()
    db.refresh(message)
    _publish_chat_message_event(
        current_user=current_user,
        room_id=channel.id,
        message_id=message.id,
        message_type=message.message_type,
    )

    attachments = list(
        db.scalars(
            select(CollabChatMessageAttachment).where(
                CollabChatMessageAttachment.message_id == message.id,
                CollabChatMessageAttachment.deleted_at.is_(None),
            )
        ).all()
    )
    return ChatMessageOut(
        id=message.id,
        channel_id=message.channel_id,
        sender_user_id=message.sender_user_id,
        message_type=message.message_type,
        content=message.content,
        reply_to_message_id=message.reply_to_message_id,
        attachments=[_attachment_out_from_message(item) for item in attachments],
        created_at=message.created_at,
    )


def list_chat_messages(
    db: Session,
    current_user: User,
    *,
    channel_id: int,
) -> list[ChatMessageOut]:
    channel = _ensure_channel_member(
        db,
        channel_id=channel_id,
        current_user=current_user,
    )
    member = db.scalar(
        select(CollabChatChannelMember).where(
            CollabChatChannelMember.channel_id == channel.id,
            CollabChatChannelMember.user_id == current_user.id,
            CollabChatChannelMember.deleted_at.is_(None),
        )
    )
    messages = list(
        db.scalars(
            select(CollabChatMessage)
            .where(
                CollabChatMessage.channel_id == channel.id,
                CollabChatMessage.tenant_id == current_user.tenant_id,
                CollabChatMessage.deleted_at.is_(None),
            )
            .order_by(CollabChatMessage.created_at.asc(), CollabChatMessage.id.asc())
            .limit(500)
        ).all()
    )
    result: list[ChatMessageOut] = []
    for message in messages:
        attachments = list(
            db.scalars(
                select(CollabChatMessageAttachment).where(
                    CollabChatMessageAttachment.message_id == message.id,
                    CollabChatMessageAttachment.deleted_at.is_(None),
                )
            ).all()
        )
        result.append(
            ChatMessageOut(
                id=message.id,
                channel_id=message.channel_id,
                sender_user_id=message.sender_user_id,
                message_type=message.message_type,
                content=message.content,
                reply_to_message_id=message.reply_to_message_id,
                attachments=[
                    _attachment_out_from_message(item) for item in attachments
                ],
                created_at=message.created_at,
            )
        )

    if member is not None and messages:
        newest_message_id = int(messages[-1].id)
        current_last_read = int(member.last_read_message_id or 0)
        if newest_message_id > current_last_read:
            member.last_read_message_id = newest_message_id
            db.add(member)
            db.commit()

    return result


def _to_typing_out(state: CollabChatTypingState, user: User) -> ChatTypingOut:
    return ChatTypingOut(
        user_id=user.id,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        is_typing=state.is_typing,
        last_typed_at=state.last_typed_at,
        expires_at=state.expires_at,
    )


def update_chat_typing_status(
    db: Session,
    current_user: User,
    *,
    channel_id: int,
    payload: ChatTypingUpdateRequest,
) -> ChatTypingOut:
    channel = _ensure_channel_member(
        db, channel_id=channel_id, current_user=current_user
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=6) if payload.is_typing else now

    state = db.scalar(
        select(CollabChatTypingState).where(
            CollabChatTypingState.channel_id == channel.id,
            CollabChatTypingState.user_id == current_user.id,
            CollabChatTypingState.deleted_at.is_(None),
        )
    )
    if state is None:
        state = CollabChatTypingState(
            tenant_id=current_user.tenant_id,
            channel_id=channel.id,
            user_id=current_user.id,
            is_typing=payload.is_typing,
            last_typed_at=now,
            expires_at=expires_at,
        )
    else:
        state.is_typing = payload.is_typing
        state.last_typed_at = now
        state.expires_at = expires_at
    db.add(state)
    db.commit()
    db.refresh(state)
    _publish_typing_event(
        current_user=current_user,
        room_id=channel.id,
        is_typing=payload.is_typing,
    )
    return _to_typing_out(state, current_user)


def list_chat_typing_states(
    db: Session,
    current_user: User,
    *,
    channel_id: int,
) -> list[ChatTypingOut]:
    channel = _ensure_channel_member(
        db, channel_id=channel_id, current_user=current_user
    )
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(CollabChatTypingState, User)
        .join(User, User.id == CollabChatTypingState.user_id)
        .where(
            CollabChatTypingState.channel_id == channel.id,
            CollabChatTypingState.tenant_id == current_user.tenant_id,
            CollabChatTypingState.deleted_at.is_(None),
            CollabChatTypingState.is_typing.is_(True),
            CollabChatTypingState.expires_at.is_not(None),
            CollabChatTypingState.expires_at >= now,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        .order_by(CollabChatTypingState.last_typed_at.desc())
        .limit(20)
    ).all()
    return [_to_typing_out(state, user) for state, user in rows]


def update_presence_status(
    current_user: User,
    *,
    payload: PresenceHeartbeatRequest,
) -> PresenceOut:
    updated_at = datetime.now(timezone.utc)
    update_presence(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        is_online=payload.is_online,
    )
    return PresenceOut(
        user_id=current_user.id,
        is_online=payload.is_online,
        updated_at=updated_at,
    )


def list_presence_statuses(
    db: Session,
    current_user: User,
    *,
    team_id: int | None = None,
) -> list[PresenceOut]:
    if team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=team_id)
        candidate_user_ids = set(
            db.scalars(
                select(TeamMember.user_id).where(
                    TeamMember.team_id == team_id,
                    TeamMember.deleted_at.is_(None),
                )
            ).all()
        )
    else:
        candidate_user_ids = set(
            db.scalars(
                select(User.id).where(
                    User.tenant_id == current_user.tenant_id,
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            ).all()
        )

    online_ids = list_online_user_ids(current_user.tenant_id)
    result = []
    now = datetime.now(timezone.utc)
    for user_id in sorted(candidate_user_ids):
        result.append(
            PresenceOut(
                user_id=int(user_id),
                is_online=int(user_id) in online_ids,
                updated_at=now,
            )
        )
    return result


def _ensure_ai_session_access(
    db: Session,
    *,
    session_id: int,
    current_user: User,
) -> CollabAiSession:
    session = db.scalar(
        select(CollabAiSession).where(
            CollabAiSession.id == session_id,
            CollabAiSession.tenant_id == current_user.tenant_id,
            CollabAiSession.deleted_at.is_(None),
            CollabAiSession.is_active.is_(True),
        )
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI session not found",
        )
    if session.user_id != current_user.id and session.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI session access denied",
        )
    if session.team_id is not None:
        _ensure_team_member_access(
            db,
            user_id=current_user.id,
            team_id=session.team_id,
        )
    return session


def create_ai_session(
    db: Session,
    current_user: User,
    payload: AiSessionCreateRequest,
) -> AiSessionOut:
    if payload.team_id is not None:
        _ensure_team_member_access(db, user_id=current_user.id, team_id=payload.team_id)

    session = CollabAiSession(
        tenant_id=current_user.tenant_id,
        team_id=payload.team_id,
        user_id=current_user.id,
        title=payload.title.strip(),
        is_active=True,
        last_message_at=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return AiSessionOut(
        id=session.id,
        team_id=session.team_id,
        user_id=session.user_id,
        title=session.title,
        is_active=session.is_active,
        last_message_at=session.last_message_at,
        created_at=session.created_at,
    )


def list_ai_sessions(db: Session, current_user: User) -> list[AiSessionOut]:
    sessions = list(
        db.scalars(
            select(CollabAiSession)
            .where(
                CollabAiSession.tenant_id == current_user.tenant_id,
                CollabAiSession.user_id == current_user.id,
                CollabAiSession.deleted_at.is_(None),
                CollabAiSession.is_active.is_(True),
            )
            .order_by(CollabAiSession.updated_at.desc(), CollabAiSession.id.desc())
            .limit(200)
        ).all()
    )
    return [
        AiSessionOut(
            id=item.id,
            team_id=item.team_id,
            user_id=item.user_id,
            title=item.title,
            is_active=item.is_active,
            last_message_at=item.last_message_at,
            created_at=item.created_at,
        )
        for item in sessions
    ]


def add_ai_message(
    db: Session,
    current_user: User,
    *,
    session_id: int,
    payload: AiMessageCreateRequest,
) -> AiMessageOut:
    session = _ensure_ai_session_access(
        db, session_id=session_id, current_user=current_user
    )
    role = payload.role.strip().lower()
    if role not in {"system", "user", "assistant"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI message role is invalid",
        )

    message = CollabAiMessage(
        tenant_id=current_user.tenant_id,
        session_id=session.id,
        role=role,
        content=payload.content,
        token_usage=payload.token_usage,
    )
    db.add(message)
    session.last_message_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(message)
    return AiMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        token_usage=message.token_usage,
        created_at=message.created_at,
    )


def list_ai_messages(
    db: Session,
    current_user: User,
    *,
    session_id: int,
) -> list[AiMessageOut]:
    _ensure_ai_session_access(db, session_id=session_id, current_user=current_user)
    rows = list(
        db.scalars(
            select(CollabAiMessage)
            .where(
                CollabAiMessage.session_id == session_id,
                CollabAiMessage.tenant_id == current_user.tenant_id,
                CollabAiMessage.deleted_at.is_(None),
            )
            .order_by(CollabAiMessage.created_at.asc(), CollabAiMessage.id.asc())
            .limit(1000)
        ).all()
    )
    return [
        AiMessageOut(
            id=item.id,
            role=item.role,
            content=item.content,
            token_usage=item.token_usage,
            created_at=item.created_at,
        )
        for item in rows
    ]
