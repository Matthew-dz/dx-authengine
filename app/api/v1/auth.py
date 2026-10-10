from typing import List, Dict
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
from app.agent import enforcer, Subject, Resource
from app.schemas.employee import EmployeeProfileResponse
from app.schemas.common import StandardResponse

router = APIRouter(tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UIPermissionsResponse(BaseModel):
    """
    Schema phản hồi phân quyền giao diện động (Bước 5.4 - Unified Experience).
    - menus: Danh sách các tab/module được phép hiển thị trên thanh điều hướng.
    - actions: Danh sách các hành động được phép theo từng tài nguyên (ví dụ: refunds: [create, approve]).
    """
    menus: List[str]
    actions: Dict[str, List[str]]


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
    FastAPI + EmployeeProfileResponse tự động gọt bỏ password, cccd và đảm bảo đầy đủ (avatar, full_name, role).
    """
    profile_data = EmployeeProfileResponse.model_validate(current_user, from_attributes=True)
    return StandardResponse(
        success=True,
        message="Lấy thông tin tài khoản thành công",
        data=profile_data
    )


@router.get("/my-permissions", response_model=StandardResponse[UIPermissionsResponse])
@router.get("/auth/my-permissions", response_model=StandardResponse[UIPermissionsResponse])
def get_my_permissions(current_user: models.Employee = Depends(get_current_user)):
    """
    API Cấu hình UI Động (Bước 5.4 - Unified Experience).
    - Lấy current_user, truy vấn Casbin enforcer để tổng hợp các quyền hợp lệ.
    - Trả về danh sách menus và actions được phép (loại bỏ việc hardcode kiểm tra role dưới client).
    """
    subj = Subject(username=current_user.username, role=current_user.role)
    policies = enforcer.get_policy()

    # Thu thập toàn bộ các quyền hợp lệ của user theo chính sách Casbin
    raw_actions: Dict[str, set] = {}
    for p in policies:
        if len(p) >= 3:
            obj_name = p[1].strip()
            act = p[2].strip()
            if act and enforcer.enforce(subj, Resource(obj_name), act):
                if obj_name not in raw_actions:
                    raw_actions[obj_name] = set()
                raw_actions[obj_name].add(act)

    menus: List[str] = []
    actions: Dict[str, List[str]] = {}

    # 1. Trụ cột Dashboard (BFF)
    if "dashboard" in raw_actions or "analytics" in raw_actions:
        menus.append("dashboard")
        actions["dashboard"] = sorted(list(raw_actions.get("dashboard", set()) | raw_actions.get("analytics", set())))

    # 2. Quản lý Đơn hàng (Orders)
    if "order" in raw_actions or "transaction" in raw_actions:
        menus.append("orders")
        order_acts = set(raw_actions.get("order", set()))
        if "transaction" in raw_actions:
            order_acts.update(raw_actions["transaction"])
        actions["orders"] = sorted(list(order_acts))

    # 3. Yêu cầu hoàn tiền (Refunds)
    if "refund" in raw_actions:
        menus.append("refunds")
        actions["refunds"] = sorted(list(raw_actions["refund"]))

    # 4. Trợ lý AI Assistant (AI)
    # Mọi người dùng hợp lệ hoặc có quyền ai đều có menu AI
    if "ai" in raw_actions or current_user.role in ["admin", "manager", "staff_sales", "employee", "sale"]:
        menus.append("ai")
        actions["ai"] = sorted(list(raw_actions.get("ai", {"read", "chat"})))

    # 5. Quản lý Nhân sự (Employees) - chỉ dành cho admin hoặc người có quyền employee:read
    if "employee" in raw_actions:
        menus.append("employees")
        actions["employees"] = sorted(list(raw_actions["employee"]))

    # 6. Nhật ký kiểm toán (Audit Logs)
    if "audit_log" in raw_actions:
        menus.append("audit_logs")
        actions["audit_logs"] = sorted(list(raw_actions["audit_log"]))

    # 7. Cài đặt hệ thống (System / Policy)
    if "role" in raw_actions or "policy" in raw_actions:
        menus.append("system")
        actions["system"] = sorted(list(raw_actions.get("role", set()) | raw_actions.get("policy", set())))

    return StandardResponse(
        success=True,
        message="Lấy danh sách quyền hạn UI thành công",
        data=UIPermissionsResponse(
            menus=menus,
            actions=actions
        )
    )
