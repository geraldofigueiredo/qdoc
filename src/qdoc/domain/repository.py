from typing import Protocol, List, Optional
from qdoc.domain.models.document import Chunk, SearchResult

class VectorRepository(Protocol):
    def upsert_chunks(self, chunks: List[Chunk], service: str, url: str, doc_hash: str) -> None:
        ...

    def search(
        self, 
        vector: List[float], 
        service_filter: Optional[List[str]] = None, 
        url_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        ...

    def get_existing_hash(self, url: str) -> Optional[str]:
        ...

    def delete_by_url(self, url: str) -> None:
        ...

    def get_all_chunks_by_url(self, url: str) -> List[dict]:
        ...

    def init_collection(self, rebuild: bool = False) -> None:
        ...

    def get_stats(self) -> dict:
        ...

class EmbeddingService(Protocol):
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        ...

    def get_query_embedding(self, text: str) -> List[float]:
        ...

    def chunk_text(self, text: str) -> List[str]:
        ...

class NavigationService(Protocol):
    async def extract_nav_links(self, url: str, product_context: Optional[str] = None) -> List[str]:
        ...

class LLMService(Protocol):
    def generate_answer(self, query: str, context_chunks: List[str]) -> str:
        ...

    def augment_query(self, original_query: str, current_query: str, context_chunks: List[str]) -> str:
        ...

    def evaluate_results(self, query: str, context_chunks: List[str]) -> bool:
        ...
