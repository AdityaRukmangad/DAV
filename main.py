import os
import sys
import warnings
import logging

# --- NUCLEAR WARNING SUPPRESSION ---
# Set environment variables before any other imports
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Completely disable warnings at the lowest level
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore")
sys.warnoptions = []

# Suppress all warning categories
for category in [DeprecationWarning, UserWarning, ResourceWarning, FutureWarning,
                 PendingDeprecationWarning, ImportWarning, RuntimeWarning]:
    warnings.filterwarnings("ignore", category=category)

# Suppress specific patterns
for pattern in [".*PydanticDeprecated.*", ".*model_fields.*", ".*pydantic.*",
                ".*langchain.*", ".*deprecated.*"]:
    warnings.filterwarnings("ignore", message=pattern)

# Override warnings.showwarning to completely suppress output
def _suppress_warning(*args, **kwargs):
    pass

warnings.showwarning = _suppress_warning
warnings.warn = lambda *args, **kwargs: None

# Suppress logging from noisy libraries
for logger_name in ["transformers", "sentence_transformers", "chromadb",
                    "langchain", "langchain_core", "langchain_community",
                    "langchain_openai", "pydantic"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    logging.getLogger(logger_name).propagate = False

# --- STANDARD IMPORTS ---
from pathlib import Path
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# --- APP IMPORTS ---
try:
    from app.services.rag_service import get_rag_service
    from app.services.graph_agent import run_agent
    from app.tools.utils import initialize_logging, get_logger
    from app.tools.show_pdf_usage import show_pdf_usage
except ImportError as e:
    sys.stderr.write(f"CRITICAL ERROR: {e}\n")
    sys.exit(1)

load_dotenv()
# Initialize logging but keep it to file, not console (unless error)
initialize_logging()
logger = get_logger("CLI")
console = Console()
UPLOAD_DIR = Path("uploads")

@click.group()
def cli():
    """HQGE Enterprise CLI"""
    pass

@cli.command()
@click.argument("topic")
@click.option("--difficulty", default="Medium", help="Difficulty level")
@click.option("--show-context", is_flag=True, help="Show PDF context used for generation")
def generate(topic, difficulty, show_context):
    """
    Generate a unique exam question.
    """
    console.print(Panel(f"[bold green]Generating Question[/bold green]\nTopic: {topic}\nDifficulty: {difficulty}", border_style="green"))

    # Show PDF context before generation
    if show_context:
        console.print("\n[bold cyan]PDF CONTEXT BEING USED:[/bold cyan]\n")
        show_pdf_usage(topic, limit=5)
        console.print("\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task(description="Tribunal Agents Thinking...", total=None)
            result = run_agent(topic, difficulty)

        console.print_json(data=result)

    except Exception as e:
        console.print(f"[bold red]Generation Error:[/bold red] {e}")

@cli.command()
@click.argument("target", required=False, type=click.Path(exists=True))
def ingest(target):
    """
    Ingest PDFs into the knowledge base.
    """
    if not target:
        target_path = UPLOAD_DIR
    else:
        target_path = Path(target)

    rag = get_rag_service()
    files_to_process = []

    if target_path.is_dir():
        console.print(f"[blue]Scanning folder: {target_path}[/blue]")
        files_to_process = list(target_path.glob("*.pdf"))
    elif target_path.suffix.lower() == ".pdf":
        files_to_process = [target_path]
    else:
        console.print("[red]Error: Target must be a PDF file or a directory containing PDFs.[/red]")
        return

    if not files_to_process:
        console.print("[yellow]No PDF files found to ingest.[/yellow]")
        return

    console.print(f"[bold]Found {len(files_to_process)} PDF(s) to ingest...[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        "•",
        TextColumn("{task.fields[status]}"),
        console=console
    ) as progress:
        
        main_task = progress.add_task("[green]Processing Batch[/green]", total=len(files_to_process), filename="", status="Starting")
        
        for file_path in files_to_process:
            progress.update(main_task, filename=file_path.name, status="Ingesting...")
            
            try:
                result = rag.ingest_file(str(file_path))
                
                if result.success:
                    progress.console.print(f"[green]✓ {file_path.name}[/green] ({result.chunk_count} chunks)")
                else:
                    progress.console.print(f"[yellow]⚠ {file_path.name}[/yellow]: {result.error_message}")
                    
            except Exception as e:
                progress.console.print(f"[red]✗ {file_path.name}[/red]: {e}")
            
            progress.advance(main_task)

@cli.command()
def stats():
    """Show knowledge base health statistics."""
    try:
        rag = get_rag_service()
        s = rag.get_statistics()
        
        table = Table(title="Knowledge Base Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        v_stats = s.get("vector_store", {})
        
        table.add_row("Total Chunks (Vectors)", str(v_stats.get("total_vectors", "N/A")))
        table.add_row("Documents Ingested", str(s.get("ingested_documents", "N/A")))
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")

if __name__ == "__main__":
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    cli()