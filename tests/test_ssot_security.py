import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.security import create_access_token, get_password_hash
from datetime import datetime

client = TestClient(app)

def test_ssot_security():
    db = SessionLocal()
    try:
        # Chuẩn bị user test
        admin_user = db.query(models.Employee).filter(models.Employee.username == "admin_ssot").first()
        if not admin_user:
            admin_user = models.Employee(
                username="admin_ssot",
                password=get_password_hash("123"),
                full_name="Admin SSOT",
                position="Admin",
                hire_date="2024-01-01",
                address="Hà Nội",
                hometown="Hà Nội",
                phone="0911222333",
                cccd="001099999001",
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        sales_user = db.query(models.Employee).filter(models.Employee.username == "sales_ssot").first()
        if not sales_user:
            sales_user = models.Employee(
                username="sales_ssot",
                password=get_password_hash("123"),
                full_name="Sales SSOT",
                position="Sales",
                hire_date="2024-01-01",
                address="Hà Nội",
                hometown="Hà Nội",
                phone="0911222444",
                cccd="001099999002",
                role="staff_sales"
            )
            db.add(sales_user)
            db.commit()
            db.refresh(sales_user)

        admin_token = create_access_token({"sub": admin_user.username, "id": admin_user.id, "role": "admin"})
        sales_token = create_access_token({"sub": sales_user.username, "id": sales_user.id, "role": "staff_sales"})

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        sales_headers = {"Authorization": f"Bearer {sales_token}"}

        # -------------------------------------------------------------
        # 1. TEST KHÓA CHẶT INPUT SCHEMAS
        # -------------------------------------------------------------
        print("\n[1] Kiểm tra Khóa chặt Input Schemas:")
        # 1a. Cố tình gửi 'role' hoặc 'is_active' lên EmployeeUpdate -> Bị chặn 422 Unprocessable Entity
        bad_emp_update = client.put(
            f"/api/v1/employees/{sales_user.id}",
            json={"full_name": "Hacker Sales", "role": "admin"},
            headers=admin_headers
        )
        assert bad_emp_update.status_code == 422, f"Không được phép gửi role trong EmployeeUpdate! {bad_emp_update.text}"
        print(" -> EmployeeUpdate có trường 'role': Bị từ chối 422 (extra fields forbidden)")

        bad_emp_update2 = client.put(
            f"/api/v1/employees/{sales_user.id}",
            json={"full_name": "Hacker Sales", "is_active": False},
            headers=admin_headers
        )
        assert bad_emp_update2.status_code == 422
        print(" -> EmployeeUpdate có trường 'is_active': Bị từ chối 422 (extra fields forbidden)")

        # Cập nhật trường hợp lệ (full_name, phone, address, email) -> Thành công 200
        valid_emp_update = client.put(
            f"/api/v1/employees/{sales_user.id}",
            json={"full_name": "Sales Chuẩn SSOT", "phone": "0999888777"},
            headers=admin_headers
        )
        assert valid_emp_update.status_code == 200
        db.refresh(sales_user)
        assert sales_user.full_name == "Sales Chuẩn SSOT"
        print(" -> EmployeeUpdate hợp lệ (full_name, phone): Thành công 200")

        # 1b. Cố tình gửi 'status' hoặc 'processed_by' lên RefundRequestCreate -> Bị chặn 422
        bad_refund_create = client.post(
            "/api/v1/refunds",
            json={"order_id": 1, "reason": "Test", "status": "APPROVED"},
            headers=sales_headers
        )
        assert bad_refund_create.status_code == 422
        print(" -> RefundRequestCreate có trường 'status': Bị từ chối 422 (extra fields forbidden)")

        bad_refund_create2 = client.post(
            "/api/v1/refunds",
            json={"order_id": 1, "reason": "Test", "processed_by": 999},
            headers=sales_headers
        )
        assert bad_refund_create2.status_code == 422
        print(" -> RefundRequestCreate có trường 'processed_by': Bị từ chối 422 (extra fields forbidden)")

        # -------------------------------------------------------------
        # 2. TEST KIỂM SOÁT CỔNG AUDIT LOG
        # -------------------------------------------------------------
        print("\n[2] Kiểm tra Kiểm soát cổng Audit Log:")
        # 2a. POST /api/v1/audit-logs không tồn tại -> 404 hoặc 405
        res_post_audit = client.post("/api/v1/audit-logs", json={"action": "fake"}, headers=admin_headers)
        assert res_post_audit.status_code in [404, 405]
        print(" -> Không có API POST /api/v1/audit-logs: Endpoint trả về 404/405 an toàn")

        # 2b. Sales gọi GET /api/v1/audit-logs -> Bị chặn 403 Forbidden
        res_sales_audit = client.get("/api/v1/audit-logs", headers=sales_headers)
        assert res_sales_audit.status_code == 403
        print(" -> Sales xem Audit Log: Bị chặn 403 (Chỉ Admin/Manager mới được xem)")

        # 2c. Admin gọi GET /api/v1/audit-logs -> Thành công 200
        res_admin_audit = client.get("/api/v1/audit-logs", headers=admin_headers)
        assert res_admin_audit.status_code == 200
        print(" -> Admin xem Audit Log: Thành công 200")

        # -------------------------------------------------------------
        # 3. TEST BẢO VỆ JWT (TRUY VẤN DB MỚI NHẤT TRÁNH LỖI TOKEN CŨ KHI GIÁNG CHỨC)
        # -------------------------------------------------------------
        print("\n[3] Kiểm tra Bảo vệ JWT (Identity Source):")
        # Giả sử tạo hoặc lấy tài khoản manager tạm thời
        temp_manager = db.query(models.Employee).filter(models.Employee.username == "temp_manager").first()
        if not temp_manager:
            temp_manager = models.Employee(
                username="temp_manager",
                password=get_password_hash("123"),
                full_name="Manager Tạm",
                position="Manager",
                hire_date="2024-01-01",
                address="Hà Nội",
                hometown="Hà Nội",
                phone="0911777888",
                cccd="001099999003",
                role="manager"
            )
            db.add(temp_manager)
            db.commit()
            db.refresh(temp_manager)
        else:
            temp_manager.role = "manager"
            db.commit()
            db.refresh(temp_manager)


        # Phát hành token với role "manager"
        temp_token = create_access_token({"sub": temp_manager.username, "id": temp_manager.id, "role": "manager"})
        temp_headers = {"Authorization": f"Bearer {temp_token}"}

        # Kiểm tra token ban đầu truy cập được audit logs
        res_check1 = client.get("/api/v1/audit-logs", headers=temp_headers)
        assert res_check1.status_code == 200
        print(" -> Token với role manager ban đầu: Truy cập được Audit Log 200")

        # Bây giờ GIÁNG CHỨC user trong Database xuống staff_sales
        temp_manager.role = "staff_sales"
        db.commit()
        print(" -> Đã giáng chức temp_manager trong Database từ 'manager' xuống 'staff_sales'")

        # Dùng lại token cũ (trong token payload vẫn còn role='manager')
        # get_current_user PHẢI đọc lại Database theo id, thấy role='staff_sales', và CHẶN 403!
        res_check2 = client.get("/api/v1/audit-logs", headers=temp_headers)
        assert res_check2.status_code == 403, f"Phải bị 403 vì trong DB đã bị giáng chức! {res_check2.text}"
        print(" -> Dùng token cũ sau khi giáng chức: Bị chặn 403 (get_current_user đã lấy role mới nhất từ Database)")

        print("\n🎉 TẤT CẢ KIỂM THỬ BẢO MẬT SSOT ĐÃ PASS HOÀN TOÀN!")
    finally:
        db.close()

if __name__ == "__main__":
    test_ssot_security()
