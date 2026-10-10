from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from typing import Optional, List
from sqlalchemy import or_
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from app import models
from app.database import engine, SessionLocal
from app.agent import enforcer, Subject, Resource, generate_refund_content
from app.email_service import send_refund_email
from app.security import create_access_token, get_current_user, get_password_hash, verify_password
from app.schemas import EmployeeResponse
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="DX-AuthEngine API")

@app.on_event("startup")
def bootstrap_admin():
    # Kiểm tra xem quyền cho tài khoản admin mặc định đã tồn tại chưa
    # Nếu chưa, bơm quyền khởi thủy để không bị lockout
    policies = enforcer.get_policy()
    has_admin_policy = any(p[0] == "admin" for p in policies)
    if not has_admin_policy:
        enforcer.add_policy("admin", "employee", "read", "")
        enforcer.add_policy("admin", "employee", "write", "")
        enforcer.add_policy("admin", "transaction", "read", "")
        enforcer.add_policy("admin", "transaction", "refund", "999999")
        enforcer.add_policy("admin", "audit_log", "read", "")
        enforcer.add_policy("admin", "audit_log", "write", "")
        enforcer.add_policy("admin", "role", "read", "")
        enforcer.add_policy("admin", "role", "write", "")
        enforcer.add_policy("admin", "policy", "read", "")
        enforcer.add_policy("admin", "policy", "write", "")
        enforcer.save_policy()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency để lấy DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginRequest(BaseModel):
    username: str
    password: str

class RefundRequest(BaseModel):
    order_id: int

class RoleUpdateRequest(BaseModel):
    username: str
    new_role: str

class PolicyUpdateRequest(BaseModel):
    new_limit: int

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class AuditLogUpdateDecisionRequest(BaseModel):
    new_decision: str
    reason: str


class EmployeeCreate(BaseModel):
    username: str
    password: str
    full_name: str
    position: str
    hire_date: str
    address: str
    hometown: str
    phone: str
    cccd: str
    role: str

class EmployeeUpdate(BaseModel):
    password: str = None  # Add optional password field for updating
    full_name: str
    position: str
    hire_date: str
    address: str
    hometown: str
    phone: str
    cccd: str
    role: str

@app.post("/api/v1/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.Employee).filter(models.Employee.username == req.username.lower()).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác")
    
    access_token = create_access_token({"sub": user.username, "role": user.role})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "name": user.full_name,
        "role": user.role
    }

@app.get("/api/v1/employees", response_model=List[EmployeeResponse])
def get_employees(current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    return db.query(models.Employee).all()

@app.post("/api/v1/employees", response_model=EmployeeResponse)
def create_employee(req: EmployeeCreate, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    req.username = req.username.lower() # Đảm bảo username luôn là chữ thường
    if db.query(models.Employee).filter(models.Employee.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    if db.query(models.Employee).filter(models.Employee.cccd == req.cccd).first():
        raise HTTPException(status_code=400, detail="CCCD đã tồn tại")
        
    emp_data = req.dict()
    emp_data["password"] = get_password_hash(emp_data["password"])
    
    emp = models.Employee(**emp_data)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    
    enforcer.add_role_for_user(emp.username, emp.role)
    enforcer.save_policy()
    
    return emp

@app.get("/api/v1/employees/{emp_id}", response_model=EmployeeResponse)
def get_employee(emp_id: int, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    return emp

@app.put("/api/v1/employees/{emp_id}", response_model=EmployeeResponse)
def update_employee(emp_id: int, req: EmployeeUpdate, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
        
    old_role = emp.role
    
    update_data = req.dict(exclude_unset=True)
    if update_data.get("password"):
        update_data["password"] = get_password_hash(update_data["password"])
    else:
        # If password is empty/None, do not update it
        update_data.pop("password", None)
    
    for key, value in update_data.items():
        setattr(emp, key, value)
        
    db.commit()
    db.refresh(emp)
    
    if old_role != emp.role:
        enforcer.delete_roles_for_user(emp.username)
        enforcer.add_role_for_user(emp.username, emp.role)
        enforcer.save_policy()
        
    return emp

@app.delete("/api/v1/employees/{emp_id}")
def delete_employee(emp_id: int, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("employee"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
        
    enforcer.delete_roles_for_user(emp.username)
    enforcer.save_policy()
    
    db.delete(emp)
    db.commit()
    
    return {"message": "Đã xóa nhân viên"}

@app.get("/api/v1/orders")
def get_orders(current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("transaction"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    orders_with_customers = db.query(models.Order, models.Customer).join(models.Customer, models.Order.customer_id == models.Customer.id).filter(models.Order.status == "PENDING").order_by(models.Order.id.desc()).all()
    
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
            "order_date": o.order_date,
            "customer_name": c.full_name,
            "customer_email": c.email,
            "is_flagged": is_flagged,
            "is_eligible": is_eligible
        })
        
    # Sắp xếp: Đơn hàng đủ điều kiện hoàn (is_eligible=True) xếp trước
    # Trong cùng nhóm, xếp theo Ngày mua tăng dần (đơn hàng cũ/sát hạn nhất lên trên)
    result.sort(key=lambda x: (not x["is_eligible"], x["order_date"]))
    return result

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

@app.post("/api/v1/refund")
async def request_refund(req: RefundRequest, background_tasks: BackgroundTasks, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 1. Lấy thông tin đơn hàng từ Database
        order_info = db.query(models.Order, models.Customer).join(models.Customer, models.Order.customer_id == models.Customer.id).filter(models.Order.id == req.order_id).first()
        if not order_info:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        order, customer = order_info
        
        # 2. Tính số ngày kể từ khi mua
        delta = datetime.now() - order.order_date
        order_days_old = delta.days
        
        # 3. AuthZ: Casbin check
        is_allowed = enforcer.enforce(Subject(current_user.username, current_user.role), Resource("transaction", order_days_old), "refund")
        if not is_allowed:
            raise HTTPException(status_code=403, detail="Không đủ quyền duyệt hoàn tiền")
            
        # 4. Business Logic (Duyệt thành công)
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
        
        # 5. AI & Email (Chạy ngầm)
        background_tasks.add_task(
            process_ai_and_email,
            username=current_user.username,
            order_days_old=order_days_old,
            customer_email=customer.email,
            customer_name=customer.full_name,
            decision_str="ALLOW",
            audit_log_id=audit_log.id
        )
        
        # 6. Response
        return {"status": "success", "message": "Giao dịch thành công, email đang được gửi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/audit-logs")
def get_audit_logs(
    search: Optional[str] = None,
    customer: Optional[str] = None,
    employee: Optional[str] = None,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    query = db.query(models.AuditLog, models.Order, models.Customer) \
        .join(models.Order, models.AuditLog.order_id == models.Order.id) \
        .join(models.Customer, models.Order.customer_id == models.Customer.id)

    if search:
        if search.isdigit():
            query = query.filter(
                or_(
                    models.Order.id == int(search),
                    models.Order.product_name.ilike(f"%{search}%")
                )
            )
        else:
            query = query.filter(models.Order.product_name.ilike(f"%{search}%"))
            
    if customer:
        query = query.filter(models.Customer.full_name.ilike(f"%{customer}%"))
        
    if employee:
        query = query.filter(models.AuditLog.employee_username.ilike(f"%{employee}%"))

    logs = query.order_by(models.AuditLog.created_at.desc()).all()
    
    result = []
    for log, order, cust in logs:
        result.append({
            "id": log.id,
            "order_id": log.order_id,
            "product_name": order.product_name,
            "employee_username": log.employee_username,
            "decision": log.decision,
            "reason": log.reason,
            "created_at": log.created_at.isoformat()
        })
    return result

@app.put("/api/v1/audit-logs/{log_id}/decision")
def update_audit_log_decision(log_id: int, req: AuditLogUpdateDecisionRequest, background_tasks: BackgroundTasks, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "write"):
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thay đổi quyết định.")
    
    log = db.query(models.AuditLog).filter(models.AuditLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Không tìm thấy log")
        
    order = db.query(models.Order).filter(models.Order.id == log.order_id).first()
    customer = db.query(models.Customer).filter(models.Customer.id == order.customer_id).first()
    
    old_decision = log.decision
    log.decision = req.new_decision
    log.reason = f"[Cập nhật bởi {current_user.username} từ {old_decision} -> {req.new_decision}] {req.reason}"
    db.commit()
    
    email_subject = "Cập nhật kết quả xử lý hoàn tiền - DX-AuthEngine"
    if req.new_decision == "ALLOW":
        email_body = f"Kính gửi {customer.full_name},\n\nYêu cầu hoàn tiền cho đơn hàng {order.product_name} của bạn đã được Admin phê duyệt (thay đổi quyết định).\nLý do: {req.reason}\n\nTrân trọng,\nĐội ngũ CSKH."
    else:
        email_body = f"Kính gửi {customer.full_name},\n\nYêu cầu hoàn tiền cho đơn hàng {order.product_name} của bạn đã bị từ chối.\nLý do: {req.reason}\n\nTrân trọng,\nĐội ngũ CSKH."
        
    background_tasks.add_task(send_refund_email, customer.email, email_subject, email_body)
    return {"status": "success", "message": "Cập nhật quyết định thành công"}

@app.get("/api/v1/roles")
def get_roles(current_user: models.Employee = Depends(get_current_user)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("role"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    # Lấy danh sách mapping user-role hiện tại từ memory của Casbin
    policies = enforcer.get_grouping_policy()
    return [{"username": p[0], "role": p[1]} for p in policies]

@app.put("/api/v1/roles")
def update_role(req: RoleUpdateRequest, current_user: models.Employee = Depends(get_current_user)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("role"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("audit_log"), "write"):
        raise HTTPException(status_code=403, detail="Chỉ có tài khoản 'admin' mới có quyền thay đổi Role.")
        
    # 1. Tước bỏ tất cả các role cũ của user
    enforcer.delete_roles_for_user(req.username)
    # 2. Thêm role mới cho user
    enforcer.add_role_for_user(req.username, req.new_role)
    # 3. Lưu vào file policy.csv
    enforcer.save_policy()
    return {"status": "success", "message": f"Cập nhật thành công quyền của {req.username} thành {req.new_role}"}

@app.get("/api/v1/settings/policy")
def get_policy_limit(current_user: models.Employee = Depends(get_current_user)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("policy"), "read"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    policies = enforcer.get_policy()
    for p in policies:
        if len(p) >= 4 and p[0] == "staff_sales" and p[1] == "transaction" and p[2] == "refund":
            return {"limit": int(p[3])}
    return {"limit": 15}

@app.put("/api/v1/settings/policy")
def update_policy_limit(req: PolicyUpdateRequest, current_user: models.Employee = Depends(get_current_user)):
    if not enforcer.enforce(Subject(current_user.username, current_user.role), Resource("policy"), "write"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    old_policies = enforcer.get_filtered_policy(0, "staff_sales", "transaction", "refund")
    for old_policy in old_policies:
        enforcer.remove_policy(*old_policy)
        
    enforcer.add_policy("staff_sales", "transaction", "refund", str(req.new_limit))
    enforcer.save_policy()
    return {"status": "success"}

@app.put("/api/v1/settings/change-password")
def change_password(req: ChangePasswordRequest, current_user: models.Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.Employee).filter(models.Employee.username == current_user.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    if not verify_password(req.old_password, user.password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác")
        
    user.password = get_password_hash(req.new_password)
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
