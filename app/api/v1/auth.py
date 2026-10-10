from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import (
    create_access_token,
    verify_password,
    get_current_user
)
from app.schemas import EmployeeProfileResponse
from app.schemas.common import StandardResponse

router = APIRouter(tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=StandardResponse[TokenData])
@router.post("/auth/login", response_model=StandardResponse[TokenData])
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.Employee).filter(models.Employee.username == req.username.lower()).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác")
    
    access_token = create_access_token({"sub": user.username, "id": user.id, "role": user.role})
    token_data = TokenData(access_token=access_token, token_type="bearer")
    return StandardResponse(
        success=True,
        message="Đăng nhập thành công",
        data=token_data
    )


@router.get("/me", response_model=StandardResponse[EmployeeProfileResponse])
@router.get("/auth/me", response_model=StandardResponse[EmployeeProfileResponse])
def get_my_profile(current_user: models.Employee = Depends(get_current_user)):
    """
    Trả về profile của user đang đăng nhập theo chuẩn Unified API.
    FastAPI + EmployeeProfileResponse tự động gọt bỏ password, cccd.
    """
    profile_data = EmployeeProfileResponse.model_validate(current_user, from_attributes=True)
    return StandardResponse(
        success=True,
        message="Lấy thông tin tài khoản thành công",
        data=profile_data
    )
