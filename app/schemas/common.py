from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, ConfigDict, model_serializer

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Khuôn mẫu phản hồi thống nhất cho toàn bộ hệ thống API theo chuẩn DX-OS.
    Format chuẩn:
    {
        "success": bool,
        "message": str,
        "data": Optional[T]
    }
    """
    success: bool
    message: str
    data: Optional[T] = None

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    @model_serializer(mode="wrap")
    def _serialize_wrapper(self, handler):
        res = handler(self)
        # Giữ tính tương thích ngược cho các client cũ đọc trực tiếp trường của data ở root level
        if hasattr(self.data, "model_dump"):
            d = self.data.model_dump(mode="json")
            for k, v in d.items():
                if k not in res:
                    res[k] = v
        elif isinstance(self.data, dict):
            for k, v in self.data.items():
                if k not in res:
                    res[k] = v
        return res

    @classmethod
    def ok(cls, data: Optional[T] = None, message: str = "Thành công") -> "StandardResponse[T]":
        """Helper khởi tạo nhanh response thành công."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str = "Thất bại", data: Optional[T] = None) -> "StandardResponse[T]":
        """Helper khởi tạo nhanh response thất bại."""
        return cls(success=False, message=message, data=data)
