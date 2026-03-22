"""isolate team workspaces into dedicated tenants

Revision ID: qq78ll90mm12
Revises: pp67kk89ll01
Create Date: 2026-03-18 16:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "qq78ll90mm12"
down_revision: Union[str, Sequence[str], None] = "pp67kk89ll01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _build_workspace_tenant_name(raw_name: str, team_id: int) -> str:
    normalized = (raw_name or "").strip() or f"Team {team_id}"
    candidate = f"{normalized} Workspace"
    if len(candidate) > 255:
        candidate = candidate[:255].rstrip()
    return candidate


def _ensure_role_with_permissions(
    bind: sa.Connection,
    *,
    tenant_id: int,
    role_name: str,
    role_description: str | None,
    source_role_id: int | None,
) -> int:
    row = (
        bind.execute(
            sa.text(
                """
            SELECT id, deleted_at
            FROM roles
            WHERE tenant_id = :tenant_id AND name = :role_name
            ORDER BY id ASC
            LIMIT 1
            """
            ),
            {"tenant_id": tenant_id, "role_name": role_name},
        )
        .mappings()
        .first()
    )

    if row is None:
        created = bind.execute(
            sa.text(
                """
                INSERT INTO roles (tenant_id, name, description, created_at, updated_at, deleted_at)
                VALUES (:tenant_id, :name, :description, NOW(), NOW(), NULL)
                """
            ),
            {
                "tenant_id": tenant_id,
                "name": role_name,
                "description": role_description,
            },
        )
        role_id = int(created.lastrowid)
    else:
        role_id = int(row["id"])
        bind.execute(
            sa.text(
                """
                UPDATE roles
                SET
                    description = COALESCE(:description, description),
                    deleted_at = NULL,
                    updated_at = NOW()
                WHERE id = :role_id
                """
            ),
            {
                "description": role_description,
                "role_id": role_id,
            },
        )

    if source_role_id is None:
        bind.execute(
            sa.text(
                """
                UPDATE role_permissions rp
                JOIN permissions p ON p.code = rp.permission_code
                SET
                    rp.deleted_at = NULL,
                    rp.updated_at = NOW()
                WHERE
                    rp.role_id = :role_id
                    AND rp.deleted_at IS NOT NULL
                    AND p.deleted_at IS NULL
                """
            ),
            {"role_id": role_id},
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (tenant_id, role_id, permission_code, created_at, updated_at, deleted_at)
                SELECT :tenant_id, :role_id, p.code, NOW(), NOW(), NULL
                FROM permissions p
                LEFT JOIN role_permissions rp
                    ON rp.role_id = :role_id
                    AND rp.permission_code = p.code
                WHERE p.deleted_at IS NULL AND rp.id IS NULL
                """
            ),
            {
                "tenant_id": tenant_id,
                "role_id": role_id,
            },
        )
    else:
        bind.execute(
            sa.text(
                """
                UPDATE role_permissions rp
                JOIN role_permissions src
                    ON src.permission_code = rp.permission_code
                    AND src.role_id = :source_role_id
                    AND src.deleted_at IS NULL
                JOIN permissions p ON p.code = src.permission_code
                SET
                    rp.deleted_at = NULL,
                    rp.updated_at = NOW()
                WHERE
                    rp.role_id = :role_id
                    AND rp.deleted_at IS NOT NULL
                    AND p.deleted_at IS NULL
                """
            ),
            {
                "role_id": role_id,
                "source_role_id": source_role_id,
            },
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (tenant_id, role_id, permission_code, created_at, updated_at, deleted_at)
                SELECT :tenant_id, :role_id, src.permission_code, NOW(), NOW(), NULL
                FROM role_permissions src
                JOIN permissions p
                    ON p.code = src.permission_code
                    AND p.deleted_at IS NULL
                LEFT JOIN role_permissions rp
                    ON rp.role_id = :role_id
                    AND rp.permission_code = src.permission_code
                WHERE
                    src.role_id = :source_role_id
                    AND src.deleted_at IS NULL
                    AND rp.id IS NULL
                """
            ),
            {
                "tenant_id": tenant_id,
                "role_id": role_id,
                "source_role_id": source_role_id,
            },
        )

    return role_id


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    required_tables = {
        "saas_tenants",
        "users",
        "teams",
        "team_members",
        "roles",
        "permissions",
        "role_permissions",
    }
    if not all(_has_table(inspector, name) for name in required_tables):
        return

    teams = (
        bind.execute(
            sa.text(
                """
            SELECT
                t.id,
                t.name,
                t.tenant_id AS team_tenant_id,
                u.tenant_id AS owner_tenant_id
            FROM teams t
            JOIN users u ON u.id = t.owner_user_id
            WHERE t.deleted_at IS NULL
            ORDER BY t.id ASC
            """
            )
        )
        .mappings()
        .all()
    )

    for row in teams:
        team_id = int(row["id"])
        current_team_tenant_id = int(row["team_tenant_id"])
        owner_tenant_id = int(row["owner_tenant_id"])

        if current_team_tenant_id != owner_tenant_id:
            bind.execute(
                sa.text(
                    """
                    UPDATE team_members
                    SET tenant_id = :tenant_id
                    WHERE team_id = :team_id AND tenant_id <> :tenant_id
                    """
                ),
                {"tenant_id": current_team_tenant_id, "team_id": team_id},
            )
            continue

        tenant_name = _build_workspace_tenant_name(str(row["name"] or ""), team_id)
        created = bind.execute(
            sa.text(
                """
                INSERT INTO saas_tenants (name, plan_type, status, created_at, updated_at, deleted_at)
                VALUES (:name, 'BASIC', 'ACTIVE', NOW(), NOW(), NULL)
                """
            ),
            {"name": tenant_name},
        )
        workspace_tenant_id = int(created.lastrowid)

        bind.execute(
            sa.text("UPDATE teams SET tenant_id = :tenant_id WHERE id = :team_id"),
            {"tenant_id": workspace_tenant_id, "team_id": team_id},
        )
        bind.execute(
            sa.text(
                """
                UPDATE team_members
                SET tenant_id = :tenant_id
                WHERE team_id = :team_id
                """
            ),
            {"tenant_id": workspace_tenant_id, "team_id": team_id},
        )

        admin_role_id = _ensure_role_with_permissions(
            bind,
            tenant_id=workspace_tenant_id,
            role_name="ADMIN",
            role_description="Workspace manager role",
            source_role_id=None,
        )

        role_rows = (
            bind.execute(
                sa.text(
                    """
                SELECT DISTINCT
                    tm.rbac_role_id AS old_role_id,
                    r.name AS old_role_name,
                    r.description AS old_role_description
                FROM team_members tm
                LEFT JOIN roles r ON r.id = tm.rbac_role_id
                WHERE
                    tm.team_id = :team_id
                    AND tm.deleted_at IS NULL
                    AND tm.rbac_role_id IS NOT NULL
                """
                ),
                {"team_id": team_id},
            )
            .mappings()
            .all()
        )

        role_id_map: dict[int, int] = {}
        for role_row in role_rows:
            old_role_id_raw = role_row["old_role_id"]
            if old_role_id_raw is None:
                continue
            old_role_id = int(old_role_id_raw)
            old_role_name = (
                str(role_row["old_role_name"]).strip()
                if role_row["old_role_name"] is not None
                else ""
            )
            old_role_description = (
                str(role_row["old_role_description"])
                if role_row["old_role_description"] is not None
                else None
            )

            if not old_role_name:
                role_id_map[old_role_id] = admin_role_id
                continue

            new_role_id = _ensure_role_with_permissions(
                bind,
                tenant_id=workspace_tenant_id,
                role_name=old_role_name,
                role_description=old_role_description,
                source_role_id=old_role_id,
            )
            role_id_map[old_role_id] = new_role_id

        for old_role_id, new_role_id in role_id_map.items():
            bind.execute(
                sa.text(
                    """
                    UPDATE team_members
                    SET rbac_role_id = :new_role_id
                    WHERE team_id = :team_id AND rbac_role_id = :old_role_id
                    """
                ),
                {
                    "new_role_id": new_role_id,
                    "team_id": team_id,
                    "old_role_id": old_role_id,
                },
            )

        bind.execute(
            sa.text(
                """
                UPDATE team_members
                SET rbac_role_id = :admin_role_id
                WHERE
                    team_id = :team_id
                    AND member_role = 'MANAGER'
                    AND deleted_at IS NULL
                    AND (rbac_role_id IS NULL OR rbac_role_id = 0)
                """
            ),
            {"team_id": team_id, "admin_role_id": admin_role_id},
        )


def downgrade() -> None:
    # Data migration is intentionally not reversed automatically.
    pass
