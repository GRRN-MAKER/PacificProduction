"""
Pacific CLI — File handling: read, analyze, and process local files.

Supports: PDF, CSV, JSON, JSONL, Excel, plain text, code files.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ANSI colors
RESET = "\033[0m"
DIM = "\033[2m"
GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".jsonl", ".yaml", ".yml",
    ".py", ".js", ".ts", ".html", ".css", ".sql", ".sh", ".r",
    ".log", ".cfg", ".ini", ".toml", ".xml", ".env", ".bat", ".ps1",
    ".c", ".cpp", ".h", ".java", ".go", ".rs", ".rb", ".php",
}

DATA_EXTENSIONS = {".csv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
PDF_EXTENSIONS = {".pdf"}


def resolve_path(filepath: str) -> Optional[str]:
    """Resolve a file path, expanding ~ and checking existence."""
    path = Path(filepath).expanduser().resolve()
    if path.exists():
        return str(path)
    # Try relative to CWD
    cwd_path = Path.cwd() / filepath
    if cwd_path.exists():
        return str(cwd_path.resolve())
    return None


def open_file(filepath: str) -> bool:
    """Open a file using the system's default application."""
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        print(f"{RED}✗ File not found:{RESET} {path}")
        return False

    print(f"{DIM}Opening:{RESET} {path}")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{GREEN}✓ Opened:{RESET} {path.name}")
        return True
    except Exception as e:
        print(f"{RED}✗ Could not open file: {e}{RESET}")
        return False


def read_file_content(filepath: str, max_lines: int = 500) -> Optional[str]:
    """Read a text file and return its content.

    Handles: .txt, .csv, .json, .py, .pdf, and more.
    Returns None for binary/unsupported files.
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        print(f"{RED}✗ File not found:{RESET} {path}")
        return None

    ext = path.suffix.lower()

    # PDF — extract text with PyMuPDF
    if ext in PDF_EXTENSIONS:
        return read_pdf_content(str(path), max_pages=50)

    # Binary files — don't read
    if ext in IMAGE_EXTENSIONS or ext in {".xlsx", ".xls", ".parquet", ".zip", ".tar", ".gz", ".exe", ".dll"}:
        print(f"{YELLOW}⚠ Binary file ({ext}). Use /open to open it.{RESET}")
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
        print(f"{DIM}Read {path.name} ({_fmt_size(size)}, {len(lines)} lines){RESET}")
        return content

    except Exception as e:
        print(f"{RED}✗ Error reading file: {e}{RESET}")
        return None


def read_pdf_content(filepath: str, max_pages: int = 50) -> Optional[str]:
    """Extract text from a PDF file using PyMuPDF."""
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        print(f"{RED}✗ File not found:{RESET} {path}")
        return None

    try:
        import pymupdf
    except ImportError:
        print(f"{YELLOW}⚠ PDF support requires pymupdf: pip install pymupdf{RESET}")
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
            print(f"{YELLOW}⚠ PDF has no extractable text (may be scanned/image-based).{RESET}")
            return None

        content = "\n\n".join(text_parts)
        size = path.stat().st_size
        truncated = f" (showing {pages_to_read}/{total_pages} pages)" if pages_to_read < total_pages else ""
        print(f"{DIM}Read {path.name} ({_fmt_size(size)}, {total_pages} pages{truncated}){RESET}")
        return content

    except Exception as e:
        print(f"{RED}✗ Error reading PDF: {e}{RESET}")
        return None


def read_csv_summary(filepath: str) -> Optional[str]:
    """Read a CSV file and return a summary with schema + first few rows."""
    try:
        import pandas as pd
    except ImportError:
        print(f"{RED}Missing: pip install pandas{RESET}")
        return None

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        print(f"{RED}✗ File not found:{RESET} {path}")
        return None

    try:
        df = pd.read_csv(path)
        summary = []
        summary.append(f"**File:** {path.name}")
        summary.append(f"**Shape:** {df.shape[0]} rows x {df.shape[1]} columns")
        summary.append(f"**Columns:** {', '.join(df.columns.tolist())}")
        summary.append(f"\n**Data Types:**")
        for col in df.columns:
            summary.append(f"  - {col}: {df[col].dtype}")
        summary.append(f"\n**First 5 rows:**\n{df.head().to_string()}")
        summary.append(f"\n**Statistics:**\n{df.describe().to_string()}")
        return "\n".join(summary)
    except Exception as e:
        print(f"{RED}✗ Error reading CSV: {e}{RESET}")
        return None


def display_file_content(filepath: str):
    """Read and display a file's content in the terminal with syntax highlighting."""
    content = read_file_content(filepath)
    if content:
        ext = Path(filepath).suffix.lower()
        print(f"\n{'─' * 60}")
        print(content)
        print(f"{'─' * 60}\n")


def _fmt_size(size: int) -> str:
    """Format file size in human-readable form."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} TB"
