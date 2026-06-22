from google import genai
from qdoc.infrastructure.config import settings
from qdoc.domain.repository import EmbeddingService
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

class GeminiEmbeddingService(EmbeddingService):
    def __init__(self):
        # Allow use of API KEY if project/location are not set
        if settings.GOOGLE_CLOUD_PROJECT:
            self.client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
        else:
            # Fallback to API Key from env
            self.client = genai.Client()
            
        self.model_id = settings.EMBEDDING_MODEL
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=texts,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return [embedding.values for embedding in response.embeddings]

    def get_query_embedding(self, query: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=query,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        return response.embeddings[0].values

    def chunk_text(self, text: str) -> List[str]:
        return self.text_splitter.split_text(text)
