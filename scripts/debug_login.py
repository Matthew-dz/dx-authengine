import hashlib
from app.database import SessionLocal
from app import models

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password

db = SessionLocal()
username = 'rayden'
user = db.query(models.Employee).filter(models.Employee.username == username.lower()).first()
print(f"User found: {user is not None}")
if user:
    print(f"Username: '{user.username}'")
    print(f"Stored Hash: '{user.password}'")
    print(f"Calculated Hash for 1234: '{get_password_hash('1234')}'")
    print(f"Verify returns: {verify_password('1234', user.password)}")
