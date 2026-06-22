import click
import asyncio
from rich.console import Console
from rich.table import Table
from qdoc.infrastructure.config import settings
from qdoc.infrastructure.db.qdrant_repository import QdrantVectorRepository
from qdoc.infrastructure.llm.gemini_embedding import GeminiEmbeddingService
from qdoc.infrastructure.llm.gemini_llm import GeminiLLMService
from qdoc.application.ingest_use_case import IngestUseCase
from qdoc.application.smart_ingest_use_case import SmartIngestUseCase

console = Console()

def get_ingest_use_case():
    return SmartIngestUseCase(QdrantVectorRepository(), GeminiEmbeddingService(), GeminiLLMService())

def get_search_use_case():

    return SearchUseCase(QdrantVectorRepository(), GeminiEmbeddingService(), GeminiLLMService())

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """qdoc: Technical Documentation Oracle CLI/TUI."""
    if ctx.invoked_subcommand is None:
        # TODO: Update TUI to new structure
        from qdoc.tui.app import QDocApp
        app = QDocApp()
        app.run()

@cli.command()
def status():
    """Display health metrics and DB status."""
    repo = QdrantVectorRepository()
    try:
        stats = repo.get_stats()
        table = Table(title="qdoc Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Qdrant Status", stats["status"])
        table.add_row("Total Vectors", str(stats["vectors_count"]))
        table.add_row("Collection", settings.QDRANT_COLLECTION)
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error connecting to Qdrant: {e}[/red]")

@cli.command()
@click.argument("service", required=False)
@click.option("--rebuild", is_flag=True, help="Drop and rebuild collection")
@click.option("--depth", default=0, help="Crawl depth")
@click.option("--url", help="Override seed URL")
@click.option("--file", "url_file", type=click.Path(exists=True), help="Ingest from a file containing URLs")
@click.option("--smart", is_flag=True, help="Use AI to find navigation links automatically")
def ingest(service, rebuild, depth, url, url_file, smart):
    """Ingest documentation for a service."""
    repo = QdrantVectorRepository()
    if rebuild:
        repo.init_collection(rebuild=True)
    else:
        repo.init_collection()

    use_case = get_ingest_use_case()
    service_name = service or "default"

    if url_file:
        with open(url_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
        asyncio.run(use_case.execute_list(urls, service_name))
    elif smart:
        seed_url = url or settings.DEFAULT_SEED_URL
        asyncio.run(use_case.execute_smart_root(seed_url, service_name))
    else:
        seed_url = url or settings.DEFAULT_SEED_URL
        if depth > 0:
            asyncio.run(use_case.execute_recursive(seed_url, service_name, depth))
        else:
            asyncio.run(use_case.execute_url(seed_url, service_name))

    console.print("[bold green]Ingestion complete![/bold green]")

@cli.command()
@click.argument("query_text")
@click.option("--service", help="Filter by service")
@click.option("--url-filter", help="Filter by exact URL")
@click.option("--limit", default=5, help="Result limit")
@click.option("--simple", is_flag=True, help="Skip agentic reasoning")
def query(query_text, service, url_filter, limit, simple):
    """Search for chunks using a natural language query."""
    use_case = get_search_use_case()
    service_filter = [service] if service else None
    
    result = asyncio.run(use_case.execute(query_text, service_filter, url_filter, limit, simple))
    console.print(result)

@cli.command()
def serve():
    """Start the MCP stdio server."""
    from qdoc.interfaces.mcp.server import serve_mcp
    asyncio.run(serve_mcp())

@cli.command()
@click.option("--yes", is_flag=True, help="Skip confirmation")
def clear(yes):
    """Clear all data from the collection."""
    if not yes:
        if not click.confirm("Are you sure you want to clear all data? This cannot be undone."):
            return
    
    repo = QdrantVectorRepository()
    try:
        repo.init_collection(rebuild=True)
        console.print("[bold green]Collection cleared successfully![/bold green]")
    except Exception as e:
        console.print(f"[red]Error clearing collection: {e}[/red]")

def main():
    cli()
