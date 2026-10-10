from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class RecentOrderForAI(BaseModel):
    """
    Thông tin đơn hàng tóm tắt dành cho LLM Context (De-identified).
    TUYỆT ĐỐI KHÔNG chứa thông tin định danh cá nhân (PII) như tên khách, email, sđt, địa chỉ.
    """
    order_id: int
    product_name: str
    price: float
    order_date: Optional[datetime] = None
    status: str

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RefundContextForAI(BaseModel):
    """
    Ngữ cảnh yêu cầu hoàn tiền cung cấp cho AI để hỗ trợ ra quyết định.
    Chỉ chứa dữ liệu giao dịch cốt lõi, không chứa thông tin PII của khách hàng hay nhân viên.
    """
    refund_id: int
    order_id: int
    amount: Optional[float] = None
    status: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CustomerHistoryForAI(BaseModel):
    """
    Lịch sử hành vi mua sắm và hoàn tiền của khách hàng dành cho LLM đánh giá rủi ro.
    Tối đa 5 đơn hàng gần nhất để tối ưu Token Window và bảo mật dữ liệu.
    """
    total_orders: int
    total_refunds_requested: int
    recent_orders: List[RecentOrderForAI] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AIRecommendationResponse(BaseModel):
    """
    Kết quả khuyến nghị có cấu trúc (Structured JSON) từ AI Assistant.
    Quy định vai trò: Chỉ phân tích nghiệp vụ, không thay thế quyết định con người.
    """
    summary: str
    recommendation: str
    reason: str
    confidence: float
    citations: List[str] = Field(default_factory=list, description="Danh sách tên file và tiêu đề được dùng làm căn cứ")
    pending_action: Optional[Dict[str, Any]] = Field(default=None, description="Hành động rủi ro cao chờ người dùng xác nhận trên giao diện (Human-in-the-loop)")

    model_config = ConfigDict(extra="forbid")


class AIChatRequest(BaseModel):
    """
    Yêu cầu trò chuyện tương tác với Agentic AI Assistant.
    """
    query: str = Field(..., description="Câu hỏi hoặc yêu cầu nghiệp vụ của người dùng")
    session_id: Optional[str] = Field(None, description="Mã phiên làm việc với AI Assistant")


class CreateRefundArgs(BaseModel):
    """Schema tham số đầu vào cho tool create_refund_request."""
    order_id: int = Field(..., description="Mã đơn hàng cần tạo yêu cầu hoàn tiền")
    reason: str = Field(..., description="Lý do chi tiết yêu cầu hoàn tiền")
    amount: Optional[float] = Field(None, description="Số tiền hoàn lại mong muốn")


class ApproveRefundArgs(BaseModel):
    """Schema tham số đầu vào cho tool approve_refund."""
    refund_id: int = Field(..., description="Mã yêu cầu hoàn tiền cần phê duyệt")
    notes: Optional[str] = Field(None, description="Ghi chú nghiệp vụ khi phê duyệt")


class RejectRefundArgs(BaseModel):
    """Schema tham số đầu vào cho tool reject_refund."""
    refund_id: int = Field(..., description="Mã yêu cầu hoàn tiền cần từ chối")
    notes: Optional[str] = Field(None, description="Lý do hoặc ghi chú từ chối")


class ExecutePendingActionRequest(BaseModel):
    """
    Yêu cầu thực thi trực tiếp hành động chờ xác nhận (Human-in-the-loop).
    Không thông qua LLM để đảm bảo tính tất định (deterministic).
    """
    tool: Optional[str] = Field(None, description="Tên công cụ cần thực thi (create_refund_request, approve_refund, reject_refund)")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Bộ tham số truyền cho công cụ")
    action: Optional[Dict[str, Any]] = Field(None, description="Đối tượng pending_action nhận từ AI response")
    refund_id: Optional[int] = Field(None, description="ID yêu cầu hoàn tiền (tiện ích shortcut)")
    order_id: Optional[int] = Field(None, description="ID đơn hàng (tiện ích shortcut)")
    reason: Optional[str] = Field(None, description="Lý do hoàn tiền (tiện ích shortcut)")
    notes: Optional[str] = Field(None, description="Ghi chú (tiện ích shortcut)")
    session_id: Optional[str] = Field(None, description="Mã session nếu có")


