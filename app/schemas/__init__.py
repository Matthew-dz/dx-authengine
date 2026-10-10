from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models import RefundState
from app.schemas.common import StandardResponse
from app.schemas.employee import (
    EmployeeResponse,
    EmployeeProfileResponse,
    CustomerResponse,
    EmployeeUpdate,
    EmployeePerformanceResponse
)


class RefundRequestCreate(BaseModel):
    order_id: int
    reason: Optional[str] = None
    amount: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class RefundStateUpdate(BaseModel):
    status: RefundState
    notes: Optional[str] = None


class RefundActionPayload(BaseModel):
    notes: Optional[str] = None


class RefundRequestResponse(BaseModel):
    id: int
    order_id: int
    employee_id: Optional[int] = None
    reason: Optional[str] = None
    status: RefundState
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OverviewStatsResponse(BaseModel):
    """Schema thống kê tổng quan (KPIs) toàn hệ thống."""
    total_orders: int
    total_refunds: int
    total_refund_amount: float
    pending: int
    approved: int
    rejected: int
    processing: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


from app.schemas.analytics import DashboardStatsResponse
