import click
import asyncio
from rich.console import Console
from rich.table import Table
from qdoc.config import settings
from qdoc.db import VectorDB
from qdoc.embeddings import EmbeddingEngine
from qdoc.crawler import DocumentationCrawler

console = Console()

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """qdoc: GCP Technical Oracle CLI/TUI."""
    if ctx.invoked_subcommand is None:
        from qdoc.tui.app import QDocApp
        app = QDocApp()
        app.run()

@cli.command()
def status():
    """Display health metrics and DB status."""
    db = VectorDB()
    try:
        stats = db.get_stats()
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
@click.option("--all", is_flag=True, help="Ingest all services")
@click.option("--rebuild", is_flag=True, help="Drop and rebuild collection")
@click.option("--depth", default=0, help="Crawl depth")
@click.option("--url", help="Override seed URL")
def ingest(service, all, rebuild, depth, url):
    """Ingest documentation for a service."""
    db = VectorDB()
    db.init_collection(rebuild=rebuild)
    
    engine = EmbeddingEngine()
    crawler = DocumentationCrawler(db, engine)
    
    seed_url = url or settings.DEFAULT_SEED_URL
    service_name = service or "default"
    
    console.print(f"[bold green]Starting ingestion for {service_name}...[/bold green]")
    asyncio.run(crawler.crawl_recursive(seed_url, service_name, depth))
    console.print("[bold green]Ingestion complete![/bold green]")

@cli.command()
@click.argument("query_text")
@click.option("--service", help="Filter by service")
@click.option("--limit", default=5, help="Result limit")
def query(query_text, service, limit):
    """Search for chunks using a natural language query."""
    db = VectorDB()
    engine = EmbeddingEngine()
    
    console.print(f"[bold blue]Searching for:[/bold blue] {query_text}")
    vector = engine.get_query_embedding(query_text)
    
    service_filter = [service] if service else None
    results = db.search(vector, service_filter=service_filter, limit=limit)
    
    for i, res in enumerate(results):
        console.print(f"\n[bold yellow]Result {i+1} (Source: {res['url']})[/bold yellow]")
        console.print(res["content"][:300] + "...")

@cli.command()
def serve():
    """Start the MCP stdio server."""
    from qdoc.mcp_server import serve_mcp
    asyncio.run(serve_mcp())

def main():
    cli()

if __name__ == "__main__":
    main()
