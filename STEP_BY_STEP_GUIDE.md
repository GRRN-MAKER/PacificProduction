# 🌊 Pacific CLI — Microsoft Store Product: Complete Setup Guide

> **End Goal**: Users find Pacific on the Microsoft Store → Install (7-day free trial) → Open terminal → Use Pacific for financial analysis. No accounts. No API keys. No database.

---

## Architecture Overview

```
┌────────────────────────────────┐
│ User's Windows PC              │
│  pacific.exe (ZERO secrets)    │
│  1. Asks Windows for Store     │
│     Collection ID token        │
│  2. Sends token + prompt       │
└────────────┬───────────────────┘
             │ HTTPS (Cloudflare)
┌────────────▼───────────────────┐
│ Pacific Gateway (FastAPI)      │
│  pacific-gateway.grrn.io       │
│  • Validates token w/ MSFT     │
│  • Attaches hidden API key     │
│  • Proxies to AI backend       │
│  • STATELESS — zero database   │
└────────────┬───────────────────┘
             │
┌────────────▼───────────────────┐
│ Pacific vLLM (Lambda A10 GPU)  │
│  9B param financial AI         │
│  146.235.213.127:8000          │
└────────────────────────────────┘
```

---

## PHASE 1: Microsoft Partner Center Setup

### Step 1.1 — Register as a Microsoft Partner
1. Go to **https://partner.microsoft.com/dashboard**
2. Sign in with your Microsoft account
3. Complete the registration — company name: **GRRN**
4. Accept the App Developer Agreement

### Step 1.2 — Create App Reservation
1. In Partner Center → **Apps and games** → **New product** → **MSIX or PWA app**
2. Reserve name: **Pacific Financial AI**
3. This creates your Product ID (used in `MS_STORE_ID` env var)

### Step 1.3 — Configure Subscription Add-on
1. In your app → **Add-ons** → **New add-on**
2. Type: **Subscription**
3. Product ID: `pacific-monthly`
4. Configure:
   - **Trial period**: 7 days (free)
   - **Price**: $40.00/month
   - **Billing period**: Monthly
   - Microsoft auto-transitions trial → paid on day 8
   - Card fails → subscription becomes inactive

### Step 1.4 — Configure Azure AD for B2B
1. Go to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Register new app: `pacific-gateway-b2b`
3. Note down:
   - **Application (client) ID** → `MS_CLIENT_ID`
   - **Directory (tenant) ID** → `MS_TENANT_ID`
4. Create a client secret → `MS_CLIENT_SECRET`
5. API permissions: Add `https://onestore.microsoft.com/.default`
6. Grant admin consent

### Step 1.5 — Get Service Ticket
1. In Partner Center → **Services** → **Microsoft Store services**
2. Generate a service ticket for B2B license validation
3. This is your `MS_SERVICE_TICKET`

---

## PHASE 2: Deploy the Gateway

### Step 2.1 — Server Environment Variables
Set these on your gateway server (Docker, VPS, etc.):

```bash
# Backend AI (Lambda GPU)
PACIFIC_BACKEND_URL=https://pacific.grrn.io
PACIFIC_API_KEY=<your-vllm-api-key>

# Microsoft Store B2B Auth
MS_STORE_ID=<from-partner-center>
MS_TENANT_ID=<azure-ad-tenant>
MS_CLIENT_ID=<azure-ad-client>
MS_CLIENT_SECRET=<azure-ad-secret>
MS_SERVICE_TICKET=<partner-center-ticket>

# Admin
GATEWAY_ADMIN_KEY=<random-64-char-token>
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

## PHASE 3: Build the CLI Package

### Step 3.1 — Build Python Wheel
```bash
cd cli
pip install build
python -m build
# Creates dist/pacific_cli-1.0.0-py3-none-any.whl
```

### Step 3.2 — Create Windows Executable
```bash
pip install pyinstaller
pyinstaller --onefile --name pacific pacific_cli/__main__.py
# Creates dist/pacific.exe
```

### Step 3.3 — Package as MSIX
1. Use the **MSIX Packaging Tool** (free from Microsoft Store)
2. Package `pacific.exe` into an MSIX bundle
3. Sign with your code signing certificate
4. Upload to Partner Center

---

## PHASE 4: Submit to Microsoft Store

1. In Partner Center → Your app → **Submissions** → **Start submission**
2. Fill in:
   - **Store listing**: Description, screenshots, icon
   - **Pricing**: Free download (subscription handled via add-on)
   - **Packages**: Upload signed MSIX
   - **Age ratings**: Complete questionnaire
3. Submit for certification (~1-3 business days)

---

## PHASE 5: User Journey (What Customers See)

```
1. User searches "Pacific Financial AI" in Microsoft Store
2. User clicks "Install" → "Start free trial" (7-day)
3. pacific.exe is installed on their system
4. User opens terminal:
   $ pacific "What's the outlook for tech sector?"
   → Windows generates signed token
   → Proxy validates with Microsoft
   → Response streams back
5. Day 8: Microsoft auto-charges $40/month
6. User cancels: subscription goes inactive → proxy blocks → done
```

No API keys. No registration. No database. Just works.

---

## File Structure

```
ibm-cloud-product/
├── STEP_BY_STEP_GUIDE.md          ← This file
├── gateway/
│   ├── Dockerfile
│   ├── requirements.txt           ← fastapi, uvicorn, httpx, dotenv, pydantic
│   ├── .env.example               ← Template for required env vars
│   ├── server.py                  ← Stateless FastAPI proxy
│   └── key_manager.py             ← Microsoft Store license validator
├── cli/
│   ├── pyproject.toml
│   ├── README.md
│   └── pacific_cli/
│       ├── __init__.py
│       ├── __main__.py            ← Entry point + argparse
│       ├── client.py              ← API client (sends Windows token)
│       ├── commands.py            ← CLI commands (chat, analyze, etc.)
│       ├── config.py              ← User preferences (ZERO secrets)
│       ├── display.py             ← Terminal formatting
│       └── license.py             ← Windows Store token acquisition
```

---

## Security Guarantees

| Property | Value |
|----------|-------|
| Secrets in CLI binary | **ZERO** |
| User accounts / database | **NONE** |
| API keys in config files | **NONE** |
| Auth method | Windows Store Collection ID token |
| Validation | Real-time with Microsoft Collections API |
| Backend key location | Server env var only |
| Rate limiting | Cloudflare edge + IP-based in-memory |
| Subscription billing | 100% Microsoft Store |
| Trial tracking | 100% Microsoft Partner Center |
