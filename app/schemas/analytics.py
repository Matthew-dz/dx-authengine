from typing import Dict, Any, Optional, List
from pydantic import BaseModel, ConfigDict


class DashboardStatsResponse(BaseModel):
    """
    Schema Dashboard tổng hợp theo BFF Pattern (Bước 5.3), bao quát 4 trụ cột H-P-D-I:
    - human: Quản trị nhân sự & tài khoản người dùng
    - process: Tiến trình nghiệp vụ hoàn tiền
    - data: Dữ liệu đơn hàng & tài chính
    - intelligence: Trợ lý AI và giám sát hành vi
    """
    human: Dict[str, Any]
    process: Dict[str, Any]
    data: Dict[str, Any]
    intelligence: Dict[str, Any]

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
