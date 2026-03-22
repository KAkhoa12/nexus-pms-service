from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampSoftDeleteMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def import_all_models() -> None:
    """
    Ensure all ORM models are imported so Base.metadata is fully populated.
    Call this before create_all() and from Alembic env.py.
    """
    # Core domain models (SaaS/RBAC, rooms, renters, billing, maintenance, etc.)
    from app.modules.agents import models as _agent_models  # noqa: F401
    from app.modules.auth import models as _auth_models  # noqa: F401
    from app.modules.core import models as _core_models  # noqa: F401
