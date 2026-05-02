from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "gcp_docs"

    # Google Cloud / Vertex AI
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    EMBEDDING_MODEL: str = "text-embedding-004"

    # Crawler
    DEFAULT_SEED_URL: str = "https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps"

settings = Settings()
