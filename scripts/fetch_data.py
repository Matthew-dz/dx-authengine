import requests
import random
from datetime import datetime, timedelta
from app.database import SessionLocal, engine
from app.models import Base, Order, Customer, Employee
from app.security import get_password_hash



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
            # Khởi tạo nhân viên (Employees)
            employees_data = [
                Employee(username="admin", password=get_password_hash("1234"), full_name="Administrator", position="Giám đốc", hire_date="2020-01-01", address="Hà Nội", hometown="Hà Nội", phone="0988000111", cccd="001090000001", role="admin"),
                Employee(username="alice", password=get_password_hash("123"), full_name="Alice Nguyen", position="Quản lý", hire_date="2021-02-15", address="Hà Nội", hometown="Hải Phòng", phone="0988000222", cccd="001091000002", role="admin"),
                Employee(username="bob", password=get_password_hash("123"), full_name="Bob Tran", position="Nhân viên Sales", hire_date="2022-03-20", address="Đà Nẵng", hometown="Huế", phone="0988000333", cccd="001092000003", role="staff_sales"),
                Employee(username="charlie", password=get_password_hash("123"), full_name="Charlie Le", position="Nhân viên Kho", hire_date="2023-04-10", address="TP.HCM", hometown="Cần Thơ", phone="0988000444", cccd="001093000004", role="warehouse")
            ]
            db.add_all(employees_data)
            db.commit()
            # Khởi tạo khách hàng
            fraud_customer = Customer(full_name="Nguyễn Văn Lạm Dụng", phone="0123456789", address="Hà Nội", dob="1990-01-01", gender="Nam", email="buyer_fraud@example.com")
            db.add(fraud_customer)
            db.commit()
            db.refresh(fraud_customer)
            
            normal_customers = []
            for i in range(1, 10):
                c = Customer(full_name=f"Khách hàng {i}", phone=f"098765432{i}", address="Hồ Chí Minh", dob="1995-05-05", gender="Nữ", email=f"buyer_{i}@example.com")
                db.add(c)
                normal_customers.append(c)
            db.commit()
            
            for i, item in enumerate(products):
                # Random ngày mua hàng trong khoảng 60 ngày trở lại đây
                days_ago = random.randint(0, 60)
                random_date = datetime.now() - timedelta(days=days_ago)
                
                c_id = fraud_customer.id if i < 3 else random.choice(normal_customers).id
                
                order = Order(
                    product_name=item["title"],
                    price=float(item["price"]),
                    order_date=random_date,
                    customer_id=c_id
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

def init_casbin_policies():
    from app.agent import enforcer
    refund_policies = [
        # Nhóm Nhân viên (Employee/Sale): Có quyền create và process
        ("staff_sales", "refund", "create", ""),
        ("staff_sales", "refund", "process", ""),
        ("employee", "refund", "create", ""),
        ("employee", "refund", "process", ""),
        ("sale", "refund", "create", ""),
        ("sale", "refund", "process", ""),
        # Nhóm Quản lý (Manager/Admin): Có quyền approve và reject
        ("manager", "refund", "approve", ""),
        ("manager", "refund", "reject", ""),
        ("admin", "refund", "approve", ""),
        ("admin", "refund", "reject", ""),
    ]
    existing = enforcer.get_policy()
    changed = False
    for p in refund_policies:
        if not any(ep[:4] == list(p) for ep in existing):
            enforcer.add_policy(*p)
            changed = True
    if changed:
        enforcer.save_policy()
    print("Đã cấu hình chính sách Casbin cho module refund thành công.")

if __name__ == "__main__":
    fetch_and_save_data()
    init_casbin_policies()

