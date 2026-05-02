# extract-nav Design

## Overview

New CLI command that extracts links from the left sidebar navigation of a documentation page using Playwright, producing a finite and curated list of URLs ready for ingestion.

## Problem

The existing `ingest` command with recursive crawling (`--depth`) captures too many pages (body links, cross-references, etc.). The `sitemap` approach proved unreliable for GCP docs. The sidebar nav is the canonical curated index maintained by the docs team — it represents exactly the set of pages worth indexing.

## Command Interface

```bash
qdoc extract-nav --url <url> [--output extract-nav-links.txt] [--selector .devsite-book-nav a]
```

| Flag | Default | Description |
|---|---|---|
| `--url` | required | Root documentation page to extract nav from |
| `--output` | `extract-nav-links.txt` | Output file path |
| `--selector` | `.devsite-book-nav a` | CSS selector targeting sidebar nav links |

Typical workflow:
```bash
qdoc extract-nav --url https://cloud.google.com/dialogflow/cx/docs
make ingest URL_FILE=extract-nav-links.txt  # or: qdoc ingest --file extract-nav-links.txt
```

## Architecture

### New module: `src/qdoc/nav_extractor.py`

Class `NavExtractor` with a single async method `extract(url, selector)` returning `List[str]`.

Steps:
1. Launch Playwright Chromium (headless)
2. Navigate to URL, wait for `networkidle`
3. `page.query_selector_all(selector)` — extract all `href` attributes
4. Filter links: same domain as seed URL, normalize via `_normalize_url` logic, exclude patterns from `DocumentationCrawler.exclude_patterns`
5. Deduplicate, sort, return

The URL normalization logic and exclude patterns list are duplicated diretamente em `NavExtractor` — sem shared utility, mantém o escopo mínimo.

### Changes to `src/qdoc/main.py`

Register one new Click command `extract-nav` in the `cli` group. The command:
- Instantiates `NavExtractor`
- Calls `asyncio.run(extractor.extract(url, selector))`
- Writes results to output file (one URL per line)
- Prints count summary to terminal via Rich console

No changes to any other existing module.

## Out of Scope

- Auto-running ingest after extraction (user pipes manually via `--file`)
- Multi-page nav extraction (only the root page's sidebar)
- Recursive nav following (if nav has expandable sub-sections requiring clicks)
