from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import (
    DepositStatusEnum,
    LeaseStatusEnum,
    PaymentMethodEnum,
    PricingModeEnum,
    TimestampSoftDeleteMixin,
    enum_col,
)


class Renter(TimestampSoftDeleteMixin, Base):
    __tablename__ = "renters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    identity_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship(back_populates="renters")
    members: Mapped[List["RenterMember"]] = relationship(back_populates="renter")
    leases: Mapped[List["Lease"]] = relationship(back_populates="renter")
    deposits: Mapped[List["Deposit"]] = relationship(back_populates="renter")
    assets: Mapped[List["Asset"]] = relationship(back_populates="renter")
    maintenance_tickets: Mapped[List["MaintenanceTicket"]] = relationship(
        back_populates="renter"
    )

    def __repr__(self) -> str:
        return f"Renter(id={self.id}, full_name='{self.full_name}')"


class RenterMember(TimestampSoftDeleteMixin, Base):
    __tablename__ = "renter_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    renter_id: Mapped[int] = mapped_column(
        ForeignKey("renters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relation: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    renter: Mapped["Renter"] = relationship(back_populates="members")


class Lease(TimestampSoftDeleteMixin, Base):
    __tablename__ = "leases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    renter_id: Mapped[int] = mapped_column(
        ForeignKey("renters.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    lease_years: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        server_default="1",
    )
    handover_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rent_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pricing_mode: Mapped[PricingModeEnum] = mapped_column(
        enum_col(PricingModeEnum, "lease_pricing_mode_enum"), nullable=False
    )
    status: Mapped[LeaseStatusEnum] = mapped_column(
        enum_col(LeaseStatusEnum, "lease_status_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    content_html: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    security_deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    security_deposit_paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    security_deposit_payment_method: Mapped[Optional[PaymentMethodEnum]] = (
        mapped_column(
            enum_col(PaymentMethodEnum, "lease_security_deposit_method_enum"),
            nullable=True,
        )
    )
    security_deposit_paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    security_deposit_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    tenant: Mapped["SaasTenant"] = relationship(back_populates="leases")
    branch: Mapped["Branch"] = relationship(back_populates="leases")
    room: Mapped["Room"] = relationship(back_populates="leases")
    renter: Mapped["Renter"] = relationship(back_populates="leases")
    created_by_user: Mapped[Optional["User"]] = relationship()
    deposits: Mapped[List["Deposit"]] = relationship(back_populates="lease")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="lease")
    handover_sessions: Mapped[List["RoomHandoverSession"]] = relationship(
        back_populates="lease"
    )


class Deposit(TimestampSoftDeleteMixin, Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    renter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("renters.id", ondelete="SET NULL"), index=True, nullable=True
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"), index=True, nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    method: Mapped[PaymentMethodEnum] = mapped_column(
        enum_col(PaymentMethodEnum, "deposit_method_enum"), nullable=False
    )
    status: Mapped[DepositStatusEnum] = mapped_column(
        enum_col(DepositStatusEnum, "deposit_status_enum"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_html: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship()
    renter: Mapped[Optional["Renter"]] = relationship(back_populates="deposits")
    lease: Mapped["Lease"] = relationship(back_populates="deposits")
    refunds: Mapped[List["DepositRefund"]] = relationship(back_populates="deposit")


class DepositRefund(TimestampSoftDeleteMixin, Base):
    __tablename__ = "deposit_refunds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    deposit_id: Mapped[int] = mapped_column(
        ForeignKey("deposits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    refunded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    deposit: Mapped["Deposit"] = relationship(back_populates="refunds")


__all__ = ["Renter", "RenterMember", "Lease", "Deposit", "DepositRefund"]
