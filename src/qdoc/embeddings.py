from google import genai
from qdoc.config import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

class EmbeddingEngine:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION
        )
        self.model_id = settings.EMBEDDING_MODEL
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=texts,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return [embedding.values for embedding in response.embeddings]

    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a search query."""
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=query,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        return response.embeddings[0].values

    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        return self.text_splitter.split_text(text)
