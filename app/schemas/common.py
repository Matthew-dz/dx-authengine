from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, model_serializer

T = TypeVar("T")

class StandardResponse(BaseModel, Generic[T]):
    """
    Generic Standard Response model theo chuẩn Unified API (Bước 5.1).
    Bọc mọi dữ liệu trả về với success, message và data, đồng thời tương thích ngược.
    """
    success: bool
    message: str
    data: Optional[T] = None

    @model_serializer(mode="wrap")
    def _serialize_wrapper(self, handler):
        res = handler(self)
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
