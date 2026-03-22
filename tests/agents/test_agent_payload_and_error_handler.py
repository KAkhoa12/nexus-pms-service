from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.core.exception_handlers import _error_payload
from app.modules.agents.routes import _parse_agent_payload


def test_parse_agent_payload_accepts_json_bytes() -> None:
    raw = b'{"message":"Cho toi KPI","locale":"vi-VN"}'
    payload = _parse_agent_payload(raw)
    assert payload.message == "Cho toi KPI"
    assert payload.locale == "vi-VN"


def test_parse_agent_payload_rejects_invalid_json() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _parse_agent_payload(b"not-a-json")
    assert exc_info.value.status_code == 422


def test_error_payload_serializes_bytes_input() -> None:
    payload = _error_payload(
        message="invalid",
        response=[{"type": "x", "input": b'{"a":1}'}],
    )
    dumped = json.dumps(payload, ensure_ascii=False)
    assert '"{\\"a\\":1}"' in dumped
