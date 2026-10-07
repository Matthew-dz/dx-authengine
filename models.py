from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, index=True)
    price = Column(Float)
    order_date = Column(DateTime)
