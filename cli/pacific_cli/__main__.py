"""
Pacific CLI — Main entry point.

Full-featured financial AI with authentication, market data, charting,
file analysis, exports, and interactive chat.

Usage:
  pacific "What's the outlook for tech?"       Quick query (default)
  pacific chat [message]                       Interactive chat
  pacific ask [question]                       Single-turn Q&A
  pacific analyze [query]                      Financial analysis
  pacific sentiment [headline]                 Sentiment classification
  pacific portfolio [--holdings ...] [...]     Portfolio optimization
  pacific image [path]                         Analyze chart/screenshot
  pacific chart [ticker] [period]              Candlestick chart
  pacific compare [tickers]                    Multi-stock comparison
  pacific quote [ticker]                       Quick stock quote
  pacific stream [tickers]                     Live price stream
  pacific market                               Market overview
  pacific info [ticker]                        Company info
  pacific excel [ticker]                       Export to Excel
  pacific json [ticker]                        Export to JSON
  pacific pdf [text]                           Export to PDF
  pacific plans                                Show pricing
  pacific config                               Configure preferences
  pacific health                               Check server status
  pacific login                                Sign in
  pacific register                             Create account
  pacific logout                               Sign out
  pacific status                               Check subscription
"""

import argparse
import sys

from . import __version__
from .commands import (
    cmd_chat, cmd_ask, cmd_analyze, cmd_sentiment, cmd_portfolio,
    cmd_image, cmd_chart, cmd_compare, cmd_quote, cmd_stream, cmd_market,
    cmd_info, cmd_excel, cmd_pdf, cmd_json,
    cmd_plans, cmd_config, cmd_health,
    cmd_login, cmd_register, cmd_logout, cmd_status,
)


def main():
    parser = argparse.ArgumentParser(
        prog="pacific",
        description="🌊 Pacific — Elite Quantitative Financial AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start:\n"
            "  pacific register                  Create account\n"
            "  pacific login                     Sign in\n"
            "  pacific \"What's happening with TSLA?\"\n"
            "  pacific chat                      Interactive mode\n"
            "  pacific chat --think              With reasoning\n"
            "\n"
            "Analysis:\n"
            "  pacific analyze --ticker AAPL --timeframe 1W \"earnings impact\"\n"
            "  pacific sentiment \"Inflation data comes in hotter than expected\"\n"
            "  pacific portfolio --holdings \"SPY 60%, AGG 40%\" --risk low\n"
            "\n"
            "Market:\n"
            "  pacific chart AAPL 3mo volume sma20\n"
            "  pacific compare AAPL NVDA TSLA --period 1y\n"
            "  pacific quote TSLA\n"
            "  pacific stream AAPL NVDA TSLA\n"
            "\n"
            "Subscribe: https://pacific.grrn.io/subscribe\n"
            "Docs:      https://pacific.grrn.io/docs\n"
        ),
    )
    parser.add_argument("-v", "--version", action="version", version=f"pacific-cli {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── chat ──
    chat_parser = subparsers.add_parser("chat", help="Interactive chat or single query")
    chat_parser.add_argument("message", nargs="*", help="Query (omit for interactive mode)")
    chat_parser.add_argument("--think", action="store_true", help="Enable thinking/chain-of-thought")
    chat_parser.set_defaults(func=cmd_chat)

    # ── ask ──
    ask_parser = subparsers.add_parser("ask", help="Quick single-turn question")
    ask_parser.add_argument("question", nargs="*", help="Question to ask")
    ask_parser.add_argument("--think", action="store_true", help="Enable thinking mode")
    ask_parser.set_defaults(func=cmd_ask)

    # ── analyze ──
    analyze_parser = subparsers.add_parser("analyze", help="Financial analysis query")
    analyze_parser.add_argument("query", nargs="*", help="Analysis query")
    analyze_parser.add_argument("--ticker", "-t", help="Stock ticker symbol")
    analyze_parser.add_argument("--timeframe", "-tf", help="Timeframe (1D, 1W, 1M, etc.)")
    analyze_parser.add_argument("--think", action="store_true", help="Enable thinking mode")
    analyze_parser.set_defaults(func=cmd_analyze)

    # ── sentiment ──
    sentiment_parser = subparsers.add_parser("sentiment", help="Classify financial sentiment")
    sentiment_parser.add_argument("text", nargs="*", help="Text to classify")
    sentiment_parser.set_defaults(func=cmd_sentiment)

    # ── portfolio ──
    portfolio_parser = subparsers.add_parser("portfolio", help="Portfolio optimization")
    portfolio_parser.add_argument("--action", "-a", default="analyze",
                                  choices=["analyze", "optimize", "rebalance", "risk"],
                                  help="Portfolio action")
    portfolio_parser.add_argument("--holdings", "-H", help="Current holdings")
    portfolio_parser.add_argument("--risk", "-r", choices=["low", "moderate", "high", "aggressive"],
                                  help="Risk tolerance")
    portfolio_parser.add_argument("--goal", "-g", help="Investment goal")
    portfolio_parser.set_defaults(func=cmd_portfolio)

    # ── image ──
    image_parser = subparsers.add_parser("image", help="Analyze a chart/screenshot image")
    image_parser.add_argument("path", nargs="*", help="Path to image file")
    image_parser.add_argument("--prompt", "-p", nargs="*", help="Custom analysis prompt")
    image_parser.set_defaults(func=cmd_image)

    # ── chart ──
    chart_parser = subparsers.add_parser("chart", help="Generate candlestick chart")
    chart_parser.add_argument("ticker", nargs="?", default="SPY", help="Stock ticker")
    chart_parser.add_argument("period", nargs="?", default="3mo", help="Period (1d,5d,1mo,3mo,6mo,1y,2y,5y,max)")
    chart_parser.add_argument("indicators", nargs="*", default=["volume", "sma20"],
                              help="Indicators (volume, sma20, sma50, ema20, bb, rsi)")
    chart_parser.set_defaults(func=cmd_chart)

    # ── compare ──
    compare_parser = subparsers.add_parser("compare", help="Compare multiple stocks")
    compare_parser.add_argument("tickers", nargs="*", help="Stock tickers to compare")
    compare_parser.add_argument("--period", "-p", default="1y", help="Period (default: 1y)")
    compare_parser.set_defaults(func=cmd_compare)

    # ── quote ──
    quote_parser = subparsers.add_parser("quote", help="Quick stock quote")
    quote_parser.add_argument("ticker", help="Stock ticker symbol")
    quote_parser.set_defaults(func=cmd_quote)

    # ── stream ──
    stream_parser = subparsers.add_parser("stream", help="Live price streaming")
    stream_parser.add_argument("tickers", nargs="*", help="Stock tickers to stream")
    stream_parser.add_argument("--refresh", "-r", type=int, default=3, help="Refresh interval (seconds)")
    stream_parser.set_defaults(func=cmd_stream)

    # ── market ──
    market_parser = subparsers.add_parser("market", help="Market overview")
    market_parser.set_defaults(func=cmd_market)

    # ── info ──
    info_parser = subparsers.add_parser("info", help="Company information")
    info_parser.add_argument("ticker", help="Stock ticker symbol")
    info_parser.set_defaults(func=cmd_info)

    # ── excel ──
    excel_parser = subparsers.add_parser("excel", help="Export stock data to Excel")
    excel_parser.add_argument("ticker", help="Stock ticker symbol")
    excel_parser.add_argument("--period", "-p", default="3mo", help="Period (default: 3mo)")
    excel_parser.set_defaults(func=cmd_excel)

    # ── json ──
    json_parser = subparsers.add_parser("json", help="Export stock data to JSON")
    json_parser.add_argument("ticker", help="Stock ticker symbol")
    json_parser.add_argument("--period", "-p", default="3mo", help="Period (default: 3mo)")
    json_parser.set_defaults(func=cmd_json)

    # ── pdf ──
    pdf_parser = subparsers.add_parser("pdf", help="Export text to PDF")
    pdf_parser.add_argument("text", nargs="*", help="Text to export")
    pdf_parser.set_defaults(func=cmd_pdf)

    # ── plans ──
    plans_parser = subparsers.add_parser("plans", help="Show pricing info")
    plans_parser.set_defaults(func=cmd_plans)

    # ── config ──
    config_parser = subparsers.add_parser("config", help="Configure CLI preferences")
    config_parser.add_argument("--show", action="store_true", help="Show current config")
    config_parser.add_argument("--set-key", help="Set API key")
    config_parser.add_argument("--api-url", help="Set API base URL")
    config_parser.add_argument("--max-tokens", type=int, help="Default max tokens")
    config_parser.add_argument("--temperature", type=float, help="Default temperature")
    config_parser.add_argument("--thinking", help="Enable thinking (true/false)")
    config_parser.add_argument("--theme", help="Color theme")
    config_parser.add_argument("--reset", action="store_true", help="Reset to defaults")
    config_parser.set_defaults(func=cmd_config)

    # ── health ──
    health_parser = subparsers.add_parser("health", help="Check server status")
    health_parser.set_defaults(func=cmd_health)

    # ── login ──
    login_parser = subparsers.add_parser("login", help="Sign in to Pacific")
    login_parser.set_defaults(func=cmd_login)

    # ── register ──
    register_parser = subparsers.add_parser("register", help="Create a new account")
    register_parser.set_defaults(func=cmd_register)

    # ── logout ──
    logout_parser = subparsers.add_parser("logout", help="Sign out")
    logout_parser.set_defaults(func=cmd_logout)

    # ── status ──
    status_parser = subparsers.add_parser("status", help="Check subscription status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        # No subcommand — treat remaining args as a quick chat query
        remaining = sys.argv[1:]
        if remaining and not remaining[0].startswith("-"):
            # pacific "What's happening with TSLA?" → quick single query
            class QuickArgs:
                message = remaining
                think = False
            cmd_chat(QuickArgs())
        else:
            parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
