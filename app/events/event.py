from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """
    Base Event Model cho kiến trúc Event-Driven (Bước 5.2).
    """
    event_type: str
    entity_id: int
    user_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RefundApprovedEvent(BaseEvent):
    """
    Sự kiện được phát tán khi yêu cầu hoàn tiền được phê duyệt thành công.
    Tách rời Business Logic khỏi tác vụ phụ trợ (Audit, Email, Analytics).
    """
    event_type: str = "RefundApproved"
    data: Dict[str, Any] = Field(default_factory=dict)
