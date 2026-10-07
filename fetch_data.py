import requests
import random
from datetime import datetime, timedelta
from database import SessionLocal, engine
from models import Base, Order

# Tự động tạo bảng nếu chưa có (dù main.py cũng có, thêm ở đây để chạy độc lập cũng được)
Base.metadata.create_all(bind=engine)

def fetch_and_save_data():
    url = "https://dummyjson.com/products"
    print(f"Đang fetch dữ liệu từ {url}...")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        products = data.get("products", [])[:20] # Lấy 20 sản phẩm đầu tiên
        
        db = SessionLocal()
        try:
            for item in products:
                # Random ngày mua hàng trong khoảng 60 ngày trở lại đây
                days_ago = random.randint(0, 60)
                random_date = datetime.now() - timedelta(days=days_ago)
                
                order = Order(
                    product_name=item["title"],
                    price=float(item["price"]),
                    order_date=random_date
                )
                db.add(order)
            
            db.commit()
            print("Đã lưu 20 đơn hàng thành công vào cơ sở dữ liệu PostgreSQL.")
        except Exception as e:
            db.rollback()
            print("Có lỗi xảy ra khi lưu vào Database:", e)
        finally:
            db.close()
    else:
        print("Lỗi khi gọi API:", response.status_code)

if __name__ == "__main__":
    fetch_and_save_data()
