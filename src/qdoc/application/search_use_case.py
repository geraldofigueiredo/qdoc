from typing import List, Optional
from qdoc.domain.repository import VectorRepository, EmbeddingService, LLMService

class SearchUseCase:
    def __init__(self, repository: VectorRepository, embedding_service: EmbeddingService, llm_service: LLMService):
        self.repository = repository
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    async def execute(
        self, 
        query: str, 
        services_filter: Optional[List[str]] = None, 
        url_filter: Optional[str] = None,
        limit: int = 10, 
        simple: bool = False
    ) -> str:
        if simple:
            vector = self.embedding_service.get_query_embedding(query)
            results = self.repository.search(vector, service_filter=services_filter, url_filter=url_filter, limit=limit)
            if not results:
                return "No documentation found."
            
            output = []
            for res in results:
                output.append(f"Source: {res.url} (Score: {res.score:.4f})\nContent: {res.content}\n---")
            return "\n".join(output)

        current_query = query
        max_retries = 5
        all_chunks = []
        seen_chunk_keys = set()
        seen_urls = set()

        for attempt in range(max_retries):
            vector = self.embedding_service.get_query_embedding(current_query)
            results = self.repository.search(vector, service_filter=services_filter, url_filter=url_filter, limit=limit)

            if not results:
                if attempt == 0:
                    return "No documentation found for this query."
                break

            matched_urls = list(dict.fromkeys(r.url for r in results))[:3]
            for url in matched_urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                for chunk_data in self.repository.get_all_chunks_by_url(url):
                    key = url + chunk_data.get("content", "")[:50]
                    if key not in seen_chunk_keys:
                        all_chunks.append(chunk_data["content"])
                        seen_chunk_keys.add(key)

            current_query = self.llm_service.augment_query(query, current_query, all_chunks)

            if attempt > 0:
                if self.llm_service.evaluate_results(query, all_chunks):
                    return self.llm_service.generate_answer(query, all_chunks)

        if all_chunks:
            return self.llm_service.generate_answer(query, all_chunks)

        return "I couldn't find enough information to answer your query after multiple attempts."
