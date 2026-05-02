from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, DataTable, Label, Log
from textual.containers import Container, Vertical, Horizontal
from qdoc.db import VectorDB
from qdoc.config import settings

class QDocApp(App):
    TITLE = "qdoc: GCP Technical Oracle"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="dashboard"):
                yield Vertical(
                    Label("System Status", id="title"),
                    Static(id="stats-box", classes="box"),
                    id="dashboard-container"
                )
            with TabPane("Ingestor", id="ingestor"):
                yield Vertical(
                    Label("Crawler Logs", id="title"),
                    Log(id="crawler-log"),
                    id="ingestor-container"
                )
            with TabPane("Explorer", id="explorer"):
                yield Vertical(
                    Label("Document Chunks", id="title"),
                    DataTable(id="chunks-table"),
                    id="explorer-container"
                )
        yield Footer()

    def on_mount(self) -> None:
        self.update_stats()
        self.setup_explorer()

    def update_stats(self):
        db = VectorDB()
        try:
            stats = db.get_stats()
            stats_text = (
                f"Qdrant Status: {stats['status']}\n"
                f"Total Vectors: {stats['vectors_count']}\n"
                f"Collection: {settings.QDRANT_COLLECTION}\n"
                f"Endpoint: {settings.QDRANT_URL}"
            )
            self.query_one("#stats-box", Static).update(stats_text)
        except Exception as e:
            self.query_one("#stats-box", Static).update(f"Error connecting to DB: {e}")

    def setup_explorer(self):
        table = self.query_one("#chunks-table", DataTable)
        table.clear()
        table.add_columns("Service", "URL", "Content Preview")
        
        db = VectorDB()
        try:
            chunks = db.list_chunks(limit=50)
            for chunk in chunks:
                table.add_row(
                    chunk.get("service", "N/A"),
                    chunk.get("url", "N/A"),
                    chunk.get("content", "")[:100] + "..."
                )
        except Exception as e:
            table.add_row("Error", "", str(e))

    def action_quit(self) -> None:
        self.exit()
