from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import models
from database import engine, SessionLocal
from agent import process_refund_request, RefundDecision

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="DX-AuthEngine API")

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
    username: str
    order_id: int

# Cấu hình tài khoản giả lập demo
DEMO_USERS = {
    "alice": {"password": "123", "name": "Alice", "role": "Admin - Toàn quyền"},
    "bob": {"password": "123", "name": "Bob", "role": "Sales - Quyền giới hạn"},
    "charlie": {"password": "123", "name": "Charlie", "role": "Kho - Không có quyền"}
}

@app.post("/api/v1/login")
def login(req: LoginRequest):
    user = DEMO_USERS.get(req.username.lower())
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác")
    
    return {
        "username": req.username.lower(),
        "name": user["name"],
        "role": user["role"]
    }

@app.get("/api/v1/orders")
def get_orders(db: Session = Depends(get_db)):
    # Trả về tất cả các đơn hàng, sắp xếp mới nhất lên đầu
    orders = db.query(models.Order).order_by(models.Order.id.desc()).all()
    return orders

@app.post("/api/v1/refund", response_model=RefundDecision)
async def request_refund(req: RefundRequest, db: Session = Depends(get_db)):
    try:
        # 1. Lấy thông tin đơn hàng từ Database
        order = db.query(models.Order).filter(models.Order.id == req.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        
        # 2. Tính số ngày kể từ khi mua
        delta = datetime.now() - order.order_date
        order_days_old = delta.days
        
        # 3. Gửi cho AI và Casbin quyết định
        decision = await process_refund_request(
            username=req.username,
            resource="transaction",
            action="refund",
            order_days_old=order_days_old
        )
        return decision
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
