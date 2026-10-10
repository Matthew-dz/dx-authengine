from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks

from app import models
from app.security import get_current_user, get_optional_current_user
from app.services.refund_service import RefundService
from app.schemas import (
    RefundRequestCreate,
    RefundStateUpdate,
    RefundActionPayload,
    RefundRequestResponse
)

router = APIRouter(prefix="/api/v1/refunds", tags=["Refunds"])


@router.post("", response_model=RefundRequestResponse)
def create_refund(
    req: RefundRequestCreate,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Khởi tạo yêu cầu hoàn tiền mới (PENDING)."""
    return service.create_refund_request(req=req, current_user=current_user)


@router.post("/{id}/process", response_model=RefundRequestResponse)
def process_refund(
    id: int,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Xử lý yêu cầu hoàn tiền (PENDING -> PROCESSING)."""
    notes = payload.notes if payload else None
    return service.process_refund(refund_id=id, notes=notes, current_user=current_user)


@router.post("/{id}/approve", response_model=RefundRequestResponse)
def approve_refund(
    id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Phê duyệt yêu cầu hoàn tiền (PROCESSING -> APPROVED) và gửi email tự động."""
    notes = payload.notes if payload else None
    return service.approve_refund(
        refund_id=id,
        notes=notes,
        current_user=current_user,
        background_tasks=background_tasks
    )


@router.post("/{id}/reject", response_model=RefundRequestResponse)
def reject_refund(
    id: int,
    payload: Optional[RefundActionPayload] = None,
    current_user: models.Employee = Depends(get_current_user),
    service: RefundService = Depends()
):
    """Từ chối yêu cầu hoàn tiền (PROCESSING -> REJECTED)."""
    notes = payload.notes if payload else None
    return service.reject_refund(refund_id=id, notes=notes, current_user=current_user)


@router.patch("/{id}/status", response_model=RefundRequestResponse)
def update_refund_status(
    id: int,
    req: RefundStateUpdate,
    current_user: Optional[models.Employee] = Depends(get_optional_current_user),
    service: RefundService = Depends()
):
    """Cập nhật trạng thái tự do (hỗ trợ client cũ)."""
    return service.update_refund_status(
        refund_id=id,
        new_status=req.status,
        notes=req.notes,
        current_user=current_user
    )


@router.get("", response_model=List[RefundRequestResponse])
def get_all_refunds(service: RefundService = Depends()):
    """Lấy danh sách tất cả yêu cầu hoàn tiền."""
    return service.get_all_refunds()


@router.get("/{id}", response_model=RefundRequestResponse)
def get_refund(id: int, service: RefundService = Depends()):
    """Xem chi tiết yêu cầu hoàn tiền theo ID."""
    return service.get_refund_by_id(refund_id=id)
