from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import AssetLogActionEnum, TimestampSoftDeleteMixin, enum_col


class AssetType(TimestampSoftDeleteMixin, Base):
    __tablename__ = "asset_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_asset_types_tenant_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    tenant: Mapped["SaasTenant"] = relationship()
    assets: Mapped[List["Asset"]] = relationship(back_populates="asset_type")


class Asset(TimestampSoftDeleteMixin, Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    renter_id: Mapped[int] = mapped_column(
        ForeignKey("renters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_scope: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="RENTER",
        server_default="RENTER",
    )
    asset_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Tài sản",
        server_default="Tài sản",
    )
    identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )
    condition_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="GOOD",
        server_default="GOOD",
    )
    brand: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plate_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acquired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_image_url: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["SaasTenant"] = relationship()
    room: Mapped["Room"] = relationship(back_populates="assets")
    renter: Mapped["Renter"] = relationship(back_populates="assets")
    asset_type: Mapped["AssetType"] = relationship(back_populates="assets")
    logs: Mapped[List["AssetLog"]] = relationship(back_populates="asset")
    images: Mapped[List["AssetImage"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class AssetImage(TimestampSoftDeleteMixin, Base):
    __tablename__ = "asset_images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    tenant: Mapped["SaasTenant"] = relationship()
    asset: Mapped["Asset"] = relationship(back_populates="images")


class AssetLog(TimestampSoftDeleteMixin, Base):
    __tablename__ = "asset_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[AssetLogActionEnum] = mapped_column(
        enum_col(AssetLogActionEnum, "asset_log_action_enum"), nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    tenant: Mapped["SaasTenant"] = relationship()
    asset: Mapped["Asset"] = relationship(back_populates="logs")
    created_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="asset_logs"
    )


__all__ = ["AssetType", "Asset", "AssetImage", "AssetLog"]
