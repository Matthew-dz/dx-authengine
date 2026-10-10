from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.agent import enforcer, Subject, Resource
from app.email_service import send_refund_email
from app.security import get_current_user
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


class AuditLogUpdateDecisionRequest(BaseModel):
    new_decision: str
    reason: str


@router.get("", response_model=StandardResponse[List[dict]])
def get_audit_logs(
    search: Optional[str] = None,
    customer: Optional[str] = None,
    employee: Optional[str] = None,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách Audit Logs (Chỉ Admin và Manager)."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "read") or current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Audit Log. Chỉ Admin và Manager mới có quyền xem.")

    query = db.query(models.AuditLog, models.Order, models.Customer) \
        .join(models.Order, models.AuditLog.order_id == models.Order.id) \
        .join(models.Customer, models.Order.customer_id == models.Customer.id)

    if search:
        if search.isdigit():
            query = query.filter(
                or_(
                    models.Order.id == int(search),
                    models.Order.product_name.ilike(f"%{search}%")
                )
            )
        else:
            query = query.filter(models.Order.product_name.ilike(f"%{search}%"))
            
    if customer:
        query = query.filter(models.Customer.full_name.ilike(f"%{customer}%"))
        
    if employee:
        query = query.filter(models.AuditLog.employee_username.ilike(f"%{employee}%"))

    logs = query.order_by(models.AuditLog.created_at.desc()).all()
    
    result = []
    for log, order, cust in logs:
        result.append({
            "id": log.id,
            "order_id": log.order_id,
            "product_name": order.product_name,
            "employee_username": log.employee_username,
            "decision": log.decision,
            "reason": log.reason,
            "details": log.details,
            "created_at": log.created_at.isoformat()
        })
    return StandardResponse(
        success=True,
        message="Lấy danh sách nhật ký kiểm toán thành công",
        data=result
    )


@router.put("/{log_id}/decision", response_model=StandardResponse[dict])
def update_audit_log_decision(
    log_id: int,
    req: AuditLogUpdateDecisionRequest,
    background_tasks: BackgroundTasks,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Thay đổi quyết định kiểm toán (Chỉ Admin)."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "write"):
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thay đổi quyết định.")
    
    log = db.query(models.AuditLog).filter(models.AuditLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Không tìm thấy log")
        
    order = db.query(models.Order).filter(models.Order.id == log.order_id).first()
    customer = db.query(models.Customer).filter(models.Customer.id == order.customer_id).first()
    
    old_decision = log.decision
    log.decision = req.new_decision
    log.reason = f"[Cập nhật bởi {current_user.username} từ {old_decision} -> {req.new_decision}] {req.reason}"
    db.commit()
    
    email_subject = "Cập nhật kết quả xử lý hoàn tiền - DX-AuthEngine"
    if req.new_decision == "ALLOW":
        email_body = f"Kính gửi {customer.full_name},\n\nYêu cầu hoàn tiền cho đơn hàng {order.product_name} của bạn đã được Admin phê duyệt (thay đổi quyết định).\nLý do: {req.reason}\n\nTrân trọng,\nĐội ngũ CSKH."
    else:
        email_body = f"Kính gửi {customer.full_name},\n\nYêu cầu hoàn tiền cho đơn hàng {order.product_name} của bạn đã bị từ chối.\nLý do: {req.reason}\n\nTrân trọng,\nĐội ngũ CSKH."
        
    background_tasks.add_task(send_refund_email, customer.email, email_subject, email_body)
    return StandardResponse(
        success=True,
        message="Cập nhật quyết định thành công",
        data={"log_id": log_id, "new_decision": req.new_decision}
    )
