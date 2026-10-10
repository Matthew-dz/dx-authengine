---
title: "Kiến trúc hệ thống và quy tắc nghiệp vụ"
category: "system"
version: "1.0"
language: "vi"
updated_at: "2026-10-10"
---
# Kiến trúc hệ thống và quy tắc nghiệp vụ
## Tổng quan
DX-AuthEngine & OS vận hành dựa trên cơ chế phân quyền RBAC kết hợp ABAC (Casbin).
## Quy tắc an toàn
1. Mọi giao dịch tài chính phải được kiểm toán (Audit Log).
2. Tách biệt vai trò giữa người tạo và người phê duyệt.
