from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:123456@localhost:5432/dx_ecommerce')
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'PENDING'"))
    conn.commit()
