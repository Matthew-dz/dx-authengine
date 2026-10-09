import sys
import os
from app.database import SessionLocal
from app.models import Employee

db = SessionLocal()
employees = db.query(Employee).all()
print("Employees:")
for emp in employees:
    print(f"- {emp.username} ({emp.password})")
