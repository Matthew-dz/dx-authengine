"""
Migration script: Thêm cột 'email' vào bảng 'employees' (PostgreSQL).
Chạy 1 lần duy nhất. An toàn - sẽ bỏ qua nếu cột đã tồn tại.
"""
import os
import sys

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        # Kiểm tra xem bảng employees có tồn tại không
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employees'
            )
        """))
        table_exists = result.scalar()
        
        if not table_exists:
            print("[INFO] Bảng 'employees' chưa tồn tại - sẽ được tạo khi app khởi động (đã bao gồm cột email).")
            return
        
        # Kiểm tra xem cột email đã tồn tại chưa
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'employees' AND column_name = 'email'
            )
        """))
        column_exists = result.scalar()
        
        if column_exists:
            print("[OK] Cột 'email' đã tồn tại trong bảng 'employees'.")
        else:
            conn.execute(text("ALTER TABLE employees ADD COLUMN email VARCHAR(150) UNIQUE"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_employees_email ON employees (email)"))
            conn.commit()
            print("[DONE] Đã thêm cột 'email' vào bảng 'employees'.")

if __name__ == "__main__":
    migrate()
    print("\n✅ Migration hoàn tất!")
