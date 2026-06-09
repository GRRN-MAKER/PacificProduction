"""
Pacific CLI — Market data: charts, quotes, live streaming, comparisons.

Uses yfinance for data, mplfinance for candlestick charts, matplotlib for comparisons.
All output saved to ~/.pacific/outputs/ and auto-opened.
"""

import os
import sys
import time
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import load_config

# ANSI colors for terminal display
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"

_running = True
_prev_prices: Dict[str, float] = {}


def _signal_handler(sig, frame):
    global _running
    _running = False


def _get_output_dir() -> Path:
    cfg = load_config()
    out_dir = Path(cfg.get("output_dir", str(Path.home() / ".pacific" / "outputs")))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _open_file(path: str):
    """Open file with system default app (cross-platform)."""
    if sys.platform == "darwin":
        os.system(f'open "{path}" 2>/dev/null')
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        os.system(f'xdg-open "{path}" 2>/dev/null &')


# ─── Quick Quote ─────────────────────────────────────────────────────

def quick_quote(ticker: str):
    """Display a quick stock quote with key metrics."""
    try:
        import yfinance as yf
    except ImportError:
        print(f"{RED}Missing: pip install yfinance{RESET}")
        return

    print(f"{DIM}Fetching {ticker.upper()}...{RESET}")
    t = yf.Ticker(ticker.upper())

    try:
        info = t.info
    except Exception:
        info = {}

    if not info or "symbol" not in info:
        # Fallback to fast_info
        try:
            fi = t.fast_info
            price = fi.get("lastPrice", fi.get("regularMarketPrice", 0))
            prev = fi.get("previousClose", fi.get("regularMarketPreviousClose", 0))
            change = price - prev if prev else 0
            pct = (change / prev * 100) if prev else 0
            color = GREEN if change >= 0 else RED
            arrow = "▲" if change >= 0 else "▼"

            print(f"\n  {BOLD}{ticker.upper()}{RESET}")
            print(f"  Price:   {color}${price:,.2f} {arrow} {change:+,.2f} ({pct:+.2f}%){RESET}")
            return
        except Exception:
            print(f"{RED}No data for {ticker.upper()}{RESET}")
            return

    name = info.get("shortName", ticker.upper())
    price = info.get("regularMarketPrice", info.get("currentPrice", 0))
    prev = info.get("regularMarketPreviousClose", 0)
    change = price - prev if prev else 0
    pct = (change / prev * 100) if prev else 0
    color = GREEN if change >= 0 else RED
    arrow = "▲" if change >= 0 else "▼"

    mkt_cap = info.get("marketCap", 0)
    pe = info.get("trailingPE", 0)
    volume = info.get("regularMarketVolume", info.get("volume", 0))
    high52 = info.get("fiftyTwoWeekHigh", 0)
    low52 = info.get("fiftyTwoWeekLow", 0)
    div_yield = info.get("dividendYield", 0)

    print(f"\n  {BOLD}{name} ({ticker.upper()}){RESET}")
    print(f"  {'─' * 40}")
    print(f"  Price:    {color}${price:,.2f} {arrow} {change:+,.2f} ({pct:+.2f}%){RESET}")
    if mkt_cap:
        cap_str = f"${mkt_cap/1e9:,.2f}B" if mkt_cap > 1e9 else f"${mkt_cap/1e6:,.2f}M"
        print(f"  Mkt Cap:  {cap_str}")
    if pe:
        print(f"  P/E:      {pe:,.2f}")
    if volume:
        print(f"  Volume:   {volume:,.0f}")
    if high52:
        print(f"  52w H/L:  ${high52:,.2f} / ${low52:,.2f}")
    if div_yield:
        print(f"  Div Yld:  {div_yield*100:.2f}%")
    print()


# ─── Stock Chart ─────────────────────────────────────────────────────

def plot_stock_chart(
    ticker: str,
    period: str = "3mo",
    indicators: Optional[List[str]] = None,
    show: bool = True,
) -> str:
    """Generate a candlestick chart with optional indicators."""
    try:
        import yfinance as yf
        import mplfinance as mpf
        import pandas as pd
    except ImportError as e:
        print(f"{RED}Missing: pip install yfinance mplfinance{RESET}")
        return ""

    indicators = indicators or []
    print(f"{DIM}Fetching {ticker.upper()} data ({period})...{RESET}")
    data = yf.download(ticker.upper(), period=period, progress=False)
    if data.empty:
        print(f"{RED}No data for {ticker.upper()}{RESET}")
        return ""

    # Flatten multi-level columns
    if hasattr(data.columns, "levels") and len(data.columns.levels) > 1:
        data.columns = data.columns.get_level_values(0)

    addplots = []
    colors = {"sma20": "blue", "sma50": "orange", "ema20": "purple"}

    for ind in indicators:
        ind = ind.lower()
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
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            data["RSI"] = 100 - (100 / (1 + rs))
            addplots.append(mpf.make_addplot(data["RSI"], panel=2, color="purple", ylabel="RSI"))

    # Show volume unless indicators conflict
    show_volume = "volume" in [i.lower() for i in indicators] or not indicators

    out_dir = _get_output_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = out_dir / f"{ticker.upper()}_chart_{ts}.png"

    kwargs = dict(
        type="candle",
        style="charles",
        title=f"{ticker.upper()} — {period}",
        volume=show_volume,
        savefig=str(filepath),
        figscale=1.3,
        figratio=(16, 9),
    )
    if addplots:
        kwargs["addplot"] = addplots

    mpf.plot(data, **kwargs)
    print(f"{GREEN}✓ Chart saved:{RESET} {filepath}")

    if show:
        _open_file(str(filepath))

    return str(filepath)


# ─── Comparison Chart ────────────────────────────────────────────────

def plot_comparison(
    tickers: List[str],
    period: str = "1y",
    show: bool = True,
) -> str:
    """Generate a normalized comparison chart for multiple tickers."""
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError:
        print(f"{RED}Missing: pip install yfinance matplotlib{RESET}")
        return ""

    print(f"{DIM}Fetching data for {', '.join(tickers)} ({period})...{RESET}")

    fig, ax = plt.subplots(figsize=(14, 7))
    colors_list = ["#2196F3", "#FF5722", "#4CAF50", "#FFC107", "#9C27B0", "#00BCD4", "#FF9800", "#E91E63"]

    for i, ticker in enumerate(tickers):
        try:
            data = yf.download(ticker.upper(), period=period, progress=False)
            if data.empty:
                continue
            close = data["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            # Normalize to percentage change from start
            normalized = (close / close.iloc[0] - 1) * 100
            ax.plot(normalized.index, normalized.values,
                    label=ticker.upper(),
                    color=colors_list[i % len(colors_list)],
                    linewidth=2)
        except Exception as e:
            print(f"{YELLOW}Warning: Could not fetch {ticker}: {e}{RESET}")

    ax.set_title(f"Performance Comparison — {period}", fontsize=14, fontweight="bold")
    ax.set_ylabel("% Change", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

    plt.tight_layout()

    out_dir = _get_output_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = out_dir / f"comparison_{'_'.join(t.upper() for t in tickers)}_{ts}.png"
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"{GREEN}✓ Comparison saved:{RESET} {filepath}")
    if show:
        _open_file(str(filepath))

    return str(filepath)


# ─── Live Price Stream ───────────────────────────────────────────────

def live_price_stream(
    symbols: List[str],
    refresh_secs: int = 3,
):
    """Compact live-scrolling price stream with colored flash indicators."""
    try:
        import yfinance as yf
    except ImportError:
        print(f"{RED}Missing: pip install yfinance{RESET}")
        return

    global _running
    _running = True
    signal.signal(signal.SIGINT, _signal_handler)

    prices: Dict[str, float] = {}

    print(
        f"\n{CYAN}{BOLD}⚡ Pacific Live Stream{RESET} "
        f"{DIM}— {len(symbols)} symbols · {refresh_secs}s · Ctrl+C to stop{RESET}\n"
    )

    while _running:
        ts = time.strftime("%H:%M:%S")
        parts = []
        for sym in symbols:
            try:
                t = yf.Ticker(sym.upper())
                hist = t.history(period="1d", interval="1m")
                if hist.empty:
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = prices.get(sym, price)
                delta = price - prev
                prices[sym] = price

                if delta > 0:
                    flash = f"{GREEN}▲{sym.upper()} ${price:,.2f} (+${delta:,.2f}){RESET}"
                elif delta < 0:
                    flash = f"{RED}▼{sym.upper()} ${price:,.2f} (-${abs(delta):,.2f}){RESET}"
                else:
                    flash = f"{DIM}{sym.upper()} ${price:,.2f} ─{RESET}"
                parts.append(flash)
            except Exception:
                parts.append(f"{RED}{sym.upper()} ERR{RESET}")

        if parts:
            line = f"{DIM}{ts}{RESET}  " + "  │  ".join(parts)
            print(line)

        for _ in range(refresh_secs * 10):
            if not _running:
                break
            time.sleep(0.1)

    print(f"\n{DIM}Stream stopped.{RESET}")


# ─── Market Summary ─────────────────────────────────────────────────

def market_summary():
    """Display a quick market overview of major indices and sectors."""
    try:
        import yfinance as yf
    except ImportError:
        print(f"{RED}Missing: pip install yfinance{RESET}")
        return

    indices = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Dow Jones": "^DJI",
        "Russell 2000": "^RUT",
        "VIX": "^VIX",
        "10Y Treasury": "^TNX",
    }

    print(f"\n{BOLD}📊 Market Overview{RESET}")
    print(f"{'─' * 50}")

    for name, sym in indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if hist.empty or len(hist) < 2:
                print(f"  {name:<16} {DIM}No data{RESET}")
                continue
            price = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            change = price - prev
            pct = (change / prev * 100) if prev else 0
            color = GREEN if change >= 0 else RED
            arrow = "▲" if change >= 0 else "▼"

            if sym == "^VIX":
                print(f"  {name:<16} {color}{price:,.2f} {arrow} {change:+.2f}{RESET}")
            elif sym == "^TNX":
                print(f"  {name:<16} {color}{price:.3f}% {arrow} {change:+.3f}{RESET}")
            else:
                print(f"  {name:<16} {color}{price:,.2f} {arrow} {change:+,.2f} ({pct:+.2f}%){RESET}")
        except Exception:
            print(f"  {name:<16} {DIM}Error{RESET}")

    print(f"{'─' * 50}")
    print(f"  {DIM}Data: Yahoo Finance · {time.strftime('%H:%M:%S')}{RESET}\n")
