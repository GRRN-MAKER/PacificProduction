# 🌊 PACIFIC — Elite Financial Intelligence CLI

> **AI inference engine powered by GRRN** — Wall Street–grade terminal intelligence for traders, quants, and portfolio managers.

## Installation

```bash
cd "/Volumes/EXTERNAL/Elite Financial Intelligence CLI"
pip install -e .
```

## Quick Start

```bash
# Set your API key
pacific config set-key pacific-api-key

# Start chatting
pacific

# One-shot query
pacific ask "Black-Scholes price for AAPL $200 call, 30 days, 25% vol"

# Analyze a chart image
pacific image chart.png

# Generate a stock chart
pacific chart AAPL --period 6mo -i volume -i sma20 -i bb

# Live ticker
pacific ticker AAPL TSLA NVDA MSFT

# Market overview
pacific market

# Quick quote
pacific quote AAPL

# Stock profile
pacific info AAPL

# Export to Excel
pacific excel AAPL --period 1y

# Compare tickers
pacific compare AAPL MSFT GOOGL --period 1y
```

## Chat Commands

| Command | Description |
|---------|-------------|
| `/clear` | Reset conversation history |
| `/history` | Show message count |
| `/think on\|off` | Toggle thinking mode |
| `/image PATH` | Analyze a chart image |
| `/run` | Execute code blocks from last response |
| `/export pdf` | Save last response as PDF |
| `/export excel AAPL` | Export stock data to Excel |
| `/chart AAPL 3mo volume sma20` | Generate a stock chart |
| `/quote AAPL` | Quick stock quote |
| `exit` | End session |

## Capabilities

- **Quantitative Finance**: Black-Scholes, Greeks, VaR, Monte Carlo, portfolio optimization
- **Market Analysis**: Technical indicators, fundamental analysis, macro commentary
- **Code Generation**: Production-quality Python for finance, backtesting, ML
- **Chart Analysis**: Pattern recognition, candlestick interpretation, support/resistance
- **Live Data**: Real-time tickers, quotes, market overview
- **Output Formats**: Charts (PNG), Excel (.xlsx), PDF reports, executable code canvas
- **Trading**: Algorithmic strategies, risk management, execution concepts

## Architecture

```
pacific/
├── __init__.py          # Version & metadata
├── cli.py               # Click CLI entry point
├── chat.py              # Interactive chat REPL
├── config.py            # Configuration management
├── engine.py            # Core AI inference engine
├── output/
│   ├── terminal.py      # Rich terminal rendering
│   ├── charts.py        # matplotlib/mplfinance charts
│   ├── excel.py         # Excel spreadsheet generation
│   ├── pdf.py           # PDF report generation
│   └── canvas.py        # Code execution from AI responses
├── market/
│   ├── ticker.py        # Live stock ticker
│   └── data.py          # Market data & stock info
└── utils/
    └── __init__.py
```

## Powered By

- **Pacific Model** — Qwen3_5 quantized on GRRN infrastructure
- **vLLM** — High-throughput inference at `pacific.grrn.io`
- **Rich** — Beautiful terminal rendering
- **yfinance** — Market data
- **mplfinance** — Professional stock charts

---
*PACIFIC v1.0.0 · GRRN · Markets never sleep. 📈*
