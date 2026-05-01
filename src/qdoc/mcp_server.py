from mcp.server.fastmcp import FastMCP
from qdoc.db import VectorDB
from qdoc.embeddings import EmbeddingEngine
from typing import List, Optional

mcp = FastMCP("qdoc")

@mcp.tool()
def search_gcp_docs(query: str, services_filter: Optional[List[str]] = None, limit: int = 5) -> str:
    """
    Search for technical documentation about GCP services.
    
    Args:
        query: The natural language search query.
        services_filter: Optional list of services to filter by (e.g., ['dialogflow-cx']).
        limit: Maximum number of results to return.
    """
    db = VectorDB()
    engine = EmbeddingEngine()
    
    vector = engine.get_query_embedding(query)
    results = db.search(vector, service_filter=services_filter, limit=limit)
    
    if not results:
        return "No relevant documentation found."
    
    output = []
    for res in results:
        output.append(f"Source: {res['url']}\nContent: {res['content']}\n---")
    
    return "\n".join(output)

async def serve_mcp():
    """Run the MCP server."""
    await mcp.run_stdio_async()
