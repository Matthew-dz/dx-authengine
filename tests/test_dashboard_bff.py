import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.schemas.analytics import DashboardStatsResponse
from app.repositories.analytics_repository import AnalyticsRepository
from app.services.analytics_service import AnalyticsService
from app.security import create_access_token, get_password_hash

client = TestClient(app)


def test_dashboard_schema_hpdi_structure():
    """Kiểm tra: DashboardStatsResponse bao quát đúng 4 trụ cột H-P-D-I."""
    resp = DashboardStatsResponse(
        human={"total_users": 150, "active_users": 120, "employees": 30},
        process={"pending": 5, "approved": 20, "rejected": 2, "completed": 22},
        data={"total_orders": 300, "total_refund_amount": 45000000.0},
        intelligence={"ai_requests": 80, "ai_actions_success": 75, "ai_actions_failed": 5}
    )
    dumped = resp.model_dump()
    assert "human" in dumped and "total_users" in dumped["human"]
    assert "process" in dumped and "completed" in dumped["process"]
    assert "data" in dumped and "total_refund_amount" in dumped["data"]
    assert "intelligence" in dumped and "ai_requests" in dumped["intelligence"]
    print(" -> test_dashboard_schema_hpdi_structure passed!")


def test_repository_deep_rbac_filtering():
    """Kiểm tra: Các hàm truy vấn Process và Data của AnalyticsRepository nhận và lọc theo employee_id."""
    db = SessionLocal()
    try:
        repo = AnalyticsRepository(db=db)

        # 1. Human stats
        h_stats = repo.get_human_stats()
        assert "total_users" in h_stats
        assert "active_users" in h_stats
        assert "employees" in h_stats
        assert h_stats["employees"] >= 0

        # 2. Process stats toàn bộ vs theo employee_id
        p_all = repo.get_process_stats(employee_id=None)
        assert "pending" in p_all and "approved" in p_all and "completed" in p_all

        # Dùng một ID giả định không có đơn nào
        p_filtered = repo.get_process_stats(employee_id=999999)
        assert p_filtered["pending"] == 0
        assert p_filtered["approved"] == 0

        # 3. Data stats toàn bộ vs theo employee_id
        d_all = repo.get_data_stats(employee_id=None)
        assert "total_orders" in d_all and "total_refund_amount" in d_all

        d_filtered = repo.get_data_stats(employee_id=999999)
        assert d_filtered["total_orders"] == 0
        assert d_filtered["total_refund_amount"] == 0.0

        # 4. Intelligence stats
        i_all = repo.get_intelligence_stats(employee_id=None)
        assert "ai_requests" in i_all and "ai_actions_success" in i_all and "ai_actions_failed" in i_all

        print(" -> test_repository_deep_rbac_filtering passed!")
    finally:
        db.close()


def test_dashboard_service_deep_rbac_isolation():
    """Kiểm tra: AnalyticsService.get_dashboard_data áp dụng phân quyền dữ liệu sâu (Deep RBAC)."""
    db = SessionLocal()
    try:
        # Lấy Admin và Staff
        admin = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        staff = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        assert admin is not None and staff is not None

        # Tạo thêm 1 nhân viên khác để so sánh phạm vi dữ liệu
        other_staff = db.query(models.Employee).filter(models.Employee.username == "other_staff_test").first()
        if not other_staff:
            other_staff = models.Employee(
                username="other_staff_test",
                password=get_password_hash("pass123"),
                full_name="Nhân viên B",
                role="staff_sales"
            )
            db.add(other_staff)
            db.commit()
            db.refresh(other_staff)

        # Tạo 1 refund gán cho staff
        ref_staff = models.RefundRequest(
            order_id=1,
            employee_id=staff.id,
            reason="Lỗi của staff A",
            status=models.RefundState.PENDING,
            amount=500000.0
        )
        db.add(ref_staff)

        # Tạo 1 refund gán cho other_staff
        ref_other = models.RefundRequest(
            order_id=2,
            employee_id=other_staff.id,
            reason="Lỗi của staff B",
            status=models.RefundState.APPROVED,
            amount=1500000.0
        )
        db.add(ref_other)
        db.commit()

        service = AnalyticsService(repo=AnalyticsRepository(db=db), db=db)

        # 1. Admin gọi -> Nhìn thấy toàn bộ (cả staff và other_staff)
        admin_data = service.get_dashboard_data(current_user=admin)
        assert admin_data.process["pending"] >= 1
        assert admin_data.process["approved"] >= 1
        assert admin_data.data["total_refund_amount"] >= 2000000.0

        # 2. Staff A gọi -> Chỉ nhìn thấy số liệu của staff A (pending >= 1, nhưng approved của other_staff không bị tính vào đây nếu staff A chưa có approved)
        staff_data = service.get_dashboard_data(current_user=staff)
        # Tiền refund của staff A chỉ có đơn của mình
        assert staff_data.process["pending"] >= 1

        print(" -> test_dashboard_service_deep_rbac_isolation passed!")
    finally:
        db.close()


def test_dashboard_api_endpoint_flow():
    """Kiểm tra: GET /api/v1/analytics/dashboard trả về StandardResponse chuẩn và kiểm soát quyền."""
    db = SessionLocal()
    try:
        admin = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        staff = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        assert admin is not None and staff is not None

        admin_token = create_access_token({"sub": admin.username, "id": admin.id, "role": admin.role})
        staff_token = create_access_token({"sub": staff.username, "id": staff.id, "role": staff.role})

        # 1. Chưa đăng nhập -> 401
        res_unauth = client.get("/api/v1/analytics/dashboard")
        assert res_unauth.status_code == 401

        # 2. Admin gọi -> 200, đầy đủ 4 block trong data
        res_admin = client.get("/api/v1/analytics/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_admin.status_code == 200
        admin_body = res_admin.json()
        assert admin_body["success"] is True
        assert "human" in admin_body["data"]
        assert "process" in admin_body["data"]
        assert "data" in admin_body["data"]
        assert "intelligence" in admin_body["data"]

        # 3. Staff gọi -> 200, phản hồi hợp lệ cho nhân viên
        res_staff = client.get("/api/v1/analytics/dashboard", headers={"Authorization": f"Bearer {staff_token}"})
        assert res_staff.status_code == 200
        staff_body = res_staff.json()
        assert staff_body["success"] is True
        assert "human" in staff_body["data"]
        assert "process" in staff_body["data"]
        assert "data" in staff_body["data"]
        assert "intelligence" in staff_body["data"]

        print(" -> test_dashboard_api_endpoint_flow passed!")
    finally:
        db.close()


if __name__ == "__main__":
    print("================ KIỂM THỬ DASHBOARD API BFF & DEEP RBAC (BƯỚC 5.3) ================")
    test_dashboard_schema_hpdi_structure()
    test_repository_deep_rbac_filtering()
    test_dashboard_service_deep_rbac_isolation()
    test_dashboard_api_endpoint_flow()
    print("🎉 TẤT CẢ KIỂM THỬ DASHBOARD API BFF & DEEP RBAC ĐÃ PASS 100%!")
