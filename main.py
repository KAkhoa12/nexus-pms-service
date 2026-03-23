from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.db.init_db import init_db
from app.middleware.auth_token import AuthTokenMiddleware
from app.modules.agents.services.event_retention import (
    start_agent_run_events_retention_worker,
    stop_agent_run_events_retention_worker,
)
from app.services.realtime_gateway import stop_realtime_gateway

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
)
assets_dir = Path(__file__).resolve().parent / "app" / "assetss"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assetss", StaticFiles(directory=str(assets_dir)), name="assetss")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthTokenMiddleware)
app.include_router(api_v1_router, prefix="/api/v1")

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    start_agent_run_events_retention_worker()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_agent_run_events_retention_worker()
    await stop_realtime_gateway()
