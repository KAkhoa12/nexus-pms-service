from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from .m00_base import TimestampSoftDeleteMixin


class FormTemplate(TimestampSoftDeleteMixin, Base):
    __tablename__ = "form_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_form_templates_tenant_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("saas_tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="GENERAL", server_default="GENERAL"
    )
    page_size: Mapped[str] = mapped_column(
        String(16), nullable=False, default="A4", server_default="A4"
    )
    orientation: Mapped[str] = mapped_column(
        String(16), nullable=False, default="portrait", server_default="portrait"
    )
    font_family: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Arial", server_default="Arial"
    )
    font_size: Mapped[int] = mapped_column(nullable=False, default=14, server_default="14")
    text_color: Mapped[str] = mapped_column(
        String(16), nullable=False, default="#111827", server_default="#111827"
    )
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tenant: Mapped["SaasTenant"] = relationship()


__all__ = ["FormTemplate"]
