from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models import RefundState
from app.schemas.common import StandardResponse

class EmployeeResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    position: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class EmployeeProfileResponse(BaseModel):
    """Schema bảo mật cho API /me — KHÔNG bao giờ trả về password hay cccd."""
    id: int
    username: str
    full_name: str
    position: Optional[str] = None
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerResponse(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


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


class EmployeePerformanceResponse(BaseModel):
    """Schema thống kê hiệu suất xử lý đơn của nhân viên."""
    employee_name: str
    processed: int
    approved: int
    rejected: int
    average_processing_time_minutes: float
    employee_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


from app.schemas.analytics import DashboardStatsResponse
