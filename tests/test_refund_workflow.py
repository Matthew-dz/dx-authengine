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

def test_full_refund_workflow_dx_os():
    db = SessionLocal()
    try:
        # 1. Chuẩn bị tài khoản nhân viên (Sales/Employee) và Quản lý (Manager/Admin)
        sales_user = db.query(models.Employee).filter(models.Employee.username == "test_sales").first()
        if not sales_user:
            sales_user = models.Employee(
                username="test_sales",
                password=get_password_hash("123"),
                full_name="Nhân viên Sales Test",
                position="Sales",
                hire_date="2024-01-01",
                address="Hà Nội",
                hometown="Hà Nội",
                phone="0911000111",
                cccd="001099000001",
                role="staff_sales"
            )
            db.add(sales_user)
            db.commit()
            db.refresh(sales_user)

        manager_user = db.query(models.Employee).filter(models.Employee.username == "test_manager").first()
        if not manager_user:
            manager_user = models.Employee(
                username="test_manager",
                password=get_password_hash("123"),
                full_name="Quản lý Manager Test",
                position="Trưởng phòng",
                hire_date="2023-01-01",
                address="Hà Nội",
                hometown="Đà Nẵng",
                phone="0911000222",
                cccd="001099000002",
                role="manager"
            )
            db.add(manager_user)
            db.commit()
            db.refresh(manager_user)

        sales_token = create_access_token({"sub": sales_user.username, "role": sales_user.role})
        manager_token = create_access_token({"sub": manager_user.username, "role": manager_user.role})

        sales_headers = {"Authorization": f"Bearer {sales_token}"}
        manager_headers = {"Authorization": f"Bearer {manager_token}"}

        # 2. Tạo đơn hàng và khách hàng test
        customer = models.Customer(
            full_name="Khách Hàng Workflow DX-OS",
            phone="0988776655",
            address="TP. Hồ Chí Minh",
            dob="1992-05-10",
            gender="Nam",
            email="customer_dxos@example.com"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        order = models.Order(
            product_name="Laptop Gaming DX-OS Pro",
            price=35000000.0,
            order_date=datetime.now(),
            customer_id=customer.id,
            status="DELIVERED"
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        order_id = order.id

        # =========================================================================
        # BƯỚC 1: CREATE (POST /api/v1/refunds)
        # =========================================================================
        print("\n[TEST 1] Kiểm tra quyền CREATE:")
        # 1a. Manager thử tạo -> Kỳ vọng 403 Forbidden (Vì Manager chỉ có quyền approve/reject)
        res_create_manager = client.post("/api/v1/refunds", json={"order_id": order_id, "reason": "Lỗi màn hình"}, headers=manager_headers)
        assert res_create_manager.status_code == 403, f"Manager không được quyền create! {res_create_manager.text}"
        print(" -> Manager tạo đơn hoàn tiền: Bị chặn 403 (Đúng chuẩn Casbin)")

        # 1b. Sales tạo -> Thành công 200, status mặc định PENDING
        res_create_sales = client.post("/api/v1/refunds", json={"order_id": order_id, "reason": "Lỗi phần cứng"}, headers=sales_headers)
        assert res_create_sales.status_code == 200, res_create_sales.text
        refund_data = res_create_sales.json()
        refund_id = refund_data["id"]
        assert refund_data["status"] == "PENDING"
        assert refund_data["order_id"] == order_id
        print(f" -> Sales tạo đơn hoàn tiền #{refund_id}: Thành công với status PENDING")

        # Kiểm tra Audit Log của CREATE
        log_create = db.query(models.AuditLog).filter(models.AuditLog.order_id == order_id).order_by(models.AuditLog.id.desc()).first()
        assert log_create is not None
        assert log_create.details is not None
        details_create = json.loads(log_create.details)
        assert details_create["action"] == "create"
        assert details_create["new_state"] == "PENDING"
        print(" -> Audit Log CREATE: Ghi nhận đúng action 'create' và details JSON")

        # =========================================================================
        # BƯỚC 2: PROCESS (POST /api/v1/refunds/{id}/process)
        # =========================================================================
        print("\n[TEST 2] Kiểm tra quyền PROCESS:")
        # 2a. Manager thử process -> 403 Forbidden
        res_proc_manager = client.post(f"/api/v1/refunds/{refund_id}/process", json={"notes": "Manager thử process"}, headers=manager_headers)
        assert res_proc_manager.status_code == 403, f"Manager không được process! {res_proc_manager.text}"
        print(" -> Manager process: Bị chặn 403 (Đúng chuẩn Casbin)")

        # 2b. Sales process -> Thành công 200, chuyển PENDING -> PROCESSING
        res_proc_sales = client.post(f"/api/v1/refunds/{refund_id}/process", json={"notes": "Đã nhận máy kiểm tra"}, headers=sales_headers)
        assert res_proc_sales.status_code == 200, res_proc_sales.text
        assert res_proc_sales.json()["status"] == "PROCESSING"
        print(f" -> Sales process #{refund_id}: Thành công chuyển sang PROCESSING")

        # 2c. Thử process lần nữa khi đã ở PROCESSING -> Phải báo lỗi 400
        res_proc_again = client.post(f"/api/v1/refunds/{refund_id}/process", headers=sales_headers)
        assert res_proc_again.status_code == 400
        print(" -> Thử process lại đơn đã PROCESSING: Báo lỗi 400 (Chặn sai workflow)")

        # Kiểm tra Audit Log của PROCESS
        log_proc = db.query(models.AuditLog).filter(models.AuditLog.order_id == order_id).order_by(models.AuditLog.id.desc()).first()
        details_proc = json.loads(log_proc.details)
        assert details_proc["action"] == "process"
        assert details_proc["old_state"] == "PENDING"
        assert details_proc["new_state"] == "PROCESSING"
        print(" -> Audit Log PROCESS: Ghi nhận đúng PENDING -> PROCESSING và details JSON")

        # =========================================================================
        # BƯỚC 3: APPROVE & BACKGROUND TASKS (POST /api/v1/refunds/{id}/approve)
        # =========================================================================
        print("\n[TEST 3] Kiểm tra quyền APPROVE & TỰ ĐỘNG HÓA:")
        # 3a. Sales thử approve -> 403 Forbidden
        res_app_sales = client.post(f"/api/v1/refunds/{refund_id}/approve", json={"notes": "Sales thử duyệt"}, headers=sales_headers)
        assert res_app_sales.status_code == 403, f"Sales không được approve! {res_app_sales.text}"
        print(" -> Sales approve: Bị chặn 403 (Đúng chuẩn Casbin)")

        # 3b. Manager approve -> Thành công 200
        res_app_manager = client.post(f"/api/v1/refunds/{refund_id}/approve", json={"notes": "Đủ điều kiện bảo hành"}, headers=manager_headers)
        assert res_app_manager.status_code == 200, res_app_manager.text
        assert res_app_manager.json()["status"] == "APPROVED"
        print(" -> Manager approve: Thành công chuyển sang APPROVED")

        # 3c. Kiểm tra đồng bộ đơn hàng: Order.status phải thành "REFUNDED"
        db.refresh(order)
        assert order.status == "REFUNDED", f"Order status phải là REFUNDED nhưng lại là {order.status}"
        print(" -> Transaction đồng bộ: Đơn hàng Order.status đã tự động chuyển thành 'REFUNDED'")

        # 3d. Kiểm tra Audit Log của APPROVE
        log_app = db.query(models.AuditLog).filter(models.AuditLog.order_id == order_id).order_by(models.AuditLog.id.desc()).first()
        details_app = json.loads(log_app.details)
        assert details_app["action"] == "approve"
        assert details_app["old_state"] == "PROCESSING"
        assert details_app["new_state"] == "APPROVED"
        print(" -> Audit Log APPROVE: Ghi nhận đúng PROCESSING -> APPROVED và details JSON")

        # 3e. Thử reject hoặc approve khi đã APPROVED -> Báo lỗi 400
        res_rej_closed = client.post(f"/api/v1/refunds/{refund_id}/reject", headers=manager_headers)
        assert res_rej_closed.status_code == 400
        print(" -> Thử can thiệp vào đơn đã đóng (APPROVED): Báo lỗi 400")

        # =========================================================================
        # BƯỚC 4: REJECT WORKFLOW (POST /api/v1/refunds/{id}/reject)
        # =========================================================================
        print("\n[TEST 4] Kiểm tra quy trình REJECT:")
        # Tạo thêm 1 order để test reject
        order2 = models.Order(
            product_name="Bàn phím cơ DX-OS Key",
            price=2500000.0,
            order_date=datetime.now(),
            customer_id=customer.id,
            status="DELIVERED"
        )
        db.add(order2)
        db.commit()
        db.refresh(order2)

        # Sales tạo và process đơn 2
        r2 = client.post("/api/v1/refunds", json={"order_id": order2.id, "reason": "Không ưng màu"}, headers=sales_headers).json()
        r2_id = r2["id"]
        client.post(f"/api/v1/refunds/{r2_id}/process", headers=sales_headers)

        # Sales thử reject đơn 2 -> 403 Forbidden
        res_rej_sales = client.post(f"/api/v1/refunds/{r2_id}/reject", headers=sales_headers)
        assert res_rej_sales.status_code == 403
        print(" -> Sales reject: Bị chặn 403 (Đúng chuẩn Casbin)")

        # Manager reject đơn 2 -> Thành công 200, chuyển sang REJECTED
        res_rej_manager = client.post(f"/api/v1/refunds/{r2_id}/reject", json={"notes": "Không hỗ trợ đổi trả vì màu sắc"}, headers=manager_headers)
        assert res_rej_manager.status_code == 200
        assert res_rej_manager.json()["status"] == "REJECTED"
        print(" -> Manager reject: Thành công chuyển sang REJECTED")

        # Kiểm tra Audit Log của REJECT
        log_rej = db.query(models.AuditLog).filter(models.AuditLog.order_id == order2.id).order_by(models.AuditLog.id.desc()).first()
        details_rej = json.loads(log_rej.details)
        assert details_rej["action"] == "reject"
        assert details_rej["old_state"] == "PROCESSING"
        assert details_rej["new_state"] == "REJECTED"
        print(" -> Audit Log REJECT: Ghi nhận đúng PROCESSING -> REJECTED và details JSON")

        print("\n🎉 TẤT CẢ CÁC BƯỚC WORKFLOW, PHÂN QUYỀN CASBIN, TRANSACTION VÀ AUDIT LOG ĐÃ PASS 100%!")

    finally:
        db.close()

if __name__ == "__main__":
    test_full_refund_workflow_dx_os()
