from qdrant_client import QdrantClient, models
from qdoc.config import settings
import uuid
from typing import List, Dict, Any, Optional

class VectorDB:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = 768  # text-embedding-004

    def init_collection(self, rebuild: bool = False):
        """Initialize the collection and payload indexes."""
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
            # Create payload index for 'service' and 'url'
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
        """Get the hash of an existing page in the DB."""
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            ),
            limit=1,
            with_payload=True
        )
        points, _ = results
        if points:
            return points[0].payload.get("hash")
        return None

    def delete_by_url(self, url: str):
        """Delete all points associated with a URL."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
                )
            )
        )

    def upsert_chunks(self, chunks: List[str], embeddings: List[List[float]], metadata: Dict[str, Any]):
        """Upsert chunks with embeddings and metadata."""
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            payload = metadata.copy()
            payload["content"] = chunk
            points.append(models.PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search(self, vector: List[float], service_filter: Optional[List[str]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks."""
        query_filter = None
        if service_filter:
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(key="service", match=models.MatchValue(value=s))
                    for s in service_filter
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        
        output = []
        for hit in results.points:
            data = hit.payload.copy()
            data["score"] = hit.score
            output.append(data)
            
        return output

    def get_all_chunks_by_url(self, url: str) -> List[Dict[str, Any]]:
        """Fetch all chunks stored for a given URL."""
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            ),
            limit=200,
            with_payload=True
        )
        return [p.payload for p in results]

    def list_chunks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List chunks for the TUI explorer."""
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True
        )
        return [p.payload for p in results]

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        info = self.client.get_collection(self.collection_name)
        return {
            "vectors_count": info.points_count,
            "status": info.status,
            # Qdrant info doesn't easily give disk size in MB without deeper API calls or storage info
            # For simplicity, we'll return the points count.
        }
