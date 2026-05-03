# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is qdoc

qdoc is a GCP documentation RAG (Retrieval-Augmented Generation) tool that crawls GCP docs, embeds them into a Qdrant vector store using Google's `text-embedding-004`, and answers queries via Gemini. It also exposes an MCP server for Claude integration and a Textual TUI.

## Development Commands

```bash
# Install (globally via uv tool)
make install

# Start Qdrant (required before any ingest/query)
make up

# Run directly without installing
PYTHONPATH=src uv run python -m qdoc.main <command>

# Ingest docs from a URL (recursive crawl)
make ingest URL=https://... DEPTH=5

# Ingest from a sitemap
make sitemap-ingest SITEMAP=https://.../sitemap.xml URL=https://... SITEMAP_LIMIT=20

# List URLs that would be crawled (dry run)
make list URL=https://... DEPTH=3

# Query the vector DB
make query Q="how to configure agents" LIMIT=5

# Discover URLs using Gemini (saves to links.txt)
make discover P="Conversational Agents" QUERY="site:cloud.google.com docs"

# Start TUI
make tui

# Clear all data from Qdrant
make clear

# Start MCP server (stdio)
PYTHONPATH=src uv run python -m qdoc.main serve
```

## Architecture

```
src/qdoc/
├── main.py        # CLI entrypoint (Click group); no-subcommand launches TUI
├── config.py      # Settings via pydantic-settings; reads from .env
├── crawler.py     # DocumentationCrawler: recursive crawl + sitemap + parallel batch ingest
├── embeddings.py  # EmbeddingEngine: chunks text (1000/100 overlap) + Vertex AI embeddings
├── db.py          # VectorDB: Qdrant wrapper; content-hash dedup, payload indexes on service+url
├── llm.py         # LLMEngine: Gemini for answer generation, query augmentation, evaluation
├── mcp_server.py  # FastMCP server exposing search_gcp_docs tool with agentic retry loop
├── discovery.py   # IntelligentDiscovery: Gemini-based URL discovery from search queries
└── tui/app.py     # Textual TUI: dashboard, ingestor log, document chunk explorer
```

### Key design decisions

- **Content-hash dedup** (`db.py`): Before re-embedding a page, `get_existing_hash` checks if the markdown content changed. Only changed pages are re-embedded and upserted.
- **Agentic search loop** (`mcp_server.py`): `search_gcp_docs` runs up to 5 iterations of vector search → evaluate with LLM → augment query → retry if insufficient results.
- **Parallel crawling** (`crawler.py`): Uses `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` and `asyncio.Queue` for bounded parallel workers. `_should_crawl` filters by domain and path prefix; strips non-doc paths (pricing, blog, etc.).
- **Embeddings use task types**: `RETRIEVAL_DOCUMENT` for indexing, `RETRIEVAL_QUERY` for queries — required by `text-embedding-004`.

## Configuration

Settings are loaded from `.env` via pydantic-settings. Key variables:

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_COLLECTION` | `gcp_docs` | Collection name |
| `GOOGLE_CLOUD_PROJECT` | — | Required for Vertex AI auth |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI region |
| `EMBEDDING_MODEL` | `text-embedding-004` | Vector size is hardcoded to 768 in `db.py` |
| `GENAI_MODEL` | `gemini-2.0-flash` | Gemini model for LLM calls |
| `MAX_CONCURRENT_REQUESTS` | `20` | Crawler concurrency |

## MCP Integration

To use qdoc as an MCP tool in Claude, configure the server with:
```json
{
  "mcpServers": {
    "qdoc": {
      "command": "qdoc",
      "args": ["serve"]
    }
  }
}
```

The `search_gcp_docs` tool accepts `query`, `services_filter`, `limit`, and `simple` (bypasses agentic loop for raw results).

## Notes

- `build/` contains a compiled copy of `src/`; edit only in `src/`.
- Playwright (Chromium) must be installed for JS-heavy pages: `uv run playwright install chromium`.
- GCP auth is handled by ADC (`gcloud auth application-default login`); no explicit key management in code.
