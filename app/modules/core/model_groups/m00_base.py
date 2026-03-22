from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampSoftDeleteMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PlanTypeEnum(str, enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class TenantStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class SubscriptionStatusEnum(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SubscriptionBillingCycleEnum(str, enum.Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class PermissionEffectEnum(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class PricingModeEnum(str, enum.Enum):
    FIXED = "FIXED"
    PER_PERSON = "PER_PERSON"


class RoomCurrentStatusEnum(str, enum.Enum):
    VACANT = "VACANT"
    DEPOSITED = "DEPOSITED"
    RENTED = "RENTED"
    MAINTENANCE = "MAINTENANCE"


class LeaseStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class PaymentMethodEnum(str, enum.Enum):
    CASH = "CASH"
    BANK = "BANK"
    QR = "QR"


class DepositStatusEnum(str, enum.Enum):
    HELD = "HELD"
    REFUNDED = "REFUNDED"
    FORFEITED = "FORFEITED"


class MeterTypeEnum(str, enum.Enum):
    ELECTRIC = "ELECTRIC"
    WATER = "WATER"


class FeeCalculationTypeEnum(str, enum.Enum):
    FIXED = "FIXED"
    PER_PERSON = "PER_PERSON"
    METER_BASED = "METER_BASED"


class InvoiceStatusEnum(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class PenaltyTypeEnum(str, enum.Enum):
    LATE_FEE = "LATE_FEE"


class PaymentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class QrRequestStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    PAID = "PAID"


class CashAccountTypeEnum(str, enum.Enum):
    CASH = "CASH"
    BANK = "BANK"


class TransactionTypeEnum(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class AssetLogActionEnum(str, enum.Enum):
    CHECKIN = "CHECKIN"
    CHECKOUT = "CHECKOUT"
    UPDATE = "UPDATE"


class HandoverTypeEnum(str, enum.Enum):
    CHECKIN = "CHECKIN"
    CHECKOUT = "CHECKOUT"


class HandoverSessionStatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HandoverChecklistStatusEnum(str, enum.Enum):
    OK = "OK"
    DAMAGED = "DAMAGED"


class MaintenancePriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MaintenanceStatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class NotificationTargetScopeEnum(str, enum.Enum):
    ALL = "ALL"
    BRANCH = "BRANCH"
    ROLE = "ROLE"
    USER = "USER"


class TeamMemberRoleEnum(str, enum.Enum):
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


def enum_col(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name)


__all__ = [
    "TimestampSoftDeleteMixin",
    "PlanTypeEnum",
    "TenantStatusEnum",
    "SubscriptionStatusEnum",
    "SubscriptionBillingCycleEnum",
    "PermissionEffectEnum",
    "PricingModeEnum",
    "RoomCurrentStatusEnum",
    "LeaseStatusEnum",
    "PaymentMethodEnum",
    "DepositStatusEnum",
    "MeterTypeEnum",
    "FeeCalculationTypeEnum",
    "InvoiceStatusEnum",
    "PenaltyTypeEnum",
    "PaymentStatusEnum",
    "QrRequestStatusEnum",
    "CashAccountTypeEnum",
    "TransactionTypeEnum",
    "AssetLogActionEnum",
    "HandoverTypeEnum",
    "HandoverSessionStatusEnum",
    "HandoverChecklistStatusEnum",
    "MaintenancePriorityEnum",
    "MaintenanceStatusEnum",
    "NotificationTargetScopeEnum",
    "TeamMemberRoleEnum",
    "enum_col",
]
