from qdrant_client import QdrantClient, models
from qdoc.infrastructure.config import settings
from qdoc.domain.models.document import Chunk, SearchResult
from qdoc.domain.repository import VectorRepository
import uuid
from typing import List, Dict, Any, Optional

from rich.console import Console

console = Console()

class QdrantVectorRepository(VectorRepository):
    _client_instance = None

    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = 768  # text-embedding-004
        self._init_client()

    def _init_client(self):
        if QdrantVectorRepository._client_instance:
            self.client = QdrantVectorRepository._client_instance
            return

        try:
            if settings.QDRANT_URL.startswith(("http://", "https://")):
                self.client = QdrantClient(url=settings.QDRANT_URL)
            else:
                import os
                os.makedirs(settings.QDRANT_URL, exist_ok=True)
                self.client = QdrantClient(path=settings.QDRANT_URL)
            
            QdrantVectorRepository._client_instance = self.client
        except Exception as e:
            if "already accessed by another instance" in str(e):
                console.print("[bold red]Concurrency Error:[/bold red] The vector database is locked by another process.")
                console.print("[yellow]Tip:[/yellow] Close other qdoc instances (Claude Code, Gemini CLI, or TUI) or use a Qdrant Server (Docker).")
            raise e

    def init_collection(self, rebuild: bool = False):
        if rebuild:
            self.client.delete_collection(self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                )
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="service",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="url",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    def get_existing_hash(self, url: str) -> Optional[str]:
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            ),
            limit=1,
            with_payload=True
        )
        if results:
            return results[0].payload.get("hash")
        return None

    def delete_by_url(self, url: str):
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
                )
            )
        )

    def upsert_chunks(self, chunks: List[Chunk], service: str, url: str, doc_hash: str) -> None:
        import time
        points = []
        for chunk in chunks:
            point_id = str(uuid.uuid4())
            payload = chunk.metadata.copy()
            payload.update({
                "content": chunk.content,
                "url": url,
                "service": service,
                "hash": doc_hash,
                "updated_at": time.time()
            })
            points.append(models.PointStruct(
                id=point_id,
                vector=chunk.vector,
                payload=payload
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search(
        self, 
        vector: List[float], 
        service_filter: Optional[List[str]] = None, 
        url_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        must_filters = []
        
        if service_filter:
            must_filters.append(models.Filter(
                should=[
                    models.FieldCondition(key="service", match=models.MatchValue(value=s))
                    for s in service_filter
                ]
            ))
            
        if url_filter:
            must_filters.append(models.FieldCondition(key="url", match=models.MatchValue(value=url_filter)))

        query_filter = models.Filter(must=must_filters) if must_filters else None

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        
        return [
            SearchResult(
                content=hit.payload["content"],
                url=hit.payload["url"],
                score=hit.score,
                metadata=hit.payload
            )
            for hit in results.points
        ]

    def get_all_chunks_by_url(self, url: str) -> List[dict]:
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            ),
            limit=200,
            with_payload=True
        )
        return [p.payload for p in results]

    def get_stats(self) -> dict:
        info = self.client.get_collection(self.collection_name)
        return {
            "vectors_count": info.points_count,
            "status": info.status,
        }
