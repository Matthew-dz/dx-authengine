from pydantic import BaseModel
from typing import Optional

class EmployeeResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    position: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class CustomerResponse(BaseModel):
    id: int
    full_name: str
    email: str

    class Config:
        from_attributes = True
