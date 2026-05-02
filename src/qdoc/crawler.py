import asyncio
import hashlib
import time
import httpx
import xml.etree.ElementTree as ET
from typing import List, Set, Optional
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from qdoc.db import VectorDB
from qdoc.embeddings import EmbeddingEngine
from qdoc.config import settings
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

console = Console()

class DocumentationCrawler:
    def __init__(self, db: VectorDB, engine: EmbeddingEngine):
        self.db = db
        self.engine = engine
        self.visited_urls: Set[str] = set()
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
        path_scope = urlparse(start_url).path.strip("/")
        if path_scope and path_scope not in url:
            return False
        parsed = urlparse(url)
        path = parsed.path.lower()
        if any(pattern in path for pattern in self.exclude_patterns):
            return False
        query_params = parse_qs(parsed.query)
        if "hl" in query_params:
            lang = query_params["hl"][0].lower()
            if lang not in ["pt-br", "en"]:
                return False
        return True

    async def get_urls_from_sitemap(self, sitemap_url: str, base_url: str, max_sub_sitemaps: int = 50) -> List[str]:
        urls = []
        visited_sitemaps = set()
        queue = [sitemap_url]
        processed_count = 0

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("Discovering URLs...", total=None)
                while queue and processed_count < max_sub_sitemaps:
                    current_sitemap = queue.pop(0)
                    if current_sitemap in visited_sitemaps: continue
                    visited_sitemaps.add(current_sitemap)
                    progress.update(task, description=f"Processing sitemap: {current_sitemap.split('/')[-1]}")
                    try:
                        response = await client.get(current_sitemap)
                        if response.status_code != 200: continue
                        import io
                        context = ET.iterparse(io.BytesIO(response.content), events=("start", "end"))
                        for event, elem in context:
                            if event == "end":
                                tag_name = elem.tag.split("}")[-1]
                                if tag_name == "loc":
                                    loc_url = elem.text
                                    if not loc_url: continue
                                    if ".xml" in loc_url:
                                        if "/reference/" in loc_url and "/reference/" not in base_url:
                                            elem.clear()
                                            continue
                                        queue.append(loc_url)
                                    else:
                                        if self._should_crawl(loc_url, base_url):
                                            urls.append(loc_url)
                                            progress.update(task, description=f"Found {len(urls)} relevant URLs...")
                                elem.clear()
                        processed_count += 1
                    except Exception as e:
                        console.print(f"[red]Error parsing {current_sitemap}: {e}[/red]")
        return list(set(urls))

    async def ingest_url(self, crawler: AsyncWebCrawler, url: str, service: str) -> List[str]:
        """Ingest a single URL using a shared crawler instance."""
        async with self.semaphore:
            normalized_url = self._normalize_url(url)
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, process_iframes=False, remove_overlay_elements=True)
            
            try:
                result = await crawler.arun(url=url, config=config)
                if not result.success: return []
                
                markdown = result.markdown
                current_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
                existing_hash = self.db.get_existing_hash(normalized_url)
                internal_links = [link["href"] for link in result.links.get("internal", [])]

                if existing_hash == current_hash:
                    return internal_links

                if existing_hash:
                    self.db.delete_by_url(normalized_url)

                chunks = self.engine.chunk_text(markdown)
                if not chunks: return internal_links

                embeddings = self.engine.get_embeddings(chunks)
                self.db.upsert_chunks(chunks, embeddings, {"url": normalized_url, "hash": current_hash, "service": service, "updated_at": time.time()})
                return internal_links
            except Exception as e:
                console.print(f"[red]Error processing {url}: {e}[/red]")
                return []

    async def ingest_from_list(self, urls: List[str], service: str):
        """Ingest multiple URLs in parallel."""
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

    async def crawl_recursive(self, start_url: str, service: str, depth: int, list_only: bool = False):
        if list_only:
            # Recursive discovery is still sequential as it depends on findings
            queue = [(start_url, 0)]
            while queue:
                url, current_depth = queue.pop(0)
                normalized = self._normalize_url(url)
                if normalized in self.visited_urls or current_depth > depth: continue
                self.visited_urls.add(normalized)
                console.print(f"[dim][{current_depth}][/dim] {url}")
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
                    if result.success:
                        for link in [link["href"] for link in result.links.get("internal", [])]:
                            if self._should_crawl(link, start_url):
                                if self._normalize_url(link) not in self.visited_urls:
                                    queue.append((link, current_depth + 1))
        else:
            # Parallel ingestion for recursive crawl is more complex, 
            # for now we focus on parallelizing the list/sitemap ingestion
            await self.ingest_from_list([start_url], service)
