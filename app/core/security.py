from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import base64
from typing import Any

from jose import JWTError, jwt
from passlib.exc import UnknownHashError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 210000


class TokenDecodeError(Exception):
    pass


def _pbkdf2_hash(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _make_pbkdf2_password_hash(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = os.urandom(16)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8")
    digest_b64 = _pbkdf2_hash(password, salt, iterations)
    return f"{PBKDF2_SCHEME}${iterations}${salt_b64}${digest_b64}"


def _verify_pbkdf2_password(password: str, hashed_password: str) -> bool:
    try:
        scheme, iterations_str, salt_b64, digest_b64 = hashed_password.split("$", 3)
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iterations_str)
        salt = base64.urlsafe_b64decode(salt_b64.encode("utf-8"))
        expected = _pbkdf2_hash(password, salt, iterations)
        return hmac.compare_digest(expected, digest_b64)
    except Exception:
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Preferred verification path for new hashes.
    if hashed_password.startswith(f"{PBKDF2_SCHEME}$"):
        return _verify_pbkdf2_password(plain_password, hashed_password)

    # Legacy compatibility for old bcrypt hashes only.
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError):
        return False


def get_password_hash(password: str) -> str:
    # Use PBKDF2 to avoid bcrypt backend incompatibility in some Windows environments.
    return _make_pbkdf2_password_hash(password)


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None, expires_minutes: int | None = None) -> str:
    exp_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=exp_minutes),
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None, expires_days: int | None = None) -> str:
    exp_days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=exp_days),
        extra_claims=extra_claims,
    )


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            raise TokenDecodeError("Invalid token type")
        return payload
    except JWTError as exc:
        raise TokenDecodeError("Invalid token") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type="refresh")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
