from typing import List, Optional
from qdoc.domain.repository import VectorRepository, EmbeddingService, LLMService, NavigationService
from qdoc.infrastructure.crawler.crawler_impl import DocumentationCrawlerImpl
from qdoc.infrastructure.crawler.smart_navigation import SmartNavigationService
from rich.console import Console

console = Console()

class SmartIngestUseCase:
    def __init__(
        self, 
        repository: VectorRepository, 
        embedding_service: EmbeddingService,
        llm_service: LLMService
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.crawler = DocumentationCrawlerImpl(repository, embedding_service)
        self.nav_service = SmartNavigationService(llm_service)

    async def execute_smart_root(self, root_url: str, service: str):
        """
        AI-powered ingestion starting from a root documentation URL.
        1. Identifies nav links using LLM analysis.
        2. Validates if the page is indeed a doc root.
        3. Ingests all discovered pages.
        """
        console.print(f"[bold green]Starting Smart Ingestion for {service}...[/bold green]")
        
        # 1. Discover links intelligently
        links = await self.nav_service.extract_nav_links(root_url, product_context=service)
        
        if not links:
            console.print("[red]Could not discover any links. Aborting.[/red]")
            return

        console.print(f"[green]Smart Discovery found {len(links)} relevant pages.[/green]")
        
        # 2. Ingest the list of links
        await self.crawler.ingest_from_list(links, service)
        
        console.print(f"[bold green]Smart Ingestion for {service} complete![/bold green]")

    async def execute_url(self, url: str, service: str):
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler() as mcrawler:
            await self.crawler.ingest_url(mcrawler, url, service)

    async def execute_recursive(self, url: str, service: str, depth: int):
        await self.crawler.crawl_recursive(url, service, depth)

    async def execute_list(self, urls: List[str], service: str):
        await self.crawler.ingest_from_list(urls, service)
