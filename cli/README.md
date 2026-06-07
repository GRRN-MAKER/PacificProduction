# 🌊 Pacific CLI

**Elite Quantitative Financial AI — from your terminal.**

Pacific is a 9B parameter model purpose-built for quantitative finance. Real-time analysis, sentiment classification, portfolio optimization, and risk management — all through a simple CLI.

## Get Pacific

**Available on the Microsoft Store** — 7-day free trial, then $40/month.

Search **"Pacific Financial AI"** in the Microsoft Store, or:

```
ms-windows-store://pdp/?productid=pacific
```

No registration. No accounts. No API keys.
Install → open terminal → start using it. Windows handles everything.

## Quick Start

```bash
# Start chatting (interactive mode)
pacific chat

# Single query
pacific "What's the outlook for tech sector Q3 2026?"

# With chain-of-thought reasoning
pacific chat --think "Analyze macro headwinds for small caps"

# Financial analysis
pacific analyze "AAPL earnings beat impact" --ticker AAPL --timeframe 1D

# Sentiment classification
pacific sentiment "Fed announces surprise rate cut of 50bps"

# Portfolio optimization
pacific portfolio --holdings "AAPL 30%, MSFT 25%, BND 45%" --risk moderate
```

## Commands

| Command | Description |
|---------|-------------|
| `pacific [message]` | Quick single query |
| `pacific chat [message]` | Interactive chat or single query |
| `pacific analyze [query]` | Detailed financial analysis |
| `pacific sentiment [text]` | Classify BULLISH / BEARISH / NEUTRAL |
| `pacific portfolio` | Portfolio optimization & risk metrics |
| `pacific plans` | Show pricing info |
| `pacific config` | Configure CLI preferences |
| `pacific health` | Check server status |

## Pricing

| | Details |
|---|---|
| **Trial** | 7 days free |
| **Monthly** | $40/month — unlimited tokens |
| **Platform** | Microsoft Store |
| **Rate Limit** | 50 requests/minute |

Subscribe and manage your subscription entirely through the Microsoft Store.

## How Authentication Works

Pacific uses **zero-knowledge, stateless authentication**:

1. You install Pacific from the Microsoft Store
2. Windows generates a cryptographically signed license token
3. Every request sends this token to the Pacific proxy
4. The proxy verifies with Microsoft in real-time: "Is this subscription active?"
5. If YES → your query is processed. If NO → you're told to renew.

**No accounts. No passwords. No API keys. No database.**
Your queries are never stored or logged.

## Configuration

```bash
# Show current settings
pacific config

# Change proxy URL (advanced)
pacific config --proxy-url https://custom-proxy.example.com

# Set default max tokens
pacific config --max-tokens 16384

# Enable thinking mode by default
pacific config --thinking true
```

Settings are stored in `~/.pacific/config.json` — **zero secrets** are ever saved locally.

## Interactive Mode Shortcuts

| Shortcut | Action |
|----------|--------|
| `/think` | Toggle chain-of-thought reasoning |
| `/clear` | Clear conversation context |
| `/help` | Show available shortcuts |
| `exit` | Exit interactive mode |

## Development

For development on macOS/Linux (where the Windows Store API isn't available):

```bash
export PACIFIC_DEV_TOKEN="your-test-token"
pacific chat "test query"
```

## System Requirements

- Windows 10 or later
- Microsoft Store account
- Internet connection

## License

Proprietary — © GRRN. All rights reserved.
