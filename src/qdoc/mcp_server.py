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
    seen_urls = set()
    
    for attempt in range(max_retries):
        # 1. Vector Search
        vector = embed_engine.get_query_embedding(current_query)
        results = db.search(vector, service_filter=services_filter, limit=limit)
        
        if not results:
            if attempt == 0:
                return "No documentation found for this query."
            break # Try to answer with what we have
            
        # Add new chunks to our context
        new_chunks = []
        for res in results:
            if res['url'] + res['content'][:50] not in seen_urls:
                new_chunks.append(res['content'])
                seen_urls.add(res['url'] + res['content'][:50])
        
        all_chunks.extend(new_chunks)
        
        # 2. Reasoning/Evaluation
        is_sufficient = llm_engine.evaluate_results(query, all_chunks)
        
        if is_sufficient:
            # 3. Generate final answer
            return llm_engine.generate_answer(query, all_chunks)
        
        # 4. Query Augmentation
        current_query = llm_engine.augment_query(query, current_query)
        
    # Final attempt to answer with whatever we gathered
    if all_chunks:
        return llm_engine.generate_answer(query, all_chunks)
        
    return "I couldn't find enough information to answer your query after multiple attempts."

async def serve_mcp():
    """Run the MCP server."""
    await mcp.run_stdio_async()
