from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import CashAccountTypeEnum, TimestampSoftDeleteMixin, TransactionTypeEnum, enum_col


class CashAccount(TimestampSoftDeleteMixin, Base):
    __tablename__ = "cash_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_cash_accounts_tenant_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[CashAccountTypeEnum] = mapped_column(enum_col(CashAccountTypeEnum, "cash_account_type_enum"), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="VND", server_default="VND")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    tenant: Mapped["SaasTenant"] = relationship()
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="account")


class TransactionCategory(TimestampSoftDeleteMixin, Base):
    __tablename__ = "transaction_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name", "type", name="uq_transaction_categories_scope"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TransactionTypeEnum] = mapped_column(enum_col(TransactionTypeEnum, "transaction_category_type_enum"), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="category")


class Transaction(TimestampSoftDeleteMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_tenant_occurred_at", "tenant_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("cash_accounts.id", ondelete="RESTRICT"), index=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("transaction_categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    type: Mapped[TransactionTypeEnum] = mapped_column(enum_col(TransactionTypeEnum, "transaction_type_enum"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    branch: Mapped[Optional["Branch"]] = relationship(back_populates="transactions")
    account: Mapped["CashAccount"] = relationship(back_populates="transactions")
    category: Mapped["TransactionCategory"] = relationship(back_populates="transactions")


__all__ = ["CashAccount", "TransactionCategory", "Transaction"]
