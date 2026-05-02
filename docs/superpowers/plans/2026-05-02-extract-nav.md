# extract-nav Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar o comando `qdoc extract-nav` que extrai links do menu lateral de uma página de documentação usando Playwright e salva em arquivo para uso com `qdoc ingest --file`.

**Architecture:** `NavExtractor` em `src/qdoc/nav_extractor.py` encapsula toda a lógica — filtragem pura em `_filter_links`/`_normalize_url` (testáveis sem browser) e extração com Playwright em `extract`. O comando CLI em `main.py` apenas instancia e chama.

**Tech Stack:** Playwright async API, Click, Rich, Python 3.13, pytest

---

### Task 1: NavExtractor — lógica de filtragem (TDD)

**Files:**
- Create: `src/qdoc/nav_extractor.py`
- Create: `tests/test_nav_extractor.py`

- [ ] **Step 1: Adicionar pytest como dependência de desenvolvimento**

```bash
uv add --dev pytest
```

Esperado: `pytest` adicionado ao `pyproject.toml` em `[dependency-groups]`.

- [ ] **Step 2: Criar o arquivo de testes com casos que vão falhar**

Criar `tests/test_nav_extractor.py`:

```python
import pytest
from qdoc.nav_extractor import NavExtractor

BASE = "https://cloud.google.com/dialogflow/cx/docs"


def test_filter_keeps_same_domain():
    extractor = NavExtractor()
    hrefs = [
        "https://cloud.google.com/dialogflow/cx/docs/concept",
        "https://other.com/page",
    ]
    result = extractor._filter_links(hrefs, BASE)
    assert result == ["https://cloud.google.com/dialogflow/cx/docs/concept"]


def test_filter_excludes_patterns():
    extractor = NavExtractor()
    hrefs = [
        "https://cloud.google.com/dialogflow/cx/docs/pricing",
        "https://cloud.google.com/dialogflow/cx/docs/blog/post",
        "https://cloud.google.com/dialogflow/cx/docs/concept",
    ]
    result = extractor._filter_links(hrefs, BASE)
    assert result == ["https://cloud.google.com/dialogflow/cx/docs/concept"]


def test_filter_deduplicates_with_trailing_slash():
    extractor = NavExtractor()
    hrefs = [
        "https://cloud.google.com/dialogflow/cx/docs/concept",
        "https://cloud.google.com/dialogflow/cx/docs/concept/",
    ]
    result = extractor._filter_links(hrefs, BASE)
    assert len(result) == 1


def test_filter_skips_relative_and_empty():
    extractor = NavExtractor()
    hrefs = ["/relative/path", "", "https://cloud.google.com/dialogflow/cx/docs/concept"]
    result = extractor._filter_links(hrefs, BASE)
    assert result == ["https://cloud.google.com/dialogflow/cx/docs/concept"]


def test_filter_returns_sorted():
    extractor = NavExtractor()
    hrefs = [
        "https://cloud.google.com/dialogflow/cx/docs/z-page",
        "https://cloud.google.com/dialogflow/cx/docs/a-page",
    ]
    result = extractor._filter_links(hrefs, BASE)
    assert result[0] < result[1]


def test_normalize_strips_trailing_slash():
    extractor = NavExtractor()
    assert extractor._normalize_url("https://cloud.google.com/docs/") == "https://cloud.google.com/docs"


def test_normalize_keeps_hl_pt_br():
    extractor = NavExtractor()
    result = extractor._normalize_url("https://cloud.google.com/docs?hl=pt-br")
    assert "hl=pt-br" in result


def test_normalize_keeps_hl_en():
    extractor = NavExtractor()
    result = extractor._normalize_url("https://cloud.google.com/docs?hl=en")
    assert "hl=en" in result


def test_normalize_drops_unsupported_hl():
    extractor = NavExtractor()
    result = extractor._normalize_url("https://cloud.google.com/docs?hl=ja")
    assert "hl=" not in result
```

- [ ] **Step 3: Rodar os testes e verificar que falham**

```bash
PYTHONPATH=src uv run pytest tests/test_nav_extractor.py -v
```

Esperado: `ERROR` ou `ImportError` — `nav_extractor` ainda não existe.

- [ ] **Step 4: Criar `src/qdoc/nav_extractor.py` com a lógica de filtragem**

```python
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
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
        seen: set = set()
        result = []

        for href in hrefs:
            if not href or not href.startswith("http"):
                continue

            parsed = urlparse(href)
            if parsed.netloc != parsed_base.netloc:
                continue

            path = parsed.path.lower()
            if any(p in path for p in self.EXCLUDE_PATTERNS):
                continue

            normalized = self._normalize_url(href)
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

        return sorted(result)

    async def extract(self, url: str, selector: str = ".devsite-book-nav a") -> List[str]:
        raise NotImplementedError
```

- [ ] **Step 5: Rodar os testes e verificar que passam**

```bash
PYTHONPATH=src uv run pytest tests/test_nav_extractor.py -v
```

Esperado: todos os 9 testes passam.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/qdoc/nav_extractor.py tests/test_nav_extractor.py
git commit -m "feat: add NavExtractor with filtering logic and tests"
```

---

### Task 2: NavExtractor — método `extract` com Playwright

**Files:**
- Modify: `src/qdoc/nav_extractor.py`

> Sem testes unitários para este método — automação de browser é testada manualmente no Step 3.

- [ ] **Step 1: Substituir o `NotImplementedError` pelo método real**

Substituir o método `extract` em `src/qdoc/nav_extractor.py`:

```python
async def extract(self, url: str, selector: str = ".devsite-book-nav a") -> List[str]:
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
```

- [ ] **Step 2: Verificar que os testes de filtragem ainda passam**

```bash
PYTHONPATH=src uv run pytest tests/test_nav_extractor.py -v
```

Esperado: todos passam (o método `extract` não é chamado pelos testes de filtragem).

- [ ] **Step 3: Smoke test manual**

```bash
PYTHONPATH=src uv run python -c "
import asyncio
from qdoc.nav_extractor import NavExtractor
links = asyncio.run(NavExtractor().extract('https://cloud.google.com/dialogflow/cx/docs'))
print(f'Found {len(links)} links')
for l in links[:5]: print(l)
"
```

Esperado: lista com links do domínio `cloud.google.com`. Se o count for 0, o seletor `.devsite-book-nav a` não bateu — inspecionar a página e ajustar o seletor padrão.

- [ ] **Step 4: Commit**

```bash
git add src/qdoc/nav_extractor.py
git commit -m "feat: implement Playwright extraction in NavExtractor"
```

---

### Task 3: Comando CLI `extract-nav`

**Files:**
- Modify: `src/qdoc/main.py`

- [ ] **Step 1: Adicionar o comando `extract-nav` ao grupo `cli` em `main.py`**

Adicionar após o comando `discover` existente (linha ~43), antes do comando `status`:

```python
@cli.command("extract-nav")
@click.option("--url", required=True, help="Root documentation page URL")
@click.option("--output", default="extract-nav-links.txt", show_default=True, help="Output file path")
@click.option("--selector", default=".devsite-book-nav a", show_default=True, help="CSS selector for nav links")
def extract_nav(url, output, selector):
    """Extract sidebar nav links from a documentation page into a file."""
    from qdoc.nav_extractor import NavExtractor
    extractor = NavExtractor()
    links = asyncio.run(extractor.extract(url, selector))

    with open(output, "w") as f:
        for link in links:
            f.write(f"{link}\n")

    console.print(f"[bold green]Saved {len(links)} links to {output}[/bold green]")
```

- [ ] **Step 2: Verificar que o comando aparece no help**

```bash
PYTHONPATH=src uv run python -m qdoc.main --help
```

Esperado: `extract-nav` listado entre os comandos disponíveis.

- [ ] **Step 3: Smoke test end-to-end**

```bash
PYTHONPATH=src uv run python -m qdoc.main extract-nav \
  --url https://cloud.google.com/dialogflow/cx/docs \
  --output /tmp/test-nav-links.txt

cat /tmp/test-nav-links.txt | head -10
wc -l /tmp/test-nav-links.txt
```

Esperado: arquivo com N links, um por linha, todos começando com `https://cloud.google.com`.

- [ ] **Step 4: Rodar todos os testes para garantir nenhuma regressão**

```bash
PYTHONPATH=src uv run pytest tests/ -v
```

Esperado: todos passam.

- [ ] **Step 5: Commit final**

```bash
git add src/qdoc/main.py
git commit -m "feat: add extract-nav CLI command"
```
