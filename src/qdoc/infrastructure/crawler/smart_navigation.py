import asyncio
import json
from typing import List, Optional, Dict, Any
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from qdoc.domain.repository import NavigationService, LLMService
from qdoc.infrastructure.config import settings
from rich.console import Console

console = Console()

class SmartNavigationService(NavigationService):
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.strategies = [
            "devsite-book-nav a",             # GCP Standard
            "nav a",                          # Standard HTML
            "aside a",                        # Sidebar
            ".sidebar a",                     # Common class
            "header nav a",                   # Top nav fallback
            "internal-links"                  # Fallback to all internal links
        ]

    async def extract_nav_links(self, url: str, product_context: Optional[str] = None) -> List[str]:
        async with AsyncWebCrawler() as crawler:
            console.print(f"[bold blue]Starting Smart Discovery for:[/bold blue] {url}")
            
            # 1. Initial attempt with standard config
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_until="networkidle")
            result = await crawler.arun(url=url, config=config)
            
            if not result.success:
                console.print(f"[red]Failed to fetch root URL: {url}[/red]")
                return []

            # 2. Extract simplified HTML for LLM analysis
            # We take a slice of the HTML to avoid token limits, focusing on nav/aside tags
            html_sample = result.cleaned_html[:10000] 
            
            prompt = f"""
            Analyze the following HTML structure of a documentation page.
            Goal: Identify the CSS selector that most likely contains the navigation sidebar or table of contents links.
            Product: {product_context or 'Technical Documentation'}
            URL: {url}
            
            HTML Sample:
            {html_sample}
            
            Return a JSON object with:
            {{
                "suggested_selector": "string",
                "confidence": 0-1,
                "reasoning": "string",
                "is_documentation_root": boolean
            }}
            """
            
            try:
                # We use the LLM to find the best selector
                llm_decision_raw = self.llm_service.generate_answer(prompt, [])
                # Extract JSON from potential markdown
                if "```json" in llm_decision_raw:
                    llm_decision_raw = llm_decision_raw.split("```json")[1].split("```")[0]
                decision = json.loads(llm_decision_raw)
                
                selector = decision.get("suggested_selector")
                console.print(f"[cyan]LLM suggests selector:[/cyan] {selector} (Reason: {decision.get('reasoning')})")
                
                # 3. Try the suggested selector
                links = [link["href"] for link in result.links.get("internal", [])]
                # Filter links based on the selector if possible, or use the heuristic
                # For now, let's use the internal links and let the LLM filter them
                
                if not links:
                    console.print("[yellow]No links found with LLM suggestion. Trying fallback strategies...[/yellow]")
                    # Fallback to general internal links
                    links = [l["href"] for l in result.links.get("internal", [])]

                # 4. Filter and Validate links with LLM if too many/too few
                if len(links) > 100:
                    console.print(f"[yellow]Found {len(links)} links. Pruning with IA...[/yellow]")
                    pruning_prompt = f"From this list of links, keep only those that belong to the technical documentation of '{product_context}'. Return as a JSON list of strings.\nLinks: {links[:100]}"
                    pruned_raw = self.llm_service.generate_answer(pruning_prompt, [])
                    if "[" in pruned_raw:
                        links = json.loads(pruned_raw[pruned_raw.find("["):pruned_raw.rfind("]")+1])

                return list(set(links))

            except Exception as e:
                console.print(f"[red]Error in Smart Discovery: {e}[/red]")
                # Absolute fallback: just return what crawl4ai found as internal
                return [l["href"] for l in result.links.get("internal", [])]
