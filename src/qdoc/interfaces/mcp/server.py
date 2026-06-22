from mcp.server.fastmcp import FastMCP
from qdoc.infrastructure.db.qdrant_repository import QdrantVectorRepository
from qdoc.infrastructure.llm.gemini_embedding import GeminiEmbeddingService
from qdoc.infrastructure.llm.gemini_llm import GeminiLLMService
from qdoc.application.smart_ingest_use_case import SmartIngestUseCase
from qdoc.application.search_use_case import SearchUseCase
from typing import List, Optional

mcp = FastMCP("qdoc")

# Factory for Use Cases
def get_ingest_use_case():
    return SmartIngestUseCase(QdrantVectorRepository(), GeminiEmbeddingService(), GeminiLLMService())

def get_search_use_case():
    return SearchUseCase(QdrantVectorRepository(), GeminiEmbeddingService(), GeminiLLMService())

@mcp.tool()
async def ingest_docs(url: str, service: Optional[str] = None, smart: bool = True, recursive: bool = False, depth: int = 1) -> str:
    """
    Ingest documentation from a URL into the vector database.
    
    Args:
        url: The URL to ingest.
        service: Optional service name.
        smart: Use AI to automatically find and ingest all relevant sub-pages from a root URL (default True).
        recursive: Standard recursive crawl (only if smart is False).
        depth: Recursion depth.
    """
    use_case = get_ingest_use_case()
    service_name = service or "default"
    
    try:
        if smart:
            await use_case.execute_smart_root(url, service_name)
        elif recursive:
            await use_case.execute_recursive(url, service_name, depth)
        else:
            await use_case.execute_url(url, service_name)
        return f"Successfully ingested documentation from {url} into service '{service_name}' (smart={smart})."
    except Exception as e:
        return f"Error ingesting documentation: {str(e)}"

@mcp.tool()
async def search_docs(query: str, services_filter: Optional[List[str]] = None, url_filter: Optional[str] = None, limit: int = 10, simple: bool = False) -> str:
    """
    Search for technical documentation.
    
    Args:
        query: The search query.
        services_filter: Optional list of services to filter by.
        url_filter: Optional exact URL to filter by.
        limit: Max results.
        simple: Skip AI reasoning.
    """
    use_case = get_search_use_case()
    return await use_case.execute(query, services_filter, url_filter, limit, simple)

async def serve_mcp():
    await mcp.run_stdio_async()
