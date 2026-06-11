"""PACIFIC — Chart generation: matplotlib + plotly for financial charts."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from pacific.config import load_config

console = Console()


def plot_stock_chart(
    ticker: str,
    period: str = "3mo",
    chart_type: str = "candle",
    indicators: Optional[list] = None,
    output_path: Optional[str] = None,
    show: bool = True,
) -> str:
    """Generate a stock chart with optional indicators.

    Args:
        ticker: Stock symbol (e.g. 'AAPL')
        period: Data period — 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
        chart_type: 'candle', 'line', 'ohlc'
        indicators: List of indicators — 'sma20', 'sma50', 'ema20', 'bb', 'rsi', 'macd', 'volume'
        output_path: Where to save the image. If None, auto-generates.
        show: Whether to open the chart after saving.

    Returns:
        Path to the saved chart image.
    """
    try:
        import yfinance as yf
        import mplfinance as mpf
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}. Install with: pip install yfinance mplfinance[/red]")
        return ""

    indicators = indicators or []
    cfg = load_config()

    # Fetch data
    console.print(f"[dim]Fetching {ticker} data ({period})…[/dim]")
    data = yf.download(ticker, period=period, progress=False)
    if data.empty:
        console.print(f"[red]No data found for {ticker}[/red]")
        return ""

    # Flatten multi-level columns if present
    if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
        data.columns = data.columns.get_level_values(0)

    # Build addplots
    addplots = []
    colors = {"sma20": "blue", "sma50": "orange", "ema20": "purple"}

    for ind in indicators:
        if ind == "sma20":
            data["SMA20"] = data["Close"].rolling(20).mean()
            addplots.append(mpf.make_addplot(data["SMA20"], color=colors["sma20"]))
        elif ind == "sma50":
            data["SMA50"] = data["Close"].rolling(50).mean()
            addplots.append(mpf.make_addplot(data["SMA50"], color=colors["sma50"]))
        elif ind == "ema20":
            data["EMA20"] = data["Close"].ewm(span=20).mean()
            addplots.append(mpf.make_addplot(data["EMA20"], color=colors["ema20"]))
        elif ind == "bb":
            sma = data["Close"].rolling(20).mean()
            std = data["Close"].rolling(20).std()
            data["BB_Upper"] = sma + 2 * std
            data["BB_Lower"] = sma - 2 * std
            addplots.append(mpf.make_addplot(data["BB_Upper"], color="gray", linestyle="dashed"))
            addplots.append(mpf.make_addplot(data["BB_Lower"], color="gray", linestyle="dashed"))
        elif ind == "rsi":
            delta = data["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            data["RSI"] = 100 - (100 / (1 + rs))
            addplots.append(mpf.make_addplot(data["RSI"], panel=2, color="magenta", ylabel="RSI"))

    # Output path
    if not output_path:
        out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"{ticker}_{chart_type}_{ts}.png")

    # Plot
    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        rc={"font.size": 9},
    )

    chart_kwargs = {
        "type": chart_type,
        "style": style,
        "title": f"{ticker} — {period.upper()}",
        "ylabel": "Price ($)",
        "volume": "volume" in indicators,
        "figsize": (14, 8),
        "savefig": output_path,
    }
    if addplots:
        chart_kwargs["addplot"] = addplots

    mpf.plot(data, **chart_kwargs)
    console.print(f"[green]✓ Chart saved:[/green] {output_path}")

    if show:
        try:
            os.system(f"open '{output_path}' 2>/dev/null || xdg-open '{output_path}' 2>/dev/null &")
        except Exception:
            pass

    return output_path


def plot_comparison(
    tickers: list,
    period: str = "1y",
    normalize: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """Plot multiple tickers on the same chart for comparison."""
    try:
        import yfinance as yf
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        return ""

    cfg = load_config()
    fig, ax = plt.subplots(figsize=(14, 7))

    for ticker in tickers:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            continue
        close = data["Close"].squeeze()
        if normalize:
            close = (close / close.iloc[0]) * 100
        ax.plot(close.index, close.values, label=ticker, linewidth=1.5)

    ax.set_title(f"{'Normalized ' if normalize else ''}Price Comparison — {period.upper()}")
    ax.set_ylabel("Indexed (100)" if normalize else "Price ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if not output_path:
        out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"comparison_{ts}.png")

    plt.savefig(output_path, dpi=150)
    plt.close()
    console.print(f"[green]✓ Comparison chart saved:[/green] {output_path}")
    return output_path
