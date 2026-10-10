import json
from datetime import datetime
from typing import List, Optional
from fastapi import Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.repositories.refund_repository import RefundRepository
from app.agent import enforcer, Subject, Resource
from app.email_service import send_notification_email
from app.schemas import RefundRequestCreate


class RefundService:
    """
    Business Logic Layer cho module Hoàn tiền (Refund).
    Quản lý luồng kiểm tra quyền Casbin, State Machine, Audit Log và ACID Transactions.
    """
    def __init__(
        self,
        repo: RefundRepository = Depends(),
        db: Session = Depends(get_db)
    ):
        self.repo = repo
        self.db = db

    def _log_workflow_transition(
        self,
        user: any,
        resource_id: int,
        order_id: int,
        old_state: any,
        new_state: any,
        action: str
    ) -> models.AuditLog:
        """Ghi nhận Audit Log sự kiện chuyển đổi trạng thái workflow với cấu trúc details JSON."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "system")

        old_state_str = old_state.value if hasattr(old_state, "value") else (str(old_state) if old_state is not None else None)
        new_state_str = new_state.value if hasattr(new_state, "value") else (str(new_state) if new_state is not None else None)

        details_payload = {
            "resource_id": resource_id,
            "action": action,
            "old_state": old_state_str,
            "new_state": new_state_str,
            "timestamp": datetime.utcnow().isoformat()
        }

        audit_log = models.AuditLog(
            order_id=order_id,
            employee_username=username,
            decision=new_state_str or action.upper(),
            reason=f"Chuyển trạng thái ({action}): {old_state_str or 'NONE'} -> {new_state_str}",
            details=json.dumps(details_payload, ensure_ascii=False),
            created_at=datetime.utcnow()
        )
        return self.repo.add_audit_log(audit_log)

    def get_refund_by_id(self, refund_id: int) -> models.RefundRequest:
        """Lấy yêu cầu hoàn tiền theo ID."""
        refund = self.repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")
        return refund

    def get_all_refunds(self) -> List[models.RefundRequest]:
        """Lấy danh sách tất cả yêu cầu hoàn tiền."""
        return self.repo.get_all()

    def create_refund_request(
        self,
        req: RefundRequestCreate,
        current_user: models.Employee
    ) -> models.RefundRequest:
        """Nghiệp vụ tạo mới yêu cầu hoàn tiền (bắt đầu từ PENDING)."""
        # 1. Kiểm tra quyền Casbin: create
        if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("refund"), "create"):
            raise HTTPException(status_code=403, detail="Bạn không có quyền tạo yêu cầu hoàn tiền")

        # 2. Kiểm tra đơn hàng tồn tại
        order = self.repo.get_order_by_id(req.order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

        # 2b. Kiểm tra trùng lặp yêu cầu đang chờ xử lý
        existing = self.db.query(models.RefundRequest).filter(
            models.RefundRequest.order_id == req.order_id,
            models.RefundRequest.status.in_([models.RefundState.PENDING, models.RefundState.PROCESSING])
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Đơn hàng #{req.order_id} đã có yêu cầu hoàn tiền #{existing.id} đang chờ xử lý."
            )

        try:
            # 3. Tạo bản ghi mới với trạng thái PENDING
            refund_amount = req.amount if hasattr(req, "amount") and req.amount is not None else (order.price if order and order.price is not None else 0.0)
            refund = models.RefundRequest(
                order_id=req.order_id,
                reason=req.reason,
                status=models.RefundState.PENDING,
                employee_id=current_user.id,
                amount=refund_amount
            )
            created_refund = self.repo.create(refund)

            # 4. Ghi nhận Audit Log
            self._log_workflow_transition(
                user=current_user,
                resource_id=created_refund.id,
                order_id=created_refund.order_id,
                old_state=None,
                new_state=models.RefundState.PENDING,
                action="create"
            )

            # 5. Commit Transaction
            self.db.commit()
            self.db.refresh(created_refund)
            return created_refund
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def process_refund(
        self,
        refund_id: int,
        notes: Optional[str],
        current_user: models.Employee
    ) -> models.RefundRequest:
        """Nghiệp vụ xử lý yêu cầu hoàn tiền (PENDING -> PROCESSING)."""
        # 1. Kiểm tra quyền Casbin: process
        if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("refund"), "process"):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xử lý yêu cầu hoàn tiền")

        # 2. Kiểm tra bản ghi
        refund = self.repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")

        # 3. State Machine check: Chỉ cho phép chuyển từ PENDING
        if refund.status != models.RefundState.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể chuyển sang PROCESSING từ trạng thái PENDING (hiện tại: {refund.status.value})"
            )

        try:
            old_state = refund.status
            refund.status = models.RefundState.PROCESSING
            if notes:
                refund.notes = notes
            refund.employee_id = current_user.id
            self.repo.update(refund)

            # 4. Ghi Audit Log
            self._log_workflow_transition(
                user=current_user,
                resource_id=refund.id,
                order_id=refund.order_id,
                old_state=old_state,
                new_state=models.RefundState.PROCESSING,
                action="process"
            )

            # 5. Commit Transaction
            self.db.commit()
            self.db.refresh(refund)
            return refund
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def approve_refund(
        self,
        refund_id: int,
        notes: Optional[str],
        current_user: models.Employee,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> models.RefundRequest:
        """Nghiệp vụ phê duyệt yêu cầu hoàn tiền (PROCESSING -> APPROVED) và đồng bộ Order."""
        # 1. Kiểm tra quyền Casbin: approve
        if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("refund"), "approve"):
            raise HTTPException(status_code=403, detail="Bạn không có quyền phê duyệt hoàn tiền")

        # 2. Kiểm tra bản ghi
        refund = self.repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")

        # 3. State Machine check: Chỉ cho phép phê duyệt khi đang ở PENDING hoặc PROCESSING
        if refund.status not in [models.RefundState.PENDING, models.RefundState.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể phê duyệt yêu cầu ở trạng thái PENDING hoặc PROCESSING (hiện tại: {refund.status.value}), không thể phê duyệt."
            )

        try:
            old_state = refund.status
            refund.status = models.RefundState.APPROVED
            if notes:
                refund.notes = notes
            refund.employee_id = current_user.id
            self.repo.update(refund)

            # Đồng bộ Order sang REFUNDED
            order = self.repo.get_order_by_id(refund.order_id)
            if order:
                order.status = "REFUNDED"

            # Ghi Audit Log
            self._log_workflow_transition(
                user=current_user,
                resource_id=refund.id,
                order_id=refund.order_id,
                old_state=old_state,
                new_state=models.RefundState.APPROVED,
                action="approve"
            )

            # Commit Transaction
            self.db.commit()
            self.db.refresh(refund)

            # Chạy ngầm gửi Email thông báo sau khi transaction commit thành công
            if background_tasks and order and order.customer and order.customer.email:
                cust_name = order.customer.full_name or "Quý khách"
                subj = f"Thông báo kết quả xử lý hoàn tiền - DX-OS"
                body = f"Kính gửi {cust_name},\n\nYêu cầu hoàn tiền cho đơn hàng #{order.id} ({order.product_name}) đã được phê duyệt thành công.\n\nTrân trọng,\nĐội ngũ CSKH DX-OS."
                background_tasks.add_task(send_notification_email, order.customer.email, subj, body)

            return refund
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def reject_refund(
        self,
        refund_id: int,
        notes: Optional[str],
        current_user: models.Employee
    ) -> models.RefundRequest:
        """Nghiệp vụ từ chối yêu cầu hoàn tiền (PROCESSING -> REJECTED)."""
        # 1. Kiểm tra quyền Casbin: reject
        if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("refund"), "reject"):
            raise HTTPException(status_code=403, detail="Bạn không có quyền từ chối hoàn tiền")

        # 2. Kiểm tra bản ghi
        refund = self.repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")

        # 3. State Machine check: Chỉ từ chối khi ở PENDING hoặc PROCESSING
        if refund.status not in [models.RefundState.PENDING, models.RefundState.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể từ chối yêu cầu ở trạng thái PENDING hoặc PROCESSING (hiện tại: {refund.status.value}), không thể từ chối."
            )

        try:
            old_state = refund.status
            refund.status = models.RefundState.REJECTED
            if notes:
                refund.notes = notes
            refund.employee_id = current_user.id
            self.repo.update(refund)

            # Ghi Audit Log
            self._log_workflow_transition(
                user=current_user,
                resource_id=refund.id,
                order_id=refund.order_id,
                old_state=old_state,
                new_state=models.RefundState.REJECTED,
                action="reject"
            )

            # Commit Transaction
            self.db.commit()
            self.db.refresh(refund)
            return refund
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def update_refund_status(
        self,
        refund_id: int,
        new_status: models.RefundState,
        notes: Optional[str],
        current_user: Optional[models.Employee] = None
    ) -> models.RefundRequest:
        """Cập nhật trạng thái tự do (hỗ trợ API PATCH), có logic kiểm tra trạng thái đóng."""
        refund = self.repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")

        closed_states = [
            models.RefundState.APPROVED,
            models.RefundState.REJECTED,
            models.RefundState.COMPLETED
        ]
        if refund.status in closed_states:
            raise HTTPException(
                status_code=400,
                detail="Không thể thay đổi trạng thái của yêu cầu đã đóng"
            )

        try:
            old_status = refund.status
            refund.status = new_status
            if notes is not None:
                refund.notes = notes
            if current_user:
                refund.employee_id = current_user.id
            self.repo.update(refund)

            self._log_workflow_transition(
                user=current_user,
                resource_id=refund.id,
                order_id=refund.order_id,
                old_state=old_status,
                new_state=new_status,
                action="status_update"
            )

            self.db.commit()
            self.db.refresh(refund)
            return refund
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
