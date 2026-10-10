import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app import models
from app.events.event import BaseEvent, RefundApprovedEvent
from app.events.event_bus import EventBus, event_bus
from app.events.handlers.refund_handler import handle_refund_approved
from app.repositories.refund_repository import RefundRepository
from app.services.refund_service import RefundService
from app.security import create_access_token


client = TestClient(app)


def test_event_models():
    """Kiểm tra: Cấu trúc BaseEvent và RefundApprovedEvent theo chuẩn Pydantic."""
    base = BaseEvent(event_type="GenericEvent", entity_id=101, user_id=1)
    assert base.event_type == "GenericEvent"
    assert base.entity_id == 101
    assert base.user_id == 1
    assert isinstance(base.timestamp, datetime)

    refund_event = RefundApprovedEvent(
        entity_id=202,
        user_id=5,
        data={"order_id": 999, "amount": 500000.0, "notes": "Hàng lỗi linh kiện"}
    )
    assert refund_event.event_type == "RefundApproved"
    assert refund_event.entity_id == 202
    assert refund_event.user_id == 5
    assert refund_event.data["order_id"] == 999
    assert refund_event.data["notes"] == "Hàng lỗi linh kiện"
    print(" -> test_event_models passed!")


def test_event_bus_singleton_and_pubsub():
    """Kiểm tra: EventBus tuân thủ mẫu Singleton và cơ chế publish/subscribe bất đồng bộ."""
    bus1 = EventBus()
    bus2 = EventBus()
    assert bus1 is bus2, "EventBus phải là Singleton!"
    assert bus1 is event_bus

    received_events = []

    def sample_handler(event: BaseEvent):
        received_events.append(event)

    bus1.subscribe("TestCustomEvent", sample_handler)

    test_ev = BaseEvent(event_type="TestCustomEvent", entity_id=1, user_id=2)

    # 1. Publish không có BackgroundTasks (đồng bộ an toàn)
    bus1.publish(test_ev)
    assert len(received_events) == 1
    assert received_events[0].entity_id == 1

    # 2. Publish với BackgroundTasks (bất đồng bộ FastAPI)
    import asyncio
    bg_tasks = BackgroundTasks()
    bus1.publish(test_ev, background_tasks=bg_tasks)
    assert len(bg_tasks.tasks) == 1
    asyncio.run(bg_tasks())
    assert len(received_events) == 2
    print(" -> test_event_bus_singleton_and_pubsub passed!")


def test_handle_refund_approved_isolated_session():
    """Kiểm tra: Handler tự mở DB session độc lập và ghi AuditLog thành công."""
    db = SessionLocal()
    try:
        # Tạo order mẫu
        cust = models.Customer(
            full_name="Khách Hàng Event Test",
            phone="0988776655",
            address="Hà Nội",
            email="event_test@example.com"
        )
        db.add(cust)
        db.commit()
        db.refresh(cust)

        ord_obj = models.Order(
            product_name="Tai nghe Bluetooth DX-Event",
            price=2500000.0,
            order_date=datetime.now(),
            customer_id=cust.id,
            status="DELIVERED"
        )
        db.add(ord_obj)
        db.commit()
        db.refresh(ord_obj)

        event = RefundApprovedEvent(
            entity_id=9999,
            user_id=1,
            data={
                "order_id": ord_obj.id,
                "employee_username": "manager_event",
                "notes": "Duyệt qua Event Bus",
                "old_state": "PROCESSING",
                "product_name": ord_obj.product_name,
                "customer_name": cust.full_name,
                "customer_email": cust.email
            }
        )

        # Gọi handler độc lập
        handle_refund_approved(event)

        # Kiểm tra AuditLog được ghi lại
        log_entry = db.query(models.AuditLog).filter(
            models.AuditLog.order_id == ord_obj.id,
            models.AuditLog.employee_username == "manager_event"
        ).order_by(models.AuditLog.id.desc()).first()

        assert log_entry is not None
        assert "EventBus: Phê duyệt hoàn tiền" in log_entry.reason
        assert log_entry.decision == "ALLOW"
        print(" -> test_handle_refund_approved_isolated_session passed!")
    finally:
        db.close()


def test_full_refund_workflow_event_driven():
    """Kiểm tra: Luồng duyệt hoàn tiền qua API kích hoạt EventBus và BackgroundTasks."""
    db = SessionLocal()
    try:
        manager_user = db.query(models.Employee).filter(models.Employee.role == "manager").first()
        sales_user = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        assert manager_user is not None and sales_user is not None

        manager_token = create_access_token({"sub": manager_user.username, "id": manager_user.id, "role": manager_user.role})
        sales_token = create_access_token({"sub": sales_user.username, "id": sales_user.id, "role": sales_user.role})

        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        sales_headers = {"Authorization": f"Bearer {sales_token}"}

        # 1. Tạo customer & order
        cust = models.Customer(
            full_name="Nguyễn Văn Event",
            phone="0901234567",
            email="event_bus_user@example.com"
        )
        db.add(cust)
        db.commit()
        db.refresh(cust)

        order = models.Order(
            product_name="Điện thoại DX-Event Pro",
            price=15000000.0,
            order_date=datetime.now(),
            customer_id=cust.id,
            status="DELIVERED"
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # 2. Tạo refund (sales)
        res_create = client.post("/api/v1/refunds", json={"order_id": order.id, "reason": "Lỗi phần mềm"}, headers=sales_headers)
        assert res_create.status_code == 200
        refund_id = res_create.json()["id"]

        # 3. Process refund (sales)
        res_proc = client.post(f"/api/v1/refunds/{refund_id}/process", json={"notes": "Đã kiểm tra"}, headers=sales_headers)
        assert res_proc.status_code == 200

        # 4. Mock listener để bắt RefundApprovedEvent
        captured_events = []
        def listener(ev: RefundApprovedEvent):
            captured_events.append(ev)

        event_bus.subscribe("RefundApproved", listener)

        # 5. Manager duyệt refund -> Kích hoạt event_bus.publish
        res_app = client.post(f"/api/v1/refunds/{refund_id}/approve", json={"notes": "Chấp thuận hoàn tiền"}, headers=manager_headers)
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "APPROVED"

        # Đảm bảo event được bắt và có dữ liệu chính xác
        matching = [e for e in captured_events if e.entity_id == refund_id]
        assert len(matching) >= 1, "RefundApprovedEvent phải được phát tán khi duyệt hoàn tiền!"
        ev = matching[0]
        assert ev.entity_id == refund_id
        assert ev.user_id == manager_user.id
        assert ev.data["order_id"] == order.id

        print(" -> test_full_refund_workflow_event_driven passed!")
    finally:
        db.close()


if __name__ == "__main__":
    print("================ KIỂM THỬ EVENT-DRIVEN ARCHITECTURE (BƯỚC 5.2) ================")
    test_event_models()
    test_event_bus_singleton_and_pubsub()
    test_handle_refund_approved_isolated_session()
    test_full_refund_workflow_event_driven()
    print("🎉 TẤT CẢ KIỂM THỬ EVENT-DRIVEN ARCHITECTURE ĐÃ PASS 100%!")
