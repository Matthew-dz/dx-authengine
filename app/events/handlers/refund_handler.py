import json
import logging
from app import models
from app.database import SessionLocal
from app.email_service import send_notification_email
from app.events.event import RefundApprovedEvent

logger = logging.getLogger(__name__)


def handle_refund_approved(event: RefundApprovedEvent) -> None:
    """
    Event Handler xử lý sự kiện RefundApproved:
    1. Tự mở DB session độc lập (ngoài request context thông thường).
    2. Ghi Audit Log vào bảng tương ứng.
    3. Gửi Email thông báo cho khách hàng nếu có email.
    """
    logger.info(f"[EventHandler] Bắt đầu xử lý RefundApprovedEvent cho entity_id={event.entity_id}")
    data = event.data or {}
    refund_id = event.entity_id
    user_id = event.user_id
    order_id = data.get("order_id")
    employee_username = data.get("employee_username", "system")
    notes = data.get("notes")
    old_state = data.get("old_state", "PROCESSING")

    db = SessionLocal()
    try:
        # Tra cứu Order và Refund nếu thiếu dữ liệu trong payload
        if not order_id:
            ref = db.query(models.RefundRequest).filter(models.RefundRequest.id == refund_id).first()
            if ref:
                order_id = ref.order_id

        # 1. Ghi Audit Log vào DB
        audit_entry = models.AuditLog(
            order_id=order_id,
            employee_username=employee_username,
            decision="ALLOW",
            reason=f"EventBus: Phê duyệt hoàn tiền #{refund_id}. Ghi chú: {notes or 'Không có'}",
            details=json.dumps({
                "action": "approve",
                "old_state": old_state,
                "new_state": "APPROVED",
                "event_type": event.event_type,
                "refund_id": refund_id,
                "user_id": user_id
            })
        )
        db.add(audit_entry)
        db.commit()
        logger.info(f"[EventHandler] Đã ghi AuditLog thành công cho Refund #{refund_id}")

        # 2. Gửi Email thông báo khách hàng
        customer_email = data.get("customer_email")
        customer_name = data.get("customer_name")
        product_name = data.get("product_name")

        if (not customer_email) and order_id:
            ord_obj = db.query(models.Order).filter(models.Order.id == order_id).first()
            if ord_obj:
                product_name = product_name or ord_obj.product_name
                if ord_obj.customer:
                    customer_email = ord_obj.customer.email
                    customer_name = ord_obj.customer.full_name

        if customer_email:
            cust_name = customer_name or "Quý khách"
            subj = "Thông báo kết quả xử lý hoàn tiền - DX-OS"
            body = (
                f"Kính gửi {cust_name},\n\n"
                f"Yêu cầu hoàn tiền cho đơn hàng #{order_id} ({product_name or ''}) "
                f"đã được phê duyệt thành công.\n\n"
                f"Trân trọng,\nĐội ngũ CSKH DX-OS."
            )
            try:
                send_notification_email(customer_email, subj, body)
                logger.info(f"[EventHandler] Đã gửi email thông báo phê duyệt tới {customer_email}")
            except Exception as mail_err:
                logger.error(f"[EventHandler] Lỗi khi gửi email trong handle_refund_approved: {mail_err}")

    except Exception as e:
        db.rollback()
        logger.error(f"[EventHandler] Lỗi trong handle_refund_approved: {e}", exc_info=True)
    finally:
        db.close()
