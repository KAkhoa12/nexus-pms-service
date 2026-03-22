from fastapi import APIRouter

from app.modules.agents.routes import router as agents_router
from app.modules.areas.routes import router as areas_router
from app.modules.auth.routes import router as auth_router
from app.modules.branches.routes import router as branches_router
from app.modules.buildings.routes import router as buildings_router
from app.modules.collaboration.routes import router as collaboration_router
from app.modules.customer_appointments.routes import (
    router as customer_appointments_router,
)
from app.modules.customers.routes import router as customers_router
from app.modules.deposits.routes import router as deposits_router
from app.modules.developer_portal.routes import router as developer_portal_router
from app.modules.form_templates.routes import router as form_templates_router
from app.modules.invoices.routes import router as invoices_router
from app.modules.leases.routes import router as leases_router
from app.modules.materials_assets.routes import router as materials_assets_router
from app.modules.renter_members.routes import router as renter_members_router
from app.modules.renters.routes import router as renters_router
from app.modules.room_types.routes import router as room_types_router
from app.modules.rooms.routes import router as rooms_router
from app.modules.service_fees.routes import router as service_fees_router
from app.modules.teams.routes import router as teams_router
from app.modules.user_permissions.routes import router as user_permissions_router
from app.modules.users.routes import router as users_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(agents_router, prefix="/agents", tags=["agents"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(
    user_permissions_router,
    prefix="/user-permissions",
    tags=["user-permissions"],
)
router.include_router(areas_router, prefix="/areas", tags=["areas"])
router.include_router(branches_router, prefix="/branches", tags=["branches"])
router.include_router(buildings_router, prefix="/buildings", tags=["buildings"])
router.include_router(
    collaboration_router,
    prefix="/collaboration",
    tags=["collaboration"],
)
router.include_router(
    customer_appointments_router,
    prefix="/customer-appointments",
    tags=["customer-appointments"],
)
router.include_router(customers_router, prefix="/customers", tags=["customers"])
router.include_router(developer_portal_router, prefix="/developer", tags=["developer"])
router.include_router(deposits_router, prefix="/deposits", tags=["deposits"])
router.include_router(
    form_templates_router, prefix="/form-templates", tags=["form-templates"]
)
router.include_router(room_types_router, prefix="/room-types", tags=["room-types"])
router.include_router(rooms_router, prefix="/rooms", tags=["rooms"])
router.include_router(
    service_fees_router, prefix="/service-fees", tags=["service-fees"]
)
router.include_router(renters_router, prefix="/renters", tags=["renters"])
router.include_router(
    renter_members_router, prefix="/renter-members", tags=["renter-members"]
)
router.include_router(invoices_router, prefix="/invoices", tags=["invoices"])
router.include_router(leases_router, prefix="/leases", tags=["leases"])
router.include_router(
    materials_assets_router,
    prefix="/materials-assets",
    tags=["materials-assets"],
)
router.include_router(teams_router, prefix="/teams", tags=["teams"])
