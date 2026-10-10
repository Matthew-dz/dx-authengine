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

class Subject:
    def __init__(self, username: str, role: str):
        self.username = username
        self.role = role

class Resource:
    def __init__(self, name: str, order_days_old: float = 0.0):
        self.name = name
        self.order_days_old = order_days_old

class RefundContent(BaseModel):
    reason: str
    email_template: str

async def generate_refund_content(username: str, order_days_old: int, customer_email: str, customer_name: str, decision: str) -> RefundContent:
    prompt = f"""
Bạn là hệ thống xét duyệt hoàn tiền tự động. Hãy xử lý yêu cầu hoàn tiền sau:
- Nhân viên duyệt (nội bộ): {username}
- Tên Khách hàng: {customer_name}
- Email Khách hàng: {customer_email}
- Order days old: {order_days_old} ngày

Hệ thống đã chốt quyết định là {decision}. Dựa vào dữ liệu khách hàng sau, hãy viết reason (lý do) và email_template (email thông báo).

Nhiệm vụ của bạn:
1. reason: Hãy viết 1-2 câu giải thích cho nhân viên ({username}) biết tại sao đơn hàng này được duyệt (dựa trên số ngày).
2. email_template: Viết một đoạn email ĐỂ GỬI CHO KHÁCH HÀNG ({customer_email}). Bắt buộc chào tên khách hàng (VD: Xin chào anh/chị {customer_name},...), TUYỆT ĐỐI KHÔNG chào tên nhân viên nội bộ ({username}). Email phải thân thiện, thông báo kết quả {decision} và lý do.

Hãy trả về DUY NHẤT một chuỗi JSON chuẩn (không kèm theo markdown như ```json hay bất kỳ văn bản nào khác) với cấu trúc:
{{
    "reason": "...",
    "email_template": "..."
}}
"""
    
    config = LocalAgentConfig(
        model="gemini-3.5-flash-lite",
        system_instructions="Bạn là AI hỗ trợ viết nội dung hoàn tiền. Chỉ trả về chuỗi JSON chuẩn.",
        api_key=os.getenv("GEMINI_API_KEY")
    )
    
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        text_resp = await response.text()
        
    # Xử lý text để loại bỏ markdown nếu AI lỡ sinh ra
    text_resp = text_resp.strip()
    if text_resp.startswith("```json"):
        text_resp = text_resp[7:]
    if text_resp.endswith("```"):
        text_resp = text_resp[:-3]
        
    # Parse JSON sang Pydantic Model
    data = json.loads(text_resp.strip())
    return RefundContent(**data)
