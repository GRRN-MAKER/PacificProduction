"""
Pacific API Gateway — Stateless Microsoft Store license enforcement.

ARCHITECTURE:
  ┌───────────────────────────────────┐
  │ Windows PC (pacific.exe)          │
  │  • Contains ZERO secrets          │
  │  • Asks Windows for Store token   │
  │  • Sends token + prompt to proxy  │
  └──────────────┬────────────────────┘
                 │
    ── Cloudflare Tunnel (HTTPS) ──
                 │
  ┌──────────────▼────────────────────┐
  │ This Server (FastAPI on :8080)    │
  │  1. Receives Windows Store token  │
  │  2. Asks Microsoft: "Active?"     │
  │  3. If YES → attach hidden key    │
  │     → proxy to Pacific vLLM       │
  │  4. If NO → 403 Access Denied     │
  │  • ZERO database                  │
  │  • ZERO user accounts             │
  │  • ZERO stored state              │
  └──────────────┬────────────────────┘
                 │
  ┌──────────────▼────────────────────┐
  │ Pacific vLLM (Lambda A10 GPU)     │
  │  • 9B param financial AI          │
  │  • API key lives ONLY on proxy    │
  └───────────────────────────────────┘

PRICING (configured in Microsoft Partner Center, NOT here):
  • 7-day free trial
  • $40/month flat fee — unlimited tokens
  • Microsoft auto-bills on day 8
  • Card fails → Microsoft marks inactive → we block
"""

import os
import time
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from key_manager import validate_store_license, check_rate_limit

load_dotenv()

# ─── Configuration (server-side secrets — NEVER sent to CLI) ─────────

PACIFIC_BACKEND_URL = os.getenv("PACIFIC_BACKEND_URL", "https://pacific.grrn.io")
PACIFIC_BACKEND_KEY = os.getenv("PACIFIC_API_KEY", "")   # Hidden AI API key for Lambda
GATEWAY_ADMIN_KEY = os.getenv("GATEWAY_ADMIN_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("pacific.gateway")

# ─── App ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🌊 Pacific Gateway starting (stateless, Microsoft Store auth)...")
    logger.info(f"   Backend: {PACIFIC_BACKEND_URL}")
    logger.info(f"   API key configured: {'YES' if PACIFIC_BACKEND_KEY else 'NO'}")
    yield
    logger.info("🌊 Pacific Gateway shutting down.")

app = FastAPI(
    title="Pacific API Gateway",
    version="3.0.0",
    description="Stateless proxy — validates Microsoft Store licenses, proxies to AI backend. Zero database, zero accounts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Model ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Every CLI request sends exactly two things:
      1. windowsToken — cryptographically signed by the local Windows OS
      2. userPrompt   — the user's question / chat messages

    Optional fields control generation behavior.
    NO API keys. NO passwords. NO user IDs.
    """
    windowsToken: str                      # Microsoft Store Collection ID from Windows
    userPrompt: str = ""                   # Single-turn prompt (simple mode)
    messages: list = None                  # Multi-turn conversation (advanced mode)
    max_tokens: int = 8192
    temperature: float = 0.7
    stream: bool = True
    enable_thinking: bool = False


# ─── Helpers ─────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extract real client IP (Cloudflare sets CF-Connecting-IP)."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )


# ─── Routes: Health (Public — no auth) ───────────────────────────────

@app.get("/health")
async def health():
    """Health check — verifies backend AI model connectivity."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{PACIFIC_BACKEND_URL}/v1/models",
                headers={"Authorization": f"Bearer {PACIFIC_BACKEND_KEY}"},
                timeout=5.0,
            )
            backend_ok = resp.status_code == 200
    except Exception:
        backend_ok = False

    return {
        "status": "healthy" if backend_ok else "degraded",
        "service": "Pacific API Gateway",
        "version": "3.0.0",
        "backend_connected": backend_ok,
        "auth_method": "microsoft_store_license",
        "timestamp": time.time(),
    }


# ─── Routes: Chat (Main Endpoint) ────────────────────────────────────

@app.post("/api/chat")
async def chat(request: Request, payload: ChatRequest):
    """
    The ONLY endpoint the CLI calls. Stateless. No accounts. No database.

    Flow:
      1. Extract Windows Store token from request
      2. Ask Microsoft Store API: "Is this user's subscription active?"
      3. If YES → attach hidden PACIFIC_API_KEY → proxy to vLLM backend
      4. If NO  → 403 Access Denied. CLI tells user to renew in Microsoft Store.
    """
    client_ip = get_client_ip(request)

    # ── Step 0: Rate limit (IP-based — prevents flat-rate abuse) ──
    rate_check = check_rate_limit(client_ip)
    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded. Please slow down.",
                "retry_after_seconds": rate_check.get("retry_after_seconds", 60),
            },
        )

    # ── Step 1: Validate Microsoft Store license ──
    license_result = await validate_store_license(payload.windowsToken)

    if not license_result.get("valid"):
        error = license_result.get("error", "unknown")
        detail = license_result.get("detail", "Access denied")
        renew_url = license_result.get("renew_url", "")

        if error == "subscription_inactive":
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "subscription_inactive",
                    "message": detail,
                    "renew_url": renew_url,
                },
            )
        elif error == "invalid_token":
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_token",
                    "message": "Could not verify Windows Store license. Are you running the official app?",
                },
            )
        else:
            # Server-side issue (timeout, config error, etc.)
            logger.error(f"License validation failed: {error} — {detail}")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "license_check_unavailable",
                    "message": "License verification is temporarily unavailable. Please try again.",
                },
            )

    # ── Step 2: Build the AI request ──
    if payload.messages:
        messages = payload.messages
    else:
        messages = [
            {
                "role": "system",
                "content": "You are Pacific, an elite quantitative financial AI. You provide precise, data-driven analysis with institutional-grade insights.",
            },
            {"role": "user", "content": payload.userPrompt},
        ]

    body = {
        "model": "pacific",
        "messages": messages,
        "max_tokens": min(payload.max_tokens, 32768),
        "temperature": payload.temperature,
        "stream": payload.stream,
    }

    if payload.enable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": True}
        body["temperature"] = 0.6
        if body["max_tokens"] < 4096:
            body["max_tokens"] = 4096

    # ── Step 3: Proxy to Pacific backend (hidden key attached HERE) ──
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PACIFIC_BACKEND_KEY}",
    }

    try:
        if body.get("stream", False):
            async def stream_proxy():
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        f"{PACIFIC_BACKEND_URL}/v1/chat/completions",
                        json=body,
                        headers=headers,
                        timeout=120.0,
                    ) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk

            return StreamingResponse(
                stream_proxy(),
                media_type="text/event-stream",
            )
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{PACIFIC_BACKEND_URL}/v1/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=120.0,
                )

            return JSONResponse(content=resp.json(), status_code=resp.status_code)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Backend timeout — please retry")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach Pacific backend")


# ─── Routes: Models (Public) ────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """List available models. Public endpoint for compatibility."""
    return {
        "object": "list",
        "data": [{
            "id": "pacific",
            "object": "model",
            "created": 1717200000,
            "owned_by": "grrn",
            "description": "Pacific V4 — 9B Financial Quantitative Expert",
        }],
    }


# ─── Routes: Pricing Info (Public) ──────────────────────────────────

@app.get("/v1/plans")
async def list_plans():
    """Public — show pricing. Subscription managed entirely by Microsoft Store."""
    return {
        "pricing": {
            "trial": "7 days free",
            "monthly": "$40/month (unlimited tokens)",
            "platform": "Microsoft Store",
        },
        "features": [
            "🌊 Pacific V4 — 9B Financial Quantitative AI",
            "📊 Real-time technical & fundamental analysis",
            "📈 Sentiment classification (BULLISH / BEARISH / NEUTRAL)",
            "💼 Portfolio optimization & risk metrics",
            "🧠 Chain-of-thought reasoning mode",
            "⚡ Streaming responses",
            "🔒 Zero-knowledge architecture — your queries are never stored",
        ],
        "rate_limit": "50 requests/minute (flat rate, unlimited tokens per month)",
        "subscribe_url": "ms-windows-store://pdp/?productid=pacific",
    }


# ─── Routes: Admin ──────────────────────────────────────────────────

@app.get("/admin/health")
async def admin_health(request: Request):
    """Admin: detailed health check including config status."""
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != GATEWAY_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "status": "healthy",
        "version": "3.0.0",
        "auth_method": "microsoft_store_license",
        "database": "none (stateless)",
        "backend_url": PACIFIC_BACKEND_URL,
        "backend_key_set": bool(PACIFIC_BACKEND_KEY),
        "ms_store_configured": bool(os.getenv("MS_STORE_ID")),
        "ms_tenant_configured": bool(os.getenv("MS_TENANT_ID")),
        "cloudflare_tunnel": "pacific-gateway.grrn.io",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
