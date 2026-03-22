from __future__ import annotations

from email_validator import EmailNotValidError, validate_email

COMMON_WEAK_PASSWORDS = {
    "123456",
    "12345678",
    "password",
    "password123",
    "qwerty",
    "admin",
    "letmein",
}


def is_valid_email(email: str) -> bool:
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def is_valid_phone(phone: str) -> bool:
    normalized = (
        phone.strip()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
    )
    if normalized.startswith("+"):
        digits = normalized[1:]
    else:
        digits = normalized
    return digits.isdigit() and 9 <= len(digits) <= 15


def password_strength_errors(password: str) -> list[str]:
    errors: list[str] = []
    value = password or ""

    if len(value) < 8:
        errors.append("Password must be at least 8 characters")
    if value.lower() in COMMON_WEAK_PASSWORDS:
        errors.append("Password is too common")
    if value and len(set(value)) == 1:
        errors.append("Password cannot contain the same character only")
    if not any(char.islower() for char in value):
        errors.append("Password must contain at least one lowercase letter")
    if not any(char.isupper() for char in value):
        errors.append("Password must contain at least one uppercase letter")
    if not any(char.isdigit() for char in value):
        errors.append("Password must contain at least one digit")
    if not any(not char.isalnum() for char in value):
        errors.append("Password must contain at least one special character")
    if any(char.isspace() for char in value):
        errors.append("Password cannot contain spaces")

    return errors


def is_strong_password(password: str) -> bool:
    return len(password_strength_errors(password)) == 0
