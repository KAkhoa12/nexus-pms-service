from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from redis.exceptions import RedisError

from app.core.config import settings
from redis import Redis

_redis_client: Redis | None = None


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _get_client() -> Redis | None:
    global _redis_client
    if not settings.REDIS_ENABLED:
        return None
    if _redis_client is None:
        _redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return _redis_client


def _publish(channel: str, payload: dict[str, Any]) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.publish(channel, json.dumps(payload, default=_json_default))
    except RedisError:
        return


def build_chat_channel(tenant_id: int, room_id: int) -> str:
    return f"tenant:{tenant_id}:room:{room_id}"


def build_notification_channel(tenant_id: int, user_id: int) -> str:
    return f"tenant:{tenant_id}:user:{user_id}:notifications"


def build_typing_channel(tenant_id: int, room_id: int) -> str:
    return f"tenant:{tenant_id}:room:{room_id}:typing"


def build_presence_channel(tenant_id: int) -> str:
    return f"tenant:{tenant_id}:presence"


def publish_chat_message(
    *,
    tenant_id: int,
    room_id: int,
    payload: dict[str, Any],
) -> None:
    _publish(build_chat_channel(tenant_id, room_id), payload)


def publish_notification(
    *,
    tenant_id: int,
    user_id: int,
    payload: dict[str, Any],
) -> None:
    _publish(build_notification_channel(tenant_id, user_id), payload)


def publish_typing(
    *,
    tenant_id: int,
    room_id: int,
    payload: dict[str, Any],
) -> None:
    _publish(build_typing_channel(tenant_id, room_id), payload)


def update_presence(*, tenant_id: int, user_id: int, is_online: bool) -> None:
    client = _get_client()
    if client is None:
        return
    key = f"tenant:{tenant_id}:presence:users"
    timestamp = int(time.time())
    try:
        if is_online:
            client.hset(key, str(user_id), str(timestamp))
            client.expire(key, settings.PRESENCE_TTL_SECONDS * 10)
        else:
            client.hdel(key, str(user_id))
    except RedisError:
        pass
    _publish(
        build_presence_channel(tenant_id),
        {
            "event": "presence",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "is_online": is_online,
            "updated_at": timestamp,
        },
    )


def list_online_user_ids(tenant_id: int) -> set[int]:
    client = _get_client()
    if client is None:
        return set()
    key = f"tenant:{tenant_id}:presence:users"
    try:
        raw_values = client.hkeys(key)
    except RedisError:
        return set()
    result: set[int] = set()
    for item in raw_values:
        if str(item).isdigit():
            result.add(int(item))
    return result
