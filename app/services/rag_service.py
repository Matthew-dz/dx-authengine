import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

import google.generativeai as genai
from google.api_core.exceptions import NotFound, GoogleAPIError

from app.settings import settings
from app.services.knowledge_service import KnowledgeBaseService, KnowledgeDocument

logger = logging.getLogger(__name__)

# Cấu hình API Key
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Model embedding: Ưu tiên text-embedding-004 theo yêu cầu, tự động fallback sang gemini-embedding-001 nếu môi trường 404
PRIMARY_EMBEDDING_MODEL = "models/text-embedding-004"
FALLBACK_EMBEDDING_MODEL = "models/gemini-embedding-001"


class MarkdownChunk(BaseModel):
    """Đoạn văn bản được chia tách ngữ nghĩa (Semantic Chunk) từ tài liệu Markdown."""
    chunk_id: str
    filename: str
    title: str
    category: str
    version: str
    header: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def get_embedding(text: str, task_type: str = "retrieval_document") -> List[float]:
    """
    Sinh vector nhúng (embedding) cho đoạn văn bản sử dụng model text-embedding-004 của Google
    (thông qua genai.embed_content).
    Tự động fallback sang gemini-embedding-001 nếu model ban đầu không khả dụng.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY chưa được cấu hình để sinh embedding")

    try:
        response = genai.embed_content(
            model=PRIMARY_EMBEDDING_MODEL,
            content=text,
            task_type=task_type
        )
        return response["embedding"]
    except NotFound:
        logger.info(f"Model {PRIMARY_EMBEDDING_MODEL} không khả dụng, chuyển sang {FALLBACK_EMBEDDING_MODEL}")
        response = genai.embed_content(
            model=FALLBACK_EMBEDDING_MODEL,
            content=text,
            task_type=task_type
        )
        return response["embedding"]
    except Exception as e:
        logger.error(f"Lỗi khi sinh vector embedding từ Google Gemini: {e}")
        raise e


def semantic_chunk_document(doc: KnowledgeDocument) -> List[MarkdownChunk]:
    """
    Semantic Chunking: Chia nhỏ văn bản dựa trên các thẻ tiêu đề Markdown (#, ##, ###)
    thay vì cắt theo số lượng ký tự, đảm bảo giữ nguyên tính trọn vẹn ngữ nghĩa của từng phần.
    """
    lines = doc.content.splitlines()
    chunks: List[MarkdownChunk] = []

    current_header = f"# {doc.title}" if doc.title else ""
    current_lines: List[str] = []
    chunk_idx = 0

    header_regex = re.compile(r"^(#{1,3})\s+(.+)$")

    for line in lines:
        match = header_regex.match(line.strip())
        if match:
            # Gặp header mới: lưu chunk trước đó nếu có nội dung
            if current_lines:
                chunk_body = "\n".join(current_lines).strip()
                if chunk_body:
                    chunk_id = f"{doc.filename}#chunk_{chunk_idx}"
                    chunk_meta = {
                        "filename": doc.filename,
                        "title": doc.title or doc.filename,
                        "category": doc.category or "general",
                        "version": doc.version or "1.0",
                        "header": current_header
                    }
                    chunks.append(MarkdownChunk(
                        chunk_id=chunk_id,
                        filename=doc.filename,
                        title=doc.title or doc.filename,
                        category=doc.category or "general",
                        version=doc.version or "1.0",
                        header=current_header,
                        content=chunk_body,
                        metadata=chunk_meta
                    ))
                    chunk_idx += 1
                current_lines = []
            current_header = line.strip()
            current_lines.append(line)
        else:
            current_lines.append(line)

    # Xử lý đoạn cuối cùng
    if current_lines:
        chunk_body = "\n".join(current_lines).strip()
        if chunk_body:
            chunk_id = f"{doc.filename}#chunk_{chunk_idx}"
            chunk_meta = {
                "filename": doc.filename,
                "title": doc.title or doc.filename,
                "category": doc.category or "general",
                "version": doc.version or "1.0",
                "header": current_header
            }
            chunks.append(MarkdownChunk(
                chunk_id=chunk_id,
                filename=doc.filename,
                title=doc.title or doc.filename,
                category=doc.category or "general",
                version=doc.version or "1.0",
                header=current_header,
                content=chunk_body,
                metadata=chunk_meta
            ))

    # Nếu tài liệu không có tiêu đề markdown (#), tạo 1 chunk cho toàn bộ nội dung
    if not chunks and doc.content.strip():
        chunk_id = f"{doc.filename}#chunk_0"
        chunk_meta = {
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "category": doc.category or "general",
            "version": doc.version or "1.0",
            "header": f"# {doc.title or doc.filename}"
        }
        chunks.append(MarkdownChunk(
            chunk_id=chunk_id,
            filename=doc.filename,
            title=doc.title or doc.filename,
            category=doc.category or "general",
            version=doc.version or "1.0",
            header=f"# {doc.title or doc.filename}",
            content=doc.content.strip(),
            metadata=chunk_meta
        ))

    return chunks


class RAGService:
    """
    RAG Service quản lý lưu trữ vector cục bộ với ChromaDB và cung cấp chức năng Retriever.
    Thiết kế theo Singleton pattern để chia sẻ kết nối ChromaDB PersistentClient.
    """
    _instance: Optional["RAGService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RAGService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, chroma_path: Optional[str] = None, collection_name: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        self.chroma_path = chroma_path or getattr(settings, "CHROMA_DATA_PATH", "./chroma_data")
        self.collection_name = collection_name or getattr(settings, "CHROMA_COLLECTION_NAME", "dxos_knowledge_base")
        self._client = None
        self._collection = None
        self._initialized = True

    def _get_collection(self):
        """Khởi tạo lazy connection tới ChromaDB PersistentClient."""
        if self._collection is None:
            import chromadb
            # Đảm bảo thư mục lưu trữ tồn tại
            os.makedirs(self.chroma_path, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.chroma_path)
            self._collection = self._client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def index_knowledge_base(self, force_reload: bool = False) -> int:
        """
        Đọc các tài liệu từ KnowledgeBaseService, chia nhỏ theo Semantic Chunking,
        tính vector embedding và lưu trữ vào ChromaDB collection.
        """
        kb_service = KnowledgeBaseService()
        if not kb_service.is_loaded:
            kb_service.load_documents()

        docs = kb_service.get_all_documents()
        if not docs:
            logger.info("Không có tài liệu nào trong Knowledge Base để index.")
            return 0

        collection = self._get_collection()
        all_chunks: List[MarkdownChunk] = []

        for doc in docs:
            chunks = semantic_chunk_document(doc)
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        # Chuẩn bị dữ liệu cho ChromaDB
        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for chunk in all_chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)
            # Metadata chỉ chấp nhận str, int, float, bool
            clean_meta = {
                "filename": str(chunk.filename),
                "title": str(chunk.title),
                "category": str(chunk.category),
                "version": str(chunk.version),
                "header": str(chunk.header)
            }
            metadatas.append(clean_meta)

            # Tính vector embedding
            emb = get_embedding(chunk.content, task_type="retrieval_document")
            embeddings.append(emb)

        # Đẩy vào ChromaDB
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        logger.info(f"Đã index thành công {len(ids)} chunks vào ChromaDB collection '{self.collection_name}'.")
        return len(ids)

    def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retriever: Chuyển câu hỏi/truy vấn thành vector, truy vấn vào ChromaDB và trả về
        nội dung của top_k chunk phù hợp nhất cùng với metadata của chúng.
        """
        if not query or not query.strip():
            return []

        collection = self._get_collection()
        if collection.count() == 0:
            # Nếu collection rỗng, tự động index Knowledge Base
            logger.info("Collection rỗng, tự động index Knowledge Base...")
            self.index_knowledge_base()

        if collection.count() == 0:
            return []

        # Chuyển câu hỏi thành vector embedding
        query_vector = get_embedding(query.strip(), task_type="retrieval_query")

        # Query vào ChromaDB
        actual_k = min(top_k, collection.count())
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=actual_k
        )

        hits: List[Dict[str, Any]] = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results.get("metadatas", [[]])[0]
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0] if "distances" in results and results["distances"] else [None] * len(docs)

            for i in range(len(docs)):
                hits.append({
                    "id": ids[i] if i < len(ids) else f"hit_{i}",
                    "content": docs[i],
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": distances[i] if i < len(distances) else None
                })

        return hits
