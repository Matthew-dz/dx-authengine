import os
import sys
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app import models
from app.schemas_ai import AIRecommendationResponse, AIChatRequest
from app.services.ai_tools import SecureAITools
from app.services.ai_service import (
    chat_with_ai,
    AGENTIC_SYSTEM_INSTRUCTION,
    AIService
)
from app.security import create_access_token

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def get_test_context():
    db = SessionLocal()
    # 1. Nhân viên kiểm thử
    authorized_emp = db.query(models.Employee).filter_by(username="agentic_admin").first()
    if not authorized_emp:
        authorized_emp = models.Employee(
            username="agentic_admin",
            password="hashed_pw",
            role="admin"
        )
        db.add(authorized_emp)
        db.commit()
        db.refresh(authorized_emp)

    unauthorized_emp = db.query(models.Employee).filter_by(username="agentic_intern").first()
    if not unauthorized_emp:
        unauthorized_emp = models.Employee(
            username="agentic_intern",
            password="hashed_pw",
            role="intern"  # intern không có quyền đọc order hay refund trong policy.csv
        )
        db.add(unauthorized_emp)
        db.commit()
        db.refresh(unauthorized_emp)

    # 2. Khách hàng và Đơn hàng mẫu
    cust = db.query(models.Customer).filter_by(id=999).first()
    if not cust:
        cust = models.Customer(
            id=999,
            full_name="Secret Customer",
            email="secret@example.com",
            phone="0901234567"
        )
        db.add(cust)
        db.commit()

    order = db.query(models.Order).filter_by(id=1001).first()
    if not order:
        order = models.Order(
            id=1001,
            customer_id=cust.id,
            product_name="MacBook Pro M3",
            price=2500.0,
            status="DELIVERED",
            order_date=datetime.utcnow()
        )
        db.add(order)
        db.commit()

    # 3. Yêu cầu hoàn tiền mẫu
    refund = db.query(models.RefundRequest).filter_by(id=2001).first()
    if not refund:
        refund = models.RefundRequest(
            id=2001,
            order_id=1001,
            employee_id=authorized_emp.id,
            reason="Lỗi màn hình sọc",
            status=models.RefundState.PENDING,
            amount=2500.0,
            created_at=datetime.utcnow()
        )
        db.add(refund)
        db.commit()

    return {
        "db": db,
        "authorized": authorized_emp,
        "unauthorized": unauthorized_emp,
        "order_id": 1001,
        "refund_id": 2001
    }


def test_secure_ai_tools_init_validation():
    """Kiểm tra: SecureAITools BẮT BUỘC nhận vào db Session và current_user."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        # 1. Thiếu db -> raise ValueError
        threw_db = False
        try:
            SecureAITools(db=None, current_user=ctx["authorized"])
        except ValueError as e:
            threw_db = True
            assert "SecureAITools bắt buộc" in str(e)
        assert threw_db, "SecureAITools phải raise ValueError khi thiếu db"

        # 2. Thiếu current_user -> raise ValueError
        threw_user = False
        try:
            SecureAITools(db=db, current_user=None)
        except ValueError as e:
            threw_user = True
            assert "SecureAITools bắt buộc" in str(e)
        assert threw_user, "SecureAITools phải raise ValueError khi thiếu current_user"

        # 3. Khởi tạo hợp lệ
        tools = SecureAITools(db=db, current_user=ctx["authorized"])
        assert tools.db == db
        assert tools.current_user == ctx["authorized"]
        print(" -> SecureAITools: Khởi tạo với kiểm tra bắt buộc (db, current_user) thành công.")
    finally:
        db.close()


def test_get_order_casbin_unauthorized():
    """Kiểm tra: Casbin deny -> trả về chuỗi chính xác 'Lỗi: Bạn không có quyền truy cập đơn hàng này.'"""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        tools = SecureAITools(db=db, current_user=ctx["unauthorized"])
        res = tools.get_order(order_id=ctx["order_id"])
        assert res == "Lỗi: Bạn không có quyền truy cập đơn hàng này.", f"Thực tế: {res}"
        print(" -> get_order: Chặn quyền truy cập Casbin (unauthorized) trả về đúng thông báo lỗi.")
    finally:
        db.close()


def test_get_order_authorized_and_audit_log():
    """Kiểm tra: Authorized role đọc order thành công, khử PII, và ghi AIAuditLog."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        tools = SecureAITools(db=db, current_user=ctx["authorized"])
        res = tools.get_order(order_id=ctx["order_id"])

        # Parse kết quả JSON
        data = json.loads(res)
        assert data["order_id"] == ctx["order_id"]
        assert data["product_name"] == "MacBook Pro M3"
        assert data["price"] == 2500.0
        # Đảm bảo không chứa PII
        assert "customer_name" not in data
        assert "customer_email" not in data

        # Kiểm tra bản ghi AIAuditLog
        log = db.query(models.AIAuditLog).filter(
            models.AIAuditLog.user_id == ctx["authorized"].id,
            models.AIAuditLog.action_type == "tool_call"
        ).order_by(models.AIAuditLog.id.desc()).first()

        assert log is not None
        assert log.input_context.get("tool_name") == "get_order"
        assert log.input_context.get("resource_id") == ctx["order_id"]
        assert log.output_result.get("product_name") == "MacBook Pro M3"
        print(" -> get_order: Khử định danh PII và ghi nhận AIAuditLog thành công.")
    finally:
        db.close()


def test_get_refund_casbin_unauthorized():
    """Kiểm tra: Casbin deny cho refund -> 'Lỗi: Bạn không có quyền truy cập yêu cầu hoàn tiền này.'"""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        tools = SecureAITools(db=db, current_user=ctx["unauthorized"])
        res = tools.get_refund(refund_id=ctx["refund_id"])
        assert res == "Lỗi: Bạn không có quyền truy cập yêu cầu hoàn tiền này.", f"Thực tế: {res}"
        print(" -> get_refund: Chặn quyền truy cập Casbin (unauthorized) thành công.")
    finally:
        db.close()


def test_get_refund_authorized_and_audit_log():
    """Kiểm tra: Authorized role đọc refund thành công, và ghi AIAuditLog."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        tools = SecureAITools(db=db, current_user=ctx["authorized"])
        res = tools.get_refund(refund_id=ctx["refund_id"])

        data = json.loads(res)
        assert data["refund_id"] == ctx["refund_id"]
        assert data["order_id"] == ctx["order_id"]
        assert data["reason"] == "Lỗi màn hình sọc"
        assert data["amount"] == 2500.0

        # Kiểm tra bản ghi AIAuditLog
        log = db.query(models.AIAuditLog).filter(
            models.AIAuditLog.user_id == ctx["authorized"].id,
            models.AIAuditLog.action_type == "tool_call"
        ).order_by(models.AIAuditLog.id.desc()).first()

        assert log is not None
        assert log.input_context.get("tool_name") == "get_refund"
        assert log.input_context.get("resource_id") == ctx["refund_id"]
        print(" -> get_refund: Authorized thành công và ghi AIAuditLog chính xác.")
    finally:
        db.close()


def test_search_policy_rag_tool():
    """Kiểm tra: search_policy bọc RAG Service và ghi AIAuditLog."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        tools = SecureAITools(db=db, current_user=ctx["authorized"])

        with patch("app.services.rag_service.RAGService.search_knowledge") as mock_search:
            mock_search.return_value = [
                {
                    "id": "chunk_1",
                    "content": "Sản phẩm đổi trả trong vòng 30 ngày kể từ ngày giao hàng.",
                    "metadata": {"title": "Chính sách hoàn tiền", "filename": "refund_policy.md", "header": "Thời hạn"}
                }
            ]
            res = tools.search_policy(query="thời hạn hoàn tiền")
            assert "Chính sách hoàn tiền" in res
            assert "30 ngày" in res

            # Kiểm tra AIAuditLog
            log = db.query(models.AIAuditLog).filter(
                models.AIAuditLog.user_id == ctx["authorized"].id,
                models.AIAuditLog.action_type == "tool_call"
            ).order_by(models.AIAuditLog.id.desc()).first()

            assert log is not None
            assert log.input_context.get("tool_name") == "search_policy"
            assert log.input_context.get("query") == "thời hạn hoàn tiền"
        print(" -> search_policy: Tích hợp RAG Service làm tool và ghi AIAuditLog thành công.")
    finally:
        db.close()


def test_agentic_system_prompt_adherence():
    """Kiểm tra: System Prompt quy định rõ vai trò và hướng dẫn tra cứu."""
    assert "Bạn là DX-OS AI Assistant." in AGENTIC_SYSTEM_INSTRUCTION
    assert "Bạn có các công cụ để tra cứu chính sách (search_policy) và tra cứu dữ liệu (get_order, get_refund)." in AGENTIC_SYSTEM_INSTRUCTION
    assert "Chỉ trả lời dựa trên dữ liệu công cụ trả về." in AGENTIC_SYSTEM_INSTRUCTION
    assert "Nếu công cụ báo lỗi quyền truy cập, hãy thông báo lịch sự cho người dùng biết họ không đủ thẩm quyền." in AGENTIC_SYSTEM_INSTRUCTION
    print(" -> System Prompt: Nội dung định hướng Agent và bảo mật quyền truy cập đạt chuẩn.")


def test_agent_loop_function_calling_and_output_schema():
    """Kiểm tra: Vòng lặp Agent Loop nhận diện Function Call, gọi tool và trả về AIRecommendationResponse."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        mock_fc = MagicMock()
        mock_fc.name = "get_order"
        mock_fc.args = {"order_id": ctx["order_id"]}

        mock_part_fc = MagicMock()
        mock_part_fc.function_call = mock_fc
        mock_part_fc.text = ""

        mock_resp_1 = MagicMock()
        mock_candidate_1 = MagicMock()
        mock_candidate_1.content.parts = [mock_part_fc]
        mock_resp_1.candidates = [mock_candidate_1]

        final_json = {
            "summary": "Đơn hàng #1001 là MacBook Pro M3 trị giá 2500 USD.",
            "recommendation": "REVIEW",
            "reason": "Đã tra cứu dữ liệu đơn hàng thành công qua SecureAITools",
            "confidence": 0.95,
            "citations": ["Order Database"]
        }
        mock_part_text = MagicMock()
        mock_part_text.function_call = None
        mock_part_text.text = json.dumps(final_json)

        mock_resp_2 = MagicMock()
        mock_candidate_2 = MagicMock()
        mock_candidate_2.content.parts = [mock_part_text]
        mock_resp_2.candidates = [mock_candidate_2]

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_resp_1, mock_resp_2]

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            res = chat_with_ai(
                user_query="Kiểm tra thông tin đơn hàng 1001",
                current_user=ctx["authorized"],
                db=db
            )

            assert isinstance(res, AIRecommendationResponse)
            assert res.summary == final_json["summary"]
            assert res.confidence == 0.95
            assert "Order Database" in res.citations
        print(" -> Agent Loop: Function Calling và ép kiểu AIRecommendationResponse đạt chuẩn.")
    finally:
        db.close()


def test_circuit_breaker_prevents_infinite_loop():
    """Kiểm tra: Bảo vệ ngắt mạch (Circuit Breaker) dừng lại sau tối đa 3 lần gọi tool liên tiếp."""
    ctx = get_test_context()
    db = ctx["db"]
    try:
        mock_fc = MagicMock()
        mock_fc.name = "get_order"
        mock_fc.args = {"order_id": ctx["order_id"]}

        mock_part_fc = MagicMock()
        mock_part_fc.function_call = mock_fc
        mock_part_fc.text = "Đang xử lý tiếp bước..."

        mock_resp = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_fc]
        mock_resp.candidates = [mock_candidate]

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_resp

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            res = chat_with_ai(
                user_query="Thực hiện kiểm tra liên tục",
                current_user=ctx["authorized"],
                db=db
            )

            # 1 lần gọi ban đầu + 3 lần gọi tool response = 4 lần send_message
            assert mock_chat.send_message.call_count == 4
            assert isinstance(res, AIRecommendationResponse)
            assert res.confidence is not None
        print(" -> Circuit Breaker: Ngắt mạch chính xác sau 3 bước gọi hàm liên tiếp, bảo vệ an toàn.")
    finally:
        db.close()


def test_api_chat_endpoint():
    """Kiểm tra: API POST /api/v1/ai/chat tích hợp bảo mật JWT và trả về chuẩn JSON."""
    ctx = get_test_context()
    token = create_access_token(data={"sub": ctx["authorized"].username})
    headers = {"Authorization": f"Bearer {token}"}

    expected_resp = AIRecommendationResponse(
        summary="Đã xử lý câu hỏi qua Agentic AI",
        recommendation="APPROVE",
        reason="Khách hàng đủ điều kiện bảo hành theo chính sách",
        confidence=0.9,
        citations=["Knowledge Base Policy"]
    )

    with patch.object(AIService, "chat_with_ai", return_value=expected_resp):
        response = client.post(
            "/api/v1/ai/chat",
            json={"query": "Kiểm tra quyền và quy định đổi trả"},
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == expected_resp.summary
        assert data["recommendation"] == "APPROVE"
        assert data["confidence"] == 0.9
        assert "Knowledge Base Policy" in data["citations"]
    print(" -> API Endpoint: POST /api/v1/ai/chat hoạt động chính xác với bảo mật JWT.")
    ctx["db"].close()


if __name__ == "__main__":
    print("\n================ BẮT ĐẦU KIỂM THỬ AGENTIC AI (BƯỚC 4.3) ================")
    test_secure_ai_tools_init_validation()
    test_get_order_casbin_unauthorized()
    test_get_order_authorized_and_audit_log()
    test_get_refund_casbin_unauthorized()
    test_get_refund_authorized_and_audit_log()
    test_search_policy_rag_tool()
    test_agentic_system_prompt_adherence()
    test_agent_loop_function_calling_and_output_schema()
    test_circuit_breaker_prevents_infinite_loop()
    test_api_chat_endpoint()
    print("\n🎉 TẤT CẢ 10 KIỂM THỬ AGENTIC AI ĐÃ HOÀN TẤT VÀ ĐẠT 100%!")
