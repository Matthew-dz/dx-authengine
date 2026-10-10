from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.agent import enforcer, Subject, Resource
from app.security import get_current_user
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=StandardResponse[List[dict]])
def get_orders(
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách các đơn hàng đủ điều kiện hoặc cần xử lý."""
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("transaction"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    orders_with_customers = db.query(models.Order, models.Customer).join(
        models.Customer, models.Order.customer_id == models.Customer.id
    ).filter(models.Order.status == "PENDING").order_by(models.Order.id.desc()).all()
    
    # Tính toán rủi ro gian lận
    customer_counts = {}
    for o, c in orders_with_customers:
        customer_counts[c.id] = customer_counts.get(c.id, 0) + 1
    # Lấy giới hạn ngày hoàn tiền từ Casbin
    policy = enforcer.get_filtered_policy(0, "staff_sales", "transaction", "refund")
    refund_limit = int(policy[0][3]) if policy else 30
            
    result = []
    now = datetime.utcnow()
    for o, c in orders_with_customers:
        is_flagged = customer_counts.get(c.id, 0) >= 3
        days_passed = (now - o.order_date).days
        is_eligible = days_passed <= refund_limit
        
        result.append({
            "id": o.id,
            "product_name": o.product_name,
            "price": o.price,
            "order_date": o.order_date.isoformat() if hasattr(o.order_date, "isoformat") else str(o.order_date),
            "customer_name": c.full_name,
            "customer_email": c.email,
            "is_flagged": is_flagged,
            "is_eligible": is_eligible
        })
        
    result.sort(key=lambda x: (not x["is_eligible"], x["order_date"]))
    return StandardResponse(
        success=True,
        message="Lấy danh sách đơn hàng thành công",
        data=result
    )
