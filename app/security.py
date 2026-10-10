import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import jwt

# Nạp biến môi trường từ file .env
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("LỖI NGHIÊM TRỌNG: JWT_SECRET_KEY chưa được cấu hình trong .env")

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Đọc và ép kiểu thời gian hết hạn token, có bọc lỗi (Try-Catch)
try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
except ValueError:
    raise RuntimeError("LỖI CẤU HÌNH: ACCESS_TOKEN_EXPIRE_MINUTES trong .env phải là số nguyên!")
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models



pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_db_security():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_id = payload.get("id")
        username: str = payload.get("sub")
        if token_id is None and username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    # Luôn truy vấn Database mới nhất để lấy role và thông tin thực tế từ DB, tránh tin tưởng role cứng trong JWT
    if token_id is not None:
        user = db.query(models.Employee).filter(models.Employee.id == token_id).first()
    else:
        user = db.query(models.Employee).filter(models.Employee.username == username).first()

    if not user:
        raise credentials_exception
    return user


oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/login", auto_error=False)


def get_optional_current_user(token: Optional[str] = Depends(oauth2_scheme_optional), db: Session = Depends(get_db_security)) -> Optional[models.Employee]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_id = payload.get("id")
        username: str = payload.get("sub")
        if token_id is None and username is None:
            return None
    except jwt.PyJWTError:
        return None

    if token_id is not None:
        return db.query(models.Employee).filter(models.Employee.id == token_id).first()
    return db.query(models.Employee).filter(models.Employee.username == username).first()


