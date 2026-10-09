from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

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
    cccd = Column(String, unique=True, index=True)
    role = Column(String)

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

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    employee_username = Column(String)
    decision = Column(String)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
