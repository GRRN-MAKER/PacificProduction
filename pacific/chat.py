"""PACIFIC — Interactive multi-turn chat REPL for finance."""

import re
import time
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from pacific.engine import stream_response, analyze_image
from pacific.output.terminal import print_banner, print_separator
from pacific.output.canvas import auto_execute_response
from pacific.output.pdf import analysis_to_pdf
from pacific.output.json_export import analysis_to_json, stock_data_to_json
from pacific.output.excel import stock_data_to_excel
from pacific.output.charts import plot_stock_chart
from pacific.output.html_charts import interactive_chart, interactive_comparison, html_report
from pacific.market.ticker import quick_quote, live_price_stream
from pacific.utils.files import open_file, read_file_content, display_file_content, resolve_path

console = Console()

# ── Patterns for auto-detecting market/ticker queries ────────────────
_MARKET_KEYWORDS = re.compile(
    r"\b(market|ticker|stock|stocks|quote|price|prices|trading|indices|index"
    r"|s&p|s&p500|sp500|nasdaq|dow|djia|russell|vix|treasury|yield|bond"
    r"|crypto|bitcoin|btc|ethereum|eth|gold|oil|crude|commodity|commodities"
    r"|forex|fx|eur|usd|dxy|sector|sectors|today.?s market|market today"
    r"|how.?s the market|market overview|market update|what.?s trading"
    r"|pre.?market|after.?hours|gainers|losers|movers)\b",
    re.IGNORECASE,
)

# Explicit $TICKER pattern — the ONLY way to specify individual tickers
# Users type $AAPL, $NVDA, $TSLA — this is unambiguous
_DOLLAR_TICKER = re.compile(r"\$([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b")


def _quiet_yf_download(sym, **kwargs):
    """Download yfinance data with ALL output suppressed."""
    import io, os, sys, logging
    import yfinance as yf

    # Silence every noise channel yfinance uses
    _loggers = [logging.getLogger(n) for n in logging.root.manager.loggerDict if "yfinance" in n.lower()]
    _old_levels = [(lg, lg.level) for lg in _loggers]
    for lg in _loggers:
        lg.setLevel(logging.CRITICAL + 1)

    _old_stderr = sys.stderr
    _old_stdout_fd = os.dup(1)
    _old_stderr_fd = os.dup(2)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    sys.stderr = io.StringIO()
    os.dup2(_devnull, 1)
    os.dup2(_devnull, 2)
    try:
        result = yf.download(sym, progress=False, **kwargs)
    finally:
        os.dup2(_old_stdout_fd, 1)
        os.dup2(_old_stderr_fd, 2)
        os.close(_devnull)
        os.close(_old_stdout_fd)
        os.close(_old_stderr_fd)
        sys.stderr = _old_stderr
        for lg, lvl in _old_levels:
            lg.setLevel(lvl)
    return result


def _quiet_yf_ticker_info(sym):
    """Get yfinance Ticker.info with ALL output suppressed. Returns {} on failure."""
    import io, os, sys, logging
    import yfinance as yf

    _loggers = [logging.getLogger(n) for n in logging.root.manager.loggerDict if "yfinance" in n.lower()]
    _old_levels = [(lg, lg.level) for lg in _loggers]
    for lg in _loggers:
        lg.setLevel(logging.CRITICAL + 1)

    _old_stderr = sys.stderr
    _old_stdout_fd = os.dup(1)
    _old_stderr_fd = os.dup(2)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    sys.stderr = io.StringIO()
    os.dup2(_devnull, 1)
    os.dup2(_devnull, 2)
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
    except Exception:
        info = {}
    finally:
        os.dup2(_old_stdout_fd, 1)
        os.dup2(_old_stderr_fd, 2)
        os.close(_devnull)
        os.close(_old_stdout_fd)
        os.close(_old_stderr_fd)
        sys.stderr = _old_stderr
        for lg, lvl in _old_levels:
            lg.setLevel(lvl)
    return info


def _fetch_market_context(user_input: str) -> str:
    """Auto-detect market queries and $TICKER mentions, fetch real data.

    Returns a context string to inject into the prompt, or empty string.

    Simple rules (no false positives):
    - Market keywords detected → fetch major indices overview
    - $AAPL / $NVDA syntax   → fetch those specific tickers
    - Plain English words     → NEVER treated as tickers
    """
    is_market_query = bool(_MARKET_KEYWORDS.search(user_input))

    # Only explicit $TICKER mentions — never guess from words
    dollar_tickers = _DOLLAR_TICKER.findall(user_input)

    if not is_market_query and not dollar_tickers:
        return ""

    try:
        import yfinance as yf
    except ImportError:
        return ""

    context_parts = []
    now_str = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    context_parts.append(f"[LIVE MARKET DATA — fetched {now_str}]")

    # Broad market query → fetch major indices
    if is_market_query and not dollar_tickers:
        indices = {
            "^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ",
            "^RUT": "Russell 2000", "^VIX": "VIX", "^TNX": "10Y Treasury Yield",
            "GC=F": "Gold", "CL=F": "Crude Oil (WTI)",
            "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
        }
        console.print("[dim]📡 Fetching live market data...[/dim]")
        for sym, name in indices.items():
            try:
                hist = _quiet_yf_download(sym, period="2d")
                if hist.empty or len(hist) < 2:
                    continue
                close_col = hist["Close"]
                if hasattr(close_col, "columns"):
                    close_col = close_col.iloc[:, 0]
                price = float(close_col.iloc[-1])
                prev = float(close_col.iloc[-2])
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                arrow = "▲" if change >= 0 else "▼"
                context_parts.append(
                    f"  {name}: ${price:,.2f}  {arrow} {change:+,.2f} ({pct:+.2f}%)"
                )
            except Exception:
                pass

    # Fetch explicit $TICKER mentions
    if dollar_tickers:
        valid_tickers = []
        for sym in dict.fromkeys(dollar_tickers):  # deduplicate, preserve order
            try:
                info = _quiet_yf_ticker_info(sym)
                if not info.get("longName") and not info.get("shortName"):
                    continue  # silently skip invalid symbols

                hist = _quiet_yf_download(sym, period="5d")
                if hist.empty:
                    continue
                close_col = hist["Close"]
                if hasattr(close_col, "columns"):
                    close_col = close_col.iloc[:, 0]
                price = float(close_col.iloc[-1])
                prev = float(close_col.iloc[-2]) if len(close_col) > 1 else price
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                name = info.get("longName") or info.get("shortName") or sym
                mkt_cap = info.get("marketCap", 0)
                pe = info.get("trailingPE", None)
                high52 = info.get("fiftyTwoWeekHigh", None)
                low52 = info.get("fiftyTwoWeekLow", None)
                vol = info.get("volume", None)

                arrow = "▲" if change >= 0 else "▼"
                line = f"  {sym} ({name}): ${price:,.2f}  {arrow} {change:+,.2f} ({pct:+.2f}%)"
                if mkt_cap:
                    line += f"  | MCap: ${mkt_cap/1e9:,.1f}B" if mkt_cap > 1e9 else f"  | MCap: ${mkt_cap/1e6:,.0f}M"
                if pe:
                    line += f"  | P/E: {pe:.1f}"
                if high52 and low52:
                    line += f"  | 52W: ${low52:,.2f}–${high52:,.2f}"
                if vol:
                    line += f"  | Vol: {vol:,.0f}"
                context_parts.append(line)
                valid_tickers.append(sym)
            except Exception:
                pass
        if valid_tickers:
            console.print(f"[dim]📡 Fetched data for {', '.join(valid_tickers)}[/dim]")

    if len(context_parts) <= 1:
        return ""  # Only header, no data

    context_parts.append("[END LIVE DATA]")
    return "\n".join(context_parts)


def chat_session(enable_thinking: bool = False):
    """Interactive multi-turn chat REPL."""
    # Auth gate — require API key for AI chat
    from pacific.auth import require_auth
    require_auth()

    print_banner()
    console.print(
        Panel(
            "[bold cyan]PACIFIC Chat — Finance AI[/bold cyan]\n"
            "[dim]Type [bold]exit[/bold] or [bold]quit[/bold] to end · "
            "[bold]/clear[/bold] to reset history · "
            "[bold]/help[/bold] for commands[/dim]",
            border_style="cyan",
        )
    )

    history: List[dict] = []
    session_num = 0
    last_response = ""

    while True:
        try:
            console.print(
                f"\n[bold cyan]Pacific[/bold cyan] "
                f"[bold white]>[/bold white] ",
                end="",
            )
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n\n[dim]Session ended.[/dim]")
            break

        if not user_input:
            continue

        # ── Slash commands ──
        if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            console.print("\n[dim]Session ended. Markets never sleep. 📈[/dim]")
            break

        if user_input == "/clear":
            history.clear()
            session_num = 0
            last_response = ""
            console.clear()
            print_banner()
            console.print("[dim]History cleared.[/dim]")
            continue

        if user_input == "/help":
            _print_help()
            continue

        if user_input == "/history":
            console.print(f"[dim]{len(history)} messages in current session.[/dim]")
            continue

        if user_input == "/run":
            if last_response:
                auto_execute_response(last_response)
            else:
                console.print("[dim]No response to execute.[/dim]")
            continue

        if user_input.startswith("/export pdf"):
            if last_response:
                analysis_to_pdf("analysis", last_response)
            else:
                console.print("[dim]No response to export.[/dim]")
            continue

        if user_input.startswith("/export excel "):
            ticker = user_input.split()[-1].upper()
            stock_data_to_excel(ticker)
            continue

        if user_input.startswith("/export json"):
            parts = user_input.split()
            if len(parts) >= 3:
                # /export json AAPL → stock data export
                ticker = parts[2].upper()
                period = parts[3] if len(parts) > 3 else "3mo"
                stock_data_to_json(ticker, period=period)
            elif last_response:
                # /export json → export last AI response
                analysis_to_json("analysis", last_response)
            else:
                console.print("[dim]No response to export. Use /export json TICKER for stock data.[/dim]")
            continue

        if user_input.startswith("/chart "):
            parts = user_input.split()
            ticker = parts[1].upper() if len(parts) > 1 else "SPY"
            period = parts[2] if len(parts) > 2 else "3mo"
            indicators = parts[3:] if len(parts) > 3 else ["volume", "sma20"]
            plot_stock_chart(ticker, period=period, indicators=indicators)
            continue

        if user_input.startswith("/compare "):
            from pacific.output.charts import plot_comparison
            parts = user_input.split()
            # /compare AAPL NVDA TSLA 1y
            tickers_list = []
            period = "1y"
            for p in parts[1:]:
                if p.lower() in ("1d","5d","1mo","3mo","6mo","1y","2y","5y","ytd","max"):
                    period = p.lower()
                else:
                    tickers_list.append(p.upper())
            if tickers_list:
                chart_path = plot_comparison(tickers_list, period=period)
                if chart_path:
                    import os
                    os.system(f"open '{chart_path}' 2>/dev/null || xdg-open '{chart_path}' 2>/dev/null &")
            else:
                console.print("[dim]Usage: /compare AAPL NVDA TSLA [1y][/dim]")
            continue

        if user_input.startswith("/quote "):
            ticker = user_input.split()[1].upper()
            quick_quote(ticker)
            continue

        # ── Live price stream ──
        if user_input.startswith("/stream "):
            parts = user_input.split()
            syms = [p.upper() for p in parts[1:] if not p.startswith("-")]
            refresh = 3
            for i, p in enumerate(parts):
                if p == "-r" and i + 1 < len(parts):
                    try:
                        refresh = int(parts[i + 1])
                    except ValueError:
                        pass
            if syms:
                live_price_stream(syms, refresh_secs=refresh)
            else:
                console.print("[dim]Usage: /stream AAPL NVDA TSLA [-r 2][/dim]")
            continue

        # ── Interactive HTML charts ──
        if user_input.startswith("/html chart "):
            parts = user_input.split()
            ticker = parts[2].upper() if len(parts) > 2 else "SPY"
            period = "3mo"
            indicators = []
            for p in parts[3:]:
                if p.lower() in ("1d","5d","1mo","3mo","6mo","1y","2y","5y","ytd","max"):
                    period = p.lower()
                else:
                    indicators.append(p.lower())
            interactive_chart(ticker, period=period, indicators=indicators or ["volume", "sma20"])
            continue

        if user_input.startswith("/html compare "):
            parts = user_input.split()
            tickers_list = []
            period = "1y"
            for p in parts[2:]:
                if p.lower() in ("1d","5d","1mo","3mo","6mo","1y","2y","5y","ytd","max"):
                    period = p.lower()
                else:
                    tickers_list.append(p.upper())
            if tickers_list:
                interactive_comparison(tickers_list, period=period)
            else:
                console.print("[dim]Usage: /html compare AAPL NVDA TSLA [1y][/dim]")
            continue

        if user_input.startswith("/html report"):
            if last_response:
                html_report("PACIFIC Analysis", last_response)
            else:
                console.print("[dim]No response to export as HTML.[/dim]")
            continue

        # ── File operations ──
        if user_input.startswith("/open "):
            filepath = user_input[6:].strip().strip('"').strip("'")
            resolved = resolve_path(filepath)
            if resolved:
                open_file(resolved)
            else:
                console.print(f"[red]✗ File not found:[/red] {filepath}")
            continue

        if user_input.startswith("/read "):
            filepath = user_input[6:].strip().strip('"').strip("'")
            resolved = resolve_path(filepath)
            if resolved:
                display_file_content(resolved)
            else:
                console.print(f"[red]✗ File not found:[/red] {filepath}")
            continue

        if user_input.startswith("/file "):
            # Read a file and send its content to Pacific for analysis
            filepath = user_input[6:].strip().strip('"').strip("'")
            resolved = resolve_path(filepath)
            if resolved:
                content = read_file_content(resolved, max_lines=500)
                if content:
                    fname = Path(resolved).name
                    user_input = (
                        f"I'm sharing a file with you: **{fname}**\n\n"
                        f"```\n{content}\n```\n\n"
                        f"Please analyze this file and provide insights."
                    )
                    # Fall through to the stream_response below
                else:
                    console.print("[dim]Could not read file content.[/dim]")
                    continue
            else:
                console.print(f"[red]✗ File not found:[/red] {filepath}")
                continue

        if user_input.startswith("/think"):
            if user_input == "/think on":
                enable_thinking = True
                console.print("[green]Thinking mode: ON[/green]")
            elif user_input == "/think off":
                enable_thinking = False
                console.print("[dim]Thinking mode: OFF[/dim]")
            else:
                console.print(f"[dim]Thinking: {'ON' if enable_thinking else 'OFF'}[/dim]")
            continue

        # ── Auto-detect file paths in natural messages ──
        # If the user mentions a file path (~/..., /Users/..., etc.) try to read it
        _file_match = re.search(
            r'(?:^|\s)(/[\w/. -]+\.\w{1,5}|~/[\w/. -]+\.\w{1,5})',
            user_input,
        )
        if _file_match and not user_input.startswith("/"):
            _detected_path = _file_match.group(1).strip()
            _resolved = resolve_path(_detected_path)
            if _resolved:
                _content = read_file_content(_resolved, max_lines=500)
                if _content:
                    _fname = Path(_resolved).name
                    console.print(f"[dim]📄 Auto-read local file: {_fname}[/dim]")
                    user_input = (
                        f"{user_input}\n\n"
                        f"--- LOCAL FILE CONTENT: {_fname} ---\n"
                        f"```\n{_content}\n```"
                    )

        # ── Image analysis ──
        image_path = None
        if user_input.startswith("/image "):
            parts = user_input.split(" ", 1)
            if len(parts) == 2:
                image_path = parts[1].strip()
                user_input = (
                    "Analyze this financial chart. Identify patterns, trends, "
                    "key levels, and provide a trading outlook."
                )
                if not Path(image_path).exists():
                    console.print(f"[red]Image not found: {image_path}[/red]")
                    continue

        # ── Auto-inject live market data for finance queries ──
        market_ctx = _fetch_market_context(user_input)
        enriched_input = user_input
        if market_ctx:
            enriched_input = (
                f"{user_input}\n\n"
                f"--- REAL-TIME DATA (from PACIFIC terminal's Yahoo Finance feed) ---\n"
                f"{market_ctx}\n"
                f"---\n"
                f"Use this live data in your analysis. Do NOT say you cannot access "
                f"real-time data — you just received it above."
            )

        # ── Stream the response ──
        response = stream_response(
            enriched_input,
            history=history,
            image_path=image_path,
            enable_thinking=enable_thinking,
        )

        # Update history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})
        last_response = response
        session_num += 1

        # ── Auto-detect executable code blocks ──
        from pacific.output.canvas import extract_code_blocks
        code_blocks = extract_code_blocks(response)
        python_blocks = [b for b in code_blocks if b["lang"] == "python"]
        if python_blocks:
            console.print(f"\n[bold cyan]📦 {len(python_blocks)} code block(s) detected.[/bold cyan] "
                          "[dim]Type [bold]/run[/bold] to execute, or continue chatting.[/dim]")

        print_separator()


def _print_help():
    """Print the help panel."""
    console.print(
        Panel(
            "[bold]Chat Commands:[/bold]\n"
            "  [cyan]/clear[/cyan]           Reset conversation history\n"
            "  [cyan]/history[/cyan]         Show message count\n"
            "  [cyan]/think on|off[/cyan]    Toggle thinking mode\n"
            "  [cyan]/image PATH[/cyan]      Analyze a chart image\n"
            "  [cyan]exit[/cyan]             End session\n\n"
            "[bold]Output Commands:[/bold]\n"
            "  [cyan]/run[/cyan]             Execute code blocks from last response\n"
            "  [cyan]/export pdf[/cyan]      Save last response as PDF\n"
            "  [cyan]/export json[/cyan]     Save last response as JSON\n"
            "  [cyan]/export json AAPL[/cyan]  Export stock data to JSON\n"
            "  [cyan]/export excel AAPL[/cyan]  Export stock data to Excel\n\n"
            "[bold]Market & Charts:[/bold]\n"
            "  [cyan]/chart AAPL 3mo volume sma20[/cyan]  Candlestick chart (PNG)\n"
            "  [cyan]/compare NVDA TSLA AAPL 1y[/cyan]   Comparison chart (PNG)\n"
            "  [cyan]/html chart AAPL 3mo volume[/cyan]   Interactive chart (browser)\n"
            "  [cyan]/html compare NVDA TSLA 1y[/cyan]    Interactive comparison (browser)\n"
            "  [cyan]/html report[/cyan]     Export last response as HTML page\n"
            "  [cyan]/quote AAPL[/cyan]      Quick stock quote\n"
            "  [cyan]/stream AAPL NVDA TSLA[/cyan]        Live price stream\n\n"
            "[bold]File Operations:[/bold]\n"
            "  [cyan]/open ~/file.pdf[/cyan]  Open any file with system default app\n"
            "  [cyan]/read ~/data.csv[/cyan]  Read & display file in terminal\n"
            "  [cyan]/file ~/report.pdf[/cyan] Send file to Pacific for AI analysis\n"
            "  [cyan]/image chart.png[/cyan]  Analyze chart image with AI\n"
            "  [dim]  Supports: .txt, .csv, .json, .py, .pdf, and more[/dim]\n\n"
            "[bold]Finance Shortcuts:[/bold]\n"
            "  [dim]Just type naturally — Pacific understands finance natively.[/dim]\n"
            '  [dim]"Black-Scholes for AAPL $200 call, 30 days, 25% vol"[/dim]\n'
            '  [dim]"Compare AAPL vs MSFT vs GOOGL YTD performance"[/dim]\n'
            '  [dim]"Build me a pairs trading backtest for GLD/SLV"[/dim]',
            title="[bold cyan]PACIFIC Help[/bold cyan]",
            border_style="dim",
        )
    )
