# 🌊 Pacific CLI

**Elite Quantitative Financial AI — from your terminal.**

Pacific is a 9B parameter model purpose-built for quantitative finance. Real-time analysis, sentiment classification, portfolio optimization, market data, charting, and risk management — all through a powerful CLI with 22 commands and 15+ interactive slash commands.

## Get Pacific

**Download from [grrn.io/pacific](https://grrn.io/pacific)** — 7-day free trial, then $40/month via Stripe.

## Quick Start

```bash
# Register (email + OTP verification)
pacific register

# Login (saves API key locally)
pacific login

# Start chatting (interactive mode with slash commands)
pacific chat

# Single query
pacific ask "What's the outlook for tech sector Q3 2026?"

# Financial analysis
pacific analyze "AAPL earnings beat impact"

# Sentiment classification
pacific sentiment "Fed announces surprise rate cut of 50bps"

# Portfolio optimization
pacific portfolio "AAPL 30%, MSFT 25%, BND 45%"

# Stock chart
pacific chart AAPL --period 6mo

# Live price stream
pacific stream AAPL

# Image analysis
pacific image photo.jpg "What does this chart show?"
```

## Commands (22 total)

| Command | Description |
|---------|-------------|
| `pacific chat` | Interactive AI chat with 15+ slash commands |
| `pacific ask "question"` | Single-turn question |
| `pacific analyze "text"` | Deep financial analysis |
| `pacific sentiment "text"` | Classify BULLISH / BEARISH / NEUTRAL |
| `pacific portfolio "holdings"` | Portfolio review & optimization |
| `pacific image <file>` | Vision/image analysis |
| `pacific chart <ticker>` | Candlestick chart with indicators |
| `pacific compare T1 T2 ...` | Multi-stock comparison chart |
| `pacific quote <ticker>` | Quick stock quote |
| `pacific stream <ticker>` | Live price stream in terminal |
| `pacific market` | Market overview (major indices) |
| `pacific info <ticker>` | Company information |
| `pacific excel <ticker>` | Export stock data to Excel |
| `pacific pdf <ticker>` | Export analysis to PDF |
| `pacific json <ticker>` | Export stock data to JSON |
| `pacific plans` | View subscription plans |
| `pacific config` | Show/set configuration |
| `pacific health` | Check API connectivity |
| `pacific register` | Create new account |
| `pacific login` | Login + save API key |
| `pacific logout` | Remove saved API key |
| `pacific status` | View subscription status |

## In-Chat Slash Commands

| Command | Action |
|---------|--------|
| `/help` | Show all available commands |
| `/clear` | Clear conversation context |
| `/history` | Show conversation history |
| `/think` | Toggle chain-of-thought reasoning |
| `/export pdf\|json\|excel` | Export last response |
| `/chart <ticker>` | Candlestick stock chart |
| `/compare T1 T2 ...` | Multi-stock comparison |
| `/quote <ticker>` | Quick stock quote |
| `/stream <ticker>` | Live price stream |
| `/file <path>` | Read and analyze a file |
| `/open <path>` | Open file in system viewer |
| `/read <path>` | Display file contents |
| `/image <path>` | Analyze an image |
| `exit` / `quit` | Exit interactive mode |

## Pricing

| | Details |
|---|---|
| **Trial** | 7 days free |
| **Monthly** | $40/month — unlimited tokens |
| **Billing** | Stripe |
| **Rate Limit** | 50 requests/minute |

## Authentication

1. Register with your email — an OTP code is sent for verification
2. Login to receive your personal API key (`pac_...`)
3. API key is saved to `~/.pacific/config.json`
4. Every request authenticates via Bearer token
5. Subscription managed through Stripe (trial → active → expired)

## Configuration

```bash
# Show current settings
pacific config show

# Set API key manually
pacific config set-key pac_your-key-here

# Change API base URL
pacific config api-url https://custom-gateway.example.com

# Set max tokens
pacific config max-tokens 16384

# Enable thinking mode by default
pacific config thinking true

# Reset to defaults
pacific config reset
```

Settings are stored in `~/.pacific/config.json`.

## System Requirements

- Windows 10+ or macOS 12+
- Internet connection
- Python 3.10+ (if installing from source)

## License

Proprietary — © GRRN. All rights reserved.
