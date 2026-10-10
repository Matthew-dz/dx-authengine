from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any, Union
from fastapi import Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from app import models
from app.database import get_db


class AnalyticsRepository:
    """
    Data Access Layer cho module Data Analytics.
    Tuân thủ quy tắc tối ưu hóa hiệu năng truy vấn Database (Aggregation):
    - Sử dụng hàm gom nhóm của DB (func.count, func.sum, case) để tính toán trực tiếp dưới DB.
    - Tuyệt đối KHÔNG dùng .all() rồi đếm bằng len() hay loop trong Python.
    - Không dùng db.commit() trong repository.
    """
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_overview_stats(
        self,
        db: Optional[Session] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Tính toán các chỉ số thống kê tổng quan (KPIs) trực tiếp bằng SQL Aggregation.
        Hỗ trợ gọi dạng get_overview_stats(db, from_date, to_date) hoặc get_overview_stats(from_date=..., to_date=...).
        """
        if isinstance(db, datetime) or (db is not None and not hasattr(db, "query")):
            to_date = from_date
            from_date = db
            session = self.db
        else:
            session = db or self.db

        # 1. Đếm tổng số đơn hàng (total_orders) bằng func.count trực tiếp trong DB
        order_query = session.query(func.count(models.Order.id))
        if from_date:
            order_query = order_query.filter(models.Order.order_date >= from_date)
        if to_date:
            order_query = order_query.filter(models.Order.order_date <= to_date)
        total_orders = order_query.scalar() or 0

        # 2. Gom nhóm tính toán Refund stats trong 1 câu SQL duy nhất (Aggregation)
        refund_query = session.query(
            func.count(models.RefundRequest.id).label("total_refunds"),
            func.coalesce(func.sum(models.RefundRequest.amount), 0.0).label("total_refund_amount"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.PENDING, 1), else_=0)), 0).label("pending"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.APPROVED, 1), else_=0)), 0).label("approved"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.REJECTED, 1), else_=0)), 0).label("rejected"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.PROCESSING, 1), else_=0)), 0).label("processing")
        )
        if from_date:
            refund_query = refund_query.filter(models.RefundRequest.created_at >= from_date)
        if to_date:
            refund_query = refund_query.filter(models.RefundRequest.created_at <= to_date)

        stats = refund_query.first()

        return {
            "total_orders": int(total_orders),
            "total_refunds": int(stats.total_refunds if stats and stats.total_refunds else 0),
            "total_refund_amount": float(stats.total_refund_amount if stats and stats.total_refund_amount else 0.0),
            "pending": int(stats.pending if stats and stats.pending else 0),
            "approved": int(stats.approved if stats and stats.approved else 0),
            "rejected": int(stats.rejected if stats and stats.rejected else 0),
            "processing": int(stats.processing if stats and stats.processing else 0)
        }

    def get_employee_performance(
        self,
        db: Optional[Session] = None,
        employee_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Tuple[Optional[models.Employee], Dict[str, int], List[Tuple[datetime, datetime]]]:
        """
        Truy vấn số lượng refund theo từng trạng thái mà nhân viên đã xử lý (theo processed_by).
        Lấy danh sách cặp (created_at, processed_at) của các refund đã hoàn tất để tính thời gian.
        """
        if isinstance(db, int):
            to_date = from_date
            from_date = employee_id
            employee_id = db
            session = self.db
        else:
            session = db or self.db

        employee = session.query(models.Employee).filter(models.Employee.id == employee_id).first()
        if not employee:
            return None, {"processed": 0, "approved": 0, "rejected": 0, "processing": 0}, []

        # Truy vấn số lượng refund theo từng trạng thái bằng DB Aggregation
        counts_query = session.query(
            func.count(models.RefundRequest.id).label("processed"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.APPROVED, 1), else_=0)), 0).label("approved"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.REJECTED, 1), else_=0)), 0).label("rejected"),
            func.coalesce(func.sum(case((models.RefundRequest.status == models.RefundState.PROCESSING, 1), else_=0)), 0).label("processing")
        ).filter(models.RefundRequest.processed_by == employee_id)

        if from_date:
            counts_query = counts_query.filter(models.RefundRequest.created_at >= from_date)
        if to_date:
            counts_query = counts_query.filter(models.RefundRequest.created_at <= to_date)

        counts = counts_query.first()
        status_counts = {
            "processed": int(counts.processed if counts and counts.processed else 0),
            "approved": int(counts.approved if counts and counts.approved else 0),
            "rejected": int(counts.rejected if counts and counts.rejected else 0),
            "processing": int(counts.processing if counts and counts.processing else 0)
        }

        # Lấy danh sách cặp (created_at, processed_at) của các refund đã hoàn tất (APPROVED, REJECTED, COMPLETED)
        completed_statuses = [models.RefundState.APPROVED, models.RefundState.REJECTED, models.RefundState.COMPLETED]
        time_query = session.query(
            models.RefundRequest.created_at,
            models.RefundRequest.processed_at
        ).filter(
            models.RefundRequest.processed_by == employee_id,
            models.RefundRequest.status.in_(completed_statuses),
            models.RefundRequest.created_at.isnot(None),
            models.RefundRequest.processed_at.isnot(None)
        )
        if from_date:
            time_query = time_query.filter(models.RefundRequest.created_at >= from_date)
        if to_date:
            time_query = time_query.filter(models.RefundRequest.created_at <= to_date)

        time_pairs = time_query.all()
        return employee, status_counts, time_pairs

    def get_all_employees(self, db: Optional[Session] = None) -> List[models.Employee]:
        """Lấy danh sách tất cả nhân viên."""
        session = db or self.db
        return session.query(models.Employee).all()
