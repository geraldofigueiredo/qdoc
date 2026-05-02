from mcp.server.fastmcp import FastMCP
from qdoc.db import VectorDB
from qdoc.embeddings import EmbeddingEngine
from qdoc.llm import LLMEngine
from typing import List, Optional

mcp = FastMCP("qdoc")

@mcp.tool()
def search_gcp_docs(query: str, services_filter: Optional[List[str]] = None, limit: int = 10, simple: bool = False) -> str:
    """
    Search for technical documentation about GCP services.
    
    Args:
        query: The natural language search query.
        services_filter: Optional list of services to filter by.
        limit: Maximum number of results (default 10).
        simple: If True, bypass agentic reasoning and return raw chunks for debugging.
    """
    db = VectorDB()
    embed_engine = EmbeddingEngine()
    
    if simple:
        vector = embed_engine.get_query_embedding(query)
        results = db.search(vector, service_filter=services_filter, limit=limit)
        if not results:
            return "No documentation found."
        
        output = []
        for res in results:
            output.append(f"Source: {res['url']} (Score: {res['score']:.4f})\nContent: {res['content']}\n---")
        return "\n".join(output)

    llm_engine = LLMEngine()
    current_query = query
    max_retries = 5
    all_chunks = []
    seen_chunk_keys: set = set()
    seen_urls: set = set()

    for attempt in range(max_retries):
        # 1. Vector search
        vector = embed_engine.get_query_embedding(current_query)
        results = db.search(vector, service_filter=services_filter, limit=limit)

        if not results:
            if attempt == 0:
                return "No documentation found for this query."
            break

        # 2. Expand: fetch all chunks from the top matched URLs
        matched_urls = list(dict.fromkeys(r["url"] for r in results))[:3]
        for url in matched_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            for chunk_data in db.get_all_chunks_by_url(url):
                key = url + chunk_data.get("content", "")[:50]
                if key not in seen_chunk_keys:
                    all_chunks.append(chunk_data["content"])
                    seen_chunk_keys.add(key)

        # 3. Always augment query using what was already found as context
        current_query = llm_engine.augment_query(query, current_query, all_chunks)

        # 4. Evaluate sufficiency only after first augmentation pass
        if attempt > 0:
            if llm_engine.evaluate_results(query, all_chunks):
                return llm_engine.generate_answer(query, all_chunks)

    if all_chunks:
        return llm_engine.generate_answer(query, all_chunks)

    return "I couldn't find enough information to answer your query after multiple attempts."

async def serve_mcp():
    """Run the MCP server."""
    await mcp.run_stdio_async()
