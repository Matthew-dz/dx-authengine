# QUY ĐỊNH CHUYỂN TRẠNG THÁI HỆ THỐNG (WORKFLOW RULES)

## 1. Giới thiệu State Machine
Quy trình hoàn tiền của DX-OS được quản lý chặt chẽ theo mô hình máy trạng thái hữu hạn (Finite State Machine - FSM). Mỗi thay đổi trạng thái phải tuân thủ nguyên tắc toàn vẹn giao dịch (ACID) và được ghi vết trong Audit Log.

---

## 2. Các trạng thái tiêu chuẩn (RefundState)
1. **`PENDING` (Đang chờ xử lý):** Trạng thái khởi tạo ngay khi yêu cầu hoàn tiền được tạo bởi nhân viên bán hàng hoặc khách hàng.
2. **`PROCESSING` (Đang thẩm định):** Trạng thái sau khi nhân viên tiếp nhận đơn, kiểm tra tính hợp lệ và chứng từ liên quan.
3. **`APPROVED` (Đã phê duyệt):** Trạng thái do Quản lý (Manager/Admin) xác nhận đồng ý hoàn tiền. Trạng thái kết thúc thành công (Terminal State).
4. **`REJECTED` (Bị từ chối):** Trạng thái do Quản lý (Manager/Admin) từ chối yêu cầu. Trạng thái kết thúc đóng hồ sơ (Terminal State).
5. **`COMPLETED` (Đã hoàn tất thanh toán):** Trạng thái sau khi dòng tiền đã được ngân hàng hoặc cổng thanh toán hoàn trả về ví/tài khoản khách hàng.

---

## 3. Ma trận chuyển đổi trạng thái (State Transition Matrix)

| Trạng thái hiện tại | Trạng thái tiếp theo hợp lệ | Hành động (Action) | Quyền hạn yêu cầu | Hiệu ứng phụ (Side Effects) |
| :--- | :--- | :--- | :--- | :--- |
| *(None)* | `PENDING` | `create` | `staff_sales`, `employee` | Ghi Audit Log khởi tạo |
| `PENDING` | `PROCESSING` | `process` | `staff_sales`, `employee` | Ghi nhận nhân viên xử lý (`processed_by`) |
| `PROCESSING` | `APPROVED` | `approve` | `manager`, `admin` | Đổi trạng thái Order sang `REFUNDED`, gửi email ngầm |
| `PROCESSING` | `REJECTED` | `reject` | `manager`, `admin` | Đóng yêu cầu hoàn tiền, ghi nhận lý do từ chối |
| `APPROVED` | `COMPLETED` | `complete` | `system`, `admin` | Xác nhận hạch toán kế toán hoàn tất |

---

## 4. Các chuyển đổi bị nghiêm cấm (Invalid Transitions)
Hệ thống sẽ lập tức từ chối và phản hồi lỗi HTTP 400 đối với các hành vi sau:
- **Nhảy cóc trạng thái:** Không được chuyển trực tiếp từ `PENDING` sang `APPROVED` hoặc `REJECTED` mà chưa qua bước `PROCESSING`.
- **Can thiệp vào hồ sơ đã đóng:** Không được sửa đổi hoặc chuyển đổi bất kỳ trạng thái nào từ đơn đã `APPROVED` hoặc `REJECTED`.
- **Chuyển ngược dòng:** Không được chuyển từ `PROCESSING` ngược về `PENDING`.

---

## 5. Ràng buộc ACID và Audit Trail
- Mỗi bước chuyển đổi trạng thái phải được thực thi trong một Database Transaction thống nhất.
- Bắt buộc ghi nhận một bản ghi `AuditLog` chứa đầy đủ cấu trúc JSON trong trường `details` gồm: `resource_id`, `action`, `old_state`, `new_state`, và `timestamp`.
