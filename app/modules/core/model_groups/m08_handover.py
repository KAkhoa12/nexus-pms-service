from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import HandoverChecklistStatusEnum, HandoverSessionStatusEnum, HandoverTypeEnum, TimestampSoftDeleteMixin, enum_col


class RoomHandoverSession(TimestampSoftDeleteMixin, Base):
    __tablename__ = "room_handover_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False)
    lease_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leases.id", ondelete="SET NULL"), index=True, nullable=True)
    handover_type: Mapped[HandoverTypeEnum] = mapped_column(enum_col(HandoverTypeEnum, "handover_type_enum"), nullable=False)
    status: Mapped[HandoverSessionStatusEnum] = mapped_column(
        enum_col(HandoverSessionStatusEnum, "handover_session_status_enum"),
        nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship(back_populates="handover_sessions")
    lease: Mapped[Optional["Lease"]] = relationship(back_populates="handover_sessions")
    created_by_user: Mapped["User"] = relationship(back_populates="handover_sessions")
    checklists: Mapped[List["HandoverChecklist"]] = relationship(back_populates="session")
    images: Mapped[List["HandoverImage"]] = relationship(back_populates="session")
    damage_fees: Mapped[List["DamageFee"]] = relationship(back_populates="session")


class HandoverChecklist(TimestampSoftDeleteMixin, Base):
    __tablename__ = "handover_checklists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("room_handover_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[HandoverChecklistStatusEnum] = mapped_column(
        enum_col(HandoverChecklistStatusEnum, "handover_checklist_status_enum"),
        nullable=False,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    session: Mapped["RoomHandoverSession"] = relationship(back_populates="checklists")


class HandoverImage(TimestampSoftDeleteMixin, Base):
    __tablename__ = "handover_images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("room_handover_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    session: Mapped["RoomHandoverSession"] = relationship(back_populates="images")


class DamageFee(TimestampSoftDeleteMixin, Base):
    __tablename__ = "damage_fees"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("room_handover_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    session: Mapped["RoomHandoverSession"] = relationship(back_populates="damage_fees")


__all__ = ["RoomHandoverSession", "HandoverChecklist", "HandoverImage", "DamageFee"]
