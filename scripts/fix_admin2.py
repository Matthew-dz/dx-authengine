import hashlib
from app.database import SessionLocal
from app.models import Employee

db = SessionLocal()
admin = db.query(Employee).filter(Employee.username == 'admin').first()
if admin:
    admin.password = hashlib.sha256('1234'.encode()).hexdigest()
    db.commit()
    print("Admin password updated successfully to 1234")
else:
    print("Admin user not found")
