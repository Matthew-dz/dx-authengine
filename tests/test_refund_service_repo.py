import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.repositories.refund_repository import RefundRepository
from app.services.refund_service import RefundService
from app.security import create_access_token, get_password_hash
from datetime import datetime

client = TestClient(app)

def test_service_repo_architecture():
    db = SessionLocal()
    try:
        # 1. Kiểm tra RefundRepository
        repo = RefundRepository(db)
        assert hasattr(repo, "get_by_id")
        assert hasattr(repo, "get_all")
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")

        # 2. Kiểm tra RefundService
        service = RefundService(repo=repo, db=db)
        assert hasattr(service, "create_refund_request")
        assert hasattr(service, "process_refund")
        assert hasattr(service, "approve_refund")
        assert hasattr(service, "reject_refund")

        # 3. Tạo dữ liệu test
        customer = models.Customer(
            full_name="Khách Hàng Repo Test",
            phone="0911333444",
            address="Đà Nẵng",
            dob="1990-01-01",
            gender="Nam",
            email="repo_customer@example.com"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        order = models.Order(
            product_name="Màn hình 4K Repo Test",
            price=12000000.0,
            order_date=datetime.now(),
            customer_id=customer.id,
            status="DELIVERED"
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        sales_user = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        manager_user = db.query(models.Employee).filter(models.Employee.role == "manager").first()

        sales_token = create_access_token({"sub": sales_user.username, "id": sales_user.id, "role": sales_user.role})
        manager_token = create_access_token({"sub": manager_user.username, "id": manager_user.id, "role": manager_user.role})

        sales_headers = {"Authorization": f"Bearer {sales_token}"}
        manager_headers = {"Authorization": f"Bearer {manager_token}"}

        # 4. Kiểm tra luồng qua Router -> Service -> Repository
        # Create
        res_create = client.post("/api/v1/refunds", json={"order_id": order.id, "reason": "Lỗi sọc màn hình"}, headers=sales_headers)
        assert res_create.status_code == 200, res_create.text
        refund_id = res_create.json()["id"]
        assert res_create.json()["status"] == "PENDING"

        # Process
        res_proc = client.post(f"/api/v1/refunds/{refund_id}/process", json={"notes": "Đã nhận thẩm định"}, headers=sales_headers)
        assert res_proc.status_code == 200, res_proc.text
        assert res_proc.json()["status"] == "PROCESSING"

        # Approve
        res_app = client.post(f"/api/v1/refunds/{refund_id}/approve", json={"notes": "Đồng ý hoàn tiền"}, headers=manager_headers)
        assert res_app.status_code == 200, res_app.text
        assert res_app.json()["status"] == "APPROVED"

        # Kiểm tra Order đã chuyển sang REFUNDED
        db.refresh(order)
        assert order.status == "REFUNDED"

        print("🎉 REPOSITORY PATTERN & SERVICE LAYER TESTED SUCCESSFULLY!")
    finally:
        db.close()

if __name__ == "__main__":
    test_service_repo_architecture()
