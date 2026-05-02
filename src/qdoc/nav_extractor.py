from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, urljoin
from typing import List
from rich.console import Console

console = Console()


class NavExtractor:
    EXCLUDE_PATTERNS = [
        "privacy", "terms", "about", "site-policies", "newsletter",
        "sustainability", "events", "blog", "pricing", "contact",
        "support-hub", "release-notes", "status", "training", "marketplace",
        "/reference/"
    ]

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        new_params = {}
        if "hl" in query_params:
            lang = query_params["hl"][0].lower()
            if lang in ["pt-br", "en"]:
                new_params["hl"] = lang
        new_query = urlencode(new_params, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params, new_query, ""
        ))

    def _filter_links(self, hrefs: List[str], base_url: str) -> List[str]:
        parsed_base = urlparse(base_url)
        path_prefix = parsed_base.path.rstrip("/")
        seen: set = set()
        result = []

        for href in hrefs:
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = href if href.startswith("http") else urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc != parsed_base.netloc:
                continue

            if not parsed.path.rstrip("/").startswith(path_prefix):
                continue

            path = parsed.path.lower()
            if any(p in path for p in self.EXCLUDE_PATTERNS):
                continue

            normalized = self._normalize_url(full_url)
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

        return sorted(result)

    async def extract(self, url: str, selector: str = "devsite-book-nav a") -> List[str]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            console.print(f"[bold blue]Navigating to:[/bold blue] {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            elements = await page.query_selector_all(selector)
            hrefs = []
            for el in elements:
                href = await el.get_attribute("href")
                if href:
                    hrefs.append(href)

            await browser.close()

        console.print(f"[dim]Found {len(hrefs)} raw links from selector '{selector}'[/dim]")
        return self._filter_links(hrefs, url)
