from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import (
    FeeCalculationTypeEnum,
    InvoiceStatusEnum,
    PaymentMethodEnum,
    PaymentStatusEnum,
    PenaltyTypeEnum,
    QrRequestStatusEnum,
    TimestampSoftDeleteMixin,
    enum_col,
)


class FeeType(TimestampSoftDeleteMixin, Base):
    __tablename__ = "fee_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_fee_types_tenant_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    calculation_type: Mapped[FeeCalculationTypeEnum] = mapped_column(
        enum_col(FeeCalculationTypeEnum, "fee_calculation_type_enum"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship()
    invoice_templates: Mapped[List["InvoiceTemplate"]] = relationship(
        back_populates="fee_type"
    )
    invoice_items: Mapped[List["InvoiceItem"]] = relationship(back_populates="fee_type")


class InvoiceTemplate(TimestampSoftDeleteMixin, Base):
    __tablename__ = "invoice_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "room_type_id",
            "fee_type_id",
            name="uq_invoice_templates_scope",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fee_type_id: Mapped[int] = mapped_column(
        ForeignKey("fee_types.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship()
    room_type: Mapped["RoomType"] = relationship(back_populates="invoice_templates")
    fee_type: Mapped["FeeType"] = relationship(back_populates="invoice_templates")


class Invoice(TimestampSoftDeleteMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index(
            "ix_invoices_tenant_period_status", "tenant_id", "period_month", "status"
        ),
        UniqueConstraint(
            "tenant_id",
            "room_id",
            "period_month",
            name="uq_invoices_tenant_room_period",
        ),
    )

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
    lease_id: Mapped[int | None] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"), index=True, nullable=True
    )
    installment_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    status: Mapped[InvoiceStatusEnum] = mapped_column(
        enum_col(InvoiceStatusEnum, "invoice_status_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    content_html: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )

    tenant: Mapped["SaasTenant"] = relationship(back_populates="invoices")
    branch: Mapped["Branch"] = relationship(back_populates="invoices")
    room: Mapped["Room"] = relationship(back_populates="invoices")
    renter: Mapped["Renter"] = relationship()
    lease: Mapped[Optional["Lease"]] = relationship()
    items: Mapped[List["InvoiceItem"]] = relationship(back_populates="invoice")
    penalties: Mapped[List["InvoicePenalty"]] = relationship(back_populates="invoice")
    payments: Mapped[List["Payment"]] = relationship(back_populates="invoice")
    payment_qr_requests: Mapped[List["PaymentQrRequest"]] = relationship(
        back_populates="invoice"
    )

    def __repr__(self) -> str:
        return f"Invoice(id={self.id}, period_month='{self.period_month}', status='{self.status.value}')"


class InvoiceItem(TimestampSoftDeleteMixin, Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fee_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fee_types.id", ondelete="SET NULL"), index=True, nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=1, server_default="1"
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    fee_type: Mapped[Optional["FeeType"]] = relationship(back_populates="invoice_items")


class InvoicePenalty(TimestampSoftDeleteMixin, Base):
    __tablename__ = "invoice_penalties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    penalty_type: Mapped[PenaltyTypeEnum] = mapped_column(
        enum_col(PenaltyTypeEnum, "penalty_type_enum"), nullable=False
    )
    days_late: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    tenant: Mapped["SaasTenant"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="penalties")


class Payment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    method: Mapped[PaymentMethodEnum] = mapped_column(
        enum_col(PaymentMethodEnum, "payment_method_enum"), nullable=False
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        enum_col(PaymentStatusEnum, "payment_status_enum"), nullable=False
    )
    transaction_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped["SaasTenant"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="payments")


class PaymentQrRequest(TimestampSoftDeleteMixin, Base):
    __tablename__ = "payment_qr_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_text: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[QrRequestStatusEnum] = mapped_column(
        enum_col(QrRequestStatusEnum, "payment_qr_status_enum"), nullable=False
    )

    tenant: Mapped["SaasTenant"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="payment_qr_requests")


__all__ = [
    "FeeType",
    "InvoiceTemplate",
    "Invoice",
    "InvoiceItem",
    "InvoicePenalty",
    "Payment",
    "PaymentQrRequest",
]
