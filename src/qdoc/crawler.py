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
        # Normalize paths for comparison
        parsed_start = urlparse(start_url)
        path_scope = parsed_start.path.rstrip("/")
        
        # Handle relative URLs by joining with start_url
        if not url.startswith("http"):
            from urllib.parse import urljoin
            url = urljoin(start_url, url)

        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        # Must be in the same domain
        if parsed_url.netloc and parsed_url.netloc != parsed_start.netloc:
            return False
        
        # Google Cloud specific: Sometimes they drop parts of the path or use /docs/
        # Let's be more permissive: if it contains the product slug, it's likely relevant
        product_slug = path_scope.split("/")[-1]
        
        is_relevant = path.startswith(path_scope) or (product_slug in path and "/docs/" in path)
        
        if not is_relevant:
            return False
            
        if any(pattern in path for pattern in self.exclude_patterns):
            return False
            
        query_params = parse_qs(parsed_url.query)
        if "hl" in query_params:
            lang = query_params["hl"][0].lower()
            if lang not in ["pt-br", "en"]:
                return False
        return True

    async def get_urls_from_sitemap(self, sitemap_url: str, base_url: str, max_sub_sitemaps: int = 50) -> List[str]:
        all_urls = set()
        visited_sitemaps = set()
        sitemap_queue = asyncio.Queue()
        await sitemap_queue.put(sitemap_url)
        
        processed_count = 0
        active_tasks = 0
        lock = asyncio.Lock()

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("Discovering URLs...", total=None)
                
                async def process_sitemap():
                    nonlocal processed_count, active_tasks
                    while True:
                        try:
                            # Use a small timeout to check if we're done
                            current_sitemap = await asyncio.wait_for(sitemap_queue.get(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if active_tasks == 0: break
                            continue

                        async with lock:
                            if current_sitemap in visited_sitemaps or processed_count >= max_sub_sitemaps:
                                sitemap_queue.task_done()
                                continue
                            visited_sitemaps.add(current_sitemap)
                            processed_count += 1
                            active_tasks += 1

                        progress.update(task, description=f"Processing sitemaps... ({processed_count}/{max_sub_sitemaps})")
                        progress.console.log(f"[dim]Fetching sitemap:[/dim] [cyan]{current_sitemap.split('/')[-1]}[/cyan]")
                        
                        try:
                            response = await client.get(current_sitemap)
                            if response.status_code == 200:
                                import io
                                found_in_this_sitemap = 0
                                context = ET.iterparse(io.BytesIO(response.content), events=("end",))
                                for _, elem in context:
                                    tag_name = elem.tag.split("}")[-1]
                                    if tag_name == "loc":
                                        loc_url = elem.text
                                        if loc_url:
                                            if ".xml" in loc_url:
                                                # Avoid reference sitemaps if not requested
                                                if not ("/reference/" in loc_url and "/reference/" not in base_url):
                                                    await sitemap_queue.put(loc_url)
                                            elif self._should_crawl(loc_url, base_url):
                                                async with lock:
                                                    all_urls.add(loc_url)
                                                    found_in_this_sitemap += 1
                                    elem.clear()
                                if found_in_this_sitemap > 0:
                                    progress.console.log(f"[green]✓[/green] Found [bold]{found_in_this_sitemap}[/bold] relevant URLs in {current_sitemap.split('/')[-1]}")
                        except Exception as e:
                            progress.console.log(f"[red]Error parsing {current_sitemap}: {e}[/red]")
                        finally:
                            async with lock:
                                active_tasks -= 1
                            sitemap_queue.task_done()

                # Start parallel workers (up to 20)
                workers = [asyncio.create_task(process_sitemap()) for _ in range(20)]
                await sitemap_queue.join()
                
                # Cancel workers
                for w in workers:
                    w.cancel()
                
        return list(all_urls)

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
        """Parallel recursive discovery."""
        queue = asyncio.Queue()
        await queue.put((start_url, 0))
        visited = set()
        results = set()
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
                            # Use a more robust config for GCP pages which are JS-heavy
                            config = CrawlerRunConfig(
                                cache_mode=CacheMode.BYPASS,
                                wait_until="networkidle",
                                process_iframes=True,
                                remove_overlay_elements=True
                            )
                            result = await crawler.arun(url=url, config=config)
                            
                            if result.success:
                                all_links = result.links.get("internal", []) + result.links.get("external", [])
                                progress.console.log(f"[dim]Found {len(all_links)} total links on {url[:40]}...[/dim]")
                                
                                async with lock:
                                    results.add(normalized)
                                    if list_only:
                                        progress.console.log(f"[dim][D:{current_depth}][/dim] [green]✓[/green] {normalized}")
                                    else:
                                        await self.ingest_url(crawler, url, service)
                                
                                if current_depth < depth:
                                    added_links = 0
                                    for l in all_links:
                                        link_url = l.get("href", "")
                                        if self._should_crawl(link_url, start_url):
                                            await queue.put((link_url, current_depth + 1))
                                            added_links += 1
                                    if added_links > 0:
                                        progress.console.log(f"[blue]→[/blue] Added [bold]{added_links}[/bold] new links to queue from this page.")
                        except Exception as e:
                            progress.console.log(f"[red]Error crawling {url}: {e}[/red]")
                        finally:
                            async with lock: active_tasks -= 1
                            queue.task_done()

                # Start parallel discovery workers
                workers = [asyncio.create_task(worker()) for _ in range(settings.MAX_CONCURRENT_REQUESTS)]
                await queue.join()
                for w in workers: w.cancel()

        if list_only:
            console.print(f"\n[bold green]Discovery complete! Found {len(results)} pages.[/bold green]")
