from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import TokenDecodeError, decode_access_token


class AuthTokenMiddleware(BaseHTTPMiddleware):
    """Validate bearer token early for protected API routes."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.public_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/google",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/developer/auth/login",
        }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if request.method == "OPTIONS":
            return await call_next(request)

        if (
            path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi.json")
        ):
            return await call_next(request)

        if path in self.public_paths:
            return await call_next(request)

        if not path.startswith("/api/v1"):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        token = ""
        if authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        if not token:
            token = (request.cookies.get("auth_access_token") or "").strip()
        if not token:
            token = (request.query_params.get("token") or "").strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Missing or invalid authorization header",
                    "response": None,
                },
            )

        try:
            payload = decode_access_token(token)
        except TokenDecodeError:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Invalid or expired token",
                    "response": None,
                },
            )

        request.state.token_payload = payload
        return await call_next(request)
