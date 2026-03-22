from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import TimestampSoftDeleteMixin


class ServiceFee(TimestampSoftDeleteMixin, Base):
    __tablename__ = "service_fees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_service_fees_tenant_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    default_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    billing_cycle: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="MONTHLY",
        server_default="MONTHLY",
    )
    cycle_interval_months: Mapped[int | None] = mapped_column(nullable=True)
    charge_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="FIXED",
        server_default="FIXED",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship()


class CustomerAppointment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "customer_appointments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SCHEDULED", server_default="SCHEDULED"
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    tenant: Mapped["SaasTenant"] = relationship()


__all__ = ["ServiceFee", "CustomerAppointment"]
