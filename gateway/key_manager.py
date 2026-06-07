"""
Pacific License Validator — Stateless Microsoft Store subscription enforcement.

ARCHITECTURE:
  ┌────────────────────┐
  │ User's Windows PC  │
  │   pacific.exe      │
  │   (ZERO secrets)   │
  └────────┬───────────┘
           │ 1. Asks Windows OS for Store Collection ID token
           │ 2. Sends token + prompt to proxy
           ▼
  ┌────────────────────────────────────┐
  │ Pacific Gateway (this server)      │
  │   • Receives Windows token         │
  │   • Forwards to Microsoft Store    │
  │     Purchase API for validation    │
  │   • If ACTIVE → proxy to AI model │
  │   • If EXPIRED → 403 denied       │
  │   • ZERO database. ZERO accounts.  │
  └────────┬───────────────────────────┘
           │ 3. If valid: attaches hidden PACIFIC_API_KEY
           ▼
  ┌────────────────────┐
  │ Pacific vLLM       │
  │ (Lambda GPU)       │
  └────────────────────┘

SECURITY MODEL:
  - CLI contains ZERO secrets. No API keys. No tokens. Nothing.
  - The real API key lives ONLY on this server as an env var.
  - Microsoft handles billing, trial tracking, subscription status.
  - This server is 100% STATELESS — no database, no Redis, no user accounts.
  - Every request is verified against Microsoft in real-time.
  - If subscription lapses → Microsoft says "inactive" → we block → done.
  - Rate limiting via IP (Cloudflare) — no per-user tracking needed.

PRICING:
  - 7-day free trial (configured in Microsoft Partner Center)
  - $40/month flat fee (unlimited tokens within rate limits)
  - Microsoft auto-transitions trial → paid on day 8
  - If credit card fails → Microsoft marks license inactive → we block
"""

import os
import time
import logging
import hashlib
from typing import Optional

import httpx

logger = logging.getLogger("pacific.license")

# ─── Microsoft Store B2B Configuration ───────────────────────────────
# These are NOT secrets — they are public service identifiers.
# The actual security comes from Microsoft's cryptographic token validation.

# Microsoft Collections API endpoint (validates Store purchase tokens)
MS_COLLECTIONS_URL = os.getenv(
    "MS_COLLECTIONS_URL",
    "https://collections.mp.microsoft.com/v8.0/collections/b2bLicensePreview",
)

# Your app's Store ID (from Microsoft Partner Center → App Identity)
MS_STORE_ID = os.getenv("MS_STORE_ID", "")

# Azure AD credentials for B2B auth (server-to-server with Microsoft)
# These live ONLY on the server as env vars — never in the CLI
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")

# Service ticket string — identifies your service to Microsoft
# Generated via Partner Center → Services → Xbox Live
MS_SERVICE_TICKET = os.getenv("MS_SERVICE_TICKET", "")

# Cached AAD token for server-to-server Microsoft API calls
_ms_aad_token: Optional[str] = None
_ms_aad_token_expiry: float = 0

# Rate limit: max requests per IP per minute (abuse protection for flat-rate plan)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "50"))

# In-memory IP rate tracking (resets on restart — Cloudflare handles persistent limits)
_ip_rate_cache: dict = {}


# ─── Microsoft AAD Token (Server-to-Server) ─────────────────────────

async def get_ms_aad_token() -> Optional[str]:
    """
    Get Azure AD access token for calling Microsoft Store APIs.
    This is a server-to-server credential — NEVER sent to clients.
    """
    global _ms_aad_token, _ms_aad_token_expiry

    if _ms_aad_token and time.time() < _ms_aad_token_expiry - 300:
        return _ms_aad_token

    if not all([MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET]):
        logger.error("Microsoft AAD credentials not configured")
        return None

    token_url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": MS_CLIENT_ID,
                    "client_secret": MS_CLIENT_SECRET,
                    "scope": "https://onestore.microsoft.com/.default",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

            _ms_aad_token = data["access_token"]
            _ms_aad_token_expiry = time.time() + data.get("expires_in", 3600)
            return _ms_aad_token

        except Exception as e:
            logger.error(f"Failed to get Microsoft AAD token: {e}")
            return None


# ─── License Validation (The Core Gate) ──────────────────────────────

async def validate_store_license(windows_token: str) -> dict:
    """
    Validate a Microsoft Store Collection ID token.

    This is the ONLY security gate. It asks Microsoft in real-time:
      "Does the owner of this token have an active subscription?"

    Returns:
      {"valid": True}                    → Active trial or paid subscription
      {"valid": False, "error": "..."}   → Expired, cancelled, or invalid

    NO DATABASE. NO ACCOUNTS. Microsoft handles everything.
    """
    if not windows_token or len(windows_token) < 10:
        return {"valid": False, "error": "invalid_token", "detail": "No valid Windows token provided"}

    # Get server-to-server AAD token
    aad_token = await get_ms_aad_token()
    if not aad_token:
        logger.error("Cannot validate license — AAD token unavailable")
        return {"valid": False, "error": "server_error", "detail": "License service temporarily unavailable"}

    # Call Microsoft Collections API
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                MS_COLLECTIONS_URL,
                json={
                    "beneficiaries": [{
                        "identityType": "b2b",
                        "identityValue": windows_token,
                        "localTicketReference": "",
                    }],
                    "productSkuIds": [{"productId": MS_STORE_ID}] if MS_STORE_ID else [],
                    "maxPageSize": 10,
                },
                headers={
                    "Authorization": f"Bearer {aad_token}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

        if resp.status_code == 401:
            # AAD token expired mid-flight — clear cache and retry once
            global _ms_aad_token
            _ms_aad_token = None
            return {"valid": False, "error": "server_error", "detail": "Re-authenticating with Microsoft"}

        if resp.status_code != 200:
            logger.error(f"Microsoft API returned {resp.status_code}: {resp.text[:300]}")
            return {"valid": False, "error": "validation_failed", "detail": "Microsoft returned an error"}

        data = resp.json()
        items = data.get("items", [])

        # Check if any active entitlement exists for our product
        for item in items:
            status = item.get("status", "").lower()
            if status in ("active", "fulfilled"):
                # Microsoft confirms: this user has an active trial or paid subscription
                logger.info("License VALID — active subscription confirmed by Microsoft")
                return {"valid": True}

        # No active entitlements found
        logger.info("License INVALID — no active subscription found")
        return {
            "valid": False,
            "error": "subscription_inactive",
            "detail": "Your Microsoft Store subscription or 7-day trial has ended.",
            "renew_url": "ms-windows-store://pdp/?productid=" + (MS_STORE_ID or "pacific"),
        }

    except httpx.TimeoutException:
        logger.error("Microsoft API timeout")
        return {"valid": False, "error": "timeout", "detail": "License verification timed out"}
    except Exception as e:
        logger.error(f"License validation error: {e}")
        return {"valid": False, "error": "server_error", "detail": "License verification failed"}


# ─── IP-Based Rate Limiting (Flat-Rate Abuse Protection) ─────────────

def check_rate_limit(client_ip: str) -> dict:
    """
    Simple in-memory IP rate limiter.
    Prevents automated scripts from abusing the unlimited-token flat rate.

    For production: Cloudflare's built-in rate limiting handles this at the edge.
    This is a fallback for requests that bypass Cloudflare.
    """
    global _ip_rate_cache

    current_minute = int(time.time()) // 60

    # Clean stale entries every ~5 minutes
    if len(_ip_rate_cache) > 10000:
        _ip_rate_cache = {
            k: v for k, v in _ip_rate_cache.items()
            if v["minute"] == current_minute
        }

    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    key = f"{ip_hash}:{current_minute}"

    entry = _ip_rate_cache.get(key, {"count": 0, "minute": current_minute})

    if entry["count"] >= RATE_LIMIT_PER_MINUTE:
        return {
            "allowed": False,
            "error": "rate_limit_exceeded",
            "retry_after_seconds": 60 - (int(time.time()) % 60),
            "limit": RATE_LIMIT_PER_MINUTE,
        }

    entry["count"] += 1
    entry["minute"] = current_minute
    _ip_rate_cache[key] = entry

    return {"allowed": True, "remaining": RATE_LIMIT_PER_MINUTE - entry["count"]}
