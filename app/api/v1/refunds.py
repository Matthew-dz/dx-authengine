import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db, SessionLocal
from app.agent import enforcer, Subject, Resource, generate_refund_content, RefundContent
from app.email_service import send_refund_email
from app.security import get_current_user, get_optional_current_user
from app.services.refund_service import RefundService
from app.events.event_bus import event_bus
from app.events.event import RefundApprovedEvent
from app.schemas import (
    RefundRequestCreate,
    RefundStateUpdate,
    RefundActionPayload,
    RefundRequestResponse
)
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/api/v1/refunds", tags=["Refunds"])


class DirectRefundRequest(BaseModel):
    order_id: int


async def process_ai_and_email(
    username: str, 
    order_days_old: int, 
    customer_email: str, 
    customer_name: str, 
    decision_str: str,
    audit_log_id: int,
    refund_req_id: Optional[int] = None,
    product_name: str = "",
    order_id: int = 0,
    amount: float = 0.0
):
    import asyncio
    content = None
    try:
        content = await asyncio.wait_for(
            generate_refund_content(
                username=username,
                order_days_old=order_days_old,
                customer_email=customer_email,
                customer_name=customer_name,
                decision=decision_str
            ),
            timeout=5.0
        )
    except Exception as e:
        print(f"[AI] Fallback sinh nội dung: {e}")

    if not content:
        content = RefundContent(
            reason=f"Đơn hàng #{order_id} ({product_name}) được duyệt hoàn tiền ({order_days_old} ngày).",
            email_template=(
                f"Kính gửi {customer_name},\n\n"
                f"Yêu cầu hoàn tiền cho đơn hàng #{order_id} ({product_name}) với số tiền ${amount:,.2f} USD "
                f"đã được hệ thống DX-OS phê duyệt thành công.\n\n"
                f"Số tiền hoàn trả sẽ được chuyển về tài khoản của quý khách trong thời gian sớm nhất.\n\n"
                f"Trân trọng,\nĐội ngũ CSKH DX-OS System."
            )
        )
        
    db = SessionLocal()
    try:
        log = db.query(models.AuditLog).filter(models.AuditLog.id == audit_log_id).first()
        if log:
            log.reason = content.reason
        if refund_req_id:
            ref = db.query(models.RefundRequest).filter(models.RefundRequest.id == refund_req_id).first()
            if ref:
                ref.reason = content.reason
        db.commit()
    except Exception as err:
        print(f"[DB] Lỗi lưu reason: {err}")
    finally:
        db.close()
        
    try:
        await asyncio.to_thread(
            send_refund_email,
            to_email=customer_email,
            subject=f"Thông báo kết quả duyệt hoàn tiền đơn hàng #{order_id} ({product_name}) - DX-OS",
            body=content.email_template,
            product_name=product_name,
            order_id=order_id,
            amount=amount,
            customer_name=customer_name,
            decision=decision_str
        )
    except Exception as mail_err:
        print(f"[Email] Lỗi khi gửi mail: {mail_err}")


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
        
    # 1. Cập nhật trạng thái đơn hàng thành REFUNDED
    order.status = "REFUNDED"
    
    # 2. LƯU SẢN PHẨM / YÊU CẦU HOÀN TIỀN VÀO HỆ THỐNG (models.RefundRequest)
    refund_requests = db.query(models.RefundRequest).filter(models.RefundRequest.order_id == req.order_id).all()
    if not refund_requests:
        refund_req = models.RefundRequest(
            order_id=req.order_id,
            employee_id=current_user.id,
            reason=f"Phê duyệt hoàn tiền cho sản phẩm: {order.product_name}",
            status=models.RefundState.APPROVED,
            notes="Duyệt hoàn tiền trực tiếp qua giao diện DX-OS",
            amount=order.price if order.price is not None else 0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(refund_req)
        db.flush()
    else:
        for r in refund_requests:
            r.status = models.RefundState.APPROVED
            r.employee_id = current_user.id
            r.updated_at = datetime.utcnow()
            if not r.amount and order.price is not None:
                r.amount = order.price
        refund_req = refund_requests[0]

    # 3. GHI NHẬN AUDIT LOG VỚI ĐẦY ĐỦ DETAILS JSON VÀ THÔNG TIN SẢN PHẨM
    details_payload = {
        "resource_id": refund_req.id,
        "action": "approve",
        "old_state": "PROCESSING",
        "new_state": "APPROVED",
        "order_id": order.id,
        "product_name": order.product_name,
        "amount": order.price,
        "customer_name": customer.full_name,
        "customer_email": customer.email,
        "timestamp": datetime.utcnow().isoformat()
    }
    audit_log = models.AuditLog(
        order_id=req.order_id,
        employee_username=current_user.username,
        decision='ALLOW',
        reason=f"Đơn hàng #{order.id} ({order.product_name}) được duyệt hoàn tiền ({order_days_old} ngày).",
        details=json.dumps(details_payload, ensure_ascii=False),
        created_at=datetime.utcnow()
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    db.refresh(refund_req)

    # 4. PHÁT TÁN SỰ KIỆN QUA EVENT BUS (BƯỚC 5.2 CHUẨN KIẾN TRÚC)
    event = RefundApprovedEvent(
        event_type="RefundApproved",
        entity_id=refund_req.id,
        user_id=current_user.id,
        data={
            "refund_id": refund_req.id,
            "order_id": order.id,
            "employee_username": current_user.username,
            "employee_id": current_user.id,
            "product_name": order.product_name,
            "amount": order.price,
            "customer_name": customer.full_name,
            "customer_email": customer.email,
            "old_state": "PROCESSING",
            "new_state": "APPROVED"
        }
    )
    event_bus.publish(event, background_tasks)

    # 5. CHẠY TỰ ĐỘNG HÓA AI VÀ GỬI EMAIL THÔNG BÁO CHO KHÁCH HÀNG
    background_tasks.add_task(
        process_ai_and_email,
        username=current_user.username,
        order_days_old=order_days_old,
        customer_email=customer.email,
        customer_name=customer.full_name,
        decision_str="ALLOW",
        audit_log_id=audit_log.id,
        refund_req_id=refund_req.id,
        product_name=order.product_name,
        order_id=order.id,
        amount=order.price or 0.0
    )
    
    return StandardResponse(
        success=True,
        message=f"Đã duyệt và lưu sản phẩm '{order.product_name}' vào hệ thống thành công. Email đang được gửi.",
        data={
            "order_id": req.order_id,
            "product_name": order.product_name,
            "status": "REFUNDED",
            "refund_id": refund_req.id
        }
    )


legacy_refund_router = APIRouter(tags=["Refunds Legacy"])


@legacy_refund_router.post("/api/v1/refund", response_model=StandardResponse[dict])
async def legacy_direct_request_refund(
    req: DirectRefundRequest,
    background_tasks: BackgroundTasks,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xử lý hoàn tiền trực tiếp cho đơn hàng (Endpoint tương thích với frontend /api/v1/refund)."""
    return await direct_request_refund(req, background_tasks, current_user, db)

