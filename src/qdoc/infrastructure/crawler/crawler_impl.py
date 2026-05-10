import asyncio
import hashlib
import time
from typing import List, Set, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from qdoc.domain.repository import VectorRepository, EmbeddingService
from qdoc.domain.models.document import Chunk
from qdoc.infrastructure.config import settings
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

console = Console()

class DocumentationCrawlerImpl:
    def __init__(self, repository: VectorRepository, embedding_service: EmbeddingService):
        self.repository = repository
        self.embedding_service = embedding_service
        self.exclude_patterns = [
            "privacy", "terms", "about", "site-policies", "newsletter", 
            "sustainability", "events", "blog", "pricing", "contact", 
            "support-hub", "release-notes", "status", "training", "marketplace",
            "/reference/"
        ]
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        new_params = {}
        if "hl" in query_params:
            lang = query_params["hl"][0].lower()
            if lang in ["pt-br", "en"]:
                new_params["hl"] = lang
        new_query = urlencode(new_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.params, new_query, ""))

    def _should_crawl(self, url: str, start_url: str) -> bool:
        parsed_start = urlparse(start_url)
        path_scope = parsed_start.path.rstrip("/")
        if not url.startswith("http"):
            from urllib.parse import urljoin
            url = urljoin(start_url, url)

        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        if parsed_url.netloc and parsed_url.netloc != parsed_start.netloc:
            return False
        
        product_slug = path_scope.split("/")[-1]
        is_relevant = path.startswith(path_scope) or (product_slug in path and "/docs/" in path)
        if not is_relevant or any(pattern in path for pattern in self.exclude_patterns):
            return False
            
        query_params = parse_qs(parsed_url.query)
        if "hl" in query_params:
            lang = query_params["hl"][0].lower()
            if lang not in ["pt-br", "en"]: return False
        return True

    async def ingest_url(self, crawler: AsyncWebCrawler, url: str, service: str) -> List[str]:
        async with self.semaphore:
            normalized_url = self._normalize_url(url)
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, process_iframes=False, remove_overlay_elements=True)
            
            try:
                result = await crawler.arun(url=url, config=config)
                if not result.success: return []
                
                markdown = result.markdown
                current_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
                existing_hash = self.repository.get_existing_hash(normalized_url)
                internal_links = [link["href"] for link in result.links.get("internal", [])]

                if existing_hash == current_hash:
                    return internal_links

                if existing_hash:
                    self.repository.delete_by_url(normalized_url)

                text_chunks = self.embedding_service.chunk_text(markdown)
                if not text_chunks: return internal_links

                embeddings = self.embedding_service.get_embeddings(text_chunks)
                
                domain_chunks = [
                    Chunk(content=text, vector=vec)
                    for text, vec in zip(text_chunks, embeddings)
                ]
                
                self.repository.upsert_chunks(domain_chunks, service, normalized_url, current_hash)
                return internal_links
            except Exception as e:
                console.print(f"[red]Error processing {url}: {e}[/red]")
                return []

    async def ingest_from_list(self, urls: List[str], service: str):
        async with AsyncWebCrawler() as crawler:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Ingesting URLs...", total=len(urls))
                async def worker(url):
                    await self.ingest_url(crawler, url.strip(), service)
                    progress.update(task, advance=1, description=f"Processed {url[:30]}...")

                tasks = [worker(url) for url in urls if url.strip()]
                await asyncio.gather(*tasks)

    async def crawl_recursive(self, start_url: str, service: str, depth: int):
        queue = asyncio.Queue()
        await queue.put((start_url, 0))
        visited = set()
        active_tasks = 0
        lock = asyncio.Lock()

        async with AsyncWebCrawler() as crawler:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Discovering links (Depth {depth})...", total=None)

                async def worker():
                    nonlocal active_tasks
                    while True:
                        try:
                            url, current_depth = await asyncio.wait_for(queue.get(), timeout=2.0)
                        except asyncio.TimeoutError:
                            if active_tasks == 0: break
                            continue

                        normalized = self._normalize_url(url)
                        async with lock:
                            if normalized in visited or current_depth > depth:
                                queue.task_done()
                                continue
                            visited.add(normalized)
                            active_tasks += 1

                        progress.update(task, description=f"Crawling: {url[:50]}...")
                        try:
                            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_until="networkidle")
                            result = await crawler.arun(url=url, config=config)
                            
                            if result.success:
                                await self.ingest_url(crawler, url, service)
                                if current_depth < depth:
                                    all_links = result.links.get("internal", []) + result.links.get("external", [])
                                    for l in all_links:
                                        link_url = l.get("href", "")
                                        if self._should_crawl(link_url, start_url):
                                            await queue.put((link_url, current_depth + 1))
                        except Exception as e:
                            progress.console.log(f"[red]Error crawling {url}: {e}[/red]")
                        finally:
                            async with lock: active_tasks -= 1
                            queue.task_done()

                workers = [asyncio.create_task(worker()) for _ in range(settings.MAX_CONCURRENT_REQUESTS)]
                await queue.join()
                for w in workers: w.cancel()
