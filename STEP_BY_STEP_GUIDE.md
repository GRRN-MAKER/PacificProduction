# 🌊 Pacific CLI — Complete Setup Guide

> **End Goal**: Users register with email/password → verify OTP → get 7-day free trial → use Pacific for financial analysis, market data, charting, and AI chat. Paid via Stripe after trial.

---

## Architecture Overview

```
┌────────────────────────────────────────┐
│ User's PC (Windows / macOS)            │
│  pacific.exe / pacific binary          │
│  • 22 commands + 15 slash commands     │
│  • Market data, charts, PDF/Excel      │
│  • Stores API key in ~/.pacific/       │
└────────────┬───────────────────────────┘
             │ HTTPS (Cloudflare)
┌────────────▼───────────────────────────┐
│ Pacific Gateway (FastAPI)              │
│  pacific-gateway.grrn.io               │
│  • Password/OTP auth (MongoDB)         │
│  • Stripe subscription billing         │
│  • Rate limiting per API key           │
│  • Proxies AI requests to backend      │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│ Pacific vLLM (Lambda GPU)              │
│  9B param financial AI                 │
│  pacific.grrn.io                       │
└────────────────────────────────────────┘
```

---

## PHASE 1: Infrastructure Setup

### Step 1.1 — MongoDB
1. Deploy MongoDB (Atlas free tier or self-hosted)
2. Create database: `pacific`
3. Collections auto-created: `users`
4. Note your connection URI for `MONGO_URI`

### Step 1.2 — SMTP (OTP Email)
1. Use Gmail App Password, SendGrid, or any SMTP provider
2. Note: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
3. Set a `SMTP_FROM` address (e.g., `noreply@pacific.grrn.io`)

### Step 1.3 — Stripe (Subscription Billing)
1. Create a Stripe account at **https://stripe.com**
2. Create a product: **Pacific CLI Pro** — $40/month
3. Note your **Secret Key** → `STRIPE_SECRET_KEY`
4. Stripe manages payment, trials, cancellation

---

## PHASE 2: Deploy the Gateway

### Step 2.1 — Server Environment Variables
Set these on your gateway server (Docker, VPS, etc.):

```bash
# Backend AI (Lambda GPU)
PACIFIC_BACKEND_URL=https://pacific.grrn.io
PACIFIC_API_KEY=<your-vllm-api-key>

# MongoDB (user accounts + OTP)
MONGO_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net
MONGO_DB=pacific

# Email (OTP delivery)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@pacific.grrn.io

# Stripe (subscription billing)
STRIPE_SECRET_KEY=sk_live_...

# Admin
GATEWAY_ADMIN_KEY=<random-64-char-token>

# Optional
TRIAL_DAYS=7
RATE_LIMIT_PER_MINUTE=50
```

### Step 2.2 — Deploy with Docker
```bash
cd gateway
docker build -t pacific-gateway .
docker run -d \
  --name pacific-gateway \
  -p 8080:8080 \
  --env-file .env \
  pacific-gateway
```

### Step 2.3 — Cloudflare Tunnel
1. Install cloudflared on your server
2. Create tunnel:
   ```bash
   cloudflared tunnel create pacific-gateway
   ```
3. Route `pacific-gateway.grrn.io` → `localhost:8080`
4. Cloudflare handles HTTPS, DDoS protection, and edge rate limiting

---

## PHASE 3: Build the CLI

### Step 3.1 — Build Python Wheel
```bash
cd cli
pip install build
python -m build
# Creates dist/pacific_cli-1.0.0-py3-none-any.whl
```

### Step 3.2 — Create Executable
```bash
pip install pyinstaller
# Windows:
pyinstaller --onefile --name pacific --console --collect-all pacific_cli entry.py

# macOS:
pyinstaller --onefile --name pacific --console --collect-all pacific_cli pacific_cli/__main__.py
```

### Step 3.3 — Obfuscation (Optional)
```bash
pip install cython
# Compile .py → .so/.pyd with Cython, then bundle with PyInstaller
```

---

## PHASE 4: User Journey

```
1. User downloads pacific.exe from grrn.io/pacific
2. User registers:
   $ pacific register
   → Enter email + password
   → OTP sent to email
   → Verify OTP → 7-day free trial starts
3. User logs in:
   $ pacific login
   → API key saved to ~/.pacific/config.json
4. User chats:
   $ pacific chat
   → Interactive AI chat with slash commands
   → /chart AAPL, /export pdf, /image photo.jpg
5. Day 8: Stripe charges $40/month
6. User cancels via Stripe portal → subscription expires → API blocked
```

---

## PHASE 5: CLI Commands Reference

### Subcommands (22 total)
| Command | Description |
|---------|-------------|
| `pacific chat` | Interactive AI chat with 15+ slash commands |
| `pacific ask "question"` | Single-turn question |
| `pacific analyze "text"` | Deep analysis |
| `pacific sentiment "text"` | Sentiment analysis |
| `pacific portfolio "holdings"` | Portfolio review |
| `pacific image <file>` | Vision/image analysis |
| `pacific chart <ticker>` | Candlestick stock chart |
| `pacific compare T1 T2 ...` | Multi-stock comparison |
| `pacific quote <ticker>` | Quick stock quote |
| `pacific stream <ticker>` | Live price stream |
| `pacific market` | Market overview (indices) |
| `pacific info <ticker>` | Company info |
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

### In-Chat Slash Commands
`/help` `/clear` `/history` `/think` `/export pdf|json|excel` `/chart <ticker>` `/compare T1 T2` `/quote <ticker>` `/stream <ticker>` `/file <path>` `/open <path>` `/read <path>` `/image <path>`

---

## File Structure

```
PacificProduction/
├── STEP_BY_STEP_GUIDE.md          ← This file
├── gateway/
│   ├── Dockerfile
│   ├── requirements.txt           ← fastapi, uvicorn, httpx, motor, bcrypt
│   ├── .env.example               ← Template for required env vars
│   ├── server.py                  ← FastAPI auth proxy (v4.0)
│   └── auth_manager.py            ← User auth (MongoDB, OTP, Stripe)
├── cli/
│   ├── pyproject.toml
│   ├── README.md
│   └── pacific_cli/
│       ├── __init__.py
│       ├── __main__.py            ← Entry point + argparse (22 commands)
│       ├── auth.py                ← Password/OTP/subscription auth
│       ├── client.py              ← API client (Bearer token auth)
│       ├── commands.py            ← All command implementations
│       ├── config.py              ← Configuration + API key storage
│       ├── display.py             ← Terminal formatting + help panel
│       ├── export.py              ← PDF/Excel/JSON export
│       ├── files.py               ← File reading (PDF, CSV, code, text)
│       └── market.py              ← Market data, charts, streaming
└── .github/
    └── workflows/
        └── build-windows.yml      ← GitHub Actions: EXE + MSI + MSIX
```

---

## Security

| Property | Value |
|----------|-------|
| Secrets in CLI binary | **ZERO** |
| Auth method | Email/password + OTP verification |
| API key format | `pac_` + 48-char token |
| Password storage | bcrypt hashed in MongoDB |
| OTP | 6-digit, 10-minute expiry, email delivery |
| Backend key location | Server env var only |
| Rate limiting | Per API key + Cloudflare edge |
| Subscription billing | Stripe (7-day trial → $40/mo) |
| Trial tracking | MongoDB `subscription.trial_end` |
