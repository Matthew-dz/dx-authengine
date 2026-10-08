import casbin
import os
import json
from pydantic import BaseModel
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv

# Tải biến môi trường (ví dụ GEMINI_API_KEY) từ file .env
load_dotenv()

# Khởi tạo Casbin Enforcer với file model và policy
enforcer = casbin.Enforcer("casbin_config/model.conf", "casbin_config/policy.csv")
enforcer.add_function("float", float)

class RefundDecision(BaseModel):
    is_approved: bool
    reason: str
    email_template: str

def check_abac_policy(username: str, resource: str, action: str, order_days_old: int) -> bool:
    """
    Công cụ để kiểm tra quyền ABAC.
    Trả về True nếu người dùng được phép thực hiện hành động, ngược lại False.
    """
    return enforcer.enforce(username, resource, action, order_days_old)

async def process_refund_request(username: str, resource: str, action: str, order_days_old: int, customer_email: str, customer_name: str) -> RefundDecision:
    # Bước 1: Hệ thống kiểm tra luật cứng (Symbolic / ABAC) bằng Casbin trước
    is_allowed = check_abac_policy(username, resource, action, order_days_old)
    
    # Bước 2: Truyền kết quả luật cứng cho AI (Neuro) để sinh ra phản hồi tự nhiên
    prompt = f"""
Bạn là hệ thống xét duyệt hoàn tiền tự động. Hãy xử lý yêu cầu hoàn tiền sau:
- Nhân viên duyệt (nội bộ): {username}
- Tên Khách hàng: {customer_name}
- Email Khách hàng: {customer_email}
- Resource: {resource}
- Action: {action}
- Order days old: {order_days_old} ngày

Hệ thống bảo mật ABAC đã kiểm tra luật và kết quả là: {"ĐƯỢC PHÉP (ALLOW)" if is_allowed else "TỪ CHỐI (DENY)"}.

Nhiệm vụ của bạn:
1. is_approved: Phải bằng {str(is_allowed).lower()}.
2. reason: Hãy viết 1-2 câu giải thích cho nhân viên ({username}) biết tại sao họ duyệt hoặc từ chối đơn hàng này (dựa trên số ngày).
4. email_template: Viết một đoạn email ĐỂ GỬI CHO KHÁCH HÀNG ({customer_email}). Bắt buộc chào tên khách hàng (VD: Xin chào anh/chị {customer_name},...), TUYỆT ĐỐI KHÔNG chào tên nhân viên nội bộ ({username}). Email phải thân thiện, thông báo kết quả duyệt/từ chối và lý do.

Hãy trả về DUY NHẤT một chuỗi JSON chuẩn (không kèm theo markdown như ```json hay bất kỳ văn bản nào khác) với cấu trúc:
{{
    "is_approved": true/false,
    "reason": "...",
    "email_template": "..."
}}
"""
    
    config = LocalAgentConfig(
        model="gemini-3.5-flash-lite",
        system_instructions="Bạn là AI xét duyệt hoàn tiền. Chỉ trả về chuỗi JSON chuẩn.",
        api_key=os.getenv("GEMINI_API_KEY")
    )
    
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        # Sử dụng text() là phương thức an toàn nhất
        text_resp = await response.text()
        
    # Xử lý text để loại bỏ markdown nếu AI lỡ sinh ra
    text_resp = text_resp.strip()
    if text_resp.startswith("```json"):
        text_resp = text_resp[7:]
    if text_resp.endswith("```"):
        text_resp = text_resp[:-3]
        
    # Parse JSON sang Pydantic Model
    data = json.loads(text_resp.strip())
    return RefundDecision(**data)
