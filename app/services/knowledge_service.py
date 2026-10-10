import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class KnowledgeDocument(BaseModel):
    """
    Mô hình dữ liệu tài liệu tri thức (Knowledge Document) chuẩn Markdown Frontmatter.
    Phục vụ cho Retrieval-Augmented Generation (RAG) và truy xuất thông tin hệ thống.
    """
    filename: str
    title: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = "1.0"
    language: Optional[str] = "vi"
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content: str
    raw_content: Optional[str] = None
    filepath: Optional[str] = None


class KnowledgeBaseService:
    """
    Knowledge Base Service quản lý kho tri thức nội bộ theo chuẩn Markdown Frontmatter.
    Áp dụng mẫu thiết kế Singleton và In-Memory Caching để đảm bảo tốc độ truy xuất cao nhất.
    Tích hợp cơ chế phòng vệ chống lỗ hổng Path Traversal.
    """
    _instance: Optional["KnowledgeBaseService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(KnowledgeBaseService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if getattr(self, "_initialized", False):
            return

        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            # Mặc định trỏ về thư mục knowledge ở thư mục gốc của dự án
            project_root = Path(__file__).resolve().parent.parent.parent
            self.base_dir = (project_root / "knowledge").resolve()

        # In-Memory Cache lưu trữ tài liệu với key là tên file
        self._cache: Dict[str, KnowledgeDocument] = {}
        self._initialized = True

    @property
    def is_loaded(self) -> bool:
        return len(self._cache) > 0

    def load_documents(self) -> int:
        """
        Quét đệ quy thư mục knowledge/, đọc các file .md hợp lệ.
        Sử dụng chuỗi --- để tách Frontmatter (parse bằng yaml.safe_load) và Content.
        Lưu đối tượng KnowledgeDocument vào self._cache với key là tên file.
        Bảo mật: Chống Path Traversal và chỉ chấp nhận file .md nằm trong self.base_dir.
        """
        if not self.base_dir.exists():
            logger.warning(f"Thư mục Knowledge Base không tồn tại: {self.base_dir}")
            return 0

        loaded_count = 0
        new_cache: Dict[str, KnowledgeDocument] = {}

        for root, _, files in os.walk(self.base_dir):
            for file in files:
                # 1. Bảo mật: Chỉ đọc file có đuôi .md
                if not file.lower().endswith(".md"):
                    continue

                full_path = Path(root) / file
                resolved_path = full_path.resolve()

                # 2. Bảo mật: Chống Path Traversal (kiểm tra đường dẫn phải nằm trong self.base_dir)
                try:
                    resolved_path.relative_to(self.base_dir)
                except ValueError:
                    logger.warning(f"Cảnh báo bảo mật: Bỏ qua file nằm ngoài knowledge dir: {resolved_path}")
                    continue

                try:
                    with open(resolved_path, "r", encoding="utf-8") as f:
                        raw_text = f.read()

                    # 3. Tách Frontmatter và Content bằng chuỗi ---
                    frontmatter_data = {}
                    content_body = raw_text

                    # Regex nhận diện Frontmatter bắt đầu bằng --- và kết thúc bằng ---
                    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)$", raw_text.strip(), re.DOTALL)
                    if match:
                        yaml_part = match.group(1)
                        content_body = match.group(2).strip()
                        try:
                            frontmatter_data = yaml.safe_load(yaml_part) or {}
                        except Exception as e:
                            logger.error(f"Lỗi cú pháp YAML Frontmatter trong {file}: {e}")
                            frontmatter_data = {}
                    else:
                        # Fallback nếu dùng delimiter --- thông thường
                        parts = raw_text.split("---", 2)
                        if len(parts) >= 3 and parts[0].strip() == "":
                            try:
                                frontmatter_data = yaml.safe_load(parts[1]) or {}
                                content_body = parts[2].strip()
                            except Exception as e:
                                logger.error(f"Lỗi parse fallback Frontmatter trong {file}: {e}")

                    # 4. Tạo KnowledgeDocument
                    category_val = str(frontmatter_data.get("category", "")).strip().lower()
                    if not category_val:
                        # Nếu không có category trong frontmatter, lấy tên thư mục cha trực tiếp
                        category_val = resolved_path.parent.name.lower()

                    doc = KnowledgeDocument(
                        filename=file,
                        title=frontmatter_data.get("title", file),
                        category=category_val,
                        version=str(frontmatter_data.get("version", "1.0")),
                        language=str(frontmatter_data.get("language", "vi")),
                        updated_at=str(frontmatter_data.get("updated_at", "")),
                        metadata=frontmatter_data,
                        content=content_body,
                        raw_content=raw_text,
                        filepath=str(resolved_path)
                    )

                    new_cache[file] = doc
                    loaded_count += 1

                except Exception as e:
                    logger.error(f"Lỗi khi nạp tài liệu {file}: {e}")

        self._cache = new_cache
        logger.info(f"Đã nạp thành công {loaded_count} tài liệu vào RAM In-memory Cache.")
        return loaded_count

    def get_documents_by_category(self, category: str) -> List[KnowledgeDocument]:
        """
        Truy xuất danh sách tài liệu theo danh mục (chỉ đọc siêu tốc từ _cache trong RAM).
        """
        if not category:
            return []
        target_category = category.strip().lower()
        results: List[KnowledgeDocument] = []
        for doc in self._cache.values():
            if doc.category and doc.category.lower() == target_category:
                results.append(doc)
        return results

    def get_document_by_name(self, filename: str) -> Optional[KnowledgeDocument]:
        """
        Truy xuất tài liệu theo tên file (chỉ đọc từ _cache trong RAM).
        Bảo mật: Kiểm tra và ngăn chặn triệt để hành vi tấn công Path Traversal.
        """
        if not filename:
            return None

        # 1. Bảo mật: Chặn đứng Path Traversal ký tự đặc biệt như "..", "/", "\\"
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            logger.warning(f"Phát hiện cảnh báo an ninh Path Traversal khi truy vấn tài liệu: '{filename}'")
            raise ValueError(f"Tên file không hợp lệ hoặc chứa ký tự Path Traversal: {filename}")

        # Lấy tên file thuần túy
        clean_filename = Path(filename).name

        # Tra cứu trực tiếp trong Cache
        if clean_filename in self._cache:
            return self._cache[clean_filename]

        # Tra cứu thêm trường hợp không truyền phần mở rộng .md
        if not clean_filename.lower().endswith(".md"):
            md_name = f"{clean_filename}.md"
            if md_name in self._cache:
                return self._cache[md_name]

        return None

    def get_all_documents(self) -> List[KnowledgeDocument]:
        """Lấy toàn bộ danh sách tài liệu từ cache."""
        return list(self._cache.values())

    def clear_cache(self) -> None:
        """Xóa sạch bộ nhớ đệm."""
        self._cache.clear()
