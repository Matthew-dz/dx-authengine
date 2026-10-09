import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE audit_logs RESTART IDENTITY CASCADE;"))
        conn.commit()
    print("Đã xóa toàn bộ dữ liệu bảng audit_logs thành công!")
except Exception as e:
    print(f"Lỗi: {e}")
