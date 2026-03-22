from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import MeterTypeEnum, TimestampSoftDeleteMixin, enum_col


class MeterReading(TimestampSoftDeleteMixin, Base):
    __tablename__ = "meter_readings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "room_id",
            "meter_type",
            "period_month",
            name="uq_meter_readings_tenant_room_meter_period",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False)
    meter_type: Mapped[MeterTypeEnum] = mapped_column(enum_col(MeterTypeEnum, "meter_type_enum"), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    old_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    new_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    consumption: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship(back_populates="meter_readings")


__all__ = ["MeterReading"]
