import os
import sys
import json
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app import models
from app.schemas_ai import (
    AIRecommendationResponse,
    CreateRefundArgs,
    ApproveRefundArgs,
    RejectRefundArgs,
    ExecutePendingActionRequest
)
from app.services.ai_tools import SecureAITools
from app.services.ai_service import (
    chat_with_ai,
    AGENTIC_SYSTEM_INSTRUCTION,
    AIService
)
from app.security import create_access_token

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def get_test_fixtures():
    db = SessionLocal()
    # 1. Admin (có quyền approve, reject, create)
    admin_emp = db.query(models.Employee).filter_by(username="write_admin").first()
    if not admin_emp:
        admin_emp = models.Employee(
            username="write_admin",
            password="hashed_password",
            role="admin"
        )
        db.add(admin_emp)
        db.commit()
        db.refresh(admin_emp)

    # 2. Staff Sales (có quyền create, process nhưng KHÔNG có quyền approve/reject)
    staff_emp = db.query(models.Employee).filter_by(username="write_staff").first()
    if not staff_emp:
        staff_emp = models.Employee(
            username="write_staff",
            password="hashed_password",
            role="staff_sales"
        )
        db.add(staff_emp)
        db.commit()
        db.refresh(staff_emp)

    # 3. Intern (không có quyền gì trên refund)
    intern_emp = db.query(models.Employee).filter_by(username="write_intern").first()
    if not intern_emp:
        intern_emp = models.Employee(
            username="write_intern",
            password="hashed_password",
            role="intern"
        )
        db.add(intern_emp)
        db.commit()
        db.refresh(intern_emp)

    # 4. Customer & Orders
    cust = db.query(models.Customer).filter_by(id=8888).first()
    if not cust:
        cust = models.Customer(
            id=8888,
            full_name="Nguyen Van A",
            email="nguyenvana@example.com",
            phone="0912345678"
        )
        db.add(cust)
        db.commit()

    order1 = db.query(models.Order).filter_by(id=5001).first()
    if not order1:
        order1 = models.Order(
            id=5001,
            customer_id=cust.id,
            product_name="iPhone 15 Pro",
            price=1200.0,
            status="DELIVERED",
            order_date=datetime.utcnow()
        )
        db.add(order1)
        db.commit()

    order2 = db.query(models.Order).filter_by(id=5002).first()
    if not order2:
        order2 = models.Order(
            id=5002,
            customer_id=cust.id,
            product_name="Dell XPS 13",
            price=1500.0,
            status="DELIVERED",
            order_date=datetime.utcnow()
        )
        db.add(order2)
        db.commit()

    return {
        "db": db,
        "admin": admin_emp,
        "staff": staff_emp,
        "intern": intern_emp,
        "order1_id": 5001,
        "order2_id": 5002
    }


def test_ai_audit_log_expanded_columns():
    """Kiểm tra: Bảng AIAuditLog mở rộng đầy đủ các cột metadata."""
    cols = {c.name for c in models.AIAuditLog.__table__.columns}
    required = {"ai_session_id", "tool_name", "action_status", "execution_time", "user_id", "action_type"}
    assert required.issubset(cols), f"AIAuditLog thiếu cột: {required - cols}"
    print(" -> test_ai_audit_log_expanded_columns passed!")


def test_create_refund_request_casbin_and_business_rules():
    """Kiểm tra: create_refund_request bọc lót Pydantic, check quyền Casbin, và xử lý an toàn không dùng raise."""
    ctx = get_test_fixtures()
    db = ctx["db"]
    try:
        # 1. Intern không có quyền create -> Thất bại, không dùng raise
        tools_intern = SecureAITools(db=db, current_user=ctx["intern"], session_id="sess_001")
        args = CreateRefundArgs(order_id=ctx["order1_id"], reason="Lỗi pin sạc không vào")
        res_fail = tools_intern.create_refund_request(args)
        assert res_fail.startswith("Thất bại"), f"Kỳ vọng thất bại nhưng nhận: {res_fail}"
        assert "không có quyền" in res_fail

        # Kiểm tra audit log thất bại
        audit_fail = db.query(models.AIAuditLog).filter(
            models.AIAuditLog.user_id == ctx["intern"].id,
            models.AIAuditLog.tool_name == "create_refund_request"
        ).order_by(models.AIAuditLog.id.desc()).first()
        assert audit_fail is not None
        assert audit_fail.action_status == "FAILED"
        assert audit_fail.ai_session_id == "sess_001"
        assert audit_fail.execution_time is not None

        # 2. Staff có quyền create -> Thành công
        tools_staff = SecureAITools(db=db, current_user=ctx["staff"], session_id="sess_002")
        # Xóa refund cũ của order1 nếu có để test sạch
        db.query(models.RefundRequest).filter_by(order_id=ctx["order1_id"]).delete()
        db.commit()

        res_ok = tools_staff.create_refund_request(args)
        assert res_ok.startswith("Thành công"), f"Kỳ vọng thành công nhưng nhận: {res_ok}"
        assert f"đơn hàng #{ctx['order1_id']}" in res_ok

        # Kiểm tra record trong DB
        created_refund = db.query(models.RefundRequest).filter_by(order_id=ctx["order1_id"]).first()
        assert created_refund is not None
        assert created_refund.reason == "Lỗi pin sạc không vào"
        assert created_refund.status == models.RefundState.PENDING

        # Kiểm tra audit log thành công
        audit_ok = db.query(models.AIAuditLog).filter(
            models.AIAuditLog.user_id == ctx["staff"].id,
            models.AIAuditLog.tool_name == "create_refund_request"
        ).order_by(models.AIAuditLog.id.desc()).first()
        assert audit_ok is not None
        assert audit_ok.action_status == "SUCCESS"
        assert audit_ok.ai_session_id == "sess_002"

        # 3. Tạo lại cùng đơn hàng khi đang PENDING -> Báo lỗi trùng lặp thân thiện
        res_dup = tools_staff.create_refund_request(args)
        assert res_dup.startswith("Thất bại")
        assert "đang chờ xử lý" in res_dup

        print(" -> test_create_refund_request_casbin_and_business_rules passed!")
    finally:
        db.close()


def test_approve_refund_tool_and_permissions():
    """Kiểm tra: approve_refund kiểm soát quyền Casbin (chỉ Admin/Manager), cập nhật trạng thái."""
    ctx = get_test_fixtures()
    db = ctx["db"]
    try:
        # Tạo refund mẫu trạng thái PENDING
        db.query(models.RefundRequest).filter_by(order_id=ctx["order2_id"]).delete()
        db.commit()
        sample_refund = models.RefundRequest(
            order_id=ctx["order2_id"],
            employee_id=ctx["staff"].id,
            reason="Màn hình bị nứt do vận chuyển",
            status=models.RefundState.PENDING,
            amount=1500.0
        )
        db.add(sample_refund)
        db.commit()
        db.refresh(sample_refund)

        # 1. Staff sales cố tình duyệt -> Bị Casbin chặn, không raise exception
        tools_staff = SecureAITools(db=db, current_user=ctx["staff"], session_id="sess_approve_fail")
        approve_args = ApproveRefundArgs(refund_id=sample_refund.id, notes="Duyệt nhanh")
        res_denied = tools_staff.approve_refund(approve_args)
        assert res_denied.startswith("Thất bại")
        assert "không có quyền" in res_denied

        audit_denied = db.query(models.AIAuditLog).filter(
            models.AIAuditLog.user_id == ctx["staff"].id,
            models.AIAuditLog.tool_name == "approve_refund"
        ).order_by(models.AIAuditLog.id.desc()).first()
        assert audit_denied is not None
        assert audit_denied.action_status == "FAILED"

        # 2. Admin duyệt -> Thành công: Đã cập nhật trạng thái.
        tools_admin = SecureAITools(db=db, current_user=ctx["admin"], session_id="sess_approve_ok")
        res_approved = tools_admin.approve_refund(approve_args)
        assert res_approved == "Thành công: Đã cập nhật trạng thái."

        # Kiểm tra DB trạng thái đã đổi thành APPROVED
        db.refresh(sample_refund)
        assert sample_refund.status == models.RefundState.APPROVED
        assert sample_refund.order.status == "REFUNDED"

        # 3. Cố tình duyệt lại khi đã APPROVED -> Báo thất bại vì sai trạng thái
        res_already = tools_admin.approve_refund(approve_args)
        assert res_already.startswith("Thất bại")
        assert "không thể phê duyệt" in res_already

        print(" -> test_approve_refund_tool_and_permissions passed!")
    finally:
        db.close()


def test_reject_refund_tool_and_permissions():
    """Kiểm tra: reject_refund kiểm soát quyền Casbin, cập nhật trạng thái REJECTED."""
    ctx = get_test_fixtures()
    db = ctx["db"]
    try:
        # Tạo refund mẫu
        ref = models.RefundRequest(
            order_id=ctx["order1_id"],
            employee_id=ctx["staff"].id,
            reason="Khách đổi ý không muốn mua",
            status=models.RefundState.PENDING,
            amount=1200.0
        )
        db.add(ref)
        db.commit()
        db.refresh(ref)

        tools_admin = SecureAITools(db=db, current_user=ctx["admin"])
        reject_args = RejectRefundArgs(refund_id=ref.id, notes="Không áp dụng đổi ý sau khi đã nhận hàng")
        res_rejected = tools_admin.reject_refund(reject_args)
        assert res_rejected == "Thành công: Đã cập nhật trạng thái."

        db.refresh(ref)
        assert ref.status == models.RefundState.REJECTED
        print(" -> test_reject_refund_tool_and_permissions passed!")
    finally:
        db.close()


def test_human_in_the_loop_system_prompt_and_schema():
    """Kiểm tra: System Prompt và Schema AIRecommendationResponse có pending_action."""
    # 1. Kiểm tra System Prompt hướng dẫn không gọi tool trực tiếp cho hành động rủi ro cao
    assert "Nếu người dùng yêu cầu phê duyệt hoặc từ chối hoàn tiền (hành động rủi ro cao)" in AGENTIC_SYSTEM_INSTRUCTION
    assert "BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC GỌI TOOL TRỰC TIẾP" in AGENTIC_SYSTEM_INSTRUCTION
    assert "pending_action" in AGENTIC_SYSTEM_INSTRUCTION

    # 2. Kiểm tra Schema
    resp = AIRecommendationResponse(
        summary="Đang chờ xác nhận từ quản lý",
        recommendation="APPROVE",
        reason="Yêu cầu hợp lệ, cần quản lý xác nhận trên UI",
        confidence=0.95,
        citations=["Refund Policy"],
        pending_action={"tool": "approve_refund", "refund_id": 15}
    )
    dumped = resp.model_dump(mode="json")
    assert "pending_action" in dumped
    assert dumped["pending_action"]["tool"] == "approve_refund"
    assert dumped["pending_action"]["refund_id"] == 15
    print(" -> test_human_in_the_loop_system_prompt_and_schema passed!")


def test_chat_with_ai_human_in_the_loop_pending_action():
    """Kiểm tra: chat_with_ai chặn gọi tool rủi ro cao và trả về pending_action cho giao diện."""
    ctx = get_test_fixtures()
    db = ctx["db"]
    try:
        # Giả lập response từ Gemini chứa pending_action
        final_json = {
            "summary": "Yêu cầu hoàn tiền #25 hợp lệ và cần phê duyệt.",
            "recommendation": "APPROVE",
            "reason": "Sản phẩm lỗi phần cứng được xác nhận trong chính sách bảo hành.",
            "confidence": 0.95,
            "citations": ["Chính sách hoàn tiền"],
            "pending_action": {
                "tool": "approve_refund",
                "refund_id": 25
            }
        }
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_part.text = json.dumps(final_json)

        mock_resp = MagicMock()
        mock_cand = MagicMock()
        mock_cand.content.parts = [mock_part]
        mock_resp.candidates = [mock_cand]

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_resp

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            res = chat_with_ai(
                user_query="Hãy phê duyệt yêu cầu hoàn tiền #25 giúp tôi",
                current_user=ctx["admin"],
                db=db,
                session_id="chat_session_hitl"
            )

            assert isinstance(res, AIRecommendationResponse)
            assert res.pending_action is not None
            assert res.pending_action.get("tool") == "approve_refund"
            assert res.pending_action.get("refund_id") == 25

        print(" -> test_chat_with_ai_human_in_the_loop_pending_action passed!")
    finally:
        db.close()


def test_execute_pending_action_api_endpoint():
    """Kiểm tra: Endpoint POST /api/v1/ai/execute-pending-action thực thi lệnh trực tiếp và tất định (deterministic)."""
    ctx = get_test_fixtures()
    db = ctx["db"]
    try:
        # Tạo một refund request mẫu
        test_refund = models.RefundRequest(
            order_id=ctx["order1_id"],
            employee_id=ctx["staff"].id,
            reason="Hàng bị vỡ khi giao",
            status=models.RefundState.PENDING,
            amount=500.0
        )
        db.add(test_refund)
        db.commit()
        db.refresh(test_refund)

        # 1. Gọi với user Admin (có quyền approve)
        token_admin = create_access_token(data={"sub": ctx["admin"].username})
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        payload = {
            "action": {
                "tool": "approve_refund",
                "refund_id": test_refund.id,
                "notes": "Xác nhận duyệt từ giao diện người dùng"
            }
        }

        resp = client.post(
            "/api/v1/ai/execute-pending-action",
            json=payload,
            headers=headers_admin
        )
        assert resp.status_code == 200, f"Lỗi API: {resp.text}"
        data = resp.json()
        assert data["status"] == "success"
        assert data["tool"] == "approve_refund"
        assert "Đã cập nhật trạng thái" in data["message"]

        # Kiểm tra trạng thái DB đã đổi thành APPROVED
        db.refresh(test_refund)
        assert test_refund.status == models.RefundState.APPROVED

        # 2. Gọi lại với user Staff (không có quyền approve) trên một refund mới
        new_refund = models.RefundRequest(
            order_id=ctx["order2_id"],
            employee_id=ctx["staff"].id,
            reason="Khách phàn nàn giao chậm",
            status=models.RefundState.PENDING,
            amount=200.0
        )
        db.add(new_refund)
        db.commit()
        db.refresh(new_refund)

        token_staff = create_access_token(data={"sub": ctx["staff"].username})
        headers_staff = {"Authorization": f"Bearer {token_staff}"}

        payload_staff = {
            "tool": "approve_refund",
            "refund_id": new_refund.id
        }
        resp_staff = client.post(
            "/api/v1/ai/execute-pending-action",
            json=payload_staff,
            headers=headers_staff
        )
        assert resp_staff.status_code == 200
        data_staff = resp_staff.json()
        assert data_staff["status"] == "failed"
        assert "không có quyền" in data_staff["message"]

        # Đảm bảo trạng thái vẫn là PENDING
        db.refresh(new_refund)
        assert new_refund.status == models.RefundState.PENDING

        print(" -> test_execute_pending_action_api_endpoint passed!")
    finally:
        db.close()


if __name__ == "__main__":
    print("\n================ BẮT ĐẦU KIỂM THỬ AGENTIC AI BƯỚC 4.5 (WRITE-TOOLS & HUMAN-IN-THE-LOOP) ================")
    test_ai_audit_log_expanded_columns()
    test_create_refund_request_casbin_and_business_rules()
    test_approve_refund_tool_and_permissions()
    test_reject_refund_tool_and_permissions()
    test_human_in_the_loop_system_prompt_and_schema()
    test_chat_with_ai_human_in_the_loop_pending_action()
    test_execute_pending_action_api_endpoint()
    print("\n🎉 TẤT CẢ 7 KIỂM THỬ BƯỚC 4.5 ĐÃ HOÀN TẤT VÀ ĐẠT 100%!")
