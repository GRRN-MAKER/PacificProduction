"""
Pacific API Gateway — Password/OTP/Subscription authentication.

ARCHITECTURE:
  ┌────────────────────────────────────┐
  │ User's PC (pacific.exe / CLI)      │
  │  • Stores API key in config        │
  │  • Sends key with every request    │
  └──────────────┬─────────────────────┘
                 │
    ── Cloudflare Tunnel (HTTPS) ──
                 │
  ┌──────────────▼─────────────────────┐
  │ This Server (FastAPI on :8080)     │
  │  1. Receives API key in header     │
  │  2. Validates key + subscription   │
  │  3. If active → proxy to AI       │
  │  4. If expired → 403              │
  │  • MongoDB for user accounts       │
  │  • Stripe for subscription billing │
  └──────────────┬─────────────────────┘
                 │
  ┌──────────────▼─────────────────────┐
  │ Pacific vLLM (Lambda GPU)          │
  │  • 9B param financial AI           │
  │  • API key lives ONLY on gateway   │
  └────────────────────────────────────┘

AUTH:
  - User registers with email + password
  - Server sends OTP to email for verification
  - Verified user gets API key
  - API key sent in Authorization header
  - Server validates key, checks subscription
  - Stripe handles billing ($40/mo, 7-day trial)
"""

import os
import time
import logging
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

from auth_manager import (
    register_user, verify_otp, login_user, validate_api_key,
    get_subscription_status, forgot_password, reset_password,
    check_rate_limit,
)

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────

PACIFIC_BACKEND_URL = os.getenv("PACIFIC_BACKEND_URL", "https://pacific.grrn.io")
PACIFIC_BACKEND_KEY = os.getenv("PACIFIC_API_KEY", "")
GATEWAY_ADMIN_KEY = os.getenv("GATEWAY_ADMIN_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("pacific.gateway")


# ─── App ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🌊 Pacific Gateway starting (password/OTP/subscription auth)...")
    logger.info(f"   Backend: {PACIFIC_BACKEND_URL}")
    logger.info(f"   API key configured: {'YES' if PACIFIC_BACKEND_KEY else 'NO'}")
    yield
    logger.info("🌊 Pacific Gateway shutting down.")


app = FastAPI(
    title="Pacific API Gateway",
    version="4.0.0",
    description="Auth gateway — password/OTP registration, subscription enforcement, AI proxy.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list = None
    userPrompt: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7
    stream: bool = True
    enable_thinking: bool = False


class RegisterRequest(BaseModel):
    email: str
    password: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


# ─── Helpers ──────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extract real client IP."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )


def get_api_key_from_header(request: Request) -> str:
    """Extract API key from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


# ─── Auth Routes ──────────────────────────────────────────────────────

@app.post("/v1/auth/register", status_code=201)
async def register(payload: RegisterRequest, request: Request):
    """Register new user with email + password. Sends OTP to email."""
    client_ip = get_client_ip(request)

    # Rate limit registration attempts
    rate = check_rate_limit(client_ip, action="register", limit=5, window=3600)
    if not rate["allowed"]:
        raise HTTPException(429, detail="Too many registration attempts. Try again later.")

    result = await register_user(payload.email, payload.password)
    if result.get("error"):
        code = result.get("status_code", 400)
        raise HTTPException(code, detail=result["error"])

    return {"message": "Account created. Check your email for the verification code."}


@app.post("/v1/auth/verify-otp")
async def verify(payload: VerifyOTPRequest):
    """Verify email with OTP code. Returns API key on success."""
    result = await verify_otp(payload.email, payload.otp)
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])

    return {
        "message": "Email verified.",
        "api_key": result.get("api_key", ""),
    }


@app.post("/v1/auth/login")
async def login(payload: LoginRequest, request: Request):
    """Login with email + password. Returns API key + subscription status."""
    client_ip = get_client_ip(request)

    rate = check_rate_limit(client_ip, action="login", limit=10, window=900)
    if not rate["allowed"]:
        raise HTTPException(429, detail="Too many login attempts. Try again later.")

    result = await login_user(payload.email, payload.password)
    if result.get("error"):
        code = result.get("status_code", 401)
        raise HTTPException(code, detail=result["error"])

    return {
        "api_key": result["api_key"],
        "subscription": result.get("subscription", {}),
    }


@app.get("/v1/auth/subscription")
async def subscription_status(request: Request):
    """Check subscription status for authenticated user."""
    api_key = get_api_key_from_header(request)
    if not api_key:
        raise HTTPException(401, detail="Missing API key")

    result = await get_subscription_status(api_key)
    if result.get("error"):
        raise HTTPException(401, detail=result["error"])

    return result


@app.post("/v1/auth/forgot-password")
async def forgot_pw(payload: ForgotPasswordRequest):
    """Send password reset code to email."""
    result = await forgot_password(payload.email)
    # Always return 200 to prevent email enumeration
    return {"message": "If this email exists, a reset code has been sent."}


@app.post("/v1/auth/reset-password")
async def reset_pw(payload: ResetPasswordRequest):
    """Reset password with code."""
    result = await reset_password(payload.email, payload.code, payload.new_password)
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])
    return {"message": "Password reset successfully."}


# ─── Health (Public) ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check."""
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
        "version": "4.0.0",
        "backend_connected": backend_ok,
        "auth_method": "password_otp_subscription",
        "timestamp": time.time(),
    }


# ─── Chat (Main Endpoint) ────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: Request, payload: ChatRequest):
    """
    Main AI endpoint. Requires valid API key + active subscription.
    """
    client_ip = get_client_ip(request)

    # Rate limit
    rate = check_rate_limit(client_ip, action="chat", limit=50, window=60)
    if not rate["allowed"]:
        raise HTTPException(429, detail={
            "error": "Rate limit exceeded.",
            "retry_after_seconds": rate.get("retry_after_seconds", 60),
        })

    # Validate API key + subscription
    api_key = get_api_key_from_header(request)
    if not api_key:
        raise HTTPException(401, detail={
            "error": "missing_key",
            "message": "API key required. Sign in with 'pacific login'.",
        })

    auth_result = await validate_api_key(api_key)
    if not auth_result.get("valid"):
        error = auth_result.get("error", "invalid_key")
        if error == "subscription_expired":
            raise HTTPException(403, detail={
                "error": "subscription_inactive",
                "message": "Your subscription has expired.",
                "subscribe_url": "https://pacific.grrn.io/subscribe",
            })
        raise HTTPException(401, detail={
            "error": error,
            "message": auth_result.get("message", "Invalid API key."),
        })

    # Build AI request
    if payload.messages:
        messages = payload.messages
    else:
        messages = [
            {
                "role": "system",
                "content": "You are Pacific, an elite quantitative financial AI.",
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

    # Proxy to backend
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

            return StreamingResponse(stream_proxy(), media_type="text/event-stream")
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
        raise HTTPException(504, detail="Backend timeout — please retry")
    except httpx.ConnectError:
        raise HTTPException(502, detail="Cannot reach Pacific backend")


# ─── Models (Public) ─────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """List available models."""
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


# ─── Plans (Public) ──────────────────────────────────────────────────

@app.get("/v1/plans")
async def list_plans():
    """Public pricing info."""
    return {
        "pricing": {
            "trial": "7 days free",
            "monthly": "$40/month",
            "annual": "$399/year (save 17%)",
        },
        "features": [
            "Unlimited AI queries",
            "Real-time market data",
            "Chart generation (candlestick, comparison)",
            "PDF/Excel/JSON exports",
            "File analysis (PDF, CSV, code)",
            "Image/chart analysis",
            "Portfolio optimization",
            "Live price streaming",
        ],
        "rate_limit": "50 requests/minute",
        "subscribe_url": "https://pacific.grrn.io/subscribe",
    }
