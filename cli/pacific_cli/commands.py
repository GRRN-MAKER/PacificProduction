"""
Pacific CLI — Full command implementations.

Commands:
  pacific [message]                Quick query (default)
  pacific chat [message]           Interactive chat with all slash commands
  pacific ask [question]           Single-turn Q&A
  pacific analyze [query]          Financial analysis
  pacific sentiment [headline]     Sentiment classification
  pacific portfolio [action]       Portfolio optimization
  pacific image [path]             Analyze chart/screenshot image
  pacific chart [ticker] [period]  Generate candlestick chart
  pacific compare [tickers]        Multi-stock comparison chart
  pacific quote [ticker]           Quick stock quote
  pacific stream [tickers]         Live price stream
  pacific market                   Market overview
  pacific info [ticker]            Company info
  pacific excel [ticker] [period]  Export stock data to Excel
  pacific pdf                      Export last response as PDF
  pacific json [ticker] [period]   Export stock data to JSON
  pacific plans                    Show pricing
  pacific config                   Configure preferences
  pacific health                   Check server status
  pacific login                    Sign in
  pacific register                 Create account
  pacific logout                   Sign out
  pacific status                   Check subscription status
"""

import re
import sys
import json
from datetime import datetime
from pathlib import Path

from .client import PacificClient
from .config import load_config, save_config, get_api_key, set_api_key, get_config_value, set_config_value
from .display import (
    print_banner, print_mini, print_success, print_error, print_warning,
    print_info, print_user_prompt, print_pacific_label, print_thinking_label,
    print_divider, print_token, print_plans, print_help_panel,
    CYAN, YELLOW, GREEN, RED, RESET, BOLD, DIM, MAGENTA,
)


SYSTEM_PROMPTS = {
    "chat": (
        "You are Pacific, an elite quantitative financial AI. You provide precise, "
        "data-driven analysis with institutional-grade insights. Use clean markdown, "
        "LaTeX for math ($$...$$ blocks, $...$ inline), and production-quality code."
    ),
    "analyze": (
        "You are Pacific, an elite quantitative financial AI. Provide detailed "
        "technical and fundamental analysis. Include specific indicators, levels, "
        "and actionable insights. Format with clear sections."
    ),
    "sentiment": (
        "You are Pacific, a financial sentiment classifier. Classify the given text "
        "as BULLISH, BEARISH, or NEUTRAL. Then provide a brief explanation of key "
        "sentiment drivers. Format: [SENTIMENT] followed by analysis."
    ),
    "portfolio": (
        "You are Pacific, a portfolio optimization engine. Analyze portfolio "
        "composition, suggest rebalancing, calculate risk metrics (Sharpe, VaR, CVaR), "
        "and provide allocation recommendations."
    ),
}


# ═══════════════════════════════════════════════════════════════════════
#  INTERACTIVE CHAT — with ALL slash commands
# ═══════════════════════════════════════════════════════════════════════

def cmd_chat(args):
    """Interactive chat with full slash command support."""
    config = load_config()
    client = PacificClient()

    # Single query mode
    if hasattr(args, "message") and args.message:
        query = " ".join(args.message)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["chat"]},
            {"role": "user", "content": query},
        ]
        print_pacific_label()
        full_reply = ""
        for token in client.chat(messages, thinking=getattr(args, "think", False)):
            print_token(token)
            full_reply += token
        print("\n")
        return

    # Interactive mode
    print_banner()
    thinking = getattr(args, "think", False) or config.get("thinking_enabled", False)
    print_info(f"Thinking: {'ON' if thinking else 'OFF'}  |  Type /help for commands")
    print_divider()

    messages = [{"role": "system", "content": SYSTEM_PROMPTS["chat"]}]
    last_response = ""
    session_num = 0

    while True:
        try:
            print_user_prompt()
            user_input = input()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye! 🌊{RESET}")
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() in ("exit", "quit", "q", "/exit", "/quit"):
            print(f"{DIM}Goodbye! Markets never sleep. 📈{RESET}")
            break

        # ── Slash commands ────────────────────────────────────────────

        if stripped == "/clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPTS["chat"]}]
            last_response = ""
            session_num = 0
            print_success("Conversation cleared")
            continue

        if stripped == "/help":
            print_help_panel()
            continue

        if stripped == "/history":
            count = len([m for m in messages if m["role"] == "user"])
            print_info(f"{count} messages in current session")
            continue

        if stripped.startswith("/think"):
            if stripped == "/think on":
                thinking = True
                print(f"{GREEN}Thinking: ON{RESET}")
            elif stripped == "/think off":
                thinking = False
                print(f"{DIM}Thinking: OFF{RESET}")
            else:
                print(f"{DIM}Thinking: {'ON' if thinking else 'OFF'}{RESET}")
            continue

        # ── Export commands ────────────────────────────────────────

        if stripped.startswith("/export pdf"):
            if last_response:
                from .export import analysis_to_pdf
                analysis_to_pdf("Chat Analysis", last_response)
            else:
                print(f"{DIM}No response to export.{RESET}")
            continue

        if stripped.startswith("/export excel "):
            ticker = stripped.split()[-1].upper()
            from .export import stock_data_to_excel
            stock_data_to_excel(ticker)
            continue

        if stripped.startswith("/export json"):
            parts = stripped.split()
            if len(parts) >= 3:
                ticker = parts[2].upper()
                period = parts[3] if len(parts) > 3 else "3mo"
                from .export import stock_data_to_json
                stock_data_to_json(ticker, period=period)
            elif last_response:
                from .export import analysis_to_json
                analysis_to_json("Chat Analysis", last_response)
            else:
                print(f"{DIM}No response to export. Use /export json TICKER.{RESET}")
            continue

        # ── Chart commands ─────────────────────────────────────────

        if stripped.startswith("/chart "):
            parts = stripped.split()
            ticker = parts[1].upper() if len(parts) > 1 else "SPY"
            period = "3mo"
            indicators = []
            for p in parts[2:]:
                if p.lower() in ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"):
                    period = p.lower()
                else:
                    indicators.append(p.lower())
            from .market import plot_stock_chart
            plot_stock_chart(ticker, period=period, indicators=indicators or ["volume", "sma20"])
            continue

        if stripped.startswith("/compare "):
            parts = stripped.split()
            tickers_list = []
            period = "1y"
            for p in parts[1:]:
                if p.lower() in ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"):
                    period = p.lower()
                else:
                    tickers_list.append(p.upper())
            if tickers_list:
                from .market import plot_comparison
                plot_comparison(tickers_list, period=period)
            else:
                print(f"{DIM}Usage: /compare AAPL NVDA TSLA [1y]{RESET}")
            continue

        if stripped.startswith("/quote "):
            ticker = stripped.split()[1].upper()
            from .market import quick_quote
            quick_quote(ticker)
            continue

        if stripped.startswith("/stream "):
            parts = stripped.split()
            syms = [p.upper() for p in parts[1:] if not p.startswith("-")]
            refresh = 3
            for i, p in enumerate(parts):
                if p == "-r" and i + 1 < len(parts):
                    try:
                        refresh = int(parts[i + 1])
                    except ValueError:
                        pass
            if syms:
                from .market import live_price_stream
                live_price_stream(syms, refresh_secs=refresh)
            else:
                print(f"{DIM}Usage: /stream AAPL NVDA TSLA [-r 2]{RESET}")
            continue

        # ── File commands ──────────────────────────────────────────

        if stripped.startswith("/file "):
            filepath = stripped[6:].strip().strip('"').strip("'")
            from .files import resolve_path, read_file_content
            resolved = resolve_path(filepath)
            if resolved:
                content = read_file_content(resolved, max_lines=500)
                if content:
                    fname = Path(resolved).name
                    stripped = (
                        f"I'm sharing a file with you: **{fname}**\n\n"
                        f"```\n{content}\n```\n\n"
                        f"Please analyze this file and provide insights."
                    )
                    # Fall through to AI query below
                else:
                    print(f"{DIM}Could not read file content.{RESET}")
                    continue
            else:
                print(f"{RED}✗ File not found:{RESET} {filepath}")
                continue

        if stripped.startswith("/open "):
            filepath = stripped[6:].strip().strip('"').strip("'")
            from .files import resolve_path, open_file
            resolved = resolve_path(filepath)
            if resolved:
                open_file(resolved)
            else:
                print(f"{RED}✗ File not found:{RESET} {filepath}")
            continue

        if stripped.startswith("/read "):
            filepath = stripped[6:].strip().strip('"').strip("'")
            from .files import resolve_path, display_file_content
            resolved = resolve_path(filepath)
            if resolved:
                display_file_content(resolved)
            else:
                print(f"{RED}✗ File not found:{RESET} {filepath}")
            continue

        # ── Image analysis ─────────────────────────────────────────

        if stripped.startswith("/image "):
            image_path = stripped[7:].strip().strip('"').strip("'")
            if not Path(image_path).expanduser().exists():
                print(f"{RED}Image not found: {image_path}{RESET}")
                continue
            print_pacific_label()
            full_reply = ""
            for token in client.analyze_image(image_path):
                print_token(token)
                full_reply += token
            print()
            last_response = full_reply
            session_num += 1
            continue

        # ── Auto-detect file paths in messages ─────────────────────

        _file_match = re.search(
            r'(?:^|\s)(/[\w/. -]+\.\w{1,5}|~/[\w/. -]+\.\w{1,5}|[A-Z]:\\[\w\\/. -]+\.\w{1,5})',
            stripped,
        )
        if _file_match and not stripped.startswith("/"):
            _detected_path = _file_match.group(1).strip()
            from .files import resolve_path, read_file_content
            _resolved = resolve_path(_detected_path)
            if _resolved:
                _content = read_file_content(_resolved, max_lines=500)
                if _content:
                    _fname = Path(_resolved).name
                    print(f"{DIM}📄 Auto-read: {_fname}{RESET}")
                    stripped = (
                        f"{stripped}\n\n"
                        f"--- LOCAL FILE: {_fname} ---\n"
                        f"```\n{_content}\n```"
                    )

        # ── Send to AI ─────────────────────────────────────────────

        messages.append({"role": "user", "content": stripped})

        if thinking:
            print_thinking_label()

        print_pacific_label()
        full_reply = ""
        try:
            for token in client.chat(messages, thinking=thinking):
                print_token(token)
                full_reply += token
            print()
        except Exception as e:
            print_error(str(e))
            continue

        messages.append({"role": "assistant", "content": full_reply})
        last_response = full_reply
        session_num += 1

        # Save to history
        history_file = config.get("history_file")
        if history_file and config.get("history_enabled"):
            try:
                Path(history_file).parent.mkdir(parents=True, exist_ok=True)
                with open(history_file, "a") as f:
                    record = {
                        "ts": datetime.utcnow().isoformat(),
                        "user": stripped[:500],
                        "assistant": full_reply[:500],
                    }
                    f.write(json.dumps(record) + "\n")
            except IOError:
                pass

        print_divider()


# ═══════════════════════════════════════════════════════════════════════
#  ASK — Single-turn query (no history)
# ═══════════════════════════════════════════════════════════════════════

def cmd_ask(args):
    """Quick single-turn question."""
    if not args.question:
        print_error("Usage: pacific ask 'What is the current PE ratio of AAPL?'")
        sys.exit(1)

    query = " ".join(args.question)
    client = PacificClient()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["chat"]},
        {"role": "user", "content": query},
    ]

    print_pacific_label()
    full_reply = ""
    for token in client.chat(messages, thinking=getattr(args, "think", False)):
        print_token(token)
        full_reply += token
    print("\n")


# ═══════════════════════════════════════════════════════════════════════
#  ANALYZE — Financial analysis
# ═══════════════════════════════════════════════════════════════════════

def cmd_analyze(args):
    """Financial analysis query."""
    if not args.query:
        print_error("Usage: pacific analyze 'Analyze AAPL earnings beat'")
        sys.exit(1)

    query = " ".join(args.query)
    client = PacificClient()

    enriched = query
    if args.ticker:
        enriched = f"Ticker: {args.ticker.upper()}. {enriched}"
    if args.timeframe:
        enriched = f"{enriched} Timeframe: {args.timeframe}."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["analyze"]},
        {"role": "user", "content": enriched},
    ]

    print_mini()
    print(f"{DIM}Analyzing: {query}{RESET}")
    print_divider()

    full_reply = ""
    for token in client.chat(messages, thinking=getattr(args, "think", False)):
        print_token(token)
        full_reply += token
    print("\n")


# ═══════════════════════════════════════════════════════════════════════
#  SENTIMENT
# ═══════════════════════════════════════════════════════════════════════

def cmd_sentiment(args):
    """Classify financial sentiment."""
    if not args.text:
        print_error("Usage: pacific sentiment 'Fed announces rate pause'")
        sys.exit(1)

    text = " ".join(args.text)
    client = PacificClient()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["sentiment"]},
        {"role": "user", "content": f"Classify: {text}"},
    ]

    print_mini()
    full_reply = ""
    for token in client.chat(messages, max_tokens=512, temperature=0.3):
        print_token(token)
        full_reply += token
    print("\n")


# ═══════════════════════════════════════════════════════════════════════
#  PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════

def cmd_portfolio(args):
    """Portfolio optimization and analysis."""
    client = PacificClient()

    action = args.action or "analyze"
    query_parts = [f"Action: {action}"]

    if args.holdings:
        query_parts.append(f"Current holdings: {args.holdings}")
    if args.risk:
        query_parts.append(f"Risk tolerance: {args.risk}")
    if args.goal:
        query_parts.append(f"Investment goal: {args.goal}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["portfolio"]},
        {"role": "user", "content": " | ".join(query_parts)},
    ]

    print_mini()
    print(f"{DIM}Portfolio {action}...{RESET}")
    print_divider()

    full_reply = ""
    for token in client.chat(messages, thinking=True):
        print_token(token)
        full_reply += token
    print("\n")


# ═══════════════════════════════════════════════════════════════════════
#  IMAGE — Chart/screenshot analysis
# ═══════════════════════════════════════════════════════════════════════

def cmd_image(args):
    """Analyze a chart or screenshot image."""
    if not args.path:
        print_error("Usage: pacific image ~/chart.png")
        sys.exit(1)

    image_path = " ".join(args.path)
    client = PacificClient()

    prompt = " ".join(args.prompt) if hasattr(args, "prompt") and args.prompt else None
    prompt = prompt or "Analyze this financial chart. Identify patterns, trends, key levels, and provide a trading outlook."

    print_mini()
    print(f"{DIM}Analyzing image: {image_path}{RESET}")
    print_divider()

    full_reply = ""
    for token in client.analyze_image(image_path, prompt=prompt):
        print_token(token)
        full_reply += token
    print("\n")


# ═══════════════════════════════════════════════════════════════════════
#  CHART — Generate candlestick chart
# ═══════════════════════════════════════════════════════════════════════

def cmd_chart(args):
    """Generate a stock candlestick chart."""
    ticker = args.ticker or "SPY"
    period = args.period or "3mo"
    indicators = args.indicators or ["volume", "sma20"]

    from .market import plot_stock_chart
    plot_stock_chart(ticker.upper(), period=period, indicators=indicators)


# ═══════════════════════════════════════════════════════════════════════
#  COMPARE — Multi-stock comparison
# ═══════════════════════════════════════════════════════════════════════

def cmd_compare(args):
    """Compare multiple stocks on a normalized chart."""
    if not args.tickers:
        print_error("Usage: pacific compare AAPL NVDA TSLA --period 1y")
        sys.exit(1)

    period = args.period or "1y"
    from .market import plot_comparison
    plot_comparison([t.upper() for t in args.tickers], period=period)


# ═══════════════════════════════════════════════════════════════════════
#  QUOTE — Quick stock quote
# ═══════════════════════════════════════════════════════════════════════

def cmd_quote(args):
    """Quick stock quote with key metrics."""
    if not args.ticker:
        print_error("Usage: pacific quote AAPL")
        sys.exit(1)

    from .market import quick_quote
    quick_quote(args.ticker.upper())


# ═══════════════════════════════════════════════════════════════════════
#  STREAM — Live price stream
# ═══════════════════════════════════════════════════════════════════════

def cmd_stream(args):
    """Live price streaming for multiple tickers."""
    if not args.tickers:
        print_error("Usage: pacific stream AAPL NVDA TSLA")
        sys.exit(1)

    refresh = args.refresh or 3
    from .market import live_price_stream
    live_price_stream([t.upper() for t in args.tickers], refresh_secs=refresh)


# ═══════════════════════════════════════════════════════════════════════
#  MARKET — Overview of major indices
# ═══════════════════════════════════════════════════════════════════════

def cmd_market(args):
    """Display market overview."""
    from .market import market_summary
    market_summary()


# ═══════════════════════════════════════════════════════════════════════
#  INFO — Company information
# ═══════════════════════════════════════════════════════════════════════

def cmd_info(args):
    """Show company info for a ticker."""
    if not args.ticker:
        print_error("Usage: pacific info AAPL")
        sys.exit(1)

    try:
        import yfinance as yf
    except ImportError:
        print_error("Missing: pip install yfinance")
        return

    ticker = args.ticker.upper()
    print(f"{DIM}Fetching info for {ticker}...{RESET}")
    t = yf.Ticker(ticker)

    try:
        info = t.info
    except Exception:
        info = {}

    if not info:
        print_error(f"No data for {ticker}")
        return

    name = info.get("shortName", ticker)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    employees = info.get("fullTimeEmployees", 0)
    country = info.get("country", "N/A")
    website = info.get("website", "")
    summary = info.get("longBusinessSummary", "")

    print(f"\n{BOLD}{name} ({ticker}){RESET}")
    print(f"{'─' * 50}")
    print(f"  Sector:     {sector}")
    print(f"  Industry:   {industry}")
    print(f"  Country:    {country}")
    if employees:
        print(f"  Employees:  {employees:,}")
    if website:
        print(f"  Website:    {website}")
    print()

    # Key financials
    mkt_cap = info.get("marketCap", 0)
    pe = info.get("trailingPE", 0)
    eps = info.get("trailingEps", 0)
    revenue = info.get("totalRevenue", 0)
    profit_margin = info.get("profitMargins", 0)

    if mkt_cap:
        cap_str = f"${mkt_cap/1e9:,.2f}B" if mkt_cap > 1e9 else f"${mkt_cap/1e6:,.2f}M"
        print(f"  Mkt Cap:    {cap_str}")
    if pe:
        print(f"  P/E:        {pe:,.2f}")
    if eps:
        print(f"  EPS:        ${eps:,.2f}")
    if revenue:
        rev_str = f"${revenue/1e9:,.2f}B" if revenue > 1e9 else f"${revenue/1e6:,.2f}M"
        print(f"  Revenue:    {rev_str}")
    if profit_margin:
        print(f"  Margin:     {profit_margin*100:.2f}%")

    print()
    if summary:
        # Truncate long summaries
        if len(summary) > 400:
            summary = summary[:400] + "..."
        print(f"  {DIM}{summary}{RESET}")
    print()


# ═══════════════════════════════════════════════════════════════════════
#  EXCEL — Export stock data to spreadsheet
# ═══════════════════════════════════════════════════════════════════════

def cmd_excel(args):
    """Export stock data to Excel."""
    if not args.ticker:
        print_error("Usage: pacific excel AAPL --period 3mo")
        sys.exit(1)

    period = args.period or "3mo"
    from .export import stock_data_to_excel
    stock_data_to_excel(args.ticker.upper(), period=period)


# ═══════════════════════════════════════════════════════════════════════
#  PDF — Export last response or analysis
# ═══════════════════════════════════════════════════════════════════════

def cmd_pdf(args):
    """Export text to PDF."""
    text = " ".join(args.text) if hasattr(args, "text") and args.text else None
    if not text:
        print_error("Usage: pacific pdf 'Your analysis text here'")
        print(f"  {DIM}Or use /export pdf in chat mode.{RESET}")
        sys.exit(1)

    from .export import analysis_to_pdf
    analysis_to_pdf("Pacific Analysis", text)


# ═══════════════════════════════════════════════════════════════════════
#  JSON — Export stock data to JSON
# ═══════════════════════════════════════════════════════════════════════

def cmd_json(args):
    """Export stock data to JSON."""
    if not args.ticker:
        print_error("Usage: pacific json AAPL --period 3mo")
        sys.exit(1)

    period = args.period or "3mo"
    from .export import stock_data_to_json
    stock_data_to_json(args.ticker.upper(), period=period)


# ═══════════════════════════════════════════════════════════════════════
#  PLANS — Pricing info
# ═══════════════════════════════════════════════════════════════════════

def cmd_plans(args):
    """Show pricing info."""
    print(f"\n{BOLD}🌊 Pacific — Pricing{RESET}")
    print_divider()
    print(f"  Trial:     {GREEN}7 days free{RESET}")
    print(f"  Monthly:   {CYAN}$40/month{RESET}")
    print(f"  Annual:    {CYAN}$399/year (save 17%){RESET}")
    print_divider()
    print()
    print(f"  {BOLD}Includes:{RESET}")
    print(f"    ✓ Unlimited AI queries")
    print(f"    ✓ Real-time market data")
    print(f"    ✓ Chart generation")
    print(f"    ✓ PDF/Excel/JSON exports")
    print(f"    ✓ File analysis (PDF, CSV, code)")
    print(f"    ✓ Image/chart analysis")
    print(f"    ✓ Portfolio optimization")
    print(f"    ✓ Live price streaming")
    print()
    print(f"  {DIM}Subscribe: https://pacific.grrn.io/subscribe{RESET}")
    print()


# ═══════════════════════════════════════════════════════════════════════
#  CONFIG — Preferences
# ═══════════════════════════════════════════════════════════════════════

def cmd_config(args):
    """Configure CLI preferences."""
    config = load_config()

    if args.show:
        print(f"\n{BOLD}Pacific Configuration{RESET}")
        print_divider()
        for key, val in sorted(config.items()):
            if key == "api_key" and val:
                # Mask API key
                val = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            print(f"  {key:<22} {DIM}{val}{RESET}")
        print_divider()
        print(f"  {DIM}Config file: ~/.pacific/config.json{RESET}")
        print()
        return

    if args.set_key:
        set_api_key(args.set_key)
        print_success("API key saved.")
        return

    changed = False

    if args.api_url:
        config["api_base_url"] = args.api_url
        changed = True

    if args.max_tokens is not None:
        config["max_tokens"] = args.max_tokens
        changed = True

    if args.temperature is not None:
        config["temperature"] = args.temperature
        changed = True

    if args.thinking is not None:
        config["thinking_enabled"] = args.thinking.lower() in ("true", "1", "yes", "on")
        changed = True

    if args.theme:
        config["theme"] = args.theme
        changed = True

    if args.reset:
        from .config import DEFAULTS
        save_config(dict(DEFAULTS))
        print_success("Configuration reset to defaults.")
        return

    if changed:
        save_config(config)
        print_success("Configuration updated.")
    else:
        # No flags passed — show config
        cmd_config_show = type("Args", (), {"show": True})()
        cmd_config(cmd_config_show)


# ═══════════════════════════════════════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════════════════════════════════════

def cmd_health(args):
    """Check server health."""
    client = PacificClient()
    print(f"{DIM}Checking Pacific server...{RESET}")
    try:
        data = client.health_check()
        status = data.get("status", "unknown")
        backend = data.get("backend_connected", False)

        print(f"\n{BOLD}🌊 Pacific Server Status{RESET}")
        print_divider()
        if status == "healthy":
            print(f"  Gateway:   {GREEN}✓ Online{RESET}")
        else:
            print(f"  Gateway:   {YELLOW}⚠ {status}{RESET}")
        print(f"  Backend:   {GREEN if backend else RED}{'✓ Connected' if backend else '✗ Disconnected'}{RESET}")
        print(f"  Version:   {DIM}{data.get('version', 'unknown')}{RESET}")
        print_divider()
        print()
    except Exception as e:
        print_error(f"Cannot reach server: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  AUTH COMMANDS
# ═══════════════════════════════════════════════════════════════════════

def cmd_login(args):
    """Sign in to Pacific."""
    from .auth import login_interactive
    login_interactive()


def cmd_register(args):
    """Create a new Pacific account."""
    from .auth import register_interactive
    register_interactive()


def cmd_logout(args):
    """Sign out and clear API key."""
    from .auth import logout
    logout()


def cmd_status(args):
    """Check subscription status."""
    from .auth import print_subscription_status
    print_subscription_status()
