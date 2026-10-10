from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    position: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class EmployeeProfileResponse(BaseModel):
    """
    Schema định danh chuẩn cho API /me (Bước 5.4 - Unified Experience).
    - Trả về đầy đủ: avatar, full_name, role để hiển thị đồng nhất trên Header.
    - Bảo mật tuyệt đối: KHÔNG bao giờ trả về password hay cccd.
    """
    id: int
    username: str
    full_name: Optional[str] = ""
    role: str
    position: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: str = Field(default="")

    @field_validator("full_name", mode="before")
    @classmethod
    def set_default_full_name(cls, v, info):
        if v is not None and str(v).strip():
            return str(v).strip()
        data = info.data if hasattr(info, "data") else {}
        return data.get("username") or "User"

    @field_validator("avatar", mode="before")
    @classmethod
    def set_default_avatar(cls, v, info):
        if v:
            return v
        data = info.data if hasattr(info, "data") else {}
        name = data.get("full_name") or data.get("username") or "User"
        return f"https://ui-avatars.com/api/?name={name}&background=0D8ABC&color=fff"

    model_config = ConfigDict(from_attributes=True)


class CustomerResponse(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class EmployeePerformanceResponse(BaseModel):
    """Schema thống kê hiệu suất xử lý đơn của nhân viên."""
    employee_name: str
    processed: int
    approved: int
    rejected: int
    average_processing_time_minutes: float
    employee_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
