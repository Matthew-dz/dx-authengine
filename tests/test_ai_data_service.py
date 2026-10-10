import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app import models
from app.repositories.refund_repository import RefundRepo
from app.repositories.order_repository import OrderRepo
from app.services.ai_data_service import AIDataService
from app.schemas_ai import RefundContextForAI, CustomerHistoryForAI, RecentOrderForAI


def test_cross_check_security_source_code():
    """
    Kiểm tra an ninh chéo mã nguồn:
    Đảm bảo app/services/ai_data_service.py không chứa bất kỳ lệnh db.commit() nào
    và không import os.getenv để đọc mật khẩu hay cấu hình hệ thống.
    """
    service_file = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ai_data_service.py")
    with open(service_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".commit(" not in content, "VI PHẠM BẢO MẬT: ai_data_service.py không được chứa lệnh db.commit()!"
    assert "getenv" not in content, "VI PHẠM BẢO MẬT: ai_data_service.py không được import hoặc sử dụng getenv!"
    assert "os.environ" not in content, "VI PHẠM BẢO MẬT: ai_data_service.py không được truy cập os.environ!"
    print(" -> An ninh chéo: Không có db.commit() và không đọc os.getenv trong AI Data Service.")


def test_pii_isolation_in_schemas():
    """
    Kiểm tra triệt để nguy cơ rò rỉ PII (Personally Identifiable Information) trong schemas_ai.py.
    Tuyệt đối không có các trường nhạy cảm như full_name, email, phone, cccd, address.
    """
    forbidden_fields = {"full_name", "email", "phone", "cccd", "address", "dob", "gender", "password"}

    for schema_cls in [RefundContextForAI, CustomerHistoryForAI, RecentOrderForAI]:
        field_names = set(schema_cls.model_fields.keys())
        leakage = field_names.intersection(forbidden_fields)
        assert len(leakage) == 0, f"RÒ RỈ PII PHÁT HIỆN trong {schema_cls.__name__}: {leakage}"

    print(" -> Khử định danh (De-identification): Schemas AI sạch 100% PII.")


def test_knowledge_base_files_exist():
    """
    Kiểm tra sự tồn tại của các tài liệu tri thức tĩnh (Knowledge Base) phục vụ RAG.
    """
    kb_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "knowledge_base")
    assert os.path.isdir(kb_dir), f"Thư mục Knowledge Base không tồn tại: {kb_dir}"

    expected_files = [
        "refund_policy.md",
        "workflow_rules.md",
        "system_roles.md"
    ]
    for filename in expected_files:
        filepath = os.path.join(kb_dir, filename)
        assert os.path.isfile(filepath), f"Thiếu file Knowledge Base: {filename}"
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read().strip()
            assert len(text) > 100, f"File {filename} quá ngắn hoặc trống!"

    print(" -> Knowledge Base: Đã khởi tạo đầy đủ 3 tài liệu tĩnh chuẩn hóa.")


def test_ai_data_service_functionality_and_token_optimization():
    """
    Kiểm tra chức năng của AIDataService:
    1. get_refund_context: Trả về dict chuẩn, làm sạch dữ liệu.
    2. get_customer_context: Trả về dict, tối ưu Token Window với limit(5) khi khách hàng có nhiều hơn 5 đơn.
    """
    db = SessionLocal()
    try:
        # Khởi tạo repositories và service
        refund_repo = RefundRepo(db)
        order_repo = OrderRepo(db)
        ai_service = AIDataService(refund_repo=refund_repo, order_repo=order_repo)

        # 1. Tạo dữ liệu giả lập cho khách hàng với 8 đơn hàng (nhiều hơn 5)
        customer = models.Customer(
            full_name="Nguyễn Văn AI Test",
            phone="0911222333",
            address="123 Phố Tràng Tiền, Hà Nội",
            dob="1992-02-02",
            gender="Nam",
            email="ai_test_customer@example.com"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        created_orders = []
        for i in range(8):
            order = models.Order(
                product_name=f"Sản phẩm AI Test #{i+1}",
                price=500000.0 * (i + 1),
                order_date=datetime(2026, 10, i + 1, 10, 0, 0),
                customer_id=customer.id,
                status="DELIVERED"
            )
            db.add(order)
            created_orders.append(order)
        db.commit()

        # Tạo 2 refund request cho khách hàng này
        refund1 = models.RefundRequest(
            order_id=created_orders[0].id,
            reason="Lỗi đổi trả 1",
            status=models.RefundState.PENDING,
            amount=500000.0,
            created_at=datetime(2026, 10, 1, 11, 0, 0)
        )
        refund2 = models.RefundRequest(
            order_id=created_orders[1].id,
            reason="Lỗi đổi trả 2",
            status=models.RefundState.APPROVED,
            amount=1000000.0,
            created_at=datetime(2026, 10, 2, 11, 0, 0)
        )
        db.add_all([refund1, refund2])
        db.commit()
        db.refresh(refund1)

        # 2. Kiểm tra get_refund_context
        refund_ctx = ai_service.get_refund_context(refund1.id)
        assert isinstance(refund_ctx, dict)
        assert refund_ctx["refund_id"] == refund1.id
        assert refund_ctx["order_id"] == created_orders[0].id
        assert refund_ctx["amount"] == 500000.0
        assert refund_ctx["status"] == "PENDING"
        assert refund_ctx["reason"] == "Lỗi đổi trả 1"
        assert "customer_name" not in refund_ctx
        assert "email" not in refund_ctx
        assert "phone" not in refund_ctx

        # 3. Kiểm tra get_customer_context & Tối ưu Token Window (limit 5)
        cust_ctx = ai_service.get_customer_context(customer.id)
        assert isinstance(cust_ctx, dict)
        assert cust_ctx["total_orders"] == 8, f"Expected 8 orders, got {cust_ctx['total_orders']}"
        assert cust_ctx["total_refunds_requested"] == 2, f"Expected 2 refunds, got {cust_ctx['total_refunds_requested']}"

        # BẮT BUỘC: recent_orders chỉ chứa tối đa 5 đơn (mặc dù khách có 8 đơn)
        recent_orders = cust_ctx["recent_orders"]
        assert len(recent_orders) == 5, f"Expected 5 recent orders due to limit(5), got {len(recent_orders)}"
        # Kiểm tra đơn hàng mới nhất nằm đầu danh sách
        assert recent_orders[0]["product_name"] == "Sản phẩm AI Test #8"

        # Kiểm tra không có PII rò rỉ trong bất kỳ item nào của recent_orders
        for o in recent_orders:
            assert "full_name" not in o
            assert "email" not in o
            assert "customer_id" not in o

        print(" -> Token Optimization & Data Cleaning: limit(5) hoạt động hoàn hảo, cấu trúc JSON sạch.")
        print("🎉 TẤT CẢ KIỂM THỬ AI DATA SERVICE & KNOWLEDGE BASE ĐÃ PASS 100%!")
    finally:
        db.close()


if __name__ == "__main__":
    test_cross_check_security_source_code()
    test_pii_isolation_in_schemas()
    test_knowledge_base_files_exist()
    test_ai_data_service_functionality_and_token_optimization()
