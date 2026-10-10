import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.schemas.ai import AIChatRequest
from app.schemas.employee import EmployeeProfileResponse
from app.services.ai_service import chat_with_ai
from app.security import create_access_token

client = TestClient(app)


def test_my_permissions_api_admin_and_staff():
    """
    1. Kiểm thử API GET /api/v1/auth/my-permissions:
       - Role admin: Đầy đủ menus (dashboard, orders, refunds, ai, employees, audit_logs, system).
       - Role staff: Chỉ có các menu nghiệp vụ, không có employees và system.
       - Actions: Phân biệt rõ approve/reject cho admin và create/process cho staff.
    """
    db = SessionLocal()
    try:
        admin = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        staff = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        assert admin is not None and staff is not None

        admin_token = create_access_token({"sub": admin.username, "id": admin.id, "role": admin.role})
        staff_token = create_access_token({"sub": staff.username, "id": staff.id, "role": staff.role})

        # Test với Admin
        resp_admin = client.get("/api/v1/auth/my-permissions", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp_admin.status_code == 200
        data_admin = resp_admin.json()
        assert data_admin["success"] is True
        perms_admin = data_admin["data"]
        assert "dashboard" in perms_admin["menus"]
        assert "orders" in perms_admin["menus"]
        assert "refunds" in perms_admin["menus"]
        assert "ai" in perms_admin["menus"]
        assert "employees" in perms_admin["menus"]
        assert "system" in perms_admin["menus"]
        assert "approve" in perms_admin["actions"]["refunds"]

        # Test với Staff Sales
        resp_staff = client.get("/api/v1/auth/my-permissions", headers={"Authorization": f"Bearer {staff_token}"})
        assert resp_staff.status_code == 200
        data_staff = resp_staff.json()
        assert data_staff["success"] is True
        perms_staff = data_staff["data"]
        assert "dashboard" in perms_staff["menus"]
        assert "orders" in perms_staff["menus"]
        assert "refunds" in perms_staff["menus"]
        assert "ai" in perms_staff["menus"]
        # Staff không có quyền quản lý nhân sự hay cấu hình hệ thống
        assert "employees" not in perms_staff["menus"]
        assert "system" not in perms_staff["menus"]
        assert "create" in perms_staff["actions"]["refunds"]
        print(" -> test_my_permissions_api_admin_and_staff passed!")
    finally:
        db.close()


def test_unified_identity_api_me():
    """
    2. Kiểm thử API GET /api/v1/me và GET /api/v1/users/me:
       - Trả về StandardResponse[EmployeeProfileResponse].
       - Chứa đầy đủ avatar, full_name, role.
       - Không lộ mật khẩu hay CCCD.
    """
    db = SessionLocal()
    try:
        admin = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        staff = db.query(models.Employee).filter(models.Employee.role == "staff_sales").first()
        admin_token = create_access_token({"sub": admin.username, "id": admin.id, "role": admin.role})
        staff_token = create_access_token({"sub": staff.username, "id": staff.id, "role": staff.role})

        # Test GET /api/v1/me
        resp1 = client.get("/api/v1/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["success"] is True
        prof1 = body1["data"]
        assert prof1["username"] == admin.username
        assert prof1["full_name"] == (admin.full_name or admin.username or "User")
        assert prof1["role"] == admin.role
        assert "avatar" in prof1 and prof1["avatar"].startswith("https://")
        assert "password" not in prof1
        assert "cccd" not in prof1

        # Test GET /api/v1/users/me
        resp2 = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {staff_token}"})
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["success"] is True
        prof2 = body2["data"]
        assert prof2["username"] == staff.username
        assert prof2["full_name"] == (staff.full_name or staff.username or "User")
        assert prof2["role"] == staff.role
        assert "avatar" in prof2 and prof2["avatar"].startswith("https://")

        print(" -> test_unified_identity_api_me passed!")
    finally:
        db.close()


def test_contextual_ai_assistant_auto_tool_injection():
    """
    3. Kiểm thử Contextual AI Assistant (Bước 5.4):
       - Schema AIChatRequest nhận context_type và context_id.
       - AI Service tự động gọi ngầm Data Tool (get_refund) và ép vào System Prompt trước khi gửi LLM.
       - Tự động nhận diện pending_action từ context_id khi người dùng yêu cầu phê duyệt ngắn gọn.
    """
    db = SessionLocal()
    try:
        admin = db.query(models.Employee).filter(models.Employee.role == "admin").first()
        refund = db.query(models.RefundRequest).first()
        assert admin is not None and refund is not None

        # Kiểm thử schema
        req = AIChatRequest(
            query="Đủ điều kiện duyệt không?",
            context_type="refund",
            context_id=refund.id
        )
        assert req.context_type == "refund"
        assert req.context_id == refund.id

        # Mock Gemini GenerativeModel để kiểm tra system_instruction đã được ép context
        captured_instruction = {}

        def fake_generative_model(model_name, system_instruction, generation_config, tools):
            captured_instruction["system_instruction"] = system_instruction
            mock_model = MagicMock()
            mock_chat = MagicMock()
            mock_response = MagicMock()
            mock_response.candidates = []
            mock_chat.send_message.return_value = mock_response
            mock_model.start_chat.return_value = mock_chat
            return mock_model

        with patch("google.generativeai.GenerativeModel", side_effect=fake_generative_model):
            res = chat_with_ai(
                user_query="Duyệt đơn hoàn tiền này giúp tôi",
                current_user=admin,
                db=db,
                context_type="refund",
                context_id=refund.id
            )

            # Xác minh system prompt đã được bổ sung Local Context
            sys_instr = captured_instruction.get("system_instruction", "")
            assert "[NGỮ CẢNH CỤC BỘ HIỆN TẠI (LOCAL CONTEXT)]" in sys_instr
            assert f"<business_data type=\"refund\" id=\"{refund.id}\">" in sys_instr
            assert "Refund Database" in res.citations

            # Xác minh cơ chế pending_action tự động liên kết đúng context_id
            assert res.pending_action is not None
            assert res.pending_action["tool"] == "approve_refund"
            assert res.pending_action["refund_id"] == refund.id
            assert res.recommendation == "APPROVE"

        print(" -> test_contextual_ai_assistant_auto_tool_injection passed!")
    finally:
        db.close()


if __name__ == "__main__":
    print("================ KIỂM THỬ UNIFIED EXPERIENCE (BƯỚC 5.4) ================")
    test_my_permissions_api_admin_and_staff()
    test_unified_identity_api_me()
    test_contextual_ai_assistant_auto_tool_injection()
    print("🎉 TẤT CẢ KIỂM THỬ UNIFIED EXPERIENCE ĐÃ PASS 100%!")
