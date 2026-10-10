# ĐỊNH NGHĨA QUYỀN HẠN HỆ THỐNG (SYSTEM ROLES & CASBIN POLICIES)

## 1. Tổng quan kiến trúc Phân quyền
Hệ thống DX-OS sử dụng thư viện **Casbin** kết hợp mô hình RBAC (Role-Based Access Control) và ABAC (Attribute-Based Access Control) để kiểm soát quyền truy cập chi tiết đến từng tài nguyên (Resource) và hành động (Action).

---

## 2. Các vai trò trong hệ thống (System Roles)

### 👑 Quản trị viên hệ thống (Role: `admin`)
- **Mô tả:** Người nắm giữ toàn bộ đặc quyền quản trị kỹ thuật và vận hành cao nhất.
- **Quyền hạn chi tiết bằng ngôn ngữ tự nhiên:**
  - Được phép đọc và chỉnh sửa danh sách nhân viên (`employee:read`, `employee:write`).
  - Được phép đọc và cấu hình chính sách phân quyền Casbin (`policy:read`, `policy:write`).
  - Được phép xem toàn bộ nhật ký truy vết hệ thống (`audit_log:read`, `audit_log:write`).
  - Được phép truy cập toàn bộ module báo cáo phân tích kinh doanh (`analytics:read`).
  - Được quyền phê duyệt (`refund:approve`) và từ chối (`refund:reject`) hoàn tiền đối với mọi đơn hàng không giới hạn giá trị và thời gian (hạn mức tối đa 999,999 ngày).

---

### 👔 Quản lý nghiệp vụ (Role: `manager`)
- **Mô tả:** Cấp quản lý chịu trách nhiệm thẩm định chất lượng dịch vụ và đưa ra quyết định cuối cùng về tài chính và chăm sóc khách hàng.
- **Quyền hạn chi tiết bằng ngôn ngữ tự nhiên:**
  - Được phép phê duyệt yêu cầu hoàn tiền (`refund:approve`).
  - Được phép từ chối yêu cầu hoàn tiền (`refund:reject`).
  - Được phép truy cập xem nhật ký truy vết toàn hệ thống (`audit_log:read`).
  - Được phép truy cập xem báo cáo thống kê KPI và hiệu suất nhân viên (`analytics:read`).
  - **Giới hạn nghiệp vụ:** Không tham gia trực tiếp vào việc tạo đơn hoàn tiền (`refund:create`) hoặc quy trình sơ thẩm (`refund:process`) để đảm bảo tính khách quan (nguyên tắc phân tách trách nhiệm Segregation of Duties).

---

### 💼 Nhân viên bán hàng & CSKH (Role: `staff_sales` / `employee` / `sale`)
- **Mô tả:** Đội ngũ tiếp xúc trực tiếp với khách hàng, tiếp nhận khiếu nại và lập hồ sơ hoàn tiền.
- **Quyền hạn chi tiết bằng ngôn ngữ tự nhiên:**
  - Được phép khởi tạo yêu cầu hoàn tiền mới (`refund:create`).
  - Được phép tiếp nhận và chuyển trạng thái đơn sang thẩm định (`refund:process`).
  - Có hạn mức giới hạn thời gian mua hàng mặc định là **30 ngày** (`transaction:refund:30`). Đơn hàng ngoài 30 ngày cần chuyển cấp quản lý.
  - **Giới hạn an ninh:** Bị cấm truy cập module Báo cáo phân tích (`analytics`), bị cấm xem Nhật ký kiểm toán nội bộ (`audit-logs`), và không có quyền tự phê duyệt (`approve`) hoặc từ chối (`reject`) yêu cầu hoàn tiền.

---

## 3. Cấu hình Casbin Model & Matcher
- **Mô hình yêu cầu (Request Definition):** `r = sub, obj, act`
  - `sub`: Đối tượng thực hiện (chứa `username` và `role`).
  - `obj`: Tài nguyên được thao tác (chứa tên `name` và thuộc tính phụ như `order_days_old`).
  - `act`: Hành động thực hiện (`read`, `write`, `create`, `process`, `approve`, `reject`).
- **Matcher Logic:**
  ```ini
  m = (r.sub.role == p.sub || g(r.sub.role, p.sub)) && r.obj.name == p.obj && r.act == p.act && (p.max_days == "" || p.max_days == "999999" || float(r.obj.order_days_old) <= float(p.max_days))
  ```
- **Ý nghĩa:** Cho phép hành động khi vai trò người dùng khớp với chính sách, tài nguyên và hành động trùng khớp, đồng thời số ngày của đơn hàng không vượt quá hạn mức `max_days` quy định.
