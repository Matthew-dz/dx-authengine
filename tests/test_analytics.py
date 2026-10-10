import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.repositories.analytics_repository import AnalyticsRepository
from app.services.analytics_service import AnalyticsService
from app.security import create_access_token

client = TestClient(app)


def test_time_math_and_midnight_bug_logic():
    """
    Test các helper xử lý 2 bẫy quan trọng:
    1. The Midnight Bug: to_date phải tự động bao phủ đến 23:59:59.999999
    2. Time Math Trap: Tính trung bình cộng số phút dựa trên (created_at, processed_at)
    """
    # 1. Kiểm tra khắc phục Midnight Bug
    from_str = "2026-10-01"
    to_str = "2026-10-10"
    n_from, n_to = AnalyticsService.normalize_date_range(from_str, to_str)

    assert n_from == datetime(2026, 10, 1, 0, 0, 0)
    assert n_to.year == 2026 and n_to.month == 10 and n_to.day == 10
    assert n_to.hour == 23 and n_to.minute == 59 and n_to.second == 59

    # 2. Kiểm tra tính thời gian xử lý trung bình (Time Math Trap)
    # Cặp 1: cách nhau 30 phút (1800 giây)
    t1 = datetime(2026, 10, 10, 8, 0, 0)
    t2 = datetime(2026, 10, 10, 8, 30, 0)
    # Cặp 2: cách nhau 90 phút (5400 giây)
    t3 = datetime(2026, 10, 10, 9, 0, 0)
    t4 = datetime(2026, 10, 10, 10, 30, 0)

    time_pairs = [(t1, t2), (t3, t4)]
    avg_minutes = AnalyticsService.calculate_average_processing_time(time_pairs)
    # (30 + 90) / 2 = 60.0 phút
    assert avg_minutes == 60.0, f"Expected 60.0, got {avg_minutes}"

    # Danh sách rỗng -> 0.0
    assert AnalyticsService.calculate_average_processing_time([]) == 0.0


def test_analytics_repository_aggregation():
    """
    Kiểm tra Data Access Layer (AnalyticsRepository):
    Bẫy sập bộ nhớ: Phải dùng func.count, func.sum trực tiếp dưới DB thay vì kéo .all() về đếm.
    """
    db = SessionLocal()
    try:
        repo = AnalyticsRepository(db)
        stats = repo.get_overview_stats()
        assert isinstance(stats, dict)
        assert "total_orders" in stats
        assert "total_refunds" in stats
        assert "total_refund_amount" in stats
        assert "pending" in stats
        assert "approved" in stats
        assert "rejected" in stats
        assert stats["total_orders"] >= 0
        assert stats["total_refunds"] >= 0
        assert stats["total_refund_amount"] >= 0.0
    finally:
        db.close()


def test_analytics_api_security_and_midnight_bug_flow():
    """
    Kiểm tra toàn diện API:
    - BẢO MẬT: Chưa đăng nhập -> 401; Staff Sales -> 403; Admin / Manager -> 200
    - Nghiệp vụ Midnight Bug: Tạo record lúc 15:30 ngày 2026-10-10, khi query ?to=2026-10-10 record không bị mất!
    """
    db = SessionLocal()
    try:
        # Lấy hoặc tạo user cho từng role
        admin_user = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        manager_user = db.query(models.Employee).filter(models.Employee.role == "manager").first()
        sales_user = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()

        assert admin_user is not None
        assert manager_user is not None
        assert sales_user is not None

        admin_token = create_access_token({"sub": admin_user.username, "id": admin_user.id, "role": admin_user.role})
        manager_token = create_access_token({"sub": manager_user.username, "id": manager_user.id, "role": manager_user.role})
        sales_token = create_access_token({"sub": sales_user.username, "id": sales_user.id, "role": sales_user.role})

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        sales_headers = {"Authorization": f"Bearer {sales_token}"}

        # 1. Test 401 khi chưa đăng nhập
        res_no_auth = client.get("/api/v1/analytics/overview")
        assert res_no_auth.status_code == 401

        # 2. Test 403 với Role staff_sales
        res_sales_overview = client.get("/api/v1/analytics/overview", headers=sales_headers)
        assert res_sales_overview.status_code == 403, f"Expected 403, got {res_sales_overview.status_code}"

        res_sales_perf = client.get("/api/v1/analytics/employee-performance", headers=sales_headers)
        assert res_sales_perf.status_code == 403

        # 3. Test 200 với Role Manager và Admin
        res_manager = client.get("/api/v1/analytics/overview", headers=manager_headers)
        assert res_manager.status_code == 200
        overview_data = res_manager.json()
        assert "total_orders" in overview_data
        assert "total_refunds" in overview_data
        assert "total_refund_amount" in overview_data

        res_admin = client.get("/api/v1/analytics/overview", headers=admin_headers)
        assert res_admin.status_code == 200

        # 4. Kiểm chứng "The Midnight Bug" trên thực tế Database
        # Tạo đơn hàng và refund vào lúc 15:30 ngày 2026-10-10
        test_customer = models.Customer(
            full_name="Khách Midnight Test",
            phone="0999888777",
            address="Hà Nội",
            dob="1995-05-05",
            gender="Nữ",
            email="midnight_test@example.com"
        )
        db.add(test_customer)
        db.commit()
        db.refresh(test_customer)

        afternoon_date = datetime(2026, 10, 10, 15, 30, 0)
        test_order = models.Order(
            product_name="Tai nghe Midnight Test",
            price=2500000.0,
            order_date=afternoon_date,
            customer_id=test_customer.id,
            status="DELIVERED"
        )
        db.add(test_order)
        db.commit()
        db.refresh(test_order)

        test_refund = models.RefundRequest(
            order_id=test_order.id,
            employee_id=admin_user.id,
            reason="Midnight bug verification",
            status=models.RefundState.APPROVED,
            amount=2500000.0,
            created_at=afternoon_date,
            updated_at=afternoon_date + timedelta(minutes=45)
        )
        db.add(test_refund)
        db.commit()
        db.refresh(test_refund)

        # Lọc bằng chuỗi ngày chỉ có YYYY-MM-DD: to=2026-10-10
        # Nếu bị lỗi Midnight Bug (to = 2026-10-10 00:00:00), bản ghi lúc 15:30 sẽ BỊ MẤT.
        # Nhưng với logic khắc phục Midnight Bug, bản ghi phải được bao gồm!
        res_filtered = client.get(
            "/api/v1/analytics/overview?from=2026-10-10&to=2026-10-10",
            headers=admin_headers
        )
        assert res_filtered.status_code == 200
        filtered_data = res_filtered.json()
        assert filtered_data["total_orders"] >= 1, "Order lúc 15:30 không được bị mất bởi Midnight Bug!"
        assert filtered_data["total_refunds"] >= 1, "Refund lúc 15:30 không được bị mất bởi Midnight Bug!"
        assert filtered_data["total_refund_amount"] >= 2500000.0

        # 5. Test Employee Performance API
        res_perf = client.get(
            f"/api/v1/analytics/employee-performance/{admin_user.id}?from=2026-10-10&to=2026-10-10",
            headers=admin_headers
        )
        assert res_perf.status_code == 200
        perf_data = res_perf.json()
        assert perf_data["employee_name"] == (admin_user.full_name or admin_user.username)
        assert perf_data["approved"] >= 1
        assert perf_data["average_processing_time_minutes"] > 0

        # 6. Test All Employee Performance API
        res_all_perf = client.get(
            "/api/v1/analytics/employee-performance",
            headers=manager_headers
        )
        assert res_all_perf.status_code == 200
        assert isinstance(res_all_perf.json(), list)

        print("🎉 ALL DATA ANALYTICS & REPORTING TESTS PASSED!")
    finally:
        db.close()


if __name__ == "__main__":
    test_time_math_and_midnight_bug_logic()
    test_analytics_repository_aggregation()
    test_analytics_api_security_and_midnight_bug_flow()
