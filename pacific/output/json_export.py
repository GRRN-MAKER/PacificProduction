"""PACIFIC — JSON file export generation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console

from pacific.config import load_config

console = Console()


def export_to_json(
    data: Any,
    filename: Optional[str] = None,
    title: Optional[str] = None,
    indent: int = 2,
) -> str:
    """Export data to a formatted JSON file with PACIFIC metadata.

    Args:
        data: Any JSON-serialisable object — dict, list, str,
              pandas DataFrame, or raw AI response text.
        filename: Output filename. Auto-generated if None.
        title: Optional title / description for the metadata header.
        indent: JSON indentation (default 2).

    Returns:
        Path to saved JSON file.
    """
    cfg = load_config()
    out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not filename:
        safe = (title or "export").lower().replace(" ", "_")[:30]
        filename = f"pacific_{safe}_{ts}.json"
    if not filename.endswith(".json"):
        filename += ".json"

    filepath = out_dir / filename

    # ── Normalise various input types ──
    try:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            data = json.loads(data.to_json(orient="records", date_format="iso"))
    except ImportError:
        pass

    # Wrap raw text into a structured object
    if isinstance(data, str):
        data = {"response": data}

    envelope = {
        "meta": {
            "generator": "PACIFIC — Elite Financial Intelligence CLI",
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "title": title or "PACIFIC Export",
        },
        "data": data,
    }

    filepath.write_text(json.dumps(envelope, indent=indent, default=str), encoding="utf-8")
    console.print(f"[green]✓ JSON saved:[/green] {filepath}")
    return str(filepath)


def analysis_to_json(
    label: str,
    analysis_text: str,
    filename: Optional[str] = None,
) -> str:
    """Save a Pacific analysis / chat response as a JSON file."""
    return export_to_json(
        data={"analysis": analysis_text},
        title=f"{label} — Financial Analysis",
        filename=filename,
    )


def stock_data_to_json(
    ticker: str,
    period: str = "3mo",
    filename: Optional[str] = None,
) -> str:
    """Download stock data via yfinance and export to JSON."""
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing dependency: pip install yfinance[/red]")
        return ""

    console.print(f"[dim]Fetching {ticker} data ({period})…[/dim]")
    df = yf.download(ticker, period=period, progress=False)
    if df.empty:
        console.print(f"[red]No data for {ticker}[/red]")
        return ""

    if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ticker}_data_{ts}.json"

    return export_to_json(df, filename=filename, title=f"{ticker} Stock Data")
