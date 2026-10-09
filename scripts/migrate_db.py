import os
import sys

# Thêm thư mục hiện tại vào sys.path để có thể import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.database import engine

def add_status_column():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE orders ADD COLUMN status VARCHAR DEFAULT 'PENDING'"))
            conn.commit()
            print("Successfully added 'status' column to 'orders' table.")
        except Exception as e:
            print(f"Error (column might already exist): {e}")

if __name__ == "__main__":
    add_status_column()
