from datetime import datetime, date, time
from typing import List, Optional, Tuple, Union, Any
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.repositories.analytics_repository import AnalyticsRepository
from app.agent import enforcer, Subject, Resource
from app.schemas import OverviewStatsResponse, EmployeePerformanceResponse, DashboardStatsResponse


class AnalyticsService:
    """
    Business Logic Layer cho module Data Analytics.
    Đảm bảo:
    - Kiểm soát phân quyền Casbin nghiêm ngặt (chỉ Role Admin và Manager).
    - Xử lý triệt để Lỗ hổng 'Nửa đêm' (The Midnight Bug) khi lọc theo khoảng thời gian.
    - Xử lý Khuyết điểm tính toán thời gian (Time Math Trap) qua Python datetime diff.
    """
    def __init__(
        self,
        repo: AnalyticsRepository = Depends(),
        db: Session = Depends(get_db)
    ):
        self.repo = repo
        self.db = db

    def check_permission(self, current_user: models.Employee) -> None:
        """
        BẢO MẬT CRITICAL: Kiểm tra quyền Casbin.
        Chỉ Role Admin hoặc Manager mới được phép truy cập module Analytics.
        """
        if not current_user:
            raise HTTPException(status_code=401, detail="Yêu cầu đăng nhập")

        allowed = enforcer.enforce(
            Subject(current_user.username, current_user.role),
            Resource("analytics"),
            "read"
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="Không có quyền truy cập dữ liệu phân tích. Chỉ Quản lý (Manager) hoặc Quản trị viên (Admin) mới có quyền."
            )

    @staticmethod
    def normalize_date_range(
        from_date: Optional[Union[datetime, date, str]],
        to_date: Optional[Union[datetime, date, str]]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Xử lý triệt để Lỗ hổng 'Nửa đêm' (The Midnight Bug):
        Nếu to_date được truyền vào (dưới dạng date, string hoặc datetime tại mốc 00:00:00),
        tự động đẩy to_date đến cuối ngày (23:59:59.999999) để không làm mất các giao dịch xảy ra trong ngày cuối.
        """
        parsed_from: Optional[datetime] = None
        parsed_to: Optional[datetime] = None

        # 1. Chuẩn hóa from_date
        if from_date is not None:
            if isinstance(from_date, str):
                from_str = from_date.strip()
                if from_str:
                    try:
                        parsed_from = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
                    except ValueError:
                        parsed_from = datetime.strptime(from_str, "%Y-%m-%d")
            elif isinstance(from_date, datetime):
                parsed_from = from_date
            elif isinstance(from_date, date):
                parsed_from = datetime.combine(from_date, time.min)

        # 2. Chuẩn hóa to_date & xử lý Midnight Bug
        if to_date is not None:
            if isinstance(to_date, str):
                to_str = to_date.strip()
                if to_str:
                    try:
                        dt = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
                    except ValueError:
                        dt = datetime.strptime(to_str, "%Y-%m-%d")
                    # Nếu không có giờ hoặc là 00:00:00, đẩy về 23:59:59.999999
                    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
                        parsed_to = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    else:
                        parsed_to = dt
            elif isinstance(to_date, datetime):
                if to_date.hour == 0 and to_date.minute == 0 and to_date.second == 0 and to_date.microsecond == 0:
                    parsed_to = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    parsed_to = to_date
            elif isinstance(to_date, date):
                parsed_to = datetime.combine(to_date, time(23, 59, 59, 999999))

        return parsed_from, parsed_to

    @staticmethod
    def calculate_average_processing_time(time_pairs: List[Tuple[Any, Any]]) -> float:
        """
        Khuyết điểm tính toán thời gian (Time Math Trap):
        Dùng Python duyệt qua mảng (created_at, processed_at) do repository trả về,
        tính chênh lệch thời gian ra số phút (minutes), sau đó lấy trung bình cộng.
        Tương thích 100% với cả SQLite và PostgreSQL.
        """
        if not time_pairs:
            return 0.0

        total_seconds = 0.0
        valid_count = 0

        for created_at, processed_at in time_pairs:
            if not created_at or not processed_at:
                continue

            # Chuyển đổi an toàn nếu DB lưu dưới dạng ISO string (như SQLite)
            c_dt = created_at
            if isinstance(c_dt, str):
                try:
                    c_dt = datetime.fromisoformat(c_dt.replace("Z", "+00:00"))
                except Exception:
                    continue

            p_dt = processed_at
            if isinstance(p_dt, str):
                try:
                    p_dt = datetime.fromisoformat(p_dt.replace("Z", "+00:00"))
                except Exception:
                    continue

            diff = (p_dt - c_dt).total_seconds()
            if diff >= 0:
                total_seconds += diff
                valid_count += 1

        if valid_count == 0:
            return 0.0

        average_minutes = (total_seconds / valid_count) / 60.0
        return round(average_minutes, 2)

    def get_overview(
        self,
        current_user: models.Employee,
        from_date: Optional[Union[datetime, date, str]] = None,
        to_date: Optional[Union[datetime, date, str]] = None
    ) -> OverviewStatsResponse:
        """Lấy dữ liệu thống kê tổng quan (gọi get_filtered_stats với xử lý phân quyền và Midnight Bug)."""
        return self.get_filtered_stats(current_user=current_user, from_date=from_date, to_date=to_date)

    def get_filtered_stats(
        self,
        current_user: models.Employee,
        from_date: Optional[Union[datetime, date, str]] = None,
        to_date: Optional[Union[datetime, date, str]] = None
    ) -> OverviewStatsResponse:
        """
        Nghiệp vụ thống kê tổng quan:
        1. Kiểm tra quyền Casbin (chỉ Admin/Manager).
        2. Chuẩn hóa ngày tháng và tự động khắc phục Midnight Bug.
        3. Gọi repository thực thi SQL Aggregation.
        """
        self.check_permission(current_user)
        n_from, n_to = self.normalize_date_range(from_date, to_date)
        raw_stats = self.repo.get_overview_stats(db=self.db, from_date=n_from, to_date=n_to)
        return OverviewStatsResponse(**raw_stats)

    def get_employee_performance(
        self,
        employee_id: int,
        current_user: models.Employee,
        from_date: Optional[Union[datetime, date, str]] = None,
        to_date: Optional[Union[datetime, date, str]] = None
    ) -> EmployeePerformanceResponse:
        """
        Nghiệp vụ tính toán hiệu suất của một nhân viên cụ thể:
        1. Kiểm tra quyền Casbin.
        2. Chuẩn hóa ngày (khắc phục Midnight Bug).
        3. Truy vấn thống kê và timestamps từ repository.
        4. Tính toán thời gian xử lý trung bình (phút) bằng Python.
        """
        self.check_permission(current_user)
        n_from, n_to = self.normalize_date_range(from_date, to_date)

        employee, status_counts, time_pairs = self.repo.get_employee_performance(
            db=self.db,
            employee_id=employee_id,
            from_date=n_from,
            to_date=n_to
        )

        if not employee:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy nhân viên với ID {employee_id}")

        avg_time = self.calculate_average_processing_time(time_pairs)

        return EmployeePerformanceResponse(
            employee_id=employee.id,
            employee_name=employee.full_name or employee.username,
            processed=status_counts["processed"],
            approved=status_counts["approved"],
            rejected=status_counts["rejected"],
            average_processing_time_minutes=avg_time
        )

    def get_all_employees_performance(
        self,
        current_user: models.Employee,
        from_date: Optional[Union[datetime, date, str]] = None,
        to_date: Optional[Union[datetime, date, str]] = None
    ) -> List[EmployeePerformanceResponse]:
        """Lấy hiệu suất của tất cả nhân viên trong hệ thống."""
        self.check_permission(current_user)
        employees = self.repo.get_all_employees(db=self.db)
        results: List[EmployeePerformanceResponse] = []
        for emp in employees:
            perf = self.get_employee_performance(
                employee_id=emp.id,
                current_user=current_user,
                from_date=from_date,
                to_date=to_date
            )
            results.append(perf)
        return results

    def check_dashboard_permission(self, current_user: models.Employee) -> None:
        """Kiểm tra quyền truy cập Dashboard qua Casbin (dashboard:read hoặc analytics:read)."""
        if not current_user:
            raise HTTPException(status_code=401, detail="Yêu cầu đăng nhập")
        sub = Subject(current_user.username, current_user.role)
        enforcer.load_policy()
        has_perm = enforcer.enforce(sub, Resource("dashboard"), "read") or enforcer.enforce(sub, Resource("analytics"), "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail="Không có quyền truy cập Dashboard."
            )

    def get_dashboard_data(
        self,
        db_or_user: Any = None,
        current_user: Optional[models.Employee] = None
    ) -> DashboardStatsResponse:
        """
        Nghiệp vụ tổng hợp dữ liệu Dashboard BFF Pattern (4 trụ cột H-P-D-I).
        - Phân quyền dữ liệu sâu (Deep RBAC):
          + Role 'admin' hoặc 'manager': employee_id=None (truy xuất toàn bộ hệ thống).
          + Role 'employee' (hoặc staff_sales/sale): employee_id=current_user.id (chỉ truy xuất dữ liệu của mình).
        - Thu thập và tổng hợp 4 block: human, process, data, intelligence.
        """
        if isinstance(db_or_user, models.Employee):
            user = db_or_user
            session = self.db
        elif hasattr(db_or_user, "query"):
            session = db_or_user
            user = current_user
        else:
            session = self.db
            user = current_user or db_or_user

        self.check_dashboard_permission(user)

        # Phân quyền dữ liệu sâu (Deep RBAC):
        # Admin / Manager gọi Repo với employee_id=None (Lấy toàn bộ)
        # Employee gọi Repo với employee_id=current_user.id (Chỉ lấy của mình)
        if user.role in ["admin", "manager"]:
            target_employee_id = None
        else:
            target_employee_id = user.id

        human_stats = self.repo.get_human_stats(db=session)
        process_stats = self.repo.get_process_stats(db=session, employee_id=target_employee_id)
        data_stats = self.repo.get_data_stats(db=session, employee_id=target_employee_id)
        intel_stats = self.repo.get_intelligence_stats(db=session, employee_id=target_employee_id)

        return DashboardStatsResponse(
            human=human_stats,
            process=process_stats,
            data=data_stats,
            intelligence=intel_stats
        )
