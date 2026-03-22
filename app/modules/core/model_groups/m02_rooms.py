from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import (
    PricingModeEnum,
    RoomCurrentStatusEnum,
    TimestampSoftDeleteMixin,
    enum_col,
)


class RoomType(TimestampSoftDeleteMixin, Base):
    __tablename__ = "room_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_room_types_tenant_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pricing_mode: Mapped[PricingModeEnum] = mapped_column(
        enum_col(PricingModeEnum, "pricing_mode_enum"), nullable=False
    )
    default_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="room_types")
    rooms: Mapped[List["Room"]] = relationship(back_populates="room_type")
    invoice_templates: Mapped[List["InvoiceTemplate"]] = relationship(
        back_populates="room_type"
    )


class Room(TimestampSoftDeleteMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_rooms_tenant_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True, nullable=False
    )
    area_id: Mapped[int] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    current_status: Mapped[RoomCurrentStatusEnum] = mapped_column(
        enum_col(RoomCurrentStatusEnum, "room_current_status_enum"),
        nullable=False,
    )
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="rooms")
    branch: Mapped["Branch"] = relationship(back_populates="rooms")
    area: Mapped["Area"] = relationship(back_populates="rooms")
    building: Mapped["Building"] = relationship(back_populates="rooms")
    room_type: Mapped["RoomType"] = relationship(back_populates="rooms")
    status_history: Mapped[List["RoomStatusHistory"]] = relationship(
        back_populates="room"
    )
    leases: Mapped[List["Lease"]] = relationship(back_populates="room")
    meter_readings: Mapped[List["MeterReading"]] = relationship(back_populates="room")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="room")
    assets: Mapped[List["Asset"]] = relationship(back_populates="room")
    handover_sessions: Mapped[List["RoomHandoverSession"]] = relationship(
        back_populates="room"
    )
    maintenance_tickets: Mapped[List["MaintenanceTicket"]] = relationship(
        back_populates="room"
    )


class RoomStatusHistory(TimestampSoftDeleteMixin, Base):
    __tablename__ = "room_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    old_status: Mapped[RoomCurrentStatusEnum] = mapped_column(
        enum_col(RoomCurrentStatusEnum, "room_status_history_old_enum"),
        nullable=False,
    )
    new_status: Mapped[RoomCurrentStatusEnum] = mapped_column(
        enum_col(RoomCurrentStatusEnum, "room_status_history_new_enum"),
        nullable=False,
    )
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship(back_populates="status_history")
    changed_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="room_status_changes"
    )


__all__ = ["RoomType", "Room", "RoomStatusHistory"]
