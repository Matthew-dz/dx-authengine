import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship, synonym
from datetime import datetime
from app.database import Base

class RefundState(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String)
    position = Column(String)
    hire_date = Column(String)
    address = Column(String)
    hometown = Column(String)
    phone = Column(String)
    email = Column(String(150), unique=True, index=True, nullable=True)
    cccd = Column(String, unique=True, index=True)
    role = Column(String)

    refund_requests = relationship("RefundRequest", back_populates="employee")

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    phone = Column(String)
    address = Column(String)
    dob = Column(String)
    gender = Column(String)
    email = Column(String, index=True)
    
    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, index=True)
    price = Column(Float)
    order_date = Column(DateTime)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    status = Column(String, default="PENDING")
    
    customer = relationship("Customer", back_populates="orders")
    refund_requests = relationship("RefundRequest", back_populates="order")

class RefundRequest(Base):
    __tablename__ = "refund_requests"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    reason = Column(String, nullable=True)
    status = Column(Enum(RefundState), default=RefundState.PENDING, index=True)
    notes = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Synonyms for flexible analytics / reporting queries
    processed_by = synonym("employee_id")
    processed_at = synonym("updated_at")

    order = relationship("Order", back_populates="refund_requests")
    employee = relationship("Employee", back_populates="refund_requests")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    employee_username = Column(String)
    decision = Column(String)
    reason = Column(String)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIAuditLog(Base):
    """Bảng ghi nhận nhật ký phân tích và khuyến nghị của AI (Tracking & Compliance)."""
    __tablename__ = "ai_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    ai_session_id = Column(String, nullable=True, index=True)
    tool_name = Column(String, nullable=True, index=True)
    action_type = Column(String, index=True)
    action_status = Column(String, default="SUCCESS", index=True)
    input_context = Column(JSON, nullable=True)
    output_result = Column(JSON, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    execution_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee")



