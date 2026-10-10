from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.agent import enforcer, Subject, Resource
from app.security import get_current_user, get_password_hash
from app.schemas import (
    EmployeeResponse,
    EmployeeUpdate
)
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/api/v1/employees", tags=["Employees"])


class EmployeeCreate(BaseModel):
    username: str
    password: str
    full_name: str
    position: str
    hire_date: str
    address: str
    hometown: str
    phone: str
    cccd: str
    role: str


@router.get("", response_model=StandardResponse[List[EmployeeResponse]])
def get_employees(
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách tất cả nhân viên (yêu cầu quyền Casbin employee:read)."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emps = db.query(models.Employee).all()
    data = [EmployeeResponse.model_validate(e, from_attributes=True) for e in emps]
    return StandardResponse(
        success=True,
        message="Lấy danh sách nhân viên thành công",
        data=data
    )


@router.post("", response_model=StandardResponse[EmployeeResponse])
def create_employee(
    req: EmployeeCreate,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Tạo nhân viên mới (yêu cầu quyền Casbin employee:write)."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    req.username = req.username.lower()
    if db.query(models.Employee).filter(models.Employee.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    if db.query(models.Employee).filter(models.Employee.cccd == req.cccd).first():
        raise HTTPException(status_code=400, detail="CCCD đã tồn tại")
        
    emp_data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    emp_data["password"] = get_password_hash(emp_data["password"])
    
    emp = models.Employee(**emp_data)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    
    enforcer.add_role_for_user(emp.username, emp.role)
    enforcer.save_policy()
    
    return StandardResponse(
        success=True,
        message="Tạo nhân viên mới thành công",
        data=EmployeeResponse.model_validate(emp, from_attributes=True)
    )


@router.get("/{emp_id}", response_model=StandardResponse[EmployeeResponse])
def get_employee(
    emp_id: int,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy chi tiết nhân viên theo ID."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    return StandardResponse(
        success=True,
        message="Lấy thông tin nhân viên thành công",
        data=EmployeeResponse.model_validate(emp, from_attributes=True)
    )


@router.put("/{emp_id}", response_model=StandardResponse[EmployeeResponse])
def update_employee(
    emp_id: int,
    req: EmployeeUpdate,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin nhân viên."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
        
    update_data = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    allowed_fields = ["full_name", "phone", "address", "email"]
    for key in allowed_fields:
        if key in update_data:
            setattr(emp, key, update_data[key])
        
    db.commit()
    db.refresh(emp)
    return StandardResponse(
        success=True,
        message="Cập nhật nhân viên thành công",
        data=EmployeeResponse.model_validate(emp, from_attributes=True)
    )


@router.delete("/{emp_id}", response_model=StandardResponse[dict])
def delete_employee(
    emp_id: int,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xóa nhân viên."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
        
    enforcer.delete_roles_for_user(emp.username)
    enforcer.save_policy()
    
    db.delete(emp)
    db.commit()
    
    return StandardResponse(
        success=True,
        message="Đã xóa nhân viên",
        data={"id": emp_id}
    )
