from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.base import Base, import_all_models
from app.db.session import engine


def _ensure_permissions_table_extensions() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("permissions"):
            return

        columns = {column["name"] for column in inspector.get_columns("permissions")}
        if "module_mean" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE permissions
                    ADD COLUMN module_mean VARCHAR(128) NULL AFTER module
                    """
                )
            )


def _ensure_leases_table_extensions() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("leases"):
            return

        columns = {column["name"] for column in inspector.get_columns("leases")}

        if "created_by_user_id" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN created_by_user_id BIGINT NULL
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "lease_years" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN lease_years INT NOT NULL DEFAULT 1
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "handover_at" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN handover_at DATETIME NULL
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "security_deposit_amount" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN security_deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "security_deposit_paid_amount" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN security_deposit_paid_amount DECIMAL(18,2) NOT NULL DEFAULT 0
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "security_deposit_payment_method" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN security_deposit_payment_method ENUM('CASH', 'BANK', 'QR') NULL
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "security_deposit_paid_at" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN security_deposit_paid_at DATETIME NULL
                    """
                )
            )

        columns = {column["name"] for column in inspector.get_columns("leases")}
        if "security_deposit_note" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE leases
                    ADD COLUMN security_deposit_note TEXT NULL
                    """
                )
            )

        conn.execute(
            text(
                """
                UPDATE leases
                SET lease_years = 1
                WHERE lease_years IS NULL OR lease_years < 1
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE leases
                SET handover_at = start_date
                WHERE handover_at IS NULL AND start_date IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE leases
                SET security_deposit_amount = COALESCE(security_deposit_amount, 0),
                    security_deposit_paid_amount = COALESCE(security_deposit_paid_amount, 0),
                    security_deposit_note = COALESCE(security_deposit_note, '')
                """
            )
        )


def init_db() -> None:
    # Always load mapped classes so SQLAlchemy metadata is ready.
    import_all_models()
    _ensure_permissions_table_extensions()
    _ensure_leases_table_extensions()
    # Use Alembic as the primary schema management tool.
    # Auto create-all can fail on partially broken MySQL tables (e.g. "doesn't exist in engine").
    if settings.DB_AUTO_CREATE_TABLES_ON_STARTUP:
        Base.metadata.create_all(bind=engine)
