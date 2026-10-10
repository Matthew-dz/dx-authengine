from fastapi import APIRouter

from app.api.v1 import (
    refunds,
    auth,
    employees,
    analytics,
    ai,
    orders,
    audit_logs,
    system
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(refunds.router)
api_v1_router.include_router(employees.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(orders.router)
api_v1_router.include_router(audit_logs.router)
api_v1_router.include_router(system.router)

__all__ = [
    "refunds",
    "auth",
    "employees",
    "analytics",
    "ai",
    "orders",
    "audit_logs",
    "system",
    "api_v1_router"
]
