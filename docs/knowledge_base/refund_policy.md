# CHÍNH SÁCH HOÀN TIỀN (REFUND POLICY) - DX-OS ECOMMERCE

## 1. Giới thiệu chung
Tài liệu này định nghĩa các nguyên tắc và điều kiện để hệ thống tiếp nhận, thẩm định và phê duyệt các yêu cầu hoàn tiền (Refund Requests) cho khách hàng trong hệ thống Thương mại điện tử DX-OS.

---

## 2. Điều kiện được áp dụng hoàn tiền
Yêu cầu hoàn tiền chỉ được xem xét hợp lệ khi thỏa mãn các tiêu chí sau:
- **Thời gian mua hàng:** Đơn hàng được giao dịch trong vòng **30 ngày** (đối với quy trình xử lý thông thường của nhân viên Sales). Các đơn hàng vượt quá 30 ngày cần sự can thiệp phê duyệt của cấp Quản lý (Manager/Admin).
- **Trạng thái đơn hàng:** Đơn hàng phải ở trạng thái đã giao thành công (`DELIVERED`) hoặc đang xử lý giao dịch hợp lệ.
- **Lý do hoàn tiền hợp lệ:**
  - Sản phẩm bị lỗi kỹ thuật hoặc hư hại từ phía nhà sản xuất.
  - Giao sai sản phẩm, sai kích thước hoặc khác biệt rõ rệt so với thông tin mô tả.
  - Đơn hàng bị thất lạc hoặc chậm trễ nghiêm trọng trong quá trình vận chuyển vượt quá cam kết SLA.

---

## 3. Các trường hợp từ chối hoàn tiền
Hệ thống và nhân viên có quyền từ chối hoàn tiền trong các trường hợp:
1. Khách hàng đổi ý mà sản phẩm đã qua sử dụng, tem mác niêm phong bị rách hoặc biến dạng.
2. Sản phẩm bị hư hỏng do lỗi bảo quản hoặc sử dụng sai hướng dẫn từ phía người mua.
3. Các mặt hàng thuộc danh mục không hỗ trợ đổi trả (sản phẩm tiêu hao nhanh, dịch vụ số, thẻ cào, phần mềm đã kích hoạt).
4. Yêu cầu hoàn tiền được gửi sau thời hạn quy định mà không có lý do bất khả kháng được xác nhận.

---

## 4. Hạn mức và Thẩm quyền phê duyệt
- **Nhân viên Bán hàng (Staff Sales / Employee):**
  - Được phép tạo yêu cầu hoàn tiền (`create`) và tiếp nhận thẩm định (`process`).
  - Hạn mức thời gian xét duyệt mặc định: Đơn hàng trong vòng 30 ngày (cấu hình động qua Casbin).
- **Quản lý & Quản trị viên (Manager / Admin):**
  - Có toàn quyền phê duyệt (`approve`) hoặc từ chối (`reject`) yêu cầu hoàn tiền.
  - Phê duyệt các đơn hàng có giá trị cao hoặc thời gian mua vượt quá giới hạn thông thường.

---

## 5. Thời gian xử lý và Hoàn tiền
- Thời gian thẩm định từ khi tạo yêu cầu (`PENDING`) đến khi hoàn tất phê duyệt (`APPROVED`/`REJECTED`) cam kết trong vòng 24 - 48 giờ làm việc.
- Sau khi được phê duyệt (`APPROVED`), đơn hàng tự động chuyển trạng thái `REFUNDED` và hệ thống gửi email xác nhận đến khách hàng.
