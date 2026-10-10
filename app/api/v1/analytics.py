from typing import Optional, List, Union
from fastapi import APIRouter, Depends, Query

from app import models
from app.security import get_current_user
from app.services.analytics_service import AnalyticsService
from app.schemas import OverviewStatsResponse, EmployeePerformanceResponse, DashboardStatsResponse
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=StandardResponse[DashboardStatsResponse])
def get_dashboard(
    current_user: models.Employee = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """
    API Dashboard tổng hợp theo BFF Pattern (Bước 5.3), bao quát 4 trụ cột H-P-D-I:
    - human: Quản trị nhân sự & tài khoản người dùng
    - process: Tiến trình nghiệp vụ hoàn tiền
    - data: Dữ liệu đơn hàng & tài chính
    - intelligence: Trợ lý AI và giám sát hành vi
    Tích hợp phân quyền dữ liệu sâu (Deep RBAC): Admin xem toàn bộ, Employee chỉ xem dữ liệu của mình.
    """
    dashboard_data = service.get_dashboard_data(current_user=current_user)
    return StandardResponse(
        success=True,
        message="Lấy dữ liệu Dashboard tổng hợp thành công",
        data=dashboard_data
    )


@router.get("/overview", response_model=StandardResponse[OverviewStatsResponse])
def get_overview_analytics(
    from_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    from_query: Optional[str] = Query(None, alias="from"),
    to_query: Optional[str] = Query(None, alias="to"),
    current_user: models.Employee = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """
    API lấy số liệu thống kê tổng quan (KPIs) toàn hệ thống.
    BẢO MẬT: Bắt buộc đăng nhập và chỉ cho phép Role Admin / Manager.
    Tự động khắc phục The Midnight Bug và tối ưu DB Aggregation (tránh N+1).
    """
    actual_from = from_query or from_date
    actual_to = to_query or to_date
    res = service.get_overview(
        current_user=current_user,
        from_date=actual_from,
        to_date=actual_to
    )
    return StandardResponse(
        success=True,
        message="Lấy số liệu thống kê tổng quan thành công",
        data=res
    )


@router.get(
    "/employee-performance",
    response_model=Union[EmployeePerformanceResponse, List[EmployeePerformanceResponse]]
)
def get_employee_performance_list(
    employee_id: Optional[int] = Query(None, description="ID nhân viên cần xem (bỏ trống để lấy toàn bộ)"),
    from_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    from_query: Optional[str] = Query(None, alias="from"),
    to_query: Optional[str] = Query(None, alias="to"),
    current_user: models.Employee = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """
    API lấy hiệu suất nhân viên.
    Nếu truyền employee_id: Trả về chi tiết hiệu suất của nhân viên đó.
    Nếu không truyền employee_id: Trả về danh sách hiệu suất của tất cả nhân viên.
    """
    actual_from = from_query or from_date
    actual_to = to_query or to_date

    if employee_id is not None:
        return service.get_employee_performance(
            employee_id=employee_id,
            current_user=current_user,
            from_date=actual_from,
            to_date=actual_to
        )
    return service.get_all_employees_performance(
        current_user=current_user,
        from_date=actual_from,
        to_date=actual_to
    )


@router.get(
    "/employee-performance/{employee_id}",
    response_model=StandardResponse[EmployeePerformanceResponse]
)
def get_single_employee_performance(
    employee_id: int,
    from_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    from_query: Optional[str] = Query(None, alias="from"),
    to_query: Optional[str] = Query(None, alias="to"),
    current_user: models.Employee = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """
    API lấy hiệu suất chi tiết của một nhân viên theo ID cụ thể.
    BẢO MẬT: Bắt buộc đăng nhập và chỉ cho phép Role Admin / Manager.
    """
    actual_from = from_query or from_date
    actual_to = to_query or to_date
    perf = service.get_employee_performance(
        employee_id=employee_id,
        current_user=current_user,
        from_date=actual_from,
        to_date=actual_to
    )
    return StandardResponse(
        success=True,
        message=f"Lấy hiệu suất nhân viên #{employee_id} thành công",
        data=perf
    )
