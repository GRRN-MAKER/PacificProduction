"""PACIFIC — Interactive HTML chart generation (Plotly-based, opens in browser)."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from pacific.config import load_config

console = Console()


def _ensure_plotly():
    """Check plotly is available, install hint if not."""
    try:
        import plotly
        return True
    except ImportError:
        console.print("[red]Missing dependency: pip install plotly[/red]")
        return False


def interactive_chart(
    ticker: str,
    period: str = "3mo",
    chart_type: str = "candlestick",
    indicators: Optional[List[str]] = None,
    output_path: Optional[str] = None,
) -> str:
    """Generate an interactive HTML candlestick/line chart and open in browser.

    Args:
        ticker: Stock symbol.
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max).
        chart_type: 'candlestick' or 'line'.
        indicators: List of indicators — 'sma20', 'sma50', 'ema20', 'bb', 'volume'.
        output_path: Where to save the HTML file.

    Returns:
        Path to the saved HTML file.
    """
    if not _ensure_plotly():
        return ""

    try:
        import yfinance as yf
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        return ""

    indicators = indicators or []
    cfg = load_config()

    console.print(f"[dim]Fetching {ticker} data ({period})…[/dim]")
    data = yf.download(ticker, period=period, progress=False)
    if data.empty:
        console.print(f"[red]No data found for {ticker}[/red]")
        return ""

    # Flatten multi-level columns
    if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
        data.columns = data.columns.get_level_values(0)

    has_volume = "volume" in indicators
    rows = 2 if has_volume else 1
    row_heights = [0.7, 0.3] if has_volume else [1.0]

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Main chart
    if chart_type == "candlestick":
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name=ticker,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["Close"],
            mode="lines", name=ticker,
            line=dict(color="#2196F3", width=2),
        ), row=1, col=1)

    # Indicators
    colors = {"sma20": "#FF9800", "sma50": "#9C27B0", "ema20": "#00BCD4"}
    for ind in indicators:
        if ind == "sma20":
            sma = data["Close"].rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=data.index, y=sma, mode="lines",
                name="SMA 20", line=dict(color=colors["sma20"], width=1),
            ), row=1, col=1)
        elif ind == "sma50":
            sma = data["Close"].rolling(50).mean()
            fig.add_trace(go.Scatter(
                x=data.index, y=sma, mode="lines",
                name="SMA 50", line=dict(color=colors["sma50"], width=1),
            ), row=1, col=1)
        elif ind == "ema20":
            ema = data["Close"].ewm(span=20).mean()
            fig.add_trace(go.Scatter(
                x=data.index, y=ema, mode="lines",
                name="EMA 20", line=dict(color=colors["ema20"], width=1),
            ), row=1, col=1)
        elif ind == "bb":
            sma = data["Close"].rolling(20).mean()
            std = data["Close"].rolling(20).std()
            fig.add_trace(go.Scatter(
                x=data.index, y=sma + 2 * std, mode="lines",
                name="BB Upper", line=dict(color="gray", width=1, dash="dash"),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=data.index, y=sma - 2 * std, mode="lines",
                name="BB Lower", line=dict(color="gray", width=1, dash="dash"),
                fill="tonexty", fillcolor="rgba(128,128,128,0.1)",
            ), row=1, col=1)

    # Volume
    if has_volume and "Volume" in data.columns:
        vol_colors = ["#26a69a" if c >= o else "#ef5350"
                      for c, o in zip(data["Close"], data["Open"])]
        fig.add_trace(go.Bar(
            x=data.index, y=data["Volume"],
            name="Volume", marker_color=vol_colors, opacity=0.5,
        ), row=2, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    # Layout
    price = data["Close"].iloc[-1]
    fig.update_layout(
        title=f"<b>PACIFIC</b> — {ticker} Interactive Chart ({period.upper()}) · ${price:,.2f}",
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=700,
        margin=dict(l=60, r=30, t=80, b=40),
        font=dict(family="Menlo, monospace", size=12),
    )
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)

    # Save
    if not output_path:
        out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"{ticker}_interactive_{ts}.html")

    fig.write_html(output_path, include_plotlyjs=True)
    console.print(f"[green]✓ Interactive chart saved:[/green] {output_path}")

    # Open in browser
    os.system(f"open '{output_path}' 2>/dev/null || xdg-open '{output_path}' 2>/dev/null &")
    console.print("[dim]Opened in browser.[/dim]")

    return output_path


def interactive_comparison(
    tickers: List[str],
    period: str = "1y",
    normalize: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """Generate an interactive HTML comparison chart and open in browser."""
    if not _ensure_plotly():
        return ""

    try:
        import yfinance as yf
        import plotly.graph_objects as go
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        return ""

    cfg = load_config()
    fig = go.Figure()

    colors = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0",
              "#00BCD4", "#FF5722", "#795548", "#607D8B", "#CDDC39"]

    for i, ticker in enumerate(tickers):
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            continue
        close = data["Close"].squeeze()
        if normalize:
            close = (close / close.iloc[0]) * 100
        fig.add_trace(go.Scatter(
            x=close.index, y=close.values,
            mode="lines", name=ticker,
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig.update_layout(
        title=f"<b>PACIFIC</b> — {'Normalized ' if normalize else ''}Comparison ({period.upper()})",
        template="plotly_dark",
        yaxis_title="Indexed (100)" if normalize else "Price ($)",
        xaxis_title="Date",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600,
        margin=dict(l=60, r=30, t=80, b=40),
        font=dict(family="Menlo, monospace", size=12),
        hovermode="x unified",
    )

    if not output_path:
        out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(out_dir / f"comparison_interactive_{ts}.html")

    fig.write_html(output_path, include_plotlyjs=True)
    console.print(f"[green]✓ Interactive comparison saved:[/green] {output_path}")

    os.system(f"open '{output_path}' 2>/dev/null || xdg-open '{output_path}' 2>/dev/null &")
    console.print("[dim]Opened in browser.[/dim]")

    return output_path


def html_report(
    title: str,
    content: str,
    output_path: Optional[str] = None,
) -> str:
    """Generate a styled HTML report and open in browser.

    Args:
        title: Report title.
        content: Markdown-like content (will be rendered as HTML).

    Returns:
        Path to saved HTML file.
    """
    import re
    cfg = load_config()

    # Convert markdown-ish content to HTML
    html_body = content
    # Headings
    html_body = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html_body, flags=re.MULTILINE)
    # Bold/italic
    html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_body)
    html_body = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html_body)
    # Code
    html_body = re.sub(r"`(.+?)`", r"<code>\1</code>", html_body)
    # Bullets
    html_body = re.sub(r"^- (.+)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html_body, flags=re.DOTALL)
    # Paragraphs
    html_body = re.sub(r"\n\n", "</p><p>", html_body)
    html_body = f"<p>{html_body}</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PACIFIC — {title}</title>
<style>
  body {{
    background: #0d1117; color: #c9d1d9; font-family: 'Menlo', 'Consolas', monospace;
    max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.7;
  }}
  h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
  h2 {{ color: #79c0ff; }}
  h3 {{ color: #a5d6ff; }}
  strong {{ color: #f0f6fc; }}
  code {{ background: #161b22; padding: 2px 6px; border-radius: 4px; color: #ff7b72; }}
  ul {{ padding-left: 24px; }}
  li {{ margin-bottom: 4px; }}
  .header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }}
  .header h1 {{ margin: 0; border: none; }}
  .meta {{ color: #8b949e; font-size: 0.85em; }}
  hr {{ border: 0; border-top: 1px solid #30363d; margin: 24px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>🌊 PACIFIC</h1>
</div>
<p class="meta">Elite Financial Intelligence · {datetime.now().strftime('%B %d, %Y %H:%M')}</p>
<hr>
<h1>{title}</h1>
{html_body}
<hr>
<p class="meta">Generated by PACIFIC CLI v1.0 · pacific.grrn.io</p>
</body>
</html>"""

    if not output_path:
        out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.lower().replace(" ", "_")[:30]
        output_path = str(out_dir / f"pacific_{safe_title}_{ts}.html")

    with open(output_path, "w") as f:
        f.write(html)

    console.print(f"[green]✓ HTML report saved:[/green] {output_path}")
    os.system(f"open '{output_path}' 2>/dev/null || xdg-open '{output_path}' 2>/dev/null &")
    console.print("[dim]Opened in browser.[/dim]")

    return output_path
