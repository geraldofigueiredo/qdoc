from typing import List, Optional
from qdoc.domain.repository import VectorRepository, EmbeddingService
from qdoc.domain.models.document import Chunk, Document
from qdoc.infrastructure.crawler.crawler_impl import DocumentationCrawlerImpl # Will create this
from crawl4ai import AsyncWebCrawler

class IngestUseCase:
    def __init__(self, repository: VectorRepository, embedding_service: EmbeddingService):
        self.repository = repository
        self.embedding_service = embedding_service
        self.crawler = DocumentationCrawlerImpl(repository, embedding_service)

    async def execute_url(self, url: str, service: str):
        async with AsyncWebCrawler() as mcrawler:
            await self.crawler.ingest_url(mcrawler, url, service)

    async def execute_recursive(self, url: str, service: str, depth: int):
        await self.crawler.crawl_recursive(url, service, depth)

    async def execute_list(self, urls: List[str], service: str):
        await self.crawler.ingest_from_list(urls, service)
