from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import ApiResponse, success_response
from app.core.security import TokenDecodeError, decode_access_token
from app.db.session import SessionLocal
from app.modules.auth.service import get_user_auth_context
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
    NotificationCreateRequest,
    NotificationOut,
    PresenceHeartbeatRequest,
    PresenceOut,
    TaskCreateRequest,
    TaskOut,
    TaskStatusUpdateRequest,
)
from app.modules.collaboration.service import (
    add_ai_message,
    create_ai_session,
    create_chat_channel,
    create_notification,
    create_task,
    get_chat_file_stream,
    list_ai_messages,
    list_ai_sessions,
    list_chat_messages,
    list_chat_typing_states,
    list_my_chat_channels,
    list_my_notifications,
    list_presence_statuses,
    list_tasks,
    mark_notification_read,
    send_chat_message,
    update_chat_typing_status,
    update_presence_status,
    update_task_status,
    upload_chat_attachment,
)
from app.modules.core.models import Team, TeamMember, User
from app.services.realtime_gateway import (
    connect_realtime_client,
    disconnect_realtime_client,
    refresh_realtime_client_rooms,
)

router = APIRouter()


def _ensure_can_create_notification(db: Session, current_user: User) -> None:
    auth_context = get_user_auth_context(db, current_user)
    allowed_codes = {
        "*",
        "all:*",
        "admin:*",
        "user:mangage",
        "notifications:create",
        "collaboration:notifications:create",
        "platform:developer:access",
    }
    if not auth_context.permissions.intersection(allowed_codes):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create notifications",
        )


def _resolve_ws_token(websocket: WebSocket) -> str | None:
    token = (websocket.query_params.get("token") or "").strip()
    if token:
        return token

    cookie_token = (websocket.cookies.get("auth_access_token") or "").strip()
    if cookie_token:
        return cookie_token

    authorization = (websocket.headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _resolve_workspace_key_for_ws(websocket: WebSocket) -> str:
    workspace_key = (websocket.query_params.get("workspace_key") or "").strip()
    if workspace_key:
        return workspace_key
    workspace_key = (websocket.headers.get("x-workspace-key") or "").strip()
    if workspace_key:
        return workspace_key
    return "personal"


def _resolve_effective_tenant_for_workspace(
    db: Session,
    *,
    user: User,
    workspace_key: str,
) -> tuple[int, str]:
    if workspace_key.startswith("team:"):
        team_id_raw = workspace_key.split(":", 1)[1]
        if team_id_raw.isdigit():
            team_id = int(team_id_raw)
            team = db.scalar(
                select(Team)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(
                    Team.id == team_id,
                    Team.deleted_at.is_(None),
                    Team.is_active.is_(True),
                    TeamMember.user_id == user.id,
                    TeamMember.deleted_at.is_(None),
                )
            )
            if team is not None:
                return team.tenant_id, workspace_key
    return user.tenant_id, "personal"


@router.websocket("/ws")
async def collaboration_ws(websocket: WebSocket) -> None:
    token = _resolve_ws_token(websocket)
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", "0"))
        tenant_id = int(payload.get("tenant_id", "0"))
    except (TokenDecodeError, TypeError, ValueError):
        await websocket.close(code=4401, reason="Invalid token")
        return

    db = SessionLocal()
    try:
        user = db.scalar(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        if user is None:
            await websocket.close(code=4401, reason="User not found")
            return

        workspace_key = _resolve_workspace_key_for_ws(websocket)
        effective_tenant_id, normalized_workspace_key = (
            _resolve_effective_tenant_for_workspace(
                db,
                user=user,
                workspace_key=workspace_key,
            )
        )
    finally:
        db.close()

    await connect_realtime_client(
        websocket=websocket,
        user_id=user_id,
        tenant_id=effective_tenant_id,
        workspace_key=normalized_workspace_key,
    )
    try:
        while True:
            payload = await websocket.receive_json()
            message_type = str(payload.get("type", "")).strip().lower()
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "refresh_rooms":
                await refresh_realtime_client_rooms(websocket)
                await websocket.send_json({"type": "rooms_refreshed"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await disconnect_realtime_client(websocket)


@router.post("/notifications", response_model=ApiResponse[NotificationOut])
def add_notification(
    payload: NotificationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[NotificationOut]:
    _ensure_can_create_notification(db, current_user)
    item = create_notification(db, current_user, payload)
    return success_response(item, message="Tạo thông báo thành công")


@router.get("/notifications", response_model=ApiResponse[list[NotificationOut]])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[NotificationOut]]:
    items = list_my_notifications(db, current_user)
    return success_response(items, message="Lấy danh sách thông báo thành công")


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=ApiResponse[NotificationOut],
)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[NotificationOut]:
    item = mark_notification_read(db, current_user, notification_id=notification_id)
    return success_response(item, message="Đã đánh dấu thông báo đã đọc")


@router.post("/tasks", response_model=ApiResponse[TaskOut])
def add_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskOut]:
    item = create_task(db, current_user, payload)
    return success_response(item, message="Tạo nhiệm vụ thành công")


@router.get("/tasks", response_model=ApiResponse[list[TaskOut]])
def get_tasks(
    team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[TaskOut]]:
    items = list_tasks(db, current_user, team_id=team_id)
    return success_response(items, message="Lấy danh sách nhiệm vụ thành công")


@router.patch("/tasks/{task_id}/status", response_model=ApiResponse[TaskOut])
def edit_task_status(
    task_id: int,
    payload: TaskStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskOut]:
    item = update_task_status(db, current_user, task_id=task_id, payload=payload)
    return success_response(item, message="Cập nhật trạng thái nhiệm vụ thành công")


@router.post("/chat/channels", response_model=ApiResponse[ChatChannelOut])
def add_chat_channel(
    payload: ChatChannelCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChatChannelOut]:
    item = create_chat_channel(db, current_user, payload)
    return success_response(item, message="Tạo kênh chat thành công")


@router.get("/chat/channels", response_model=ApiResponse[list[ChatChannelOut]])
def get_chat_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[ChatChannelOut]]:
    items = list_my_chat_channels(db, current_user)
    return success_response(items, message="Lấy danh sách kênh chat thành công")


@router.post(
    "/chat/channels/{channel_id}/messages",
    response_model=ApiResponse[ChatMessageOut],
)
def add_chat_message(
    channel_id: int,
    payload: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChatMessageOut]:
    item = send_chat_message(
        db,
        current_user,
        channel_id=channel_id,
        payload=payload,
    )
    return success_response(item, message="Gửi tin nhắn thành công")


@router.post("/chat/uploads", response_model=ApiResponse[ChatUploadOut])
async def add_chat_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChatUploadOut]:
    item = await upload_chat_attachment(current_user=current_user, upload_file=file)
    return success_response(item, message="Tải file chat thành công")


@router.get("/chat/files/{object_name:path}")
def get_chat_file(
    object_name: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    object_data, content_type, content_length = get_chat_file_stream(
        current_user,
        object_name=object_name,
    )

    def _iterator():
        try:
            for chunk in object_data.stream(32 * 1024):
                yield chunk
        finally:
            object_data.close()
            object_data.release_conn()

    headers: dict[str, str] = {}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    return StreamingResponse(
        _iterator(),
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


@router.get(
    "/chat/channels/{channel_id}/messages",
    response_model=ApiResponse[list[ChatMessageOut]],
)
def get_chat_messages(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[ChatMessageOut]]:
    items = list_chat_messages(db, current_user, channel_id=channel_id)
    return success_response(items, message="Lấy lịch sử chat thành công")


@router.put(
    "/chat/channels/{channel_id}/typing",
    response_model=ApiResponse[ChatTypingOut],
)
def set_chat_typing_status(
    channel_id: int,
    payload: ChatTypingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChatTypingOut]:
    item = update_chat_typing_status(
        db,
        current_user,
        channel_id=channel_id,
        payload=payload,
    )
    return success_response(item, message="Đã cập nhật trạng thái đang gõ")


@router.get(
    "/chat/channels/{channel_id}/typing",
    response_model=ApiResponse[list[ChatTypingOut]],
)
def get_chat_typing_statuses(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[ChatTypingOut]]:
    items = list_chat_typing_states(db, current_user, channel_id=channel_id)
    return success_response(items, message="Lấy trạng thái đang gõ thành công")


@router.post("/chat/presence/heartbeat", response_model=ApiResponse[PresenceOut])
def heartbeat_chat_presence(
    payload: PresenceHeartbeatRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PresenceOut]:
    item = update_presence_status(current_user, payload=payload)
    return success_response(item, message="Đã cập nhật trạng thái online")


@router.get("/chat/presence", response_model=ApiResponse[list[PresenceOut]])
def get_chat_presence(
    team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[PresenceOut]]:
    items = list_presence_statuses(db, current_user, team_id=team_id)
    return success_response(items, message="Lấy trạng thái online thành công")


@router.post("/ai/sessions", response_model=ApiResponse[AiSessionOut])
def add_ai_session(
    payload: AiSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AiSessionOut]:
    item = create_ai_session(db, current_user, payload)
    return success_response(item, message="Tạo session AI thành công")


@router.get("/ai/sessions", response_model=ApiResponse[list[AiSessionOut]])
def get_ai_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[AiSessionOut]]:
    items = list_ai_sessions(db, current_user)
    return success_response(items, message="Lấy danh sách session AI thành công")


@router.post(
    "/ai/sessions/{session_id}/messages",
    response_model=ApiResponse[AiMessageOut],
)
def add_ai_chat_message(
    session_id: int,
    payload: AiMessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AiMessageOut]:
    item = add_ai_message(db, current_user, session_id=session_id, payload=payload)
    return success_response(item, message="Đã thêm tin nhắn AI")


@router.get(
    "/ai/sessions/{session_id}/messages",
    response_model=ApiResponse[list[AiMessageOut]],
)
def get_ai_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[AiMessageOut]]:
    items = list_ai_messages(db, current_user, session_id=session_id)
    return success_response(items, message="Lấy lịch sử hội thoại AI thành công")
