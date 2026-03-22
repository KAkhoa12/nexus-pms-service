"""add pro aurora theme feature for packages

Revision ID: gg78bb90cc12
Revises: ff67aa89bb01
Create Date: 2026-03-16 08:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "gg78bb90cc12"
down_revision: Union[str, Sequence[str], None] = "ff67aa89bb01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_KEY = "PRO_AURORA_THEME"


def _ensure_feature(
    bind: sa.Connection,
    *,
    package_code: str,
    feature_name: str,
    feature_description: str,
    is_included: bool,
    limit_value: str | None,
    sort_order: int,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO saas_package_features (
                package_id,
                feature_key,
                feature_name,
                feature_description,
                is_included,
                limit_value,
                sort_order,
                created_at,
                updated_at
            )
            SELECT
                p.id,
                :feature_key,
                :feature_name,
                :feature_description,
                :is_included,
                :limit_value,
                :sort_order,
                NOW(),
                NOW()
            FROM saas_packages p
            WHERE p.code = :package_code
              AND p.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM saas_package_features f
                  WHERE f.package_id = p.id
                    AND f.feature_key = :feature_key
                    AND f.deleted_at IS NULL
              )
            """
        ),
        {
            "feature_key": FEATURE_KEY,
            "feature_name": feature_name,
            "feature_description": feature_description,
            "is_included": 1 if is_included else 0,
            "limit_value": limit_value,
            "sort_order": sort_order,
            "package_code": package_code,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("saas_package_features"):
        return

    _ensure_feature(
        bind,
        package_code="FREE",
        feature_name="Pro Aurora Theme",
        feature_description="Theme cao cap chi mo tu goi Pro tro len",
        is_included=False,
        limit_value="Khong ho tro",
        sort_order=13,
    )
    _ensure_feature(
        bind,
        package_code="PRO",
        feature_name="Pro Aurora Theme",
        feature_description="Theme dashboard doc quyen lay cam hung tu giao dien goi Pro",
        is_included=True,
        limit_value=None,
        sort_order=13,
    )
    _ensure_feature(
        bind,
        package_code="BUSINESS",
        feature_name="Pro Aurora Theme",
        feature_description="Bao gom theme dashboard doc quyen Pro Aurora",
        is_included=True,
        limit_value=None,
        sort_order=13,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("saas_package_features"):
        return

    bind.execute(
        sa.text(
            """
            DELETE FROM saas_package_features
            WHERE feature_key = :feature_key
            """
        ),
        {"feature_key": FEATURE_KEY},
    )
