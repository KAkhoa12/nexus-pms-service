from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    response: T | None = None


class PaginationMeta(BaseModel):
    page: int
    items_per_page: int
    total_items: int
    total_pages: int


class PaginatedResult(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta


def success_response(data: T, message: str = "Success") -> ApiResponse[T]:
    return ApiResponse[T](success=True, message=message, response=data)


def build_paginated_result(
    *, items: list[T], total_items: int, page: int, items_per_page: int
) -> PaginatedResult[T]:
    total_pages = (
        max(1, ceil(total_items / items_per_page)) if items_per_page > 0 else 1
    )
    return PaginatedResult[T](
        items=items,
        pagination=PaginationMeta(
            page=page,
            items_per_page=items_per_page,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )
