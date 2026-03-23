from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import ApiResponse, success_response
from app.db.session import SessionLocal
from app.modules.agents.runtime import AgentRuntime
from app.modules.agents.schemas.api import (
    AgentCheckpointListOut,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentRunCancelOut,
    AgentRunListOut,
    AgentRunStartOut,
    AgentRunStartRequest,
    AgentRunStatusOut,
)
from app.modules.agents.services.run_service import (
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    AgentRunService,
)

router = APIRouter()
UNPROCESSABLE_STATUS = getattr(
    status,
    "HTTP_422_UNPROCESSABLE_CONTENT",
    422,
)


@router.post("/query", response_model=ApiResponse[AgentQueryResponse])
async def query_agent(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentQueryResponse]:
    payload = _parse_agent_payload(await request.body())
    runtime = AgentRuntime(db)
    result = runtime.run_query(payload=payload, current_user=current_user)
    return success_response(result, message="AI agent xử lý thành công")


@router.get(
    "/threads/{thread_id}/checkpoints",
    response_model=ApiResponse[AgentCheckpointListOut],
)
def list_agent_checkpoints(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentCheckpointListOut]:
    runtime = AgentRuntime(db)
    result = runtime.list_checkpoints(
        current_user=current_user,
        thread_id=thread_id,
        limit=limit,
    )
    return success_response(result, message="Lấy checkpoint thành công")


@router.post("/runs/start", response_model=ApiResponse[AgentRunStartOut])
async def start_agent_run(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentRunStartOut]:
    payload = _parse_agent_run_payload(await request.body())
    service = AgentRunService(db)
    result = service.start_run(payload=payload, current_user=current_user)
    return success_response(result, message="Đã tạo phiên chạy AI")


@router.get("/runs/active", response_model=ApiResponse[AgentRunListOut])
def list_active_agent_runs(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentRunListOut]:
    service = AgentRunService(db)
    result = service.list_active_runs(current_user=current_user, limit=limit)
    return success_response(result, message="Lấy danh sách run đang chạy thành công")


@router.get("/runs/history", response_model=ApiResponse[AgentRunListOut])
def list_agent_runs_history(
    limit: int = Query(default=100, ge=1, le=500),
    workspace_key: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentRunListOut]:
    service = AgentRunService(db)
    result = service.list_runs_history(
        current_user=current_user,
        limit=limit,
        workspace_key=workspace_key,
        session_id=session_id,
        thread_id=thread_id,
    )
    return success_response(result, message="Lấy lịch sử run AI thành công")


@router.get("/runs/{run_id}", response_model=ApiResponse[AgentRunStatusOut])
def get_agent_run_status(
    run_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentRunStatusOut]:
    service = AgentRunService(db)
    result = service.get_run(run_id=run_id, current_user=current_user)
    return success_response(result, message="Lấy trạng thái run thành công")


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse[AgentRunCancelOut])
def cancel_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse[AgentRunCancelOut]:
    service = AgentRunService(db)
    result = service.cancel_run(run_id=run_id, current_user=current_user)
    return success_response(result, message="Đã yêu cầu dừng run AI")


@router.get("/runs/{run_id}/stream")
async def stream_agent_run(
    run_id: str,
    request: Request,
    last_event_id: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    service = AgentRunService(db)
    snapshot = service.get_run(run_id=run_id, current_user=current_user)

    async def event_generator():
        cursor = max(0, last_event_id)
        last_streamed_partial = str(snapshot.partial_answer or "")
        yield _to_sse(
            event="snapshot",
            payload={
                "run_id": snapshot.run_id,
                "status": snapshot.status,
                "partial_answer": snapshot.partial_answer,
                "final_answer": snapshot.final_answer,
            },
            event_id=cursor,
        )
        terminal_statuses = {
            RUN_STATUS_COMPLETED,
            RUN_STATUS_FAILED,
            RUN_STATUS_CANCELLED,
        }
        while True:
            if await request.is_disconnected():
                break

            poll_db = SessionLocal()
            try:
                poll_service = AgentRunService(poll_db)
                events = poll_service.list_events(
                    run_id=run_id,
                    current_user=current_user,
                    after_event_id=cursor,
                    limit=200,
                )
                latest = poll_service.get_run(run_id=run_id, current_user=current_user)
            except HTTPException as exc:
                yield _to_sse(
                    event="error",
                    payload={"message": str(exc.detail)},
                    event_id=cursor,
                )
                break
            finally:
                poll_db.close()

            for item in events:
                cursor = max(cursor, item.id)
                yield _to_sse(
                    event=item.event_type,
                    payload=item.payload,
                    event_id=item.id,
                )

            latest_partial = str(latest.partial_answer or "")
            if latest_partial and latest_partial != last_streamed_partial:
                if latest_partial.startswith(last_streamed_partial):
                    delta_text = latest_partial[len(last_streamed_partial) :]
                else:
                    delta_text = latest_partial
                last_streamed_partial = latest_partial
                yield _to_sse(
                    event="delta",
                    payload={
                        "delta": delta_text,
                        "accumulated": latest_partial,
                    },
                    event_id=cursor,
                )

            if latest.status in terminal_statuses:
                if not events:
                    yield _to_sse(
                        event="done",
                        payload={"status": latest.status},
                        event_id=cursor,
                    )
                break

            yield ": keep-alive\n\n"
            await asyncio.sleep(0.15)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _parse_agent_payload(raw_body: bytes) -> AgentQueryRequest:
    if not raw_body:
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body is required",
        )
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body must be valid JSON",
        )

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body must be a JSON object",
        )

    try:
        return AgentQueryRequest.model_validate(parsed)
    except ValidationError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail=exc.errors(),
        )


def _parse_agent_run_payload(raw_body: bytes) -> AgentRunStartRequest:
    if not raw_body:
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body is required",
        )
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body must be valid JSON",
        )

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail="Body must be a JSON object",
        )

    try:
        return AgentRunStartRequest.model_validate(parsed)
    except ValidationError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_STATUS,
            detail=exc.errors(),
        )


def _to_sse(*, event: str, payload: dict, event_id: int) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    if event_id > 0:
        return f"id: {event_id}\nevent: {event}\ndata: {data}\n\n"
    return f"event: {event}\ndata: {data}\n\n"
