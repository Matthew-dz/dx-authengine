import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.database import engine
from app.agent import enforcer

# Import tất cả các router từ app/api/v1/
from app.api.v1.auth import router as auth_router, legacy_router as auth_legacy_router
from app.api.v1.users import router as users_router, legacy_router as users_legacy_router
from app.api.v1.employees import router as employees_router
from app.api.v1.orders import router as orders_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.ai import router as ai_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.system import router as system_router


models.Base.metadata.create_all(bind=engine)
load_dotenv()

app = FastAPI(
    title="DX-AuthEngine API",
    description="Unified API Enterprise System with Role-Based Access Control and AI Assistant",
    version="1.0.0"
)

cors_origins_str = os.getenv("FRONTEND_CORS_ORIGINS", "")
cors_origins_list = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def bootstrap_admin():
    # Kiểm tra xem quyền cho tài khoản admin mặc định đã tồn tại chưa
    # Nếu chưa, bơm quyền khởi thủy để không bị lockout
    policies = enforcer.get_policy()
    has_admin_policy = any(p[0] == "admin" for p in policies)
    if not has_admin_policy:
        enforcer.add_policy("admin", "employee", "read", "")
        enforcer.add_policy("admin", "employee", "write", "")
        enforcer.add_policy("admin", "transaction", "read", "")
        enforcer.add_policy("admin", "transaction", "refund", "999999")
        enforcer.add_policy("admin", "audit_log", "read", "")
        enforcer.add_policy("admin", "audit_log", "write", "")
        enforcer.add_policy("admin", "role", "read", "")
        enforcer.add_policy("admin", "role", "write", "")
        enforcer.add_policy("admin", "policy", "read", "")
        enforcer.add_policy("admin", "policy", "write", "")
        enforcer.save_policy()

    # Khởi tạo quyền cho module refund
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
        # Nhóm Phân tích (Analytics): Chỉ Role Admin và Manager có quyền truy cập
        ("admin", "analytics", "read", ""),
        ("manager", "analytics", "read", ""),
        # Nhóm Dashboard (BFF Pattern): Admin, Manager và Employee
        ("admin", "dashboard", "read", ""),
        ("manager", "dashboard", "read", ""),
        ("employee", "dashboard", "read", ""),
        ("staff_sales", "dashboard", "read", ""),
        ("sale", "dashboard", "read", ""),
        # Nhóm AI Assistant (Bước 5.4 - Unified Experience)
        ("admin", "ai", "read", ""),
        ("admin", "ai", "chat", ""),
        ("manager", "ai", "read", ""),
        ("manager", "ai", "chat", ""),
        ("staff_sales", "ai", "read", ""),
        ("staff_sales", "ai", "chat", ""),
        ("employee", "ai", "read", ""),
        ("employee", "ai", "chat", ""),
        ("sale", "ai", "read", ""),
        ("sale", "ai", "chat", ""),
    ]

    current_policies = enforcer.get_policy()
    changed = False
    for p in refund_policies:
        if not any(cp[:4] == list(p) for cp in current_policies):
            enforcer.add_policy(*p)
            changed = True
    if changed:
        enforcer.save_policy()

    # Nạp toàn bộ tài liệu Knowledge Base vào RAM In-Memory Cache chuẩn bị cho RAG
    from app.services.knowledge_service import KnowledgeBaseService
    KnowledgeBaseService().load_documents()

    # Tự động gọi RAG Service để Semantic Chunking và cập nhật vector mới nhất vào ChromaDB
    try:
        from app.services.rag_service import RAGService
        RAGService().index_knowledge_base()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Không thể index ChromaDB tại startup: {e}")

    # Đăng ký các Event Handlers vào EventBus (Bước 5.2)
    from app.events.event_bus import event_bus
    from app.events.handlers.refund_handler import handle_refund_approved
    event_bus.subscribe("RefundApproved", handle_refund_approved)


# ======================= UNIFIED API ROUTER (BƯỚC 5.1) =======================
# Gắn tất cả các router vào ứng dụng FastAPI chính
app.include_router(auth_router)
app.include_router(auth_legacy_router)
app.include_router(users_router)
app.include_router(users_legacy_router)
app.include_router(employees_router)
app.include_router(orders_router)
app.include_router(refunds_router)
app.include_router(analytics_router)
app.include_router(ai_router)
app.include_router(audit_logs_router)
app.include_router(system_router)


@app.get("/")
def root():
    return {
        "success": True,
        "message": "DX-AuthEngine Unified API is running",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
