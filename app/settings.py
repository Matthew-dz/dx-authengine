from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # JWT Configuration
    JWT_SECRET_KEY: str = Field(..., description="Bắt buộc phải có khóa bí mật")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./dx_os.db"

    # AI Configuration
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")

    # ChromaDB Vector Storage Configuration
    CHROMA_DATA_PATH: str = Field(default="./chroma_data", description="Đường dẫn lưu trữ ChromaDB cục bộ")
    CHROMA_COLLECTION_NAME: str = Field(default="dxos_knowledge_base", description="Tên collection ChromaDB")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Khởi tạo một instance duy nhất (Singleton) để dùng chung cho toàn dự án
settings = Settings()
