# dx-authengine
Hệ thống phân quyền và sử lý giao dịch
# DX-AuthEngine – Hệ thống quản lý và hỗ trợ vận hành theo kiến trúc DX-OS

## 1. Giới thiệu đề tài

### Tên đề tài

**DX-AuthEngine – Hệ thống quản lý nghiệp vụ và hỗ trợ ra quyết định theo kiến trúc DX-OS**

### Mô tả bài toán

Trong doanh nghiệp, các hoạt động như quản lý nhân viên, khách hàng, đơn hàng và xử lý hoàn tiền thường liên quan đến nhiều vai trò và nhiều bước nghiệp vụ. Nếu dữ liệu, quy trình và quyền truy cập được quản lý riêng lẻ, doanh nghiệp dễ gặp các vấn đề như:

* Dữ liệu bị phân tán và khó kiểm soát.
* Quy trình xử lý thiếu tính thống nhất.
* Người dùng có thể thực hiện thao tác vượt quá quyền hạn.
* Khó theo dõi lịch sử xử lý nghiệp vụ.
* Khó khai thác dữ liệu để phân tích và hỗ trợ ra quyết định.
* AI khó có thể sử dụng dữ liệu nghiệp vụ một cách an toàn và có kiểm soát.

**DX-AuthEngine** được xây dựng nhằm giải quyết các vấn đề trên bằng cách tổ chức hệ thống theo kiến trúc **H-P-D-I (Human – Process – Data – Intelligence)** của DX-OS.

Hệ thống tập trung vào:

* **Human (H):** quản lý người dùng, nhân viên, vai trò và quyền hạn.
* **Process (P):** quản lý quy trình nghiệp vụ, đặc biệt là quy trình xử lý hoàn tiền.
* **Data (D):** quản lý dữ liệu nghiệp vụ theo hướng Single Source of Truth.
* **Intelligence (I):** tích hợp AI Assistant, Knowledge Base, RAG và Agentic AI để hỗ trợ người dùng khai thác thông tin và thực hiện các tác vụ được kiểm soát.

Mục tiêu là tạo ra một hệ thống trong đó **con người, quy trình, dữ liệu và trí tuệ nhân tạo được kết nối trong cùng một nền tảng**, thay vì hoạt động độc lập.

---

# 2. Kiến trúc DX-OS – H-P-D-I

Hệ thống được tổ chức theo 4 không gian chính:

```text
                    ┌─────────────────────────┐
                    │        HUMAN (H)        │
                    │ User / Employee / Role  │
                    │ Permission / Security   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       PROCESS (P)       │
                    │ Workflow / Authorization│
                    │ Refund / Audit / Events  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         DATA (D)        │
                    │ Customer / Order / Refund│
                    │ Repository / Analytics   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    INTELLIGENCE (I)     │
                    │ AI / Knowledge Base /    │
                    │ RAG / Agentic AI         │
                    └─────────────────────────┘
```

### Human – H

Quản lý danh tính và quyền truy cập:

* Đăng nhập và xác thực người dùng.
* JWT Authentication.
* Quản lý người dùng/nhân viên.
* Quản lý role và permission.
* Phân quyền bằng Casbin.
* Đổi mật khẩu.
* Kiểm soát trạng thái tài khoản.
* Backend xác định người dùng hiện tại từ JWT thay vì tin tưởng thông tin do client gửi lên.

### Process – P

Quản lý quy trình nghiệp vụ:

* Workflow xử lý hoàn tiền.
* Các trạng thái nghiệp vụ: Pending, Approved, Rejected, Completed.
* Kiểm soát transition giữa các trạng thái.
* Phân quyền theo từng bước của workflow.
* Tự động hóa các tác vụ liên quan.
* Audit và theo dõi quá trình xử lý.
* Hướng tới event-driven architecture.

### Data – D

Quản lý dữ liệu tập trung:

* Employee.
* Customer.
* Order.
* Refund.
* AuditLog.
* Repository/Data Access Layer.
* Single Source of Truth.
* Analytics và Dashboard.
* Chuẩn hóa dữ liệu để phục vụ AI.

Backend và database là nguồn dữ liệu chính của hệ thống. Frontend không được xem là nguồn dữ liệu nghiệp vụ có thẩm quyền.

### Intelligence – I

Tích hợp trí tuệ nhân tạo:

* AI Assistant.
* Knowledge Base.
* RAG.
* AI truy xuất dữ liệu nghiệp vụ thông qua các Business Tools.
* Agentic AI.
* AI hỗ trợ phân tích và đề xuất hành động.
* Human-in-the-loop đối với các hành động có ảnh hưởng đến nghiệp vụ.
* AI không tự quyết định quyền nghiệp vụ và không được vượt qua cơ chế phân quyền của hệ thống.

---

# 3. Kiến trúc công nghệ sử dụng

## 3.1. Backend

| Công nghệ  | Vai trò                             |
| ---------- | ----------------------------------- |
| Python     | Ngôn ngữ lập trình chính            |
| FastAPI    | Xây dựng REST API                   |
| SQLAlchemy | ORM và truy cập cơ sở dữ liệu       |
| Pydantic   | Validation và định nghĩa API Schema |
| JWT        | Authentication                      |
| Argon2     | Hash mật khẩu                       |
| Casbin     | Authorization và quản lý Policy     |

## 3.2. Database

Hệ thống sử dụng cơ sở dữ liệu quan hệ để lưu trữ dữ liệu nghiệp vụ.

Các nhóm dữ liệu chính:

```text
Employee
Customer
Order
Refund
AuditLog
```

Database đóng vai trò **Single Source of Truth** đối với dữ liệu nghiệp vụ.

## 3.3. AI

Hệ thống được thiết kế để tích hợp:

```text
AI Assistant
      │
      ├── Knowledge Base
      │
      ├── RAG
      │
      ├── Business Data Tools
      │
      └── Agentic AI
```

AI sử dụng Knowledge Base để trả lời các câu hỏi liên quan đến chính sách/quy trình và sử dụng Business Data Tools để truy xuất dữ liệu nghiệp vụ cần thiết.

## 3.4. Frontend

Frontend cung cấp giao diện để người dùng:

* Đăng nhập.
* Quản lý thông tin.
* Quản lý nhân viên.
* Xem khách hàng.
* Quản lý đơn hàng.
* Xử lý hoàn tiền.
* Xem dashboard.
* Tương tác với AI Assistant.

---

# 4. Kiến trúc phần mềm

Hệ thống được tổ chức theo các tầng:

```text
Frontend
   │
   ▼
API / Router
   │
   ▼
Service
   │
   ▼
Repository
   │
   ▼
Database
```

Đối với AI:

```text
User
 │
 ▼
AI Assistant
 │
 ├──────────────► Knowledge Base / RAG
 │
 └──────────────► Business Data Tools
                         │
                         ▼
                    Data Service
                         │
                         ▼
                    Database
```

AI không truy cập trực tiếp database để tự ý thực hiện nghiệp vụ. Các thao tác cần được thực hiện thông qua các service/API/tool được hệ thống kiểm soát.

---

# 5. Cấu trúc project

Cấu trúc chính của project:

```text
dx-authengine/
│
├── app/
│   ├── agent.py
│   ├── database.py
│   ├── email_service.py
│   ├── main.py
│   ├── models.py
│   │
│   ├── api/
│   │   └── v1/
│   │
│   ├── services/
│   │
│   ├── repositories/
│   │
│   └── schemas/
│
├── frontend/
│   └── index.html
│
├── casbin_config/
│   ├── model.conf
│   └── policy.csv
│
├── knowledge/
│   ├── refund/
│   ├── system/
│   └── employee/
│
├── scripts/
│
├── tests/
│
├── patches/
│
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

# 6. Yêu cầu môi trường

Trước khi cài đặt project, cần chuẩn bị:

* Python 3.x
* pip
* Git
* Database phù hợp với cấu hình trong `.env`
* Trình duyệt web

Kiểm tra Python:

```bash
python --version
```

Kiểm tra pip:

```bash
pip --version
```

Kiểm tra Git:

```bash
git --version
```

---

# 7. Hướng dẫn cài đặt

## Bước 1 – Clone project

Clone repository:

```bash
git clone https://github.com/Matthew-dz/dx-authengine.git
```

Di chuyển vào thư mục project:

```bash
cd dx-authengine
```

---

## Bước 2 – Tạo môi trường ảo Python

Windows:

```bash
python -m venv venv
```

Kích hoạt môi trường:

```bash
venv\Scripts\activate
```

Nếu sử dụng macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Sau khi kích hoạt thành công, terminal sẽ hiển thị môi trường `venv`.

---

## Bước 3 – Cài đặt thư viện

Cài đặt các dependency:

```bash
pip install -r requirements.txt
```

Kiểm tra các package đã được cài:

```bash
pip list
```

---

# 8. Cấu hình biến môi trường

Project sử dụng file `.env` để lưu các thông tin cấu hình.

Tạo `.env` từ file mẫu:

```bash
copy .env.example .env
```

Trên macOS/Linux:

```bash
cp .env.example .env
```

Sau đó mở file `.env` và cấu hình các thông tin cần thiết.

Ví dụ:

```env
DATABASE_URL=your_database_url

JWT_SECRET=your_secret_key

GEMINI_API_KEY=your_gemini_api_key

SMTP_HOST=your_smtp_host
SMTP_PORT=your_smtp_port
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_email_password
```

> Không commit file `.env` lên GitHub vì file này có thể chứa thông tin bí mật như API Key, database password hoặc thông tin email.

---

# 9. Cấu hình Database

Kiểm tra biến:

```env
DATABASE_URL
```

trong file `.env`.

Database cần được tạo và cấu hình trước khi chạy backend.

Sau khi cấu hình database, kiểm tra khả năng kết nối từ ứng dụng.

Nếu project sử dụng database local, đảm bảo database service đang chạy trước khi khởi động backend.

---

# 10. Chạy Backend

Sau khi hoàn tất cấu hình, chạy FastAPI:

```bash
uvicorn app.main:app --reload
```

Nếu chạy thành công, backend sẽ hoạt động tại:

```text
http://127.0.0.1:8000
```

FastAPI cung cấp giao diện API documentation tại:

```text
http://127.0.0.1:8000/docs
```

Có thể sử dụng Swagger UI để kiểm tra các API của hệ thống.

---

# 11. Chạy Frontend

Frontend nằm trong thư mục:

```text
frontend/
```

Mở file:

```text
frontend/index.html
```

bằng trình duyệt hoặc sử dụng một local web server để chạy frontend.

Frontend kết nối tới Backend API để thực hiện các thao tác nghiệp vụ.

---

# 12. Luồng hoạt động chính

## 12.1. Đăng nhập

```text
User
 │
 ▼
Login API
 │
 ▼
Kiểm tra tài khoản
 │
 ▼
Kiểm tra password
 │
 ▼
JWT
 │
 ▼
Authenticated User
```

Sau khi đăng nhập, JWT được sử dụng để xác định người dùng trong các request tiếp theo.

---

## 12.2. Kiểm tra quyền

```text
Request
   │
   ▼
JWT Authentication
   │
   ▼
Current User
   │
   ▼
Casbin Authorization
   │
   ▼
Business Rules
   │
   ▼
Service
```

Frontend chỉ cung cấp giao diện. Quyền thực sự được kiểm tra ở backend.

---

## 12.3. Xử lý hoàn tiền

```text
Create Refund
      │
      ▼
Pending
      │
      ├──────► Rejected
      │
      ▼
Approved
      │
      ▼
Completed
```

Các transition phải tuân thủ workflow và quyền của người dùng.

AI có thể hỗ trợ giải thích hoặc đề xuất nhưng không được tự ý bỏ qua workflow và authorization.

---

# 13. AI và RAG

AI được tổ chức thành nhiều lớp:

```text
                ┌─────────────────┐
                │   AI Assistant  │
                └────────┬────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Knowledge Base         Business Data
              │                     │
              ▼                     ▼
             RAG              Data Tools
              │                     │
              └──────────┬──────────┘
                         ▼
                       AI
```

Knowledge Base chứa các tài liệu về:

```text
knowledge/
├── refund/
│   ├── refund_policy.md
│   └── refund_process.md
│
├── system/
│   └── system_rules.md
│
└── employee/
    └── roles_permissions.md
```

RAG giúp AI truy xuất thông tin liên quan từ Knowledge Base trước khi tạo câu trả lời.

---

# 14. Agentic AI

Agentic AI cho phép AI sử dụng các tool được hệ thống cung cấp để thực hiện những tác vụ được kiểm soát.

Ví dụ:

```text
User:
"Kiểm tra refund #15 và cho tôi biết có đủ điều kiện duyệt không."

        │
        ▼

AI Assistant
        │
        ├──► RAG
        │       └──► Refund Policy
        │
        └──► Business Tool
                └──► Refund #15
                        │
                        ▼
                 Phân tích điều kiện
                        │
                        ▼
                   AI trả kết quả
```

Đối với hành động có ảnh hưởng trực tiếp đến nghiệp vụ, hệ thống áp dụng cơ chế authorization và có thể yêu cầu xác nhận của con người.

---

# 15. Unified API

API được tổ chức theo version:

```text
/api/v1/
```

Các nhóm API chính:

```text
/api/v1/auth
/api/v1/users
/api/v1/employees
/api/v1/customers
/api/v1/orders
/api/v1/refunds
/api/v1/analytics
/api/v1/ai
```

Kiến trúc:

```text
Frontend / AI
      │
      ▼
Unified API
      │
      ▼
Service
      │
      ▼
Repository
      │
      ▼
Database
```

Điều này giúp các thành phần trong hệ thống sử dụng cùng một nguồn API và cùng một cơ chế authorization.

---

# 16. Analytics và Dashboard

Dashboard tập trung dữ liệu từ 4 không gian H-P-D-I.

### Human

* Tổng số người dùng.
* Người dùng đang hoạt động.
* Người dùng bị vô hiệu hóa.
* Nhân viên.
* Role và permission.

### Process

* Refund Pending.
* Refund Approved.
* Refund Rejected.
* Refund Completed.
* Thống kê hiệu quả xử lý workflow.

### Data

* Tổng số đơn hàng.
* Tổng số khách hàng.
* Tổng số refund.
* Tổng giá trị refund.
* Thống kê theo thời gian.

### Intelligence

* Số lượng AI request.
* AI request thành công/thất bại.
* Số lượng RAG query.
* Số lượng AI action.

Dashboard sử dụng Unified API thay vì truy cập trực tiếp database.

---

# 17. Event và Integration

Hệ thống có thể sử dụng các business event như:

```text
UserCreated
UserUpdated
UserDeactivated

OrderCreated
OrderUpdated

RefundCreated
RefundApproved
RefundRejected
RefundCompleted
```

Một event có thể chứa:

```text
event_type
entity_id
user_id
timestamp
data
```

Các event có thể được sử dụng cho:

* Audit.
* Email notification.
* Analytics.
* AI/Data processing.
* Các module tích hợp khác.

---

# 18. Bảo mật

Các cơ chế bảo mật chính:

* JWT Authentication.
* Argon2 password hashing.
* Casbin Authorization.
* Kiểm tra quyền ở backend.
* Không tin tưởng username/user information do client tự gửi.
* AI không có quyền cao hơn người dùng hiện tại.
* Không cho AI tự ý bỏ qua business rules.
* `.env` được loại khỏi Git repository.
* Không đưa password hash vào response API.

---

# 19. Open-Core và DX-OS

Project được định hướng theo mô hình **Open-Core** và kiến trúc **DX-OS**.

Hệ thống tập trung vào 4 không gian:

```text
H – Human
P – Process
D – Data
I – Intelligence
```

Mục tiêu không chỉ là xây dựng một ứng dụng CRUD mà là kết nối:

```text
Con người
    ↓
Quy trình
    ↓
Dữ liệu
    ↓
Trí tuệ nhân tạo
```

tạo thành một hệ thống vận hành thống nhất.

---

# 20. Mục tiêu của hệ thống

DX-AuthEngine hướng tới các mục tiêu:

1. Quản lý người dùng và quyền truy cập tập trung.
2. Chuẩn hóa quy trình nghiệp vụ.
3. Đảm bảo dữ liệu có một nguồn sự thật duy nhất.
4. Cung cấp khả năng phân tích dữ liệu.
5. Tích hợp AI vào quy trình nghiệp vụ.
6. Sử dụng RAG để cung cấp câu trả lời dựa trên Knowledge Base.
7. Sử dụng Agentic AI thông qua các tool được kiểm soát.
8. Đảm bảo AI hoạt động trong phạm vi quyền của người dùng.
9. Kết nối H-P-D-I thành một hệ thống thống nhất.

---

# 21. License

Project được phát hành theo license được khai báo trong file:

```text
LICENSE
```

Vui lòng xem file `LICENSE` để biết đầy đủ điều khoản sử dụng, sao chép và phân phối project.

---

# 22. Quick Start

Nếu môi trường đã được chuẩn bị đầy đủ, có thể chạy nhanh theo các bước:

```bash
git clone https://github.com/Matthew-dz/dx-authengine.git

cd dx-authengine

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt
```

Tạo và cấu hình `.env`:

```bash
copy .env.example .env
```

Sau đó chạy:

```bash
uvicorn app.main:app --reload
```

Mở:

```text
http://127.0.0.1:8000/docs
```

để kiểm tra API.

---

# 23. Tổng quan kiến trúc

```text
                         DX-OS
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       HUMAN            PROCESS            DATA
          │                │                │
          │                │                │
      User/Role        Workflow          Database
      Permission       Refund            Repository
      Security         Audit              Analytics
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                     INTELLIGENCE
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
             AI           RAG       Agentic AI
              │            │            │
              └────────────┼────────────┘
                           ▼
                    Unified API
                           │
                           ▼
                     DX-AuthEngine
```

**DX-AuthEngine** hướng tới việc kết hợp **Human – Process – Data – Intelligence** thành một nền tảng vận hành thống nhất, trong đó AI đóng vai trò hỗ trợ con người và hoạt động trong phạm vi các quy tắc, dữ liệu và quyền hạn được hệ thống kiểm soát.

