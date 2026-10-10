from typing import List, Optional
from fastapi import Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models
from app.database import get_db


class OrderRepository:
    """
    Data Access Layer cho thực thể Order và các truy vấn liên quan đến khách hàng.
    Tuân thủ nguyên tắc: Không gọi db.commit() trong repository.
    """
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_by_id(self, order_id: int) -> Optional[models.Order]:
        """Lấy đơn hàng theo ID."""
        return self.db.query(models.Order).filter(models.Order.id == order_id).first()

    def get_customer_by_id(self, customer_id: int) -> Optional[models.Customer]:
        """Lấy thông tin khách hàng theo ID."""
        return self.db.query(models.Customer).filter(models.Customer.id == customer_id).first()

    def get_recent_orders_by_customer(self, customer_id: int, limit: int = 5) -> List[models.Order]:
        """
        Lấy danh sách các đơn hàng gần đây nhất của khách hàng với giới hạn chặt chẽ (limit=5).
        Tối ưu Token Window cho mô hình LLM.
        """
        return self.db.query(models.Order)\
            .filter(models.Order.customer_id == customer_id)\
            .order_by(models.Order.order_date.desc())\
            .limit(limit)\
            .all()

    def count_customer_orders(self, customer_id: int) -> int:
        """Đếm tổng số đơn hàng của khách hàng bằng SQL Aggregation."""
        count = self.db.query(func.count(models.Order.id))\
            .filter(models.Order.customer_id == customer_id)\
            .scalar()
        return count or 0

    def count_customer_refunds(self, customer_id: int) -> int:
        """Đếm tổng số yêu cầu hoàn tiền của khách hàng qua Order join RefundRequest."""
        count = self.db.query(func.count(models.RefundRequest.id))\
            .join(models.Order, models.RefundRequest.order_id == models.Order.id)\
            .filter(models.Order.customer_id == customer_id)\
            .scalar()
        return count or 0


# Alias hỗ trợ cú pháp OrderRepo
OrderRepo = OrderRepository
