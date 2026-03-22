from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings

VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


def _is_placeholder_google_client_id(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return (
        "your_google_client_id" in normalized
        or normalized.endswith("apps.googleusercontent.com") is False
    )


def verify_google_credential(credential: str) -> GoogleIdentity:
    if _is_placeholder_google_client_id(settings.GOOGLE_CLIENT_ID):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured. Please set GOOGLE_CLIENT_ID in server .env",
        )

    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        reason = str(exc).strip().lower()
        if "wrong recipient" in reason or "audience" in reason:
            detail = "Google credential audience mismatch. Ensure GOOGLE_CLIENT_ID matches frontend VITE_GOOGLE_CLIENT_ID"
        elif "expired" in reason or "too old" in reason:
            detail = "Google credential is expired. Please sign in with Google again"
        else:
            detail = "Google credential is invalid or expired"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from exc

    issuer = payload.get("iss")
    if issuer not in VALID_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token issuer is invalid",
        )

    sub = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    email_verified = bool(payload.get("email_verified"))
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token missing subject",
        )
    if not email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified",
        )

    return GoogleIdentity(
        sub=sub,
        email=email,
        email_verified=email_verified,
        name=(payload.get("name") or None),
        picture=(payload.get("picture") or None),
    )
