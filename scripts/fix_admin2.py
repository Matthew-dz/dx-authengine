from app.security import get_password_hash
from app.database import SessionLocal
from app.models import Employee

db = SessionLocal()
admin = db.query(Employee).filter(Employee.username == 'admin').first()
if admin:
    admin.password = get_password_hash('1234')
    db.commit()
    print("Admin password updated successfully to 1234")
else:
    print("Admin user not found")
