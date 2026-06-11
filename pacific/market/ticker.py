"""PACIFIC — Live stock ticker with real-time terminal display."""

import time
import signal
import sys
from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pacific.config import load_config

console = Console()

_running = True

# Store previous prices to show fluctuation direction
_prev_prices: Dict[str, float] = {}


def _signal_handler(sig, frame):
    global _running
    _running = False


def live_ticker(
    symbols: List[str],
    refresh_secs: Optional[int] = None,
):
    """Display a live-updating stock ticker in the terminal.

    Args:
        symbols: List of ticker symbols to track.
        refresh_secs: Seconds between refreshes (default from config).
    """
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing dependency: pip install yfinance[/red]")
        return

    global _running, _prev_prices
    _running = True
    _prev_prices = {}
    signal.signal(signal.SIGINT, _signal_handler)

    cfg = load_config()
    interval = refresh_secs or cfg.get("ticker_refresh_secs", 5)

    console.print(
        f"[bold cyan]📈 PACIFIC Live Ticker[/bold cyan] "
        f"[dim]— {len(symbols)} symbols · refresh every {interval}s · Ctrl+C to stop[/dim]\n"
    )

    with Live(console=console, refresh_per_second=1) as live:
        while _running:
            table = _build_ticker_table(symbols, yf)
            live.update(table)
            for _ in range(interval * 10):
                if not _running:
                    break
                time.sleep(0.1)

    console.print("\n[dim]Ticker stopped.[/dim]")


def live_price_stream(
    symbols: List[str],
    refresh_secs: int = 2,
):
    """Compact live-scrolling price stream showing real-time fluctuations.

    Unlike the table ticker, this prints one line per update per symbol,
    showing the price change since last check with colored flash indicators.
    """
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing dependency: pip install yfinance[/red]")
        return

    global _running
    _running = True
    signal.signal(signal.SIGINT, _signal_handler)

    prices: Dict[str, float] = {}
    tick_count = 0

    console.print(
        f"[bold cyan]⚡ PACIFIC Live Stream[/bold cyan] "
        f"[dim]— {len(symbols)} symbols · {refresh_secs}s · Ctrl+C to stop[/dim]\n"
    )

    while _running:
        ts = time.strftime("%H:%M:%S")
        parts = []
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period="1d", interval="1m")
                if hist.empty:
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = prices.get(sym, price)
                delta = price - prev
                prices[sym] = price

                if delta > 0:
                    flash = f"[bold green]▲{sym} ${price:,.2f} (+${delta:,.2f})[/bold green]"
                elif delta < 0:
                    flash = f"[bold red]▼{sym} ${price:,.2f} (-${abs(delta):,.2f})[/bold red]"
                else:
                    flash = f"[dim]{sym} ${price:,.2f} ─[/dim]"
                parts.append(flash)
            except Exception:
                parts.append(f"[red]{sym} ERR[/red]")

        if parts:
            line = f"[dim]{ts}[/dim]  " + "  │  ".join(parts)
            console.print(line)

        tick_count += 1
        for _ in range(refresh_secs * 10):
            if not _running:
                break
            time.sleep(0.1)

    console.print("\n[dim]Stream stopped.[/dim]")


def _build_ticker_table(symbols: list, yf) -> Panel:
    """Fetch quotes and build a polished live-updating display with sparklines."""
    from rich.console import Group as RenderGroup

    ts = time.strftime("%H:%M:%S")
    cards: list = []

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info if hasattr(t, 'fast_info') else {}
            hist = t.history(period="5d")

            if hist.empty:
                cards.append(Text(f"  ⚪  {sym}   No data available", style="dim"))
                continue

            price = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else price
            change = price - prev_close
            pct = (change / prev_close * 100) if prev_close else 0
            volume = hist["Volume"].iloc[-1] if "Volume" in hist else 0

            # Color + arrow + status indicator
            if change > 0:
                color = "green"
                arrow = "▲"
                dot = "🟢"
            elif change < 0:
                color = "red"
                arrow = "▼"
                dot = "🔴"
            else:
                color = "dim"
                arrow = "─"
                dot = "⚪"

            # Live flash — price moved since last refresh
            prev_tracked = _prev_prices.get(sym)
            _prev_prices[sym] = float(price)
            if prev_tracked is not None:
                live_delta = float(price) - prev_tracked
                if live_delta > 0.005:
                    dot = "⚡"
                elif live_delta < -0.005:
                    dot = "💥"

            # 5-day sparkline
            closes = hist["Close"].values[-5:]
            mn, mx = float(min(closes)), float(max(closes))
            spark_chars = "▁▂▃▄▅▆▇█"
            if mx > mn:
                spark = "".join(spark_chars[int((float(v) - mn) / (mx - mn) * 7)] for v in closes)
            else:
                spark = "▅" * len(closes)

            # Market cap
            mkt_cap = getattr(info, 'market_cap', None) or 0
            mkt_cap_str = _format_large_num(mkt_cap) if mkt_cap else "—"

            # 52-week
            yr_high = getattr(info, 'year_high', None) or 0
            yr_low = getattr(info, 'year_low', None) or 0

            # ── Line 1: Symbol · Price · Change ──
            line1 = Text()
            line1.append(f"  {dot}  ", style="bold")
            line1.append(f"{sym}", style="bold cyan")
            line1.append(f"   ${price:,.2f}", style="bold white")
            line1.append(f"   {arrow} ${abs(change):,.2f} ({pct:+.2f}%)", style=f"bold {color}")

            # ── Line 2: Sparkline · 5d range ──
            line2 = Text()
            line2.append(f"       5d: ", style="dim")
            line2.append(f"{spark}", style=f"bold {color}")
            line2.append(f"  L: ${mn:,.2f} — H: ${mx:,.2f}", style="dim")

            # ── Line 3: Vol · MCap · 52w ──
            meta_parts = []
            if volume:
                meta_parts.append(f"Vol {_format_large_num(volume)}")
            if mkt_cap_str != "—":
                meta_parts.append(f"MCap {mkt_cap_str}")
            if yr_high:
                meta_parts.append(f"52w ${yr_low:,.0f}–${yr_high:,.0f}")
            line3 = Text(f"       {' · '.join(meta_parts)}", style="dim")

            cards.append(line1)
            cards.append(line2)
            cards.append(line3)
            cards.append(Text(""))  # spacer

        except Exception:
            cards.append(Text(f"  ❌  {sym}   Error fetching data", style="red"))
            cards.append(Text(""))

    group = RenderGroup(*cards)
    return Panel(
        group,
        title="[bold cyan]📈  PACIFIC Live Ticker[/bold cyan]",
        subtitle=f"[dim]⏱ {ts}  ·  Yahoo Finance  ·  Ctrl+C to stop[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )


def _format_large_num(n) -> str:
    """Format large numbers: 1.23B, 456.7M, 12.3K."""
    try:
        n = float(n)
    except (TypeError, ValueError):
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


def quick_quote(symbol: str):
    """Print a single stock quote summary with sparkline, volume, and 52w range."""
    try:
        import yfinance as yf
    except ImportError:
        console.print("[red]Missing: pip install yfinance[/red]")
        return

    t = yf.Ticker(symbol)
    info = t.fast_info if hasattr(t, 'fast_info') else {}
    hist = t.history(period="5d")
    if hist.empty:
        console.print(f"[red]No data for {symbol}[/red]")
        return

    price = hist["Close"].iloc[-1]
    prev = hist["Close"].iloc[-2] if len(hist) > 1 else price
    change = price - prev
    pct = (change / prev * 100) if prev else 0
    volume = hist["Volume"].iloc[-1] if "Volume" in hist else 0

    color = "green" if change >= 0 else "red"
    arrow = "▲" if change >= 0 else "▼"

    # Market cap
    mkt_cap = getattr(info, 'market_cap', None) or 0
    mkt_cap_str = _format_large_num(mkt_cap) if mkt_cap else ""

    # 52-week
    yr_high = getattr(info, 'year_high', None) or 0
    yr_low = getattr(info, 'year_low', None) or 0

    # Main price line
    console.print(f"\n  [bold cyan]{symbol}[/bold cyan]  "
                  f"[bold]${price:,.2f}[/bold]  "
                  f"[bold {color}]{arrow} ${abs(change):,.2f} ({pct:+.2f}%)[/bold {color}]")

    # 5-day sparkline + range
    closes = hist["Close"].values[-5:]
    mn, mx = float(min(closes)), float(max(closes))
    spark_chars = "▁▂▃▄▅▆▇█"
    if mx > mn:
        spark = "".join(spark_chars[int((float(v) - mn) / (mx - mn) * 7)] for v in closes)
    else:
        spark = "▅" * len(closes)
    console.print(f"  [dim]5d:[/dim] [{color}]{spark}[/{color}]  "
                  f"[dim]L: ${mn:,.2f} — H: ${mx:,.2f}[/dim]")

    # Volume + Market Cap + 52w
    extras = []
    if volume:
        extras.append(f"Vol: {_format_large_num(volume)}")
    if mkt_cap_str:
        extras.append(f"MCap: {mkt_cap_str}")
    if yr_high:
        extras.append(f"52w: ${yr_low:,.0f} – ${yr_high:,.0f}")
    if extras:
        console.print(f"  [dim]{' · '.join(extras)}[/dim]")
    console.print()
