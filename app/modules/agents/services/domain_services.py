from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.modules.agents.models import AgentKnowledgeDocument
from app.modules.agents.schemas.tools import (
    AreaOverviewItem,
    BranchOverviewItem,
    BuildingOverviewItem,
    ContractLookupItem,
    ContractLookupOutput,
    CustomerSearchItem,
    InstallmentInfo,
    InvoiceInstallmentsOutput,
    KnowledgeHit,
    LeaseInstallmentInfo,
    OverdueInvoiceItem,
    OverdueInvoicesOutput,
    RoomStatusOverviewOutput,
    RoomStatusRoomItem,
    RoomStatusSummaryItem,
    SearchCustomersOutput,
    SearchKnowledgeOutput,
    TeamInfo,
    TeamMemberInfo,
    TeamMembersOutput,
    TeamNotificationOutput,
    TenantKpiOutput,
)
from app.modules.core.models import (
    Area,
    Branch,
    Building,
    FormTemplate,
    Invoice,
    InvoiceStatusEnum,
    LandingPageSection,
    Lease,
    LeaseStatusEnum,
    Payment,
    PaymentStatusEnum,
    Renter,
    Role,
    Room,
    RoomCurrentStatusEnum,
    Team,
    TeamMember,
    User,
)


class DomainDataProvider(Protocol):
    def fetch_tenant_kpi(self, *, tenant_id: int) -> TenantKpiOutput: ...

    def fetch_room_status_overview(
        self,
        *,
        tenant_id: int,
        branch_id: int | None,
        area_id: int | None,
        building_id: int | None,
        include_rooms: bool,
        room_limit: int,
    ) -> RoomStatusOverviewOutput: ...

    def fetch_team_members(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        team_limit: int,
        member_limit: int,
    ) -> TeamMembersOutput: ...

    def fetch_overdue_invoices(
        self, *, tenant_id: int, limit: int, min_days_overdue: int
    ) -> OverdueInvoicesOutput: ...

    def fetch_invoice_installments(
        self,
        *,
        tenant_id: int,
        query: str,
        lease_limit: int,
        installment_limit: int,
    ) -> InvoiceInstallmentsOutput: ...

    def search_customers(
        self, *, tenant_id: int, query: str, limit: int
    ) -> SearchCustomersOutput: ...

    def fetch_contracts(
        self,
        *,
        tenant_id: int,
        query: str | None,
        customer_id: int | None,
        only_active: bool,
        limit: int,
    ) -> ContractLookupOutput: ...

    def dispatch_team_notification(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        title: str,
        body: str,
        recipient_user_ids: list[int],
        dry_run: bool,
    ) -> TeamNotificationOutput: ...

    def fetch_internal_knowledge(
        self, *, tenant_id: int, query: str, limit: int
    ) -> SearchKnowledgeOutput: ...


def _enum_to_str(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


@dataclass
class SqlAlchemyDomainDataProvider:
    db: Session

    def fetch_tenant_kpi(self, *, tenant_id: int) -> TenantKpiOutput:
        now = datetime.now(timezone.utc)
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_month.month == 12:
            next_month = start_month.replace(year=start_month.year + 1, month=1)
        else:
            next_month = start_month.replace(month=start_month.month + 1)

        room_count_row = self.db.execute(
            select(
                func.count(Room.id).label("total_rooms"),
                func.sum(
                    case(
                        (Room.current_status == RoomCurrentStatusEnum.VACANT, 1),
                        else_=0,
                    )
                ).label("vacant_rooms"),
                func.sum(
                    case(
                        (Room.current_status == RoomCurrentStatusEnum.DEPOSITED, 1),
                        else_=0,
                    )
                ).label("deposited_rooms"),
                func.sum(
                    case(
                        (Room.current_status == RoomCurrentStatusEnum.RENTED, 1),
                        else_=0,
                    )
                ).label("rented_rooms"),
                func.sum(
                    case(
                        (Room.current_status == RoomCurrentStatusEnum.MAINTENANCE, 1),
                        else_=0,
                    )
                ).label("maintenance_rooms"),
            ).where(
                Room.tenant_id == tenant_id,
                Room.deleted_at.is_(None),
            )
        ).one()

        overdue_row = self.db.execute(
            select(
                func.count(Invoice.id).label("overdue_invoices"),
                func.coalesce(
                    func.sum(Invoice.total_amount - Invoice.paid_amount),
                    0,
                ).label("overdue_amount"),
            ).where(
                Invoice.tenant_id == tenant_id,
                Invoice.deleted_at.is_(None),
                Invoice.due_date < now,
                Invoice.total_amount > Invoice.paid_amount,
                Invoice.status.in_(
                    [
                        InvoiceStatusEnum.UNPAID,
                        InvoiceStatusEnum.PARTIAL,
                        InvoiceStatusEnum.OVERDUE,
                    ]
                ),
            )
        ).one()

        active_leases = int(
            self.db.scalar(
                select(func.count(Lease.id)).where(
                    Lease.tenant_id == tenant_id,
                    Lease.deleted_at.is_(None),
                    Lease.status == LeaseStatusEnum.ACTIVE,
                )
            )
            or 0
        )

        paid_revenue_current_month = self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.tenant_id == tenant_id,
                Payment.deleted_at.is_(None),
                Payment.status == PaymentStatusEnum.SUCCESS,
                Payment.paid_at.is_not(None),
                Payment.paid_at >= start_month,
                Payment.paid_at < next_month,
            )
        ) or Decimal("0")

        total_rooms = int(room_count_row.total_rooms or 0)
        rented_rooms = int(room_count_row.rented_rooms or 0)
        occupancy_rate_percent = (
            round((rented_rooms / total_rooms) * 100, 2) if total_rooms > 0 else 0.0
        )

        return TenantKpiOutput(
            total_rooms=total_rooms,
            vacant_rooms=int(room_count_row.vacant_rooms or 0),
            deposited_rooms=int(room_count_row.deposited_rooms or 0),
            rented_rooms=rented_rooms,
            maintenance_rooms=int(room_count_row.maintenance_rooms or 0),
            occupancy_rate_percent=occupancy_rate_percent,
            active_leases=active_leases,
            overdue_invoices=int(overdue_row.overdue_invoices or 0),
            overdue_amount=Decimal(overdue_row.overdue_amount or 0),
            paid_revenue_current_month=Decimal(paid_revenue_current_month or 0),
            generated_at=now,
        )

    def fetch_room_status_overview(
        self,
        *,
        tenant_id: int,
        branch_id: int | None,
        area_id: int | None,
        building_id: int | None,
        include_rooms: bool,
        room_limit: int,
    ) -> RoomStatusOverviewOutput:
        now = datetime.now(timezone.utc)

        room_scope = [
            Room.tenant_id == tenant_id,
            Room.deleted_at.is_(None),
        ]
        if branch_id is not None:
            room_scope.append(Room.branch_id == branch_id)
        if area_id is not None:
            room_scope.append(Room.area_id == area_id)
        if building_id is not None:
            room_scope.append(Room.building_id == building_id)

        summary_rows = self.db.execute(
            select(Room.current_status, func.count(Room.id))
            .where(*room_scope)
            .group_by(Room.current_status)
            .order_by(Room.current_status.asc())
        ).all()
        status_summary = [
            RoomStatusSummaryItem(status=_enum_to_str(status), count=int(count or 0))
            for status, count in summary_rows
        ]
        total_rooms = int(sum(item.count for item in status_summary))

        branch_rows = self.db.execute(
            select(
                Branch.id,
                Branch.name,
                func.count(Room.id).label("room_count"),
            )
            .outerjoin(
                Room,
                and_(
                    Room.branch_id == Branch.id,
                    Room.tenant_id == tenant_id,
                    Room.deleted_at.is_(None),
                ),
            )
            .where(
                Branch.tenant_id == tenant_id,
                Branch.deleted_at.is_(None),
            )
            .group_by(Branch.id, Branch.name)
            .order_by(Branch.name.asc(), Branch.id.asc())
        ).all()
        branches = [
            BranchOverviewItem(
                branch_id=int(row.id),
                branch_name=row.name,
                room_count=int(row.room_count or 0),
            )
            for row in branch_rows
        ]

        area_rows = self.db.execute(
            select(
                Area.id,
                Area.name,
                Area.branch_id,
                Branch.name.label("branch_name"),
                func.count(Room.id).label("room_count"),
            )
            .join(
                Branch,
                and_(
                    Branch.id == Area.branch_id,
                    Branch.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                Room,
                and_(
                    Room.area_id == Area.id,
                    Room.tenant_id == tenant_id,
                    Room.deleted_at.is_(None),
                ),
            )
            .where(
                Area.tenant_id == tenant_id,
                Area.deleted_at.is_(None),
            )
            .group_by(Area.id, Area.name, Area.branch_id, Branch.name)
            .order_by(Branch.name.asc(), Area.name.asc(), Area.id.asc())
        ).all()
        areas = [
            AreaOverviewItem(
                area_id=int(row.id),
                area_name=row.name,
                branch_id=int(row.branch_id),
                branch_name=row.branch_name,
                room_count=int(row.room_count or 0),
            )
            for row in area_rows
        ]

        building_rows = self.db.execute(
            select(
                Building.id,
                Building.name,
                Building.total_floors,
                Building.area_id,
                Area.name.label("area_name"),
                Area.branch_id,
                Branch.name.label("branch_name"),
                func.count(Room.id).label("room_count"),
            )
            .join(
                Area,
                and_(
                    Area.id == Building.area_id,
                    Area.deleted_at.is_(None),
                ),
            )
            .join(
                Branch,
                and_(
                    Branch.id == Area.branch_id,
                    Branch.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                Room,
                and_(
                    Room.building_id == Building.id,
                    Room.tenant_id == tenant_id,
                    Room.deleted_at.is_(None),
                ),
            )
            .where(
                Building.tenant_id == tenant_id,
                Building.deleted_at.is_(None),
            )
            .group_by(
                Building.id,
                Building.name,
                Building.total_floors,
                Building.area_id,
                Area.name,
                Area.branch_id,
                Branch.name,
            )
            .order_by(
                Branch.name.asc(),
                Area.name.asc(),
                Building.name.asc(),
                Building.id.asc(),
            )
        ).all()
        buildings = [
            BuildingOverviewItem(
                building_id=int(row.id),
                building_name=row.name,
                area_id=int(row.area_id),
                area_name=row.area_name,
                branch_id=int(row.branch_id),
                branch_name=row.branch_name,
                total_floors=int(row.total_floors or 0),
                room_count=int(row.room_count or 0),
            )
            for row in building_rows
        ]

        rooms: list[RoomStatusRoomItem] = []
        if include_rooms:
            room_rows = self.db.execute(
                select(
                    Room.id,
                    Room.code,
                    Room.floor_number,
                    Room.current_status,
                    Room.branch_id,
                    Branch.name.label("branch_name"),
                    Room.area_id,
                    Area.name.label("area_name"),
                    Room.building_id,
                    Building.name.label("building_name"),
                )
                .join(Branch, Branch.id == Room.branch_id)
                .join(Area, Area.id == Room.area_id)
                .join(Building, Building.id == Room.building_id)
                .where(
                    *room_scope,
                    Branch.deleted_at.is_(None),
                    Area.deleted_at.is_(None),
                    Building.deleted_at.is_(None),
                )
                .order_by(Room.code.asc(), Room.id.asc())
                .limit(max(1, min(room_limit, 500)))
            ).all()
            rooms = [
                RoomStatusRoomItem(
                    room_id=int(row.id),
                    room_code=row.code,
                    floor_number=int(row.floor_number),
                    status=_enum_to_str(row.current_status),
                    branch_id=int(row.branch_id),
                    branch_name=row.branch_name,
                    area_id=int(row.area_id),
                    area_name=row.area_name,
                    building_id=int(row.building_id),
                    building_name=row.building_name,
                )
                for row in room_rows
            ]

        return RoomStatusOverviewOutput(
            total_rooms=total_rooms,
            status_summary=status_summary,
            branches=branches,
            areas=areas,
            buildings=buildings,
            rooms=rooms,
            generated_at=now,
        )

    def fetch_team_members(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        team_limit: int,
        member_limit: int,
    ) -> TeamMembersOutput:
        now = datetime.now(timezone.utc)
        team_ids = list(
            self.db.scalars(
                select(TeamMember.team_id)
                .join(Team, Team.id == TeamMember.team_id)
                .where(
                    TeamMember.user_id == user_id,
                    TeamMember.deleted_at.is_(None),
                    TeamMember.tenant_id == tenant_id,
                    Team.tenant_id == tenant_id,
                    Team.deleted_at.is_(None),
                    Team.is_active.is_(True),
                )
                .order_by(TeamMember.team_id.asc())
            ).all()
        )
        scoped_team_ids = sorted({int(item) for item in team_ids})
        if team_id is not None:
            if team_id not in scoped_team_ids:
                return TeamMembersOutput(total_teams=0, items=[], generated_at=now)
            scoped_team_ids = [team_id]

        if not scoped_team_ids:
            return TeamMembersOutput(total_teams=0, items=[], generated_at=now)

        teams = list(
            self.db.scalars(
                select(Team)
                .where(
                    Team.id.in_(scoped_team_ids),
                    Team.tenant_id == tenant_id,
                    Team.deleted_at.is_(None),
                    Team.is_active.is_(True),
                )
                .order_by(Team.id.asc())
                .limit(max(1, min(team_limit, 50)))
            ).all()
        )

        items: list[TeamInfo] = []
        for team in teams:
            member_count = int(
                self.db.scalar(
                    select(func.count(TeamMember.id)).where(
                        TeamMember.team_id == team.id,
                        TeamMember.deleted_at.is_(None),
                    )
                )
                or 0
            )
            member_rows = self.db.execute(
                select(TeamMember, User, Role.name.label("rbac_role_name"))
                .join(User, User.id == TeamMember.user_id)
                .outerjoin(
                    Role,
                    and_(
                        Role.id == TeamMember.rbac_role_id,
                        Role.deleted_at.is_(None),
                    ),
                )
                .where(
                    TeamMember.team_id == team.id,
                    TeamMember.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
                .order_by(TeamMember.id.asc())
                .limit(max(1, min(member_limit, 500)))
            ).all()
            members = [
                TeamMemberInfo(
                    user_id=int(user.id),
                    full_name=user.full_name,
                    email=user.email,
                    avatar_url=user.avatar_url,
                    member_role=_enum_to_str(team_member.member_role),
                    rbac_role_name=rbac_role_name,
                )
                for team_member, user, rbac_role_name in member_rows
            ]
            items.append(
                TeamInfo(
                    team_id=int(team.id),
                    team_name=team.name,
                    description=team.description,
                    owner_user_id=int(team.owner_user_id),
                    member_count=member_count,
                    members=members,
                )
            )

        return TeamMembersOutput(
            total_teams=len(items),
            items=items,
            generated_at=now,
        )

    def fetch_overdue_invoices(
        self, *, tenant_id: int, limit: int, min_days_overdue: int
    ) -> OverdueInvoicesOutput:
        now = datetime.now(timezone.utc)
        rows = self.db.execute(
            select(
                Invoice.id,
                Invoice.period_month,
                Room.code.label("room_code"),
                Renter.full_name.label("renter_name"),
                Renter.phone.label("renter_phone"),
                Invoice.due_date,
                Invoice.total_amount,
                Invoice.paid_amount,
                Invoice.status,
            )
            .join(Room, Room.id == Invoice.room_id)
            .join(Renter, Renter.id == Invoice.renter_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.deleted_at.is_(None),
                Invoice.due_date < now,
                Invoice.total_amount > Invoice.paid_amount,
                Invoice.status.in_(
                    [
                        InvoiceStatusEnum.UNPAID,
                        InvoiceStatusEnum.PARTIAL,
                        InvoiceStatusEnum.OVERDUE,
                    ]
                ),
                Room.deleted_at.is_(None),
                Renter.deleted_at.is_(None),
            )
            .order_by(Invoice.due_date.asc(), Invoice.id.asc())
            .limit(limit)
        ).all()

        items: list[OverdueInvoiceItem] = []
        for row in rows:
            due_date = row.due_date
            days_overdue = max((now.date() - due_date.date()).days, 0)
            if days_overdue < min_days_overdue:
                continue
            total_amount = Decimal(row.total_amount or 0)
            paid_amount = Decimal(row.paid_amount or 0)
            outstanding = total_amount - paid_amount
            items.append(
                OverdueInvoiceItem(
                    invoice_id=int(row.id),
                    period_month=row.period_month,
                    room_code=row.room_code,
                    renter_name=row.renter_name,
                    renter_phone=row.renter_phone,
                    due_date=due_date,
                    days_overdue=days_overdue,
                    total_amount=total_amount,
                    paid_amount=paid_amount,
                    outstanding_amount=outstanding,
                    status=row.status.value
                    if hasattr(row.status, "value")
                    else str(row.status),
                )
            )

        return OverdueInvoicesOutput(
            total_items=len(items),
            items=items,
            generated_at=now,
        )

    def fetch_invoice_installments(
        self,
        *,
        tenant_id: int,
        query: str,
        lease_limit: int,
        installment_limit: int,
    ) -> InvoiceInstallmentsOutput:
        now = datetime.now(timezone.utc)
        normalized_query = (query or "").strip()
        if not normalized_query:
            return InvoiceInstallmentsOutput(
                total_matches=0, items=[], generated_at=now
            )

        keyword = f"%{normalized_query}%"
        lease_id_from_query: int | None = None
        if normalized_query.isdigit():
            lease_id_from_query = int(normalized_query)
        elif (
            normalized_query.upper().startswith("HD-")
            and normalized_query[3:].isdigit()
        ):
            lease_id_from_query = int(normalized_query[3:])

        search_conditions = [
            Renter.full_name.ilike(keyword),
            Renter.phone.ilike(keyword),
            Renter.email.ilike(keyword),
            Room.code.ilike(keyword),
            cast(Lease.id, String).ilike(keyword),
        ]
        if lease_id_from_query is not None:
            search_conditions.append(Lease.id == lease_id_from_query)

        lease_rows = self.db.execute(
            select(Lease, Renter, Room)
            .join(Renter, Renter.id == Lease.renter_id)
            .join(Room, Room.id == Lease.room_id)
            .where(
                Lease.tenant_id == tenant_id,
                Lease.deleted_at.is_(None),
                Renter.deleted_at.is_(None),
                Room.deleted_at.is_(None),
                or_(*search_conditions),
            )
            .order_by(Lease.created_at.desc(), Lease.id.desc())
            .limit(max(1, min(lease_limit, 50)))
        ).all()

        results: list[LeaseInstallmentInfo] = []
        for lease, renter, room in lease_rows:
            invoices = list(
                self.db.scalars(
                    select(Invoice)
                    .where(
                        Invoice.tenant_id == tenant_id,
                        Invoice.lease_id == lease.id,
                        Invoice.deleted_at.is_(None),
                    )
                    .order_by(
                        Invoice.installment_no.asc(),
                        Invoice.due_date.asc(),
                        Invoice.id.asc(),
                    )
                    .limit(max(1, min(installment_limit, 120)))
                ).all()
            )
            installments = [
                InstallmentInfo(
                    invoice_id=int(invoice.id),
                    period_month=invoice.period_month,
                    installment_no=invoice.installment_no,
                    installment_total=invoice.installment_total,
                    due_date=invoice.due_date,
                    status=_enum_to_str(invoice.status),
                    total_amount=Decimal(invoice.total_amount or 0),
                    paid_amount=Decimal(invoice.paid_amount or 0),
                    outstanding_amount=Decimal(invoice.total_amount or 0)
                    - Decimal(invoice.paid_amount or 0),
                )
                for invoice in invoices
            ]
            results.append(
                LeaseInstallmentInfo(
                    lease_id=int(lease.id),
                    lease_code=f"HD-{lease.id}",
                    lease_status=_enum_to_str(lease.status),
                    renter_id=int(renter.id),
                    renter_name=renter.full_name,
                    renter_phone=renter.phone,
                    room_id=int(room.id),
                    room_code=room.code,
                    installments=installments,
                )
            )

        return InvoiceInstallmentsOutput(
            total_matches=len(results),
            items=results,
            generated_at=now,
        )

    def search_customers(
        self, *, tenant_id: int, query: str, limit: int
    ) -> SearchCustomersOutput:
        now = datetime.now(timezone.utc)
        normalized = (query or "").strip()
        if not normalized:
            return SearchCustomersOutput(total_items=0, items=[], generated_at=now)

        keyword = f"%{normalized}%"
        rows = self.db.execute(
            select(
                Renter.id,
                Renter.full_name,
                Renter.phone,
                Renter.email,
            )
            .where(
                Renter.tenant_id == tenant_id,
                Renter.deleted_at.is_(None),
                or_(
                    Renter.full_name.ilike(keyword),
                    Renter.phone.ilike(keyword),
                    Renter.email.ilike(keyword),
                    cast(Renter.id, String).ilike(keyword),
                ),
            )
            .order_by(Renter.full_name.asc(), Renter.id.asc())
            .limit(max(1, min(limit, 100)))
        ).all()

        items: list[CustomerSearchItem] = []
        for row in rows:
            renter_id = int(row.id)
            total_lease_count = int(
                self.db.scalar(
                    select(func.count(Lease.id)).where(
                        Lease.tenant_id == tenant_id,
                        Lease.renter_id == renter_id,
                        Lease.deleted_at.is_(None),
                    )
                )
                or 0
            )
            active_lease_count = int(
                self.db.scalar(
                    select(func.count(Lease.id)).where(
                        Lease.tenant_id == tenant_id,
                        Lease.renter_id == renter_id,
                        Lease.deleted_at.is_(None),
                        Lease.status == LeaseStatusEnum.ACTIVE,
                    )
                )
                or 0
            )
            outstanding_amount = self.db.scalar(
                select(
                    func.coalesce(
                        func.sum(Invoice.total_amount - Invoice.paid_amount), 0
                    )
                ).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.renter_id == renter_id,
                    Invoice.deleted_at.is_(None),
                    Invoice.total_amount > Invoice.paid_amount,
                    Invoice.status.in_(
                        [
                            InvoiceStatusEnum.UNPAID,
                            InvoiceStatusEnum.PARTIAL,
                            InvoiceStatusEnum.OVERDUE,
                        ]
                    ),
                )
            ) or Decimal("0")
            items.append(
                CustomerSearchItem(
                    renter_id=renter_id,
                    full_name=row.full_name,
                    phone=row.phone,
                    email=row.email,
                    active_lease_count=active_lease_count,
                    total_lease_count=total_lease_count,
                    outstanding_amount=Decimal(outstanding_amount or 0),
                )
            )

        return SearchCustomersOutput(
            total_items=len(items),
            items=items,
            generated_at=now,
        )

    def fetch_contracts(
        self,
        *,
        tenant_id: int,
        query: str | None,
        customer_id: int | None,
        only_active: bool,
        limit: int,
    ) -> ContractLookupOutput:
        now = datetime.now(timezone.utc)
        conditions = [
            Lease.tenant_id == tenant_id,
            Lease.deleted_at.is_(None),
            Renter.deleted_at.is_(None),
            Room.deleted_at.is_(None),
            Branch.deleted_at.is_(None),
        ]

        if customer_id is not None:
            conditions.append(Lease.renter_id == customer_id)

        if only_active:
            conditions.append(Lease.status == LeaseStatusEnum.ACTIVE)

        normalized = (query or "").strip()
        if normalized:
            keyword = f"%{normalized}%"
            lease_id_from_query: int | None = None
            if normalized.isdigit():
                lease_id_from_query = int(normalized)
            elif normalized.upper().startswith("HD-") and normalized[3:].isdigit():
                lease_id_from_query = int(normalized[3:])

            search_conditions = [
                Renter.full_name.ilike(keyword),
                Renter.phone.ilike(keyword),
                Renter.email.ilike(keyword),
                Room.code.ilike(keyword),
                cast(Lease.id, String).ilike(keyword),
            ]
            if lease_id_from_query is not None:
                search_conditions.append(Lease.id == lease_id_from_query)
            conditions.append(or_(*search_conditions))

        rows = self.db.execute(
            select(
                Lease,
                Renter,
                Room,
                Branch.name.label("branch_name"),
            )
            .join(Renter, Renter.id == Lease.renter_id)
            .join(Room, Room.id == Lease.room_id)
            .join(Branch, Branch.id == Lease.branch_id)
            .where(*conditions)
            .order_by(Lease.created_at.desc(), Lease.id.desc())
            .limit(max(1, min(limit, 100)))
        ).all()

        items: list[ContractLookupItem] = []
        for lease, renter, room, branch_name in rows:
            outstanding_amount = self.db.scalar(
                select(
                    func.coalesce(
                        func.sum(Invoice.total_amount - Invoice.paid_amount), 0
                    )
                ).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.lease_id == lease.id,
                    Invoice.deleted_at.is_(None),
                    Invoice.total_amount > Invoice.paid_amount,
                    Invoice.status.in_(
                        [
                            InvoiceStatusEnum.UNPAID,
                            InvoiceStatusEnum.PARTIAL,
                            InvoiceStatusEnum.OVERDUE,
                        ]
                    ),
                )
            ) or Decimal("0")
            items.append(
                ContractLookupItem(
                    lease_id=int(lease.id),
                    lease_code=f"HD-{lease.id}",
                    lease_status=_enum_to_str(lease.status),
                    renter_id=int(renter.id),
                    renter_name=renter.full_name,
                    renter_phone=renter.phone,
                    room_id=int(room.id),
                    room_code=room.code,
                    branch_id=int(lease.branch_id),
                    branch_name=branch_name,
                    start_date=lease.start_date,
                    end_date=lease.end_date,
                    handover_at=lease.handover_at,
                    rent_price=Decimal(lease.rent_price or 0),
                    security_deposit_amount=Decimal(lease.security_deposit_amount or 0),
                    outstanding_amount=Decimal(outstanding_amount or 0),
                )
            )

        return ContractLookupOutput(
            total_items=len(items),
            items=items,
            generated_at=now,
        )

    def dispatch_team_notification(
        self,
        *,
        tenant_id: int,
        user_id: int,
        team_id: int | None,
        title: str,
        body: str,
        recipient_user_ids: list[int],
        dry_run: bool,
    ) -> TeamNotificationOutput:
        from app.modules.collaboration.schemas import NotificationCreateRequest
        from app.modules.collaboration.service import create_notification

        now = datetime.now(timezone.utc)
        current_user = self.db.scalar(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        if current_user is None:
            raise ValueError("Không tìm thấy người dùng thực hiện thông báo")

        team_ids = sorted(
            {
                int(item)
                for item in self.db.scalars(
                    select(TeamMember.team_id)
                    .join(Team, Team.id == TeamMember.team_id)
                    .where(
                        TeamMember.user_id == user_id,
                        TeamMember.deleted_at.is_(None),
                        TeamMember.tenant_id == tenant_id,
                        Team.deleted_at.is_(None),
                        Team.is_active.is_(True),
                    )
                ).all()
            }
        )
        if not team_ids:
            raise ValueError("Bạn chưa thuộc team nào để gửi thông báo")

        resolved_team_id = team_id
        if resolved_team_id is None:
            if len(team_ids) == 1:
                resolved_team_id = team_ids[0]
            else:
                raise ValueError(
                    "Vui lòng chỉ định team_id vì bạn đang thuộc nhiều team"
                )
        if resolved_team_id not in team_ids:
            raise ValueError("Bạn không có quyền gửi thông báo cho team này")

        team_member_ids = sorted(
            {
                int(item)
                for item in self.db.scalars(
                    select(TeamMember.user_id)
                    .join(User, User.id == TeamMember.user_id)
                    .where(
                        TeamMember.team_id == resolved_team_id,
                        TeamMember.deleted_at.is_(None),
                        User.deleted_at.is_(None),
                        User.is_active.is_(True),
                    )
                ).all()
            }
        )
        if not team_member_ids:
            raise ValueError(
                "Team hiện tại không có thành viên hợp lệ để nhận thông báo"
            )

        requested = sorted(
            {
                int(item)
                for item in recipient_user_ids
                if isinstance(item, int) and item > 0
            }
        )
        if requested:
            invalid = [item for item in requested if item not in team_member_ids]
            if invalid:
                invalid_text = ", ".join(str(item) for item in invalid)
                raise ValueError(
                    f"Một số người nhận không thuộc team hiện tại: {invalid_text}"
                )
            recipients = requested
            notification_type = "SELECTED_USERS"
        else:
            recipients = team_member_ids
            notification_type = "ALL_USERS"

        clean_title = (title or "").strip()
        clean_body = (body or "").strip()
        if not clean_title or not clean_body:
            raise ValueError("Thông báo phải có tiêu đề và nội dung")

        if dry_run:
            return TeamNotificationOutput(
                sent=False,
                draft_only=True,
                notification_id=None,
                team_id=int(resolved_team_id),
                notification_type=notification_type,
                title=clean_title,
                body=clean_body,
                total_recipients=len(recipients),
                recipient_user_ids=recipients,
                generated_at=now,
            )

        payload = NotificationCreateRequest(
            title=clean_title,
            body=clean_body,
            notification_type=notification_type,
            team_id=int(resolved_team_id),
            recipient_user_ids=(
                recipients if notification_type == "SELECTED_USERS" else []
            ),
        )
        created = create_notification(self.db, current_user, payload)
        return TeamNotificationOutput(
            sent=True,
            draft_only=False,
            notification_id=int(created.id),
            team_id=int(resolved_team_id),
            notification_type=notification_type,
            title=clean_title,
            body=clean_body,
            total_recipients=len(recipients),
            recipient_user_ids=recipients,
            generated_at=created.published_at,
        )

    def fetch_internal_knowledge(
        self, *, tenant_id: int, query: str, limit: int
    ) -> SearchKnowledgeOutput:
        now = datetime.now(timezone.utc)
        keyword = f"%{query.strip()}%"
        hits: list[KnowledgeHit] = []

        doc_rows = self.db.execute(
            select(
                AgentKnowledgeDocument.id,
                AgentKnowledgeDocument.title,
                AgentKnowledgeDocument.content,
                AgentKnowledgeDocument.source_type,
                AgentKnowledgeDocument.source_ref,
                AgentKnowledgeDocument.tenant_id,
            )
            .where(
                AgentKnowledgeDocument.deleted_at.is_(None),
                AgentKnowledgeDocument.is_active.is_(True),
                or_(
                    AgentKnowledgeDocument.tenant_id == tenant_id,
                    AgentKnowledgeDocument.tenant_id.is_(None),
                ),
                or_(
                    AgentKnowledgeDocument.title.like(keyword),
                    AgentKnowledgeDocument.content.like(keyword),
                ),
            )
            .order_by(
                case((AgentKnowledgeDocument.tenant_id == tenant_id, 0), else_=1),
                AgentKnowledgeDocument.id.desc(),
            )
            .limit(limit)
        ).all()

        for row in doc_rows:
            snippet = _build_snippet(row.content, query=query)
            hits.append(
                KnowledgeHit(
                    source_type=row.source_type,
                    source_id=f"agent_knowledge_documents:{row.id}",
                    title=row.title,
                    snippet=snippet,
                    metadata={
                        "source_ref": row.source_ref,
                        "tenant_scope": "tenant"
                        if row.tenant_id == tenant_id
                        else "global",
                    },
                )
            )

        if len(hits) < limit:
            remaining = limit - len(hits)
            template_rows = self.db.execute(
                select(FormTemplate.id, FormTemplate.name, FormTemplate.content_html)
                .where(
                    FormTemplate.tenant_id == tenant_id,
                    FormTemplate.deleted_at.is_(None),
                    FormTemplate.is_active.is_(True),
                    or_(
                        FormTemplate.name.like(keyword),
                        FormTemplate.content_html.like(keyword),
                    ),
                )
                .order_by(FormTemplate.updated_at.desc(), FormTemplate.id.desc())
                .limit(remaining)
            ).all()
            for row in template_rows:
                hits.append(
                    KnowledgeHit(
                        source_type="form_template",
                        source_id=f"form_templates:{row.id}",
                        title=row.name,
                        snippet=_build_snippet(row.content_html, query=query),
                        metadata={},
                    )
                )

        if len(hits) < limit:
            remaining = limit - len(hits)
            landing_rows = self.db.execute(
                select(
                    LandingPageSection.id,
                    LandingPageSection.section_key,
                    LandingPageSection.title,
                    LandingPageSection.body_text,
                )
                .where(
                    LandingPageSection.deleted_at.is_(None),
                    LandingPageSection.is_published.is_(True),
                    or_(
                        LandingPageSection.title.like(keyword),
                        LandingPageSection.subtitle.like(keyword),
                        LandingPageSection.body_text.like(keyword),
                    ),
                )
                .order_by(
                    LandingPageSection.sort_order.asc(), LandingPageSection.id.asc()
                )
                .limit(remaining)
            ).all()
            for row in landing_rows:
                content = row.body_text or row.title or ""
                hits.append(
                    KnowledgeHit(
                        source_type="landing_page_section",
                        source_id=f"landing_page_sections:{row.id}",
                        title=row.title or row.section_key,
                        snippet=_build_snippet(content, query=query),
                        metadata={"section_key": row.section_key},
                    )
                )

        return SearchKnowledgeOutput(total_hits=len(hits), items=hits, generated_at=now)


def _build_snippet(content: str | None, *, query: str, max_len: int = 220) -> str:
    text = (content or "").strip()
    if not text:
        return "Không có nội dung"
    lowered = text.lower()
    marker = query.strip().lower()
    if not marker:
        return text[:max_len]
    pos = lowered.find(marker)
    if pos < 0:
        return text[:max_len]
    start = max(pos - 80, 0)
    end = min(pos + len(marker) + 120, len(text))
    snippet = text[start:end]
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(text):
        snippet = f"{snippet}..."
    return snippet
