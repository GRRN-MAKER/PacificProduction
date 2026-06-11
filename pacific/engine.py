"""PACIFIC — AI inference engine powered by GRRN

Core engine: streams responses from the Pacific vLLM server via the
OpenAI-compatible /v1/chat/completions endpoint using raw `requests`
(the openai SDK is blocked by Cloudflare on this endpoint).
"""

import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, List

import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.syntax import Syntax
from rich.spinner import Spinner
from rich.table import Table

from pacific.config import get_api_key, load_config
from pacific.output.math_render import format_response

console = Console()

# ── System prompt ────────────────────────────────────────────────────

PACIFIC_SYSTEM_PROMPT = """You are PACIFIC — an elite quantitative financial intelligence system and Wall Street–grade analyst. You run inside a professional terminal workstation used by traders, quants, and portfolio managers.

## Core Competencies

### Quantitative Finance & Math
- Options pricing: Black-Scholes, Binomial trees, Monte Carlo, finite differences
- Greeks: Delta, Gamma, Theta, Vega, Rho — derivations and intuition
- Risk: VaR, CVaR, Expected Shortfall, stress testing, scenario analysis
- Portfolio theory: Markowitz, Black-Litterman, risk-parity, factor models (Fama-French)
- Stochastic calculus: Itô's lemma, Brownian motion, GBM, mean-reversion (OU)
- Fixed income: Bond pricing, duration, convexity, DV01, yield curves, OAS
- Derivatives: Futures, swaps, exotic options, structured products, CDS

### Market Analysis
- Technical: RSI, MACD, Bollinger Bands, Ichimoku, Fibonacci, Elliott Wave, candlestick patterns
- Fundamental: DCF, EV/EBITDA, P/E, PEG, DuPont analysis, Altman Z-score
- Macro: Yield curve dynamics, FX carry, commodity cycles, central bank policy
- Sector rotation, momentum, mean reversion, stat arb, pairs trading
- Market microstructure: order flow, bid-ask spread, market impact

### Code Generation
- Python: pandas, numpy, scipy, statsmodels, sklearn, PyTorch/TensorFlow for ML-finance
- Backtesting frameworks: backtrader, Zipline, vectorbt, custom engines
- SQL for financial databases, R for econometrics, Pine Script for TradingView
- API integration: Bloomberg, Refinitiv, Alpaca, Interactive Brokers, Binance

### Chart Reading & Interpretation
- Identify patterns: head & shoulders, wedges, triangles, flags, cups
- Read candlestick patterns: doji, hammer, engulfing, shooting star, morning star
- Interpret volume, open interest, and order book depth
- Spot divergences, breakouts, support/resistance levels

### Trading & Execution
- Algorithmic strategies: momentum, mean reversion, market making, HFT concepts
- Order types and execution algos: TWAP, VWAP, implementation shortfall
- Risk management: position sizing, Kelly criterion, stop-loss strategies
- Crypto, equities, FX, commodities, options

## Output Format
- Use clean markdown with clear sections
- For math: use LaTeX notation — wrap block equations in $$ ... $$ and inline math in $ ... $
- Write every formula explicitly using LaTeX: \\frac{}{}, \\sum, \\int, \\Sigma, \\alpha, \\beta, ^{}, _{}, \\sqrt{}, \\text{}, \\left( \\right), etc.
- For code: produce production-quality, runnable Python with proper imports
- For analysis: lead with an executive summary, then detail
- Use financial notation: M=millions, B=billions, bps=basis points
- For recommendations: always state assumptions, confidence level, and key risks
- Numbers: 2 decimal places for prices, 4 for rates, proper thousands separators

## Output Generation Capabilities
When the user asks you to generate charts, graphs, Excel files, PDFs, or any visual/document output, produce COMPLETE, RUNNABLE Python code that:
1. Creates the output file in the current directory or a specified path
2. Uses matplotlib/plotly for charts, openpyxl for Excel, fpdf2/reportlab for PDFs
3. Includes all necessary imports and error handling
4. Prints the output file path when done

## MARKET DATA DISPLAY FORMAT

When you receive [LIVE MARKET DATA] context, ALWAYS start your response with a compact ticker board.
Use this exact format — dense, scannable, one line per asset, aligned columns:

```
═══════════════ MARKET BOARD ═══════════════
 S&P 500     7,269.02  ▲  +2.03  (+0.03%)
 Dow Jones  50,154.81  ▲ +235.43  (+0.47%)
 NASDAQ     25,189.86  ▲ +20.36   (+0.08%)
 Russell     2,862.93  ▲ +27.55   (+0.97%)
 VIX            21.72  ▼  -0.50   (-2.25%)
 10Y Yield       4.54% ─  +0.00   (+0.00%)
 Gold        4,096.30  ▼ -11.90   (-0.29%)
 Oil WTI        90.65  ▲  +0.62   (+0.69%)
 Bitcoin    62,338.00  ▲ +891.45  (+1.45%)
 Ethereum    1,632.77  ▲ +12.62   (+0.78%)
═════════════════════════════════════════════
```

After the compact board, add a brief 2-3 sentence analyst take. Keep it tight.
If the user asks for deeper analysis, THEN expand with full commentary.
The board should always be the FIRST thing shown — instant, at-a-glance data.

For individual stock queries (e.g., $NVDA), use a similar compact card:
```
═══ NVDA — NVIDIA Corp ══════════════════
 Price      $131.28  ▲ +2.45 (+1.90%)
 MCap       $3,225.1B   P/E  62.3
 52W Range  $75.61 – $153.13
 Volume     45,231,800
═════════════════════════════════════════
```

## CRITICAL RULES — READ CAREFULLY

1. You are a FINANCIAL ANALYST, not a coding assistant. When a user asks about stocks, markets, or financial topics — give them ANALYSIS, not code. Do NOT generate Python scripts, simulations, or "live stream" code unless the user explicitly asks for code.

2. The PACIFIC terminal has its own built-in Yahoo Finance integration that fetches real-time data separately. You do NOT need to write code to fetch data. Just provide your expert financial analysis directly.

3. NEVER say "I cannot access real-time market feeds" or "simulated" or "for demonstration purposes." You are a Wall Street analyst — give your analysis based on your knowledge of markets, fundamentals, technicals, and macro conditions.

4. When asked about a stock (e.g., "tell me about NVDA"), respond with:
   - Your analytical assessment of the company and stock
   - Key metrics, valuation, technicals from your training knowledge
   - Bull/bear thesis, catalysts, risks
   - DO NOT output code. DO NOT say "simulated." Just analyze.

5. Only generate code when the user explicitly says things like "write me a script", "generate code", "build a backtest", etc.

## Behavioral Guidelines
- Be precise, quantitative, and evidence-based — not vague
- Always contextualize: vs. sector, vs. historical, vs. peers
- Never guarantee returns; always frame risks
- For code tasks (only when asked): include error handling and make it immediately runnable
- For charts: describe what you see objectively, then interpret
- When asked about specific stocks or market conditions, provide detailed analytical commentary in markdown — NOT code

You are operating in a CLI environment. Keep outputs clean and terminal-friendly. Use markdown that renders well in a rich terminal."""


# ── Client ───────────────────────────────────────────────────────────

def _get_api_params() -> tuple:
    """Return (base_url, api_key, model_name) from config."""
    cfg = load_config()
    key = get_api_key()
    if not key:
        console.print(
            Panel(
                "[bold red]Not signed in.[/bold red]\n\n"
                "  Sign in:    [cyan]pacific login[/cyan]\n"
                "  Register:   [cyan]pacific register[/cyan]\n\n"
                "Or set a key manually:\n"
                "  [cyan]pacific config set-key YOUR_KEY[/cyan]",
                title="[bold red]⚠ Authentication Required[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)

    # Windows Store licensed users → route through gateway without pac_ key
    # The gateway will accept Store-validated requests
    if key == "store_licensed":
        from pacific.config import GATEWAY_URL
        base_url = f"{GATEWAY_URL}/api"
        # Use a Store-license header instead of pac_ key
        # The gateway recognizes "store_licensed" and validates via MS Store APIs
        model = cfg.get("model_name", "pacific")
        return base_url, key, model

    # Gateway keys (pac_*) route through the auth gateway
    # Direct keys route to vLLM server
    if key.startswith("pac_"):
        from pacific.config import GATEWAY_URL
        base_url = f"{GATEWAY_URL}/api"  # gateway proxies to vLLM
    else:
        base_url = cfg.get("api_base_url", "https://pacific.grrn.io/v1")

    model = cfg.get("model_name", "pacific")
    return base_url, key, model


# ── Streaming response ───────────────────────────────────────────────

def stream_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    system: Optional[str] = None,
    image_path: Optional[str] = None,
    enable_thinking: Optional[bool] = None,
) -> str:
    """Stream a response from Pacific with live terminal output. Returns full text."""
    base_url, api_key, model = _get_api_params()
    cfg = load_config()
    system_prompt = system or PACIFIC_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(list(history or []))

    # Build user content
    if image_path:
        img_data = _encode_image(image_path)
        ext = Path(image_path).suffix.lower()
        media_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(ext, "image/png")
        content = [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_data}"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    messages.append({"role": "user", "content": content})

    if enable_thinking is None:
        enable_thinking = cfg.get("enable_thinking", False)

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": cfg.get("max_tokens", 4096),
        "temperature": cfg.get("temperature", 0.7),
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        console.print("[bold red]✗ Cannot reach Pacific server[/bold red]")
        return ""
    except requests.exceptions.HTTPError as e:
        console.print(f"[bold red]✗ HTTP {e.response.status_code}:[/bold red] {e.response.text[:200]}")
        return ""

    full_text = ""
    thinking_done = False
    think_start = None
    in_thinking = bool(enable_thinking)
    if in_thinking:
        think_start = time.time()
    console.print()

    # ── Phase 1: Thinking (uses Live — small fixed widget) ──────────
    if in_thinking:
        live = Live(Text(""), refresh_per_second=12, console=console)
        live.start()
    else:
        # Show a purple loading spinner while waiting for first token
        _spinner = Spinner("dots", text="[bold bright_magenta]Pacific is working...[/bold bright_magenta]", style="bold bright_magenta")
        live = Live(_spinner, refresh_per_second=12, console=console)
        live.start()

    # ── Incremental print state for response phase ──────────────────
    line_buffer = ""         # partial line accumulator
    in_code_block = False    # track if we're inside ```
    response_started = False # have we started printing response?

    for line in resp.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            data = decoded[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if not token:
                    continue

                full_text += token

                # ── Detect </think> end-of-thinking ──
                if "</think>" in full_text and in_thinking:
                    in_thinking = False
                    thinking_done = True
                    elapsed = time.time() - think_start if think_start else 0
                    if live:
                        live.stop()
                        live = None
                    _print_thinking_badge(elapsed)
                    # Grab any text after </think> in this chunk
                    after = full_text.split("</think>", 1)[-1]
                    # Strip leading whitespace/newlines once
                    after = after.lstrip("\n\r ")
                    if after:
                        line_buffer += after
                        response_started = True
                    continue

                # Also detect explicit <think> opening (just in case)
                if "<think>" in full_text and not in_thinking and not thinking_done:
                    in_thinking = True
                    think_start = time.time()
                    if not live:
                        live = Live(Text(""), refresh_per_second=12, console=console)
                        live.start()

                if in_thinking:
                    # ── Spinner + preview in Live widget ──
                    elapsed = time.time() - think_start if think_start else 0
                    partial = re.sub(r"^<think>", "", full_text).strip()
                    display = _build_thinking_display(elapsed, partial)
                    if live:
                        live.update(display)
                else:
                    # ── Incremental response printing ──
                    # Just append the NEW token — never re-derive from full_text
                    if not response_started:
                        # First real token — stop the loading spinner
                        if live and not in_thinking:
                            live.stop()
                            live = None
                        # First token of response (no thinking mode)
                        # Skip leading newlines
                        token = token.lstrip("\n\r")
                        if not token:
                            continue
                        response_started = True

                    line_buffer += token

                    # Flush complete lines (delimited by \n)
                    while "\n" in line_buffer:
                        line_part, line_buffer = line_buffer.split("\n", 1)
                        _flush_line(line_part, in_code_block)
                        # Track code block state
                        if line_part.strip().startswith("```"):
                            in_code_block = not in_code_block

            except json.JSONDecodeError:
                pass

    # ── Flush remaining buffer ──
    if live:
        live.stop()
    if line_buffer.strip():
        _flush_line(line_buffer, in_code_block)

    console.print()
    return full_text


# ── Incremental output helpers ───────────────────────────────────────

def _flush_line(line: str, in_code: bool):
    """Render and print a single line of response with proper formatting."""
    if not line and not in_code:
        console.print()
        return

    # Inside code blocks: print raw with monospace styling
    if in_code:
        if line.strip().startswith("```"):
            console.print(f"[dim]{line}[/dim]")
        else:
            console.print(f"  [green]{line}[/green]")
        return

    # Code block delimiters
    if line.strip().startswith("```"):
        console.print(f"[dim]{line}[/dim]")
        return

    # Render math in the line
    rendered = format_response(line)

    # Headings
    if rendered.startswith("# "):
        console.print(f"\n[bold underline cyan]{rendered[2:]}[/bold underline cyan]")
    elif rendered.startswith("## "):
        console.print(f"\n[bold cyan]{rendered[3:]}[/bold cyan]")
    elif rendered.startswith("### "):
        console.print(f"[bold]{rendered[4:]}[/bold]")
    elif rendered.startswith("#### "):
        console.print(f"[bold dim]{rendered[5:]}[/bold dim]")
    # Horizontal rules
    elif rendered.strip() in ("---", "***", "___"):
        console.print("[dim]" + "─" * min(console.width, 80) + "[/dim]")
    # Bullet points
    elif re.match(r"^\s*[-*]\s", rendered):
        indent = len(rendered) - len(rendered.lstrip())
        bullet_text = rendered.lstrip()[2:]
        pad = " " * indent
        # Bold text in bullets
        bullet_text = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", bullet_text)
        console.print(f"{pad} • {bullet_text}")
    # Numbered lists
    elif re.match(r"^\s*\d+\.\s", rendered):
        rendered = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", rendered)
        console.print(f" {rendered}")
    # Block equations (already rendered by math_render into box form)
    elif rendered.strip().startswith("┌"):
        console.print(f"[cyan]{rendered}[/cyan]")
    elif rendered.strip().startswith("│"):
        console.print(f"[cyan]{rendered}[/cyan]")
    elif rendered.strip().startswith("└"):
        console.print(f"[cyan]{rendered}[/cyan]")
    else:
        # Normal text — handle inline bold/italic
        rendered = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", rendered)
        rendered = re.sub(r"\*(.+?)\*", r"[italic]\1[/italic]", rendered)
        rendered = re.sub(r"`(.+?)`", r"[cyan]\1[/cyan]", rendered)
        console.print(rendered)


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> blocks from display text."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ── Thinking display helpers ─────────────────────────────────────────

_THINK_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_think_frame_idx = 0


def _build_thinking_display(elapsed: float, partial_thinking: str) -> Text:
    """Build a live 'thinking' indicator with elapsed time and preview."""
    global _think_frame_idx
    _think_frame_idx = (_think_frame_idx + 1) % len(_THINK_FRAMES)
    spinner = _THINK_FRAMES[_think_frame_idx]

    # Truncate thinking preview to last ~120 chars
    preview = partial_thinking.replace("\n", " ").strip()
    if len(preview) > 120:
        preview = "…" + preview[-117:]

    result = Text()
    result.append(f"\n {spinner} ", style="bold bright_magenta")
    result.append("Pacific is thinking", style="bold bright_magenta")
    result.append(f"  {elapsed:.1f}s\n", style="dim bright_magenta")

    if preview:
        result.append(" │ ", style="dim bright_magenta")
        result.append(preview, style="dim italic")
        result.append("\n")

    # Progress bar based on elapsed time (cosmetic, caps at 60s)
    bar_width = 30
    fill = min(int((elapsed / 60) * bar_width), bar_width)
    bar = "█" * fill + "░" * (bar_width - fill)
    result.append(f" [{bar}]", style="dim bright_magenta")

    return result


def _print_thinking_badge(elapsed: float):
    """Print the 'done thinking' badge directly to terminal."""
    badge = Text()
    badge.append("\n ✓ ", style="bold green")
    badge.append("Thought for ", style="dim")
    badge.append(f"{elapsed:.1f}s", style="bold bright_magenta")
    badge.append("\n")
    console.print(badge)


# ── Convenience functions ────────────────────────────────────────────

def single_query(prompt: str, image_path: Optional[str] = None) -> str:
    """One-shot query — no conversation history."""
    return stream_response(prompt, image_path=image_path)


def analyze_image(image_path: str, context: str = "") -> str:
    """Analyze a financial chart or image."""
    prompt = (
        f"{context}\n\nAnalyze this financial chart in detail:\n"
        "1. **Pattern Recognition**: Identify chart patterns (H&S, wedges, triangles, flags)\n"
        "2. **Candlestick Patterns**: Note significant candlestick formations\n"
        "3. **Trend Analysis**: Primary trend direction, strength, and momentum\n"
        "4. **Key Levels**: Support, resistance, pivot points\n"
        "5. **Indicators**: If visible, interpret RSI, MACD, Bollinger Bands, volume\n"
        "6. **Trading Signals**: Bullish/bearish signals, potential entry/exit zones\n"
        "7. **Risk Assessment**: Risk/reward for the current setup\n"
        "8. **Outlook**: Short-term (days), medium-term (weeks) price forecast"
    ) if not context else context
    return stream_response(prompt, image_path=image_path)


def _encode_image(path: str) -> str:
    """Base64-encode an image file."""
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")
