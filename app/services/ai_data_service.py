from typing import Dict, Any
from fastapi import Depends, HTTPException

from app.repositories.refund_repository import RefundRepo
from app.repositories.order_repository import OrderRepo
from app.schemas_ai import RefundContextForAI, CustomerHistoryForAI, RecentOrderForAI


class AIDataService:
    """
    Dịch vụ chuẩn bị và làm sạch ngữ cảnh dữ liệu cho mô hình AI / LLM.
    Tuân thủ nghiêm ngặt các nguyên tắc bảo mật và tối ưu hóa Token:
    1. Khử định danh (De-identification): Tuyệt đối không chứa bất kỳ trường PII nào
       (không tên khách hàng, không email, không số điện thoại, không CCCD, không địa chỉ).
    2. Tối ưu Token Window: Bắt buộc dùng limit(5) khi lấy danh sách đơn hàng gần đây.
    3. An ninh chéo: Nghiêm cấm ghi dữ liệu (Read-only), không thực thi transaction write và không truy xuất biến môi trường hệ thống.
    """
    def __init__(
        self,
        refund_repo: RefundRepo = Depends(),
        order_repo: OrderRepo = Depends()
    ):
        self.refund_repo = refund_repo
        self.order_repo = order_repo

    def get_refund_context(self, refund_id: int) -> Dict[str, Any]:
        """
        Truy vấn Refund theo ID, làm sạch và khử định danh qua RefundContextForAI.
        Trả về định dạng JSON (dict) tối ưu cho LLM prompt.
        """
        refund = self.refund_repo.get_by_id(refund_id)
        if not refund:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu hoàn tiền #{refund_id}")

        status_val = refund.status.value if hasattr(refund.status, "value") else str(refund.status)
        amount_val = refund.amount
        if amount_val is None and refund.order:
            amount_val = refund.order.price

        context = RefundContextForAI(
            refund_id=refund.id,
            order_id=refund.order_id,
            amount=amount_val,
            status=status_val,
            reason=refund.reason,
            created_at=refund.created_at
        )
        return context.model_dump()

    def get_customer_context(self, customer_id: int) -> Dict[str, Any]:
        """
        Truy vấn lịch sử giao dịch và hoàn tiền của khách hàng.
        Bắt buộc dùng limit(5) cho danh sách đơn hàng gần nhất để chống tràn Token Window của LLM.
        Ép kiểu qua CustomerHistoryForAI và trả về JSON (dict).
        """
        customer = self.order_repo.get_customer_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy khách hàng #{customer_id}")

        total_orders = self.order_repo.count_customer_orders(customer_id)
        total_refunds = self.order_repo.count_customer_refunds(customer_id)

        # Bắt buộc giới hạn tối đa 5 đơn hàng gần nhất để tiết kiệm token
        recent_orders_db = self.order_repo.get_recent_orders_by_customer(customer_id, limit=5)

        recent_orders_ai = [
            RecentOrderForAI(
                order_id=o.id,
                product_name=o.product_name,
                price=float(o.price) if o.price is not None else 0.0,
                order_date=o.order_date,
                status=o.status or "UNKNOWN"
            )
            for o in recent_orders_db
        ]

        history_context = CustomerHistoryForAI(
            total_orders=total_orders,
            total_refunds_requested=total_refunds,
            recent_orders=recent_orders_ai
        )
        return history_context.model_dump()
