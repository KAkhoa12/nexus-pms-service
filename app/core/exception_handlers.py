from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _to_json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]
    return str(value)


def _error_payload(
    message: str, response: object | None = None
) -> dict[str, object | None]:
    return {
        "success": False,
        "message": message,
        "response": _to_json_safe(response) if response is not None else None,
    }


def _loc_to_vi(loc: tuple[str | int, ...] | list[str | int]) -> str:
    labels = {
        "body": "dữ liệu gửi lên",
        "query": "tham số truy vấn",
        "path": "tham số đường dẫn",
        "header": "header",
        "email": "email",
        "password": "mật khẩu",
    }
    if len(loc) >= 2:
        field = str(loc[-1])
        return labels.get(field, field)
    if len(loc) == 1:
        return labels.get(str(loc[0]), str(loc[0]))
    return "dữ liệu"


def _validation_message_vi(errors: list[dict[str, object]]) -> str:
    if not errors:
        return "Dữ liệu không hợp lệ."

    first = errors[0]
    err_type = str(first.get("type", ""))
    loc = first.get("loc", ())
    ctx = first.get("ctx", {})
    field_name = _loc_to_vi(loc if isinstance(loc, (tuple, list)) else ())

    if err_type == "string_too_short":
        min_length = ctx.get("min_length") if isinstance(ctx, dict) else None
        if min_length is not None:
            return f"{field_name.capitalize()} phải có ít nhất {min_length} ký tự."
        return f"{field_name.capitalize()} quá ngắn."

    if err_type in {"value_error", "string_type"}:
        return f"Giá trị của {field_name} không hợp lệ."

    if err_type == "missing":
        return f"Thiếu trường bắt buộc: {field_name}."

    if err_type == "value_error.email":
        return "Email không đúng định dạng."

    return "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại thông tin."


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    response: object | None = None
    if isinstance(exc.detail, str):
        message = exc.detail
    elif isinstance(exc.detail, dict):
        message = str(exc.detail.get("message", "HTTP error"))
        response = exc.detail.get("errors")
    elif isinstance(exc.detail, list):
        message = "HTTP error"
        response = exc.detail
    else:
        message = "HTTP error"
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(message=message, response=response),
    )


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = _to_json_safe(exc.errors())
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            message=_validation_message_vi(errors if isinstance(errors, list) else []),
            response=errors,
        ),
    )


async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_payload(message="Internal server error", response=None),
    )
