import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.knowledge_service import KnowledgeBaseService, KnowledgeDocument
from fastapi.testclient import TestClient
from app.main import app


def test_knowledge_base_singleton():
    """Kiểm tra KnowledgeBaseService tuân thủ nghiêm ngặt mẫu thiết kế Singleton."""
    s1 = KnowledgeBaseService()
    s2 = KnowledgeBaseService()
    assert s1 is s2, "LỖI: KnowledgeBaseService không phải là Singleton!"
    print(" -> Singleton Pattern: Hai instance cùng trỏ tới một vùng nhớ duy nhất.")


def test_directory_structure_and_sample_file():
    """Kiểm tra cấu trúc thư mục knowledge/ và file mẫu refund_policy.md."""
    project_root = Path(__file__).resolve().parent.parent
    knowledge_dir = project_root / "knowledge"

    # 1. Kiểm tra 3 thư mục
    refund_dir = knowledge_dir / "refund"
    system_dir = knowledge_dir / "system"
    employee_dir = knowledge_dir / "employee"

    assert refund_dir.is_dir(), f"Thiếu thư mục: {refund_dir}"
    assert system_dir.is_dir(), f"Thiếu thư mục: {system_dir}"
    assert employee_dir.is_dir(), f"Thiếu thư mục: {employee_dir}"

    # 2. Kiểm tra file mẫu refund_policy.md
    sample_file = refund_dir / "refund_policy.md"
    assert sample_file.is_file(), f"Thiếu file mẫu: {sample_file}"

    with open(sample_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert content.startswith("---"), "refund_policy.md phải bắt đầu bằng YAML Frontmatter '---'"
    assert 'category: "refund"' in content or "category: refund" in content
    assert 'title: "Chính sách hoàn tiền"' in content or "title: Chính sách hoàn tiền" in content
    print(" -> Cấu trúc thư mục & File mẫu: Đầy đủ 3 thư mục và refund_policy.md chuẩn Frontmatter.")


def test_load_documents_and_in_memory_cache():
    """Kiểm tra hàm load_documents() nạp dữ liệu vào _cache trong RAM."""
    kb_service = KnowledgeBaseService()
    count = kb_service.load_documents()
    assert count >= 1, "load_documents() phải nạp ít nhất 1 tài liệu!"
    assert "refund_policy.md" in kb_service._cache, "refund_policy.md phải có trong _cache"

    doc = kb_service._cache["refund_policy.md"]
    assert isinstance(doc, KnowledgeDocument)
    assert doc.title == "Chính sách hoàn tiền"
    assert doc.category == "refund"
    assert doc.version == "1.0"
    assert doc.language == "vi"
    assert doc.updated_at == "2026-10-10"
    assert "Mục đích" in doc.content
    assert "Tạo yêu cầu" in doc.content
    print(f" -> In-Memory Cache: Nạp thành công {count} tài liệu vào RAM với đầy đủ Frontmatter.")


def test_fast_retrieval_functions():
    """Kiểm tra các hàm truy xuất tốc độ cao get_documents_by_category và get_document_by_name."""
    kb_service = KnowledgeBaseService()
    kb_service.load_documents()

    # 1. Truy xuất theo danh mục (category)
    refund_docs = kb_service.get_documents_by_category("refund")
    assert len(refund_docs) >= 1
    assert any(d.filename == "refund_policy.md" for d in refund_docs)

    empty_docs = kb_service.get_documents_by_category("non_existent_category")
    assert len(empty_docs) == 0

    # 2. Truy xuất theo tên file
    doc1 = kb_service.get_document_by_name("refund_policy.md")
    assert doc1 is not None
    assert doc1.filename == "refund_policy.md"

    # Hỗ trợ truy xuất không cần gõ .md
    doc2 = kb_service.get_document_by_name("refund_policy")
    assert doc2 is not None
    assert doc2.filename == "refund_policy.md"

    # File không tồn tại
    non_existent = kb_service.get_document_by_name("unknown_file.md")
    assert non_existent is None
    print(" -> Truy xuất tốc độ cao: get_documents_by_category và get_document_by_name hoạt động chính xác.")


def test_path_traversal_security():
    """Kiểm tra an toàn bảo mật: Chống Path Traversal và chỉ đọc file .md."""
    kb_service = KnowledgeBaseService()

    # 1. Chặn Path Traversal khi gọi get_document_by_name
    malicious_inputs = [
        "../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "/etc/shadow",
        "\\system32\\cmd.exe",
        "../../app/models.py",
        "../.env"
    ]

    for evil_input in malicious_inputs:
        try:
            kb_service.get_document_by_name(evil_input)
            assert False, f"LỖI BẢO MẬT: Không chặn được Path Traversal: {evil_input}"
        except ValueError as e:
            assert "Path Traversal" in str(e)

    # 2. Kiểm tra chỉ đọc file .md (file .txt, .py trong knowledge/ không được nạp vào cache)
    project_root = Path(__file__).resolve().parent.parent
    fake_txt_file = project_root / "knowledge" / "system" / "secret.txt"
    try:
        with open(fake_txt_file, "w", encoding="utf-8") as f:
            f.write("Dữ liệu nhạy cảm không được đọc!")

        kb_service.load_documents()
        assert "secret.txt" not in kb_service._cache, "LỖI BẢO MẬT: File .txt không được nạp vào cache!"
    finally:
        if fake_txt_file.exists():
            fake_txt_file.unlink()

    print(" -> Bảo mật chống Path Traversal: Chặn 100% input nguy hiểm và cô lập chỉ đọc file .md.")


def test_app_startup_integration():
    """Kiểm tra tích hợp khởi động: Khi app FastAPI startup, Knowledge Base tự động được nạp."""
    kb_service = KnowledgeBaseService()
    kb_service.clear_cache()
    assert not kb_service.is_loaded

    # Sử dụng TestClient để kích hoạt sự kiện startup
    with TestClient(app) as client:
        assert kb_service.is_loaded, "Sau khi app khởi động, cache phải được nạp tự động!"
        assert "refund_policy.md" in kb_service._cache

    print(" -> Tích hợp Startup: KnowledgeBaseService tự động nạp toàn bộ kiến thức vào RAM khi bật server.")


if __name__ == "__main__":
    print("\n--- BẮT ĐẦU KIỂM THỬ KNOWLEDGE BASE SERVICE ---")
    test_knowledge_base_singleton()
    test_directory_structure_and_sample_file()
    test_load_documents_and_in_memory_cache()
    test_fast_retrieval_functions()
    test_path_traversal_security()
    test_app_startup_integration()
    print("\n🎉 TẤT CẢ KIỂM THỬ KNOWLEDGE BASE SERVICE ĐÃ ĐẠT 100%!")
