"""
Pacific Auth Manager — User accounts, OTP, subscription enforcement.

Uses MongoDB for user storage, Stripe for subscription billing,
and SMTP for OTP delivery.

Collections:
  - users: {email, password_hash, api_key, verified, subscription, created_at, ...}
  - otp_codes: {email, code, expires_at, type}

Subscription statuses: trial, active, expired, cancelled
"""

import os
import time
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt

logger = logging.getLogger("pacific.auth")

# ─── Configuration ────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "pacific")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@pacific.grrn.io")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))

# In-memory rate limiting (reset on restart, Cloudflare handles persistent)
_rate_cache: dict = {}

# MongoDB client (lazy init)
_db = None


def _get_db():
    """Get MongoDB database connection (lazy)."""
    global _db
    if _db is None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(MONGO_URI)
            _db = client[MONGO_DB]
            logger.info(f"Connected to MongoDB: {MONGO_DB}")
        except ImportError:
            logger.error("motor not installed: pip install motor")
            raise
    return _db


def _generate_api_key() -> str:
    """Generate a secure API key."""
    return f"pac_{secrets.token_urlsafe(48)}"


def _generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return f"{secrets.randbelow(999999):06d}"


def _hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def _send_otp_email(email: str, code: str, subject: str = "Pacific — Verification Code"):
    """Send OTP code via email."""
    if not SMTP_USER:
        logger.warning(f"SMTP not configured. OTP for {email}: {code}")
        return

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
      <div style="max-width: 400px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
        <h2 style="color: #1B4F72;">🌊 Pacific</h2>
        <p>Your verification code is:</p>
        <div style="background: #1B4F72; color: white; padding: 15px; text-align: center;
                    font-size: 32px; letter-spacing: 8px; border-radius: 5px; font-weight: bold;">
          {code}
        </div>
        <p style="color: #666; font-size: 13px; margin-top: 20px;">
          This code expires in 10 minutes. If you didn't request this, ignore this email.
        </p>
      </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info(f"OTP sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send OTP to {email}: {e}")


# ─── Registration ─────────────────────────────────────────────────────

async def register_user(email: str, password: str) -> dict:
    """Register a new user. Sends OTP for email verification."""
    email = email.lower().strip()

    if len(password) < 8:
        return {"error": "Password must be at least 8 characters.", "status_code": 400}

    db = _get_db()

    # Check if exists
    existing = await db.users.find_one({"email": email})
    if existing:
        if existing.get("verified"):
            return {"error": "Account already exists.", "status_code": 409}
        # Unverified — allow re-registration (update password, resend OTP)

    password_hash = _hash_password(password)
    api_key = _generate_api_key()
    now = datetime.utcnow()

    user_doc = {
        "email": email,
        "password_hash": password_hash,
        "api_key": api_key,
        "verified": False,
        "subscription": {
            "status": "trial",
            "plan": "trial",
            "trial_start": now,
            "trial_end": now + timedelta(days=TRIAL_DAYS),
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
        },
        "created_at": now,
        "updated_at": now,
    }

    await db.users.update_one(
        {"email": email},
        {"$set": user_doc},
        upsert=True,
    )

    # Generate and send OTP
    otp_code = _generate_otp()
    await db.otp_codes.update_one(
        {"email": email, "type": "verify"},
        {"$set": {
            "email": email,
            "code": otp_code,
            "type": "verify",
            "expires_at": now + timedelta(minutes=10),
            "created_at": now,
        }},
        upsert=True,
    )

    await _send_otp_email(email, otp_code, "Pacific — Verify Your Email")

    return {"success": True}


# ─── OTP Verification ─────────────────────────────────────────────────

async def verify_otp(email: str, otp: str) -> dict:
    """Verify email with OTP code. Returns API key on success."""
    email = email.lower().strip()
    db = _get_db()

    otp_doc = await db.otp_codes.find_one({
        "email": email,
        "type": "verify",
        "code": otp,
    })

    if not otp_doc:
        return {"error": "Invalid verification code."}

    if otp_doc.get("expires_at") and otp_doc["expires_at"] < datetime.utcnow():
        return {"error": "Code expired. Request a new one."}

    # Mark user as verified
    user = await db.users.find_one({"email": email})
    if not user:
        return {"error": "Account not found."}

    await db.users.update_one(
        {"email": email},
        {"$set": {"verified": True, "updated_at": datetime.utcnow()}},
    )

    # Remove OTP
    await db.otp_codes.delete_many({"email": email, "type": "verify"})

    return {"api_key": user["api_key"]}


# ─── Login ─────────────────────────────────────────────────────────────

async def login_user(email: str, password: str) -> dict:
    """Authenticate user and return API key + subscription status."""
    email = email.lower().strip()
    db = _get_db()

    user = await db.users.find_one({"email": email})
    if not user:
        return {"error": "Invalid email or password.", "status_code": 401}

    if not _verify_password(password, user["password_hash"]):
        return {"error": "Invalid email or password.", "status_code": 401}

    if not user.get("verified"):
        return {"error": "Email not verified. Check your inbox for the verification code.", "status_code": 403}

    # Check subscription status
    sub = user.get("subscription", {})
    sub_status = _compute_subscription_status(sub)

    return {
        "api_key": user["api_key"],
        "subscription": sub_status,
    }


# ─── API Key Validation ───────────────────────────────────────────────

async def validate_api_key(api_key: str) -> dict:
    """Validate API key and check subscription. Called on every AI request."""
    db = _get_db()

    user = await db.users.find_one({"api_key": api_key})
    if not user:
        return {"valid": False, "error": "invalid_key", "message": "Invalid API key."}

    if not user.get("verified"):
        return {"valid": False, "error": "unverified", "message": "Email not verified."}

    sub = user.get("subscription", {})
    sub_status = _compute_subscription_status(sub)

    if sub_status["status"] == "expired":
        return {"valid": False, "error": "subscription_expired", "message": "Subscription expired."}

    return {"valid": True, "email": user["email"], "subscription": sub_status}


# ─── Subscription Status ──────────────────────────────────────────────

async def get_subscription_status(api_key: str) -> dict:
    """Get subscription details for a user."""
    db = _get_db()

    user = await db.users.find_one({"api_key": api_key})
    if not user:
        return {"error": "Invalid API key."}

    sub = user.get("subscription", {})
    return _compute_subscription_status(sub)


def _compute_subscription_status(sub: dict) -> dict:
    """Compute current subscription status from stored data."""
    status = sub.get("status", "trial")
    now = datetime.utcnow()

    if status == "trial":
        trial_end = sub.get("trial_end")
        if trial_end and trial_end < now:
            return {"status": "expired", "plan": "trial", "message": "Free trial expired."}
        days_remaining = (trial_end - now).days if trial_end else 0
        return {
            "status": "trial",
            "plan": "trial",
            "days_remaining": max(days_remaining, 0),
        }

    elif status == "active":
        return {
            "status": "active",
            "plan": sub.get("plan", "monthly"),
            "renews_at": sub.get("current_period_end", "").isoformat() if sub.get("current_period_end") else "",
        }

    elif status in ("cancelled", "expired"):
        return {"status": "expired", "plan": sub.get("plan", ""), "message": "Subscription ended."}

    return {"status": status, "plan": sub.get("plan", "")}


# ─── Password Reset ───────────────────────────────────────────────────

async def forgot_password(email: str) -> dict:
    """Send password reset code."""
    email = email.lower().strip()
    db = _get_db()

    user = await db.users.find_one({"email": email})
    if not user:
        # Don't reveal whether email exists
        return {"success": True}

    code = _generate_otp()
    now = datetime.utcnow()

    await db.otp_codes.update_one(
        {"email": email, "type": "reset"},
        {"$set": {
            "email": email,
            "code": code,
            "type": "reset",
            "expires_at": now + timedelta(minutes=15),
            "created_at": now,
        }},
        upsert=True,
    )

    await _send_otp_email(email, code, "Pacific — Password Reset")
    return {"success": True}


async def reset_password(email: str, code: str, new_password: str) -> dict:
    """Reset password with verification code."""
    email = email.lower().strip()
    db = _get_db()

    if len(new_password) < 8:
        return {"error": "Password must be at least 8 characters."}

    otp_doc = await db.otp_codes.find_one({
        "email": email,
        "type": "reset",
        "code": code,
    })

    if not otp_doc:
        return {"error": "Invalid reset code."}

    if otp_doc.get("expires_at") and otp_doc["expires_at"] < datetime.utcnow():
        return {"error": "Code expired. Request a new one."}

    # Update password and regenerate API key
    new_api_key = _generate_api_key()
    password_hash = _hash_password(new_password)

    await db.users.update_one(
        {"email": email},
        {"$set": {
            "password_hash": password_hash,
            "api_key": new_api_key,
            "updated_at": datetime.utcnow(),
        }},
    )

    await db.otp_codes.delete_many({"email": email, "type": "reset"})

    return {"success": True}


# ─── Rate Limiting ─────────────────────────────────────────────────────

def check_rate_limit(
    client_ip: str,
    action: str = "chat",
    limit: int = 50,
    window: int = 60,
) -> dict:
    """Simple in-memory IP rate limiting. Resets on restart."""
    now = time.time()
    key = f"{action}:{client_ip}"

    if key not in _rate_cache:
        _rate_cache[key] = []

    # Clean old entries
    _rate_cache[key] = [t for t in _rate_cache[key] if now - t < window]

    if len(_rate_cache[key]) >= limit:
        return {
            "allowed": False,
            "retry_after_seconds": int(window - (now - _rate_cache[key][0])),
        }

    _rate_cache[key].append(now)
    return {"allowed": True}
