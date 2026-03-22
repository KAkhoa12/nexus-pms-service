from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import MaintenancePriorityEnum, MaintenanceStatusEnum, TimestampSoftDeleteMixin, enum_col


class MaintenanceTicket(TimestampSoftDeleteMixin, Base):
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False)
    renter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("renters.id", ondelete="SET NULL"), index=True, nullable=True)
    issue_type: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[MaintenancePriorityEnum] = mapped_column(
        enum_col(MaintenancePriorityEnum, "maintenance_priority_enum"),
        nullable=False,
    )
    status: Mapped[MaintenanceStatusEnum] = mapped_column(
        enum_col(MaintenanceStatusEnum, "maintenance_status_enum"),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship(back_populates="maintenance_tickets")
    renter: Mapped[Optional["Renter"]] = relationship(back_populates="maintenance_tickets")
    logs: Mapped[List["MaintenanceLog"]] = relationship(back_populates="ticket")
    costs: Mapped[List["MaintenanceCost"]] = relationship(back_populates="ticket")


class MaintenanceLog(TimestampSoftDeleteMixin, Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tickets.id", ondelete="CASCADE"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    ticket: Mapped["MaintenanceTicket"] = relationship(back_populates="logs")
    created_by_user: Mapped[Optional["User"]] = relationship(back_populates="maintenance_logs")


class Vendor(TimestampSoftDeleteMixin, Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    service_type: Mapped[str] = mapped_column(String(255), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    maintenance_costs: Mapped[List["MaintenanceCost"]] = relationship(back_populates="vendor")


class MaintenanceCost(TimestampSoftDeleteMixin, Base):
    __tablename__ = "maintenance_costs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tickets.id", ondelete="CASCADE"), index=True, nullable=False)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), index=True, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    ticket: Mapped["MaintenanceTicket"] = relationship(back_populates="costs")
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="maintenance_costs")


__all__ = ["MaintenanceTicket", "MaintenanceLog", "Vendor", "MaintenanceCost"]
