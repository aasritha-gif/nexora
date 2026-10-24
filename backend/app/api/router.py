from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai,
    analytics,
    auth,
    engagement,
    ingestion,
    payments,
    resources,
    search,
    taxonomy,
    users,
    youtube,
)

# Mounted at /api. Health endpoints live at the root (see app.main) so container
# orchestrators can probe them without traversing the versioned surface.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(resources.router)
api_router.include_router(taxonomy.router)
api_router.include_router(search.router)
api_router.include_router(engagement.router)
api_router.include_router(ai.router)
api_router.include_router(youtube.router)
api_router.include_router(payments.router)
api_router.include_router(analytics.router)
api_router.include_router(ingestion.router)
api_router.include_router(admin.router)
