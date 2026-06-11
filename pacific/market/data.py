"""PACIFIC — Market data fetching and formatting utilities."""

from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def market_overview():
    """Print a broad market overview: major indices + sectors."""
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing: pip install yfinance[/red]")
        return

    indices = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
        "^RUT": "Russell 2000",
        "^VIX": "VIX",
        "^TNX": "10Y Treasury",
        "GC=F": "Gold",
        "CL=F": "Crude Oil (WTI)",
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "EURUSD=X": "EUR/USD",
        "DX-Y.NYB": "DXY (Dollar)",
    }

    table = Table(
        title="[bold cyan]PACIFIC — Market Overview[/bold cyan]",
        show_header=True,
        header_style="bold white on blue",
    )
    table.add_column("Index", style="cyan", width=16)
    table.add_column("Price", justify="right", width=12)
    table.add_column("Change", justify="right", width=10)
    table.add_column("% Chg", justify="right", width=8)

    for sym, name in indices.items():
        try:
            hist = yf.download(sym, period="2d", progress=False)
            if hist.empty or len(hist) < 2:
                table.add_row(name, "N/A", "—", "—")
                continue

            close_col = hist["Close"]
            if hasattr(close_col, 'columns'):
                close_col = close_col.iloc[:, 0]

            price = float(close_col.iloc[-1])
            prev = float(close_col.iloc[-2])
            change = price - prev
            pct = (change / prev * 100) if prev else 0

            color = "green" if change >= 0 else "red"
            arrow = "▲" if change >= 0 else "▼"

            table.add_row(
                name,
                f"${price:,.2f}" if price > 10 else f"${price:,.4f}",
                f"[{color}]{arrow} {abs(change):,.2f}[/{color}]",
                f"[{color}]{pct:+.2f}%[/{color}]",
            )
        except Exception:
            table.add_row(name, "[red]ERR[/red]", "—", "—")

    console.print(table)


def stock_info(symbol: str):
    """Print detailed info for a single stock."""
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing: pip install yfinance[/red]")
        return

    t = yf.Ticker(symbol)
    info = t.info

    rows = [
        ("Name", info.get("longName", "—")),
        ("Sector", info.get("sector", "—")),
        ("Industry", info.get("industry", "—")),
        ("Market Cap", _fmt(info.get("marketCap"))),
        ("Enterprise Value", _fmt(info.get("enterpriseValue"))),
        ("P/E (TTM)", f"{info.get('trailingPE', '—'):.2f}" if info.get('trailingPE') else "—"),
        ("Forward P/E", f"{info.get('forwardPE', '—'):.2f}" if info.get('forwardPE') else "—"),
        ("EPS (TTM)", f"${info.get('trailingEps', 0):.2f}"),
        ("Revenue (TTM)", _fmt(info.get("totalRevenue"))),
        ("Profit Margin", f"{info.get('profitMargins', 0) * 100:.1f}%" if info.get('profitMargins') else "—"),
        ("Dividend Yield", f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "—"),
        ("52W High", f"${info.get('fiftyTwoWeekHigh', 0):,.2f}"),
        ("52W Low", f"${info.get('fiftyTwoWeekLow', 0):,.2f}"),
        ("Beta", f"{info.get('beta', 0):.2f}" if info.get('beta') else "—"),
        ("Avg Volume", _fmt(info.get("averageVolume"))),
    ]

    table = Table(
        title=f"[bold cyan]{symbol} — Stock Profile[/bold cyan]",
        show_header=False,
        border_style="dim",
    )
    table.add_column("Field", style="dim", width=18)
    table.add_column("Value", style="bold")

    for field, value in rows:
        table.add_row(field, str(value))

    console.print(table)

    # Description
    desc = info.get("longBusinessSummary", "")
    if desc:
        console.print(Panel(
            desc[:500] + ("…" if len(desc) > 500 else ""),
            title="[dim]Business Summary[/dim]",
            border_style="dim",
        ))


def _fmt(n) -> str:
    """Format number with B/M/K suffixes."""
    if not n:
        return "—"
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.1f}K"
    return f"{n:,.0f}"
