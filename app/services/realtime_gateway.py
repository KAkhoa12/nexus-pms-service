from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.core.models import CollabChatChannel, CollabChatChannelMember

REDIS_PATTERNS = (
    "tenant:*:room:*",
    "tenant:*:user:*:notifications",
    "tenant:*:room:*:typing",
    "tenant:*:presence",
)
ROOM_CACHE_TTL_SECONDS = 30


@dataclass
class GatewayConnection:
    socket_key: int
    websocket: WebSocket
    user_id: int
    tenant_id: int
    workspace_key: str
    room_ids: set[int] = field(default_factory=set)
    room_cache_at: float = 0.0


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_tenant_id_from_channel(channel: str) -> int | None:
    parts = channel.split(":")
    if len(parts) < 2:
        return None
    return _to_int(parts[1])


def _load_room_ids_for_user(*, user_id: int, tenant_id: int) -> set[int]:
    with SessionLocal() as db:
        room_ids = db.scalars(
            select(CollabChatChannelMember.channel_id)
            .join(
                CollabChatChannel,
                CollabChatChannel.id == CollabChatChannelMember.channel_id,
            )
            .where(
                CollabChatChannelMember.user_id == user_id,
                CollabChatChannelMember.tenant_id == tenant_id,
                CollabChatChannelMember.deleted_at.is_(None),
                CollabChatChannel.tenant_id == tenant_id,
                CollabChatChannel.deleted_at.is_(None),
                CollabChatChannel.is_active.is_(True),
            )
        ).all()
    return {int(room_id) for room_id in room_ids}


def _user_has_room_access(*, user_id: int, tenant_id: int, room_id: int) -> bool:
    with SessionLocal() as db:
        row_id = db.scalar(
            select(CollabChatChannelMember.id)
            .join(
                CollabChatChannel,
                CollabChatChannel.id == CollabChatChannelMember.channel_id,
            )
            .where(
                CollabChatChannelMember.user_id == user_id,
                CollabChatChannelMember.tenant_id == tenant_id,
                CollabChatChannelMember.channel_id == room_id,
                CollabChatChannelMember.deleted_at.is_(None),
                CollabChatChannel.tenant_id == tenant_id,
                CollabChatChannel.deleted_at.is_(None),
                CollabChatChannel.is_active.is_(True),
            )
        )
    return row_id is not None


class RealtimeGateway:
    def __init__(self) -> None:
        self._connections: dict[int, GatewayConnection] = {}
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task[None] | None = None
        self._redis: Redis | None = None

    async def start(self) -> None:
        if not settings.REDIS_ENABLED:
            return
        async with self._lock:
            if self._listener_task is not None and not self._listener_task.done():
                return
            self._listener_task = asyncio.create_task(
                self._run_listener(),
                name="realtime-redis-listener",
            )

    async def stop(self) -> None:
        listener_task: asyncio.Task[None] | None
        async with self._lock:
            listener_task = self._listener_task
            self._listener_task = None
        if listener_task is not None:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except RedisError:
                pass
            self._redis = None

    async def connect(
        self,
        *,
        websocket: WebSocket,
        user_id: int,
        tenant_id: int,
        workspace_key: str,
    ) -> GatewayConnection:
        await websocket.accept()
        conn = GatewayConnection(
            socket_key=id(websocket),
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            workspace_key=workspace_key,
        )
        conn.room_ids = await asyncio.to_thread(
            _load_room_ids_for_user,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        conn.room_cache_at = time.time()
        async with self._lock:
            self._connections[conn.socket_key] = conn
        await self.start()
        await self._safe_send(
            conn,
            {
                "type": "connected",
                "payload": {
                    "user_id": conn.user_id,
                    "tenant_id": conn.tenant_id,
                    "workspace_key": conn.workspace_key,
                },
            },
        )
        return conn

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(id(websocket), None)

    async def refresh_connection_rooms(self, websocket: WebSocket) -> None:
        async with self._lock:
            conn = self._connections.get(id(websocket))
        if conn is None:
            return
        conn.room_ids = await asyncio.to_thread(
            _load_room_ids_for_user,
            user_id=conn.user_id,
            tenant_id=conn.tenant_id,
        )
        conn.room_cache_at = time.time()

    async def _run_listener(self) -> None:
        while True:
            try:
                await self._listen_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)

    async def _listen_once(self) -> None:
        self._redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        await pubsub.psubscribe(*REDIS_PATTERNS)
        try:
            while True:
                message = await pubsub.get_message(timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.05)
                    continue
                raw_channel = str(message.get("channel", ""))
                raw_payload = message.get("data")
                payload = self._parse_payload(raw_payload)
                if payload is None:
                    continue
                event = str(payload.get("event", "")).strip().lower()
                if not event:
                    continue
                tenant_id = _to_int(payload.get("tenant_id"))
                if tenant_id is None:
                    tenant_id = _extract_tenant_id_from_channel(raw_channel)
                if tenant_id is None:
                    continue
                await self._dispatch_event(
                    channel=raw_channel,
                    event=event,
                    tenant_id=tenant_id,
                    payload=payload,
                )
        finally:
            await pubsub.close()

    def _parse_payload(self, raw_payload: Any) -> dict[str, Any] | None:
        if isinstance(raw_payload, dict):
            return raw_payload
        if raw_payload is None:
            return None
        if isinstance(raw_payload, bytes):
            try:
                raw_payload = raw_payload.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            parsed = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    async def _dispatch_event(
        self,
        *,
        channel: str,
        event: str,
        tenant_id: int,
        payload: dict[str, Any],
    ) -> None:
        async with self._lock:
            candidate_connections = [
                conn
                for conn in self._connections.values()
                if conn.tenant_id == tenant_id
            ]
        stale_socket_keys: list[int] = []
        for conn in candidate_connections:
            if not await self._should_deliver(conn, event=event, payload=payload):
                continue
            ok = await self._safe_send(
                conn,
                {"type": event, "channel": channel, "payload": payload},
            )
            if not ok:
                stale_socket_keys.append(conn.socket_key)
        if stale_socket_keys:
            async with self._lock:
                for socket_key in stale_socket_keys:
                    self._connections.pop(socket_key, None)

    async def _should_deliver(
        self,
        conn: GatewayConnection,
        *,
        event: str,
        payload: dict[str, Any],
    ) -> bool:
        if event == "notification":
            target_user_id = _to_int(payload.get("user_id"))
            return target_user_id == conn.user_id

        if event in {"chat_message", "typing"}:
            room_id = _to_int(payload.get("room_id"))
            if room_id is None:
                return False
            if time.time() - conn.room_cache_at > ROOM_CACHE_TTL_SECONDS:
                conn.room_ids = await asyncio.to_thread(
                    _load_room_ids_for_user,
                    user_id=conn.user_id,
                    tenant_id=conn.tenant_id,
                )
                conn.room_cache_at = time.time()
            if room_id in conn.room_ids:
                return True
            has_access = await asyncio.to_thread(
                _user_has_room_access,
                user_id=conn.user_id,
                tenant_id=conn.tenant_id,
                room_id=room_id,
            )
            if has_access:
                conn.room_ids.add(room_id)
            return has_access

        if event == "presence":
            return True

        return True

    async def _safe_send(
        self, conn: GatewayConnection, payload: dict[str, Any]
    ) -> bool:
        try:
            await conn.websocket.send_json(payload)
            return True
        except Exception:
            return False


_gateway = RealtimeGateway()


async def start_realtime_gateway() -> None:
    await _gateway.start()


async def stop_realtime_gateway() -> None:
    await _gateway.stop()


async def connect_realtime_client(
    *,
    websocket: WebSocket,
    user_id: int,
    tenant_id: int,
    workspace_key: str,
) -> GatewayConnection:
    return await _gateway.connect(
        websocket=websocket,
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_key=workspace_key,
    )


async def disconnect_realtime_client(websocket: WebSocket) -> None:
    await _gateway.disconnect(websocket)


async def refresh_realtime_client_rooms(websocket: WebSocket) -> None:
    await _gateway.refresh_connection_rooms(websocket)
