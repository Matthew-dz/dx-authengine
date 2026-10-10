from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db, SessionLocal
from app.agent import enforcer, Subject, Resource, generate_refund_content
from app.email_service import send_refund_email
from app.security import get_current_user, get_optional_current_user
from app.services.refund_service import RefundService
from app.schemas import (
    RefundRequestCreate,
    RefundStateUpdate,
    RefundActionPayload,
    RefundRequestResponse
)
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/refunds", tags=["Refunds"])


class DirectRefundRequest(BaseModel):
    order_id: int


async def process_ai_and_email(
    username: str, 
    order_days_old: int, 
    customer_email: str, 
    customer_name: str, 
    decision_str: str,
    audit_log_id: int
):
    try:
        content = await generate_refund_content(
            username=username,
            order_days_old=order_days_old,
            customer_email=customer_email,
            customer_name=customer_name,
            decision=decision_str
        )
        
        db = SessionLocal()
        try:
            log = db.query(models.AuditLog).filter(models.AuditLog.id == audit_log_id).first()
            if log:
                log.reason = content.reason
                db.commit()
        finally:
            db.close()
            
        send_refund_email(
            to_email=customer_email,
            subject='Thông báo kết quả xử lý hoàn tiền - DX-AuthEngine',
            body=content.email_template
        )
    except Exception as e:
        print(f"Lỗi khi chạy ngầm AI và Email: {e}")


@router.post("", response_model=StandardResponse[RefundRequestResponse])
def create_refund(
    req: RefundRequestCreate,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Khởi tạo yêu cầu hoàn tiền mới (PENDING) theo chuẩn Unified API."""
    refund = service.create_refund_request(req=req, current_user=current_user)
    return StandardResponse(
        success=True,
        message="Tạo yêu cầu hoàn tiền thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.post("/{id}/process", response_model=StandardResponse[RefundRequestResponse])
def process_refund(
    id: int,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Xử lý yêu cầu hoàn tiền (PENDING -> PROCESSING)."""
    notes = payload.notes if payload else None
    refund = service.process_refund(refund_id=id, notes=notes, current_user=current_user)
    return StandardResponse(
        success=True,
        message="Cập nhật trạng thái đang xử lý thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.post("/{id}/approve", response_model=StandardResponse[RefundRequestResponse])
def approve_refund(
    id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Phê duyệt yêu cầu hoàn tiền (PROCESSING -> APPROVED) và gửi email tự động."""
    notes = payload.notes if payload else None
    refund = service.approve_refund(
        refund_id=id,
        notes=notes,
        current_user=current_user,
        background_tasks=background_tasks
    )
    return StandardResponse(
        success=True,
        message="Phê duyệt yêu cầu hoàn tiền thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.post("/{id}/reject", response_model=StandardResponse[RefundRequestResponse])
def reject_refund(
    id: int,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Từ chối yêu cầu hoàn tiền (PROCESSING -> REJECTED)."""
    notes = payload.notes if payload else None
    refund = service.reject_refund(refund_id=id, notes=notes, current_user=current_user)
    return StandardResponse(
        success=True,
        message="Từ chối yêu cầu hoàn tiền thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.patch("/{id}/status", response_model=StandardResponse[RefundRequestResponse])
def update_refund_status(
    id: int,
    req: RefundStateUpdate,
    current_user: Optional[models.Employee] = Depends(get_optional_current_user),
    service: RefundService = Depends()
):
    """Cập nhật trạng thái tự do (hỗ trợ client cũ)."""
    refund = service.update_refund_status(
        refund_id=id,
        new_status=req.status,
        notes=req.notes,
        current_user=current_user
    )
    return StandardResponse(
        success=True,
        message="Cập nhật trạng thái yêu cầu hoàn tiền thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.get("", response_model=StandardResponse[List[RefundRequestResponse]])
def get_all_refunds(service: RefundService = Depends()):
    """Lấy danh sách tất cả yêu cầu hoàn tiền."""
    refunds = service.get_all_refunds()
    data = [RefundRequestResponse.model_validate(r, from_attributes=True) for r in refunds]
    return StandardResponse(
        success=True,
        message="Lấy danh sách yêu cầu hoàn tiền thành công",
        data=data
    )


@router.get("/{id}", response_model=StandardResponse[RefundRequestResponse])
def get_refund(id: int, service: RefundService = Depends()):
    """Xem chi tiết yêu cầu hoàn tiền theo ID."""
    refund = service.get_refund_by_id(refund_id=id)
    return StandardResponse(
        success=True,
        message="Lấy thông tin yêu cầu hoàn tiền thành công",
        data=RefundRequestResponse.model_validate(refund, from_attributes=True)
    )


@router.post("/direct", response_model=StandardResponse[dict])
async def direct_request_refund(
    req: DirectRefundRequest,
    background_tasks: BackgroundTasks,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xử lý hoàn tiền trực tiếp cho đơn hàng (Legacy Direct Refund API)."""
    order_info = db.query(models.Order, models.Customer).join(
        models.Customer, models.Order.customer_id == models.Customer.id
    ).filter(models.Order.id == req.order_id).first()
    if not order_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    order, customer = order_info
    
    delta = datetime.now() - order.order_date
    order_days_old = delta.days
    
    is_allowed = enforcer.enforce(Subject(current_user.username, current_user.role), Resource("transaction", order_days_old), "refund")
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Không đủ quyền duyệt hoàn tiền")
        
    order.status = "REFUNDED"
    audit_log = models.AuditLog(
        order_id=req.order_id,
        employee_username=current_user.username,
        decision='ALLOW',
        reason='Đã duyệt bởi hệ thống'
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    background_tasks.add_task(
        process_ai_and_email,
        username=current_user.username,
        order_days_old=order_days_old,
        customer_email=customer.email,
        customer_name=customer.full_name,
        decision_str="ALLOW",
        audit_log_id=audit_log.id
    )
    
    return StandardResponse(
        success=True,
        message="Giao dịch thành công, email đang được gửi",
        data={"order_id": req.order_id, "status": "REFUNDED"}
    )
