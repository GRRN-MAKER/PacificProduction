"""PACIFIC CLI — Main entry point.

Usage:
    pacific                    → Interactive chat
    pacific chat               → Interactive chat
    pacific ask "question"     → One-shot query
    pacific image chart.png    → Analyze a financial chart
    pacific chart AAPL 3mo     → Generate stock chart
    pacific compare AAPL MSFT  → Compare tickers
    pacific ticker AAPL TSLA   → Live ticker
    pacific quote AAPL         → Quick quote
    pacific market             → Market overview
    pacific info AAPL          → Stock profile
    pacific excel AAPL 6mo     → Export to Excel
    pacific json AAPL 6mo      → Export to JSON
    pacific pdf "title" "text" → Generate PDF report
    pacific register           → Create account
    pacific login              → Sign in
    pacific logout             → Sign out
    pacific status             → Subscription status
    pacific plans              → View pricing
    pacific subscribe          → Subscribe via Microsoft Store (Windows)
    pacific config show        → Show config
    pacific config set-key KEY → Set API key
"""

import sys
import click
from rich.console import Console

from pacific import __version__, __app__
from pacific.config import (
    load_config, save_config, set_api_key,
    get_api_key, set_config_value, get_config_value,
)

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name=__app__)
@click.pass_context
def cli(ctx):
    """PACIFIC — Elite Financial Intelligence CLI powered by GRRN"""
    if ctx.invoked_subcommand is None:
        # Default: launch chat
        from pacific.chat import chat_session
        chat_session()


# ── Chat ─────────────────────────────────────────────────────────────

@cli.command()
@click.option("--think", is_flag=True, help="Enable thinking mode")
def chat(think):
    """Interactive multi-turn chat session."""
    from pacific.chat import chat_session
    chat_session(enable_thinking=think)


# ── One-shot query ───────────────────────────────────────────────────

@cli.command()
@click.argument("prompt")
@click.option("--think", is_flag=True, help="Enable thinking mode")
def ask(prompt, think):
    """One-shot query — ask a single question."""
    from pacific.engine import stream_response
    stream_response(prompt, enable_thinking=think)


# ── Image analysis ───────────────────────────────────────────────────

@cli.command()
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--context", "-c", default="", help="Additional context for analysis")
def image(image_path, context):
    """Analyze a financial chart or image."""
    from pacific.engine import analyze_image
    analyze_image(image_path, context=context)


# ── Stock chart ──────────────────────────────────────────────────────

@cli.command("chart")
@click.argument("ticker")
@click.option("--period", "-p", default="3mo", help="Period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,max")
@click.option("--type", "chart_type", default="candle", help="Chart type: candle, line, ohlc")
@click.option("--indicators", "-i", multiple=True,
              help="Indicators: sma20, sma50, ema20, bb, rsi, volume")
@click.option("--output", "-o", default=None, help="Output file path")
def chart_cmd(ticker, period, chart_type, indicators, output):
    """Generate a stock chart with indicators."""
    from pacific.output.charts import plot_stock_chart
    inds = list(indicators) or ["volume", "sma20"]
    plot_stock_chart(ticker.upper(), period=period, chart_type=chart_type,
                     indicators=inds, output_path=output)


# ── Compare tickers ──────────────────────────────────────────────────

@cli.command()
@click.argument("tickers", nargs=-1, required=True)
@click.option("--period", "-p", default="1y", help="Comparison period")
@click.option("--output", "-o", default=None, help="Output file path")
def compare(tickers, period, output):
    """Compare multiple tickers on a normalized chart."""
    from pacific.output.charts import plot_comparison
    plot_comparison(list(tickers), period=period, output_path=output)


# ── Live ticker ──────────────────────────────────────────────────────

@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--refresh", "-r", default=None, type=int, help="Refresh interval (seconds)")
def ticker(symbols, refresh):
    """Live-updating stock ticker display."""
    from pacific.market.ticker import live_ticker
    live_ticker(list(symbols), refresh_secs=refresh)


@cli.command("stream")
@click.argument("symbols", nargs=-1, required=True)
@click.option("--refresh", "-r", default=3, type=int, help="Refresh interval (seconds)")
def stream_cmd(symbols, refresh):
    """Live price stream — scrolling real-time price updates."""
    from pacific.market.ticker import live_price_stream
    live_price_stream(list(symbols), refresh_secs=refresh)


@cli.command("htmlchart")
@click.argument("ticker")
@click.option("--period", "-p", default="3mo", help="Period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,max")
@click.option("--indicators", "-i", multiple=True,
              help="Indicators: sma20, sma50, ema20, bb, volume")
def htmlchart_cmd(ticker, period, indicators):
    """Interactive HTML chart — opens in browser."""
    from pacific.output.html_charts import interactive_chart
    inds = list(indicators) or ["volume", "sma20"]
    interactive_chart(ticker.upper(), period=period, indicators=inds)


@cli.command("htmlcompare")
@click.argument("tickers", nargs=-1, required=True)
@click.option("--period", "-p", default="1y", help="Comparison period")
def htmlcompare_cmd(tickers, period):
    """Interactive HTML comparison chart — opens in browser."""
    from pacific.output.html_charts import interactive_comparison
    interactive_comparison(list(tickers), period=period)


# ── Quick quote ──────────────────────────────────────────────────────

@cli.command()
@click.argument("symbol")
def quote(symbol):
    """Quick stock quote with sparkline."""
    from pacific.market.ticker import quick_quote
    quick_quote(symbol.upper())


# ── Market overview ──────────────────────────────────────────────────

@cli.command()
def market():
    """Broad market overview: indices, commodities, crypto, FX."""
    from pacific.market.data import market_overview
    market_overview()


# ── Stock info ───────────────────────────────────────────────────────

@cli.command()
@click.argument("symbol")
def info(symbol):
    """Detailed stock profile and fundamentals."""
    from pacific.market.data import stock_info
    stock_info(symbol.upper())


# ── Excel export ─────────────────────────────────────────────────────

@cli.command()
@click.argument("ticker")
@click.option("--period", "-p", default="3mo", help="Data period")
@click.option("--output", "-o", default=None, help="Output filename")
def excel(ticker, period, output):
    """Export stock data to Excel spreadsheet."""
    from pacific.output.excel import stock_data_to_excel
    stock_data_to_excel(ticker.upper(), period=period, filename=output)


# ── PDF export ───────────────────────────────────────────────────────

@cli.command()
@click.argument("title")
@click.argument("content")
@click.option("--output", "-o", default=None, help="Output filename")
def pdf(title, content, output):
    """Generate a PDF report from text."""
    from pacific.output.pdf import export_to_pdf
    export_to_pdf(title, content, filename=output)

# ── JSON export ──────────────────────────────────────────────────

@cli.command("json")
@click.argument("ticker")
@click.option("--period", "-p", default="3mo", help="Data period")
@click.option("--output", "-o", default=None, help="Output filename")
def json_cmd(ticker, period, output):
    """Export stock data to JSON file."""
    from pacific.output.json_export import stock_data_to_json
    stock_data_to_json(ticker.upper(), period=period, filename=output)

# ── Authentication ────────────────────────────────────────────────────

@cli.command()
def register():
    """Create a new Pacific account."""
    from pacific.auth import register_interactive
    register_interactive()


@cli.command()
def login():
    """Sign in to Pacific."""
    from pacific.auth import login_interactive
    login_interactive()


@cli.command()
def logout():
    """Sign out and clear API key."""
    from pacific.auth import logout
    logout()


@cli.command()
def status():
    """Check subscription status."""
    from pacific.auth import print_subscription_status
    print_subscription_status()


@cli.command()
def plans():
    """View subscription plans and pricing."""
    from pacific.auth import print_plans
    print_plans()


@cli.command("forgot-password")
def forgot_pw():
    """Reset your password via email."""
    from pacific.auth import forgot_password_interactive
    forgot_password_interactive()


@cli.command()
def subscribe():
    """Subscribe via Microsoft Store (Windows Store version only)."""
    from pacific.auth import subscribe_via_store
    subscribe_via_store()


# ── Config management ────────────────────────────────────────────────

@cli.group()
def config():
    """Manage PACIFIC configuration."""
    pass


@config.command("show")
def config_show():
    """Display current configuration."""
    from rich.table import Table
    cfg = load_config()
    table = Table(title="[bold cyan]PACIFIC Configuration[/bold cyan]", border_style="dim")
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    for k, v in cfg.items():
        display_val = "••••••••" if k == "api_key" and v else str(v)
        table.add_row(k, display_val)
    console.print(table)


@config.command("set-key")
@click.argument("key")
def config_set_key(key):
    """Set the Pacific API key."""
    set_api_key(key)
    console.print("[green]✓ API key saved.[/green]")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value. Example: pacific config set temperature 0.5"""
    # Auto-cast
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    else:
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
    set_config_value(key, value)
    console.print(f"[green]✓ {key} = {value}[/green]")


@config.command("reset")
def config_reset():
    """Reset config to defaults."""
    from pacific.config import DEFAULT_CONFIG
    save_config(DEFAULT_CONFIG)
    console.print("[green]✓ Configuration reset to defaults.[/green]")


# ── Entry point ──────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
