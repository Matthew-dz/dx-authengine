from typing import List, Optional
from fastapi import Depends
from sqlalchemy.orm import Session
from app import models
from app.database import get_db

class RefundRepository:
    """
    Data Access Layer cho module Hoàn tiền (Refund).
    CRITICAL: Tuyệt đối không dùng db.commit() trong file này.
    Chỉ dùng db.add(), db.query() và db.flush() nếu cần lấy ID sinh tự động.
    """
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_by_id(self, refund_id: int) -> Optional[models.RefundRequest]:
        """Lấy thông tin yêu cầu hoàn tiền theo ID."""
        return self.db.query(models.RefundRequest).filter(models.RefundRequest.id == refund_id).first()

    def get_all(self) -> List[models.RefundRequest]:
        """Lấy danh sách toàn bộ yêu cầu hoàn tiền sắp xếp theo thời gian mới nhất."""
        return self.db.query(models.RefundRequest).order_by(models.RefundRequest.created_at.desc()).all()

    def create(self, refund: models.RefundRequest) -> models.RefundRequest:
        """Tạo mới bản ghi yêu cầu hoàn tiền và flush để sinh ID."""
        self.db.add(refund)
        self.db.flush()
        return refund

    def update(self, refund: models.RefundRequest) -> models.RefundRequest:
        """Cập nhật bản ghi yêu cầu hoàn tiền và flush thay đổi."""
        self.db.add(refund)
        self.db.flush()
        return refund

    def get_order_by_id(self, order_id: int) -> Optional[models.Order]:
        """Lấy thông tin đơn hàng theo ID."""
        return self.db.query(models.Order).filter(models.Order.id == order_id).first()

    def add_audit_log(self, log: models.AuditLog) -> models.AuditLog:
        """Thêm bản ghi Audit Log vào session và flush."""
        self.db.add(log)
        self.db.flush()
        return log


# Alias hỗ trợ cú pháp RefundRepo
RefundRepo = RefundRepository

