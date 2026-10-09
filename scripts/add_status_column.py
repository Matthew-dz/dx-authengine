from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'PENDING';"))
    conn.commit()
print("Column added successfully")
