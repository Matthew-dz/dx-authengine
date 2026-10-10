from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.agent import enforcer, Subject, Resource
from app.security import get_current_user, verify_password, get_password_hash
from app.schemas.common import StandardResponse

router = APIRouter(tags=["System"])


class RoleUpdateRequest(BaseModel):
    username: str
    new_role: str


class PolicyUpdateRequest(BaseModel):
    new_limit: int


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.get("/roles", response_model=StandardResponse[List[Dict[str, str]]])
def get_roles(current_user: models.Employee = Depends(get_current_user)):
    """Lấy danh sách mapping user-role hiện tại từ memory của Casbin."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("role"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    policies = enforcer.get_grouping_policy()
    data = [{"username": p[0], "role": p[1]} for p in policies]
    return StandardResponse(
        success=True,
        message="Lấy danh sách vai trò thành công",
        data=data
    )


@router.put("/roles", response_model=StandardResponse[Dict[str, str]])
def update_role(
    req: RoleUpdateRequest,
    current_user: models.Employee = Depends(get_current_user)
):
    """Cập nhật vai trò người dùng (Chỉ Admin)."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("role"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "write"):
        raise HTTPException(status_code=403, detail="Chỉ có tài khoản 'admin' mới có quyền thay đổi Role.")
        
    enforcer.delete_roles_for_user(req.username)
    enforcer.add_role_for_user(req.username, req.new_role)
    enforcer.save_policy()
    return StandardResponse(
        success=True,
        message=f"Cập nhật thành công quyền của {req.username} thành {req.new_role}",
        data={"username": req.username, "role": req.new_role}
    )


@router.get("/settings/policy", response_model=StandardResponse[Dict[str, int]])
def get_policy_limit(current_user: models.Employee = Depends(get_current_user)):
    """Lấy giới hạn ngày cho phép hoàn tiền theo chính sách hệ thống."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("policy"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    policies = enforcer.get_policy()
    for p in policies:
        if len(p) >= 4 and p[0] == "staff_sales" and p[1] == "transaction" and p[2] == "refund":
            return StandardResponse(
                success=True,
                message="Lấy giới hạn chính sách thành công",
                data={"limit": int(p[3])}
            )
    return StandardResponse(
        success=True,
        message="Lấy giới hạn chính sách mặc định",
        data={"limit": 15}
    )


@router.put("/settings/policy", response_model=StandardResponse[Dict[str, int]])
def update_policy_limit(
    req: PolicyUpdateRequest,
    current_user: models.Employee = Depends(get_current_user)
):
    """Cập nhật giới hạn ngày cho phép hoàn tiền."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("policy"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    old_policies = enforcer.get_filtered_policy(0, "staff_sales", "transaction", "refund")
    for old_policy in old_policies:
        enforcer.remove_policy(*old_policy)
        
    enforcer.add_policy("staff_sales", "transaction", "refund", str(req.new_limit))
    enforcer.save_policy()
    return StandardResponse(
        success=True,
        message="Cập nhật chính sách thành công",
        data={"limit": req.new_limit}
    )


@router.put("/settings/change-password", response_model=StandardResponse[dict])
def change_password(
    req: ChangePasswordRequest,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Đổi mật khẩu người dùng."""
    user = db.query(models.Employee).filter(models.Employee.username == current_user.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    if not verify_password(req.old_password, user.password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác")
        
    user.password = get_password_hash(req.new_password)
    db.commit()
    return StandardResponse(
        success=True,
        message="Đổi mật khẩu thành công",
        data={"username": current_user.username}
    )
