import asyncio
import hashlib
import time
from typing import List, Set
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from qdoc.db import VectorDB
from qdoc.embeddings import EmbeddingEngine
from qdoc.config import settings
from rich.console import Console

console = Console()

class DocumentationCrawler:
    def __init__(self, db: VectorDB, engine: EmbeddingEngine):
        self.db = db
        self.engine = engine
        self.visited_urls: Set[str] = set()

    def _calculate_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def ingest_url(self, url: str, service: str) -> List[str]:
        """Ingest a single URL with CDC check and return internal links."""
        async with AsyncWebCrawler() as crawler:
            # Configuração mínima para evitar erros de parser XPath/Expressão do Crawl4AI
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                process_iframes=False,
                remove_overlay_elements=True
            )
            
            result = await crawler.arun(url=url, config=config)
            
            if not result.success:
                console.print(f"[red]Failed to crawl {url}[/red]")
                return []

            markdown = result.markdown
            current_hash = self._calculate_hash(markdown)
            existing_hash = self.db.get_existing_hash(url)

            # Get internal links for recursion
            internal_links = [link["href"] for link in result.links.get("internal", [])]

            if existing_hash == current_hash:
                console.print(f"[blue][KEEP][/blue] {url}")
                return internal_links

            if existing_hash:
                console.print(f"[yellow][UPDATE][/yellow] {url}")
                self.db.delete_by_url(url)
            else:
                console.print(f"[green][NEW][/green] {url}")

            chunks = self.engine.chunk_text(markdown)
            if not chunks:
                return internal_links

            try:
                embeddings = self.engine.get_embeddings(chunks)
            except Exception as e:
                console.print(f"[red]Embedding error for {url}: {e}[/red]")
                return internal_links
            
            metadata = {
                "url": url,
                "hash": current_hash,
                "service": service,
                "updated_at": time.time()
            }
            
            self.db.upsert_chunks(chunks, embeddings, metadata)
            return internal_links

    async def crawl_recursive(self, start_url: str, service: str, depth: int):
        """Crawl URLs recursively up to a certain depth."""
        queue = [(start_url, 0)]
        
        while queue:
            url, current_depth = queue.pop(0)
            if url in self.visited_urls or current_depth > depth:
                continue
            
            self.visited_urls.add(url)
            links = await self.ingest_url(url, service)
            
            if current_depth < depth:
                for link in links:
                    if link not in self.visited_urls:
                        queue.append((link, current_depth + 1))
