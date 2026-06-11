"""PACIFIC — File handling: open, read, and process local files."""

import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

# Supported file types for reading/analysis
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".jsonl", ".yaml", ".yml",
    ".py", ".js", ".ts", ".html", ".css", ".sql", ".sh", ".r",
    ".log", ".cfg", ".ini", ".toml", ".xml", ".env",
}

DATA_EXTENSIONS = {".csv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
PDF_EXTENSIONS = {".pdf"}


def open_file(filepath: str) -> bool:
    """Open a file using the system's default application.

    Args:
        filepath: Path to the file to open.

    Returns:
        True if the file was opened successfully.
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return False

    console.print(f"[dim]Opening:[/dim] {path}")
    try:
        # macOS
        if os.uname().sysname == "Darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"[green]✓ Opened:[/green] {path.name}")
        return True
    except Exception as e:
        console.print(f"[red]✗ Could not open file: {e}[/red]")
        return False


def read_file_content(filepath: str, max_lines: int = 200) -> Optional[str]:
    """Read a text file and return its content.

    Args:
        filepath: Path to the file to read.
        max_lines: Maximum lines to read (to prevent huge files from hanging).

    Returns:
        File content as string, or None if unreadable.
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return None

    ext = path.suffix.lower()

    # PDF files — extract text with PyMuPDF
    if ext in PDF_EXTENSIONS:
        return read_pdf_content(str(path), max_pages=50)

    # Binary files — don't read
    if ext in IMAGE_EXTENSIONS or ext in {".xlsx", ".xls", ".parquet", ".zip", ".tar", ".gz"}:
        console.print(f"[yellow]⚠ Binary file detected ({ext}). Use /open to open it instead.[/yellow]")
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"\n... (truncated at {max_lines} lines)")
                    break
                lines.append(line)
            content = "".join(lines)

        size = path.stat().st_size
        console.print(f"[dim]Read {path.name} ({_fmt_size(size)}, {len(lines)} lines)[/dim]")
        return content

    except Exception as e:
        console.print(f"[red]✗ Error reading file: {e}[/red]")
        return None


def read_pdf_content(filepath: str, max_pages: int = 50) -> Optional[str]:
    """Extract text from a PDF file using PyMuPDF.

    Args:
        filepath: Path to the PDF file.
        max_pages: Maximum pages to extract.

    Returns:
        Extracted text as a string, or None on failure.
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return None

    try:
        import pymupdf
    except ImportError:
        console.print("[yellow]⚠ PDF support requires pymupdf: pip install pymupdf[/yellow]")
        return None

    try:
        doc = pymupdf.open(str(path))
        total_pages = len(doc)
        pages_to_read = min(total_pages, max_pages)
        text_parts = []

        for i in range(pages_to_read):
            page = doc[i]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{text.strip()}")

        doc.close()

        if not text_parts:
            console.print(f"[yellow]⚠ PDF has no extractable text (may be scanned/image-based).[/yellow]")
            return None

        content = "\n\n".join(text_parts)
        size = path.stat().st_size
        truncated = f" (showing {pages_to_read}/{total_pages} pages)" if pages_to_read < total_pages else ""
        console.print(f"[dim]Read {path.name} ({_fmt_size(size)}, {total_pages} pages{truncated})[/dim]")
        return content

    except Exception as e:
        console.print(f"[red]✗ Error reading PDF: {e}[/red]")
        return None


def read_csv_summary(filepath: str) -> Optional[str]:
    """Read a CSV file and return a summary with schema + first few rows."""
    try:
        import pandas as pd
    except ImportError:
        console.print("[red]Missing dependency: pip install pandas[/red]")
        return None

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return None

    try:
        df = pd.read_csv(path)
        summary = []
        summary.append(f"**File:** {path.name}")
        summary.append(f"**Shape:** {df.shape[0]} rows × {df.shape[1]} columns")
        summary.append(f"**Columns:** {', '.join(df.columns.tolist())}")
        summary.append(f"\n**Data Types:**")
        for col in df.columns:
            summary.append(f"  - {col}: {df[col].dtype}")
        summary.append(f"\n**First 5 rows:**\n{df.head().to_string()}")
        summary.append(f"\n**Statistics:**\n{df.describe().to_string()}")
        return "\n".join(summary)
    except Exception as e:
        console.print(f"[red]✗ Error reading CSV: {e}[/red]")
        return None


def read_json_summary(filepath: str) -> Optional[str]:
    """Read a JSON/JSONL file and return a summary."""
    import json as json_mod

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return None

    try:
        ext = path.suffix.lower()
        if ext == ".jsonl":
            with open(path) as f:
                records = [json_mod.loads(line) for line in f if line.strip()]
            summary = f"**File:** {path.name}\n**Records:** {len(records)}\n"
            if records:
                summary += f"**Keys:** {', '.join(records[0].keys())}\n"
                summary += f"\n**First record:**\n```json\n{json_mod.dumps(records[0], indent=2)}\n```"
            return summary
        else:
            with open(path) as f:
                data = json_mod.load(f)
            if isinstance(data, list):
                summary = f"**File:** {path.name}\n**Type:** Array of {len(data)} items\n"
                if data:
                    summary += f"**Keys:** {', '.join(data[0].keys()) if isinstance(data[0], dict) else 'N/A'}\n"
                    summary += f"\n**First item:**\n```json\n{json_mod.dumps(data[0], indent=2)}\n```"
            elif isinstance(data, dict):
                summary = f"**File:** {path.name}\n**Type:** Object\n"
                summary += f"**Keys:** {', '.join(data.keys())}\n"
                summary += f"\n**Preview:**\n```json\n{json_mod.dumps(data, indent=2)[:2000]}\n```"
            else:
                summary = f"**File:** {path.name}\n**Content:** {str(data)[:500]}"
            return summary
    except Exception as e:
        console.print(f"[red]✗ Error reading JSON: {e}[/red]")
        return None


def display_file_content(filepath: str):
    """Read and display a file with syntax highlighting in the terminal."""
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]✗ File not found:[/red] {path}")
        return

    ext = path.suffix.lower()

    # Handle data files specially
    if ext == ".csv":
        summary = read_csv_summary(filepath)
        if summary:
            console.print(Panel(summary, title=f"[cyan]{path.name}[/cyan]", border_style="cyan"))
        return

    if ext in {".json", ".jsonl"}:
        summary = read_json_summary(filepath)
        if summary:
            console.print(Panel(summary, title=f"[cyan]{path.name}[/cyan]", border_style="cyan"))
        return

    # Handle PDFs — extract and display text
    if ext in PDF_EXTENSIONS:
        content = read_pdf_content(filepath)
        if content:
            console.print(Panel(content[:5000], title=f"[cyan]📄 {path.name}[/cyan]", border_style="cyan"))
        return

    # Handle images — tell user to use /image
    if ext in IMAGE_EXTENSIONS:
        console.print(f"[yellow]📷 Image file detected. Use [bold]/image {filepath}[/bold] to analyze it with Pacific AI.[/yellow]")
        return

    # Text files — show with syntax highlighting
    content = read_file_content(filepath)
    if content:
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".html": "html", ".css": "css", ".sql": "sql", ".sh": "bash",
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".md": "markdown", ".xml": "xml", ".r": "r",
        }
        lang = lang_map.get(ext, "text")
        syntax = Syntax(content, lang, theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"[cyan]{path.name}[/cyan]", border_style="cyan"))


def resolve_path(user_input: str) -> Optional[str]:
    """Try to resolve a file path from user input.

    Handles:
    - Absolute paths: /Users/GRRN/file.csv
    - Home-relative: ~/Documents/file.csv
    - Relative: ./data.json, data.json
    - Quoted: "/path/with spaces/file.csv"
    """
    # Strip quotes
    cleaned = user_input.strip().strip('"').strip("'")

    path = Path(cleaned).expanduser()
    if path.exists():
        return str(path.resolve())

    # Try relative to CWD
    cwd_path = Path.cwd() / cleaned
    if cwd_path.exists():
        return str(cwd_path.resolve())

    return None


def _fmt_size(n: int) -> str:
    """Format bytes to human-readable."""
    if n >= 1e9:
        return f"{n/1e9:.1f} GB"
    if n >= 1e6:
        return f"{n/1e6:.1f} MB"
    if n >= 1e3:
        return f"{n/1e3:.1f} KB"
    return f"{n} B"
