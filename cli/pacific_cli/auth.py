"""
Pacific CLI — Authentication: Password, OTP, Subscription.

Authentication flow:
  1. User registers with email + password → server sends OTP to email
  2. User verifies OTP → server issues API key
  3. API key stored in ~/.pacific/config.json
  4. Every request includes API key in Authorization header
  5. Server validates key + checks subscription status

Subscription managed via Stripe (server-side). CLI just checks status.
"""

import sys
import getpass
import re
from typing import Optional

import requests

from .config import load_config, save_config, get_api_key, set_api_key, get_api_base_url
from .display import (
    print_banner, print_success, print_error, print_warning, print_info,
    print_divider, CYAN, GREEN, RED, YELLOW, RESET, BOLD, DIM,
)


def _api_url(path: str) -> str:
    """Build full API URL."""
    base = get_api_base_url().rstrip("/")
    return f"{base}{path}"


def _validate_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


# ─── Registration ────────────────────────────────────────────────────

def register_interactive():
    """Interactive registration flow: email + password → OTP verification."""
    print_banner()
    print(f"\n{BOLD}🌊 Pacific — Create Account{RESET}")
    print_divider()

    # Email
    email = input(f"{CYAN}Email:{RESET} ").strip()
    if not _validate_email(email):
        print_error("Invalid email format.")
        return False

    # Password
    password = getpass.getpass(f"{CYAN}Password:{RESET} ")
    if len(password) < 8:
        print_error("Password must be at least 8 characters.")
        return False

    confirm = getpass.getpass(f"{CYAN}Confirm password:{RESET} ")
    if password != confirm:
        print_error("Passwords do not match.")
        return False

    # Register
    print_info("Creating account...")
    try:
        resp = requests.post(
            _api_url("/v1/auth/register"),
            json={"email": email, "password": password},
            timeout=15,
        )

        if resp.status_code == 201:
            data = resp.json()
            print_success("Account created! Check your email for the verification code.")
            print()

            # Prompt for OTP
            return verify_otp_interactive(email)

        elif resp.status_code == 409:
            print_error("An account with this email already exists.")
            print(f"  {DIM}Use 'pacific login' to sign in.{RESET}")
            return False

        else:
            detail = _parse_error(resp)
            print_error(f"Registration failed: {detail}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("Cannot reach Pacific server. Check your internet connection.")
        return False
    except requests.exceptions.Timeout:
        print_error("Request timed out. Please try again.")
        return False


# ─── OTP Verification ───────────────────────────────────────────────

def verify_otp_interactive(email: str = None) -> bool:
    """Verify email with OTP code."""
    if not email:
        email = input(f"{CYAN}Email:{RESET} ").strip()

    otp_code = input(f"{CYAN}Enter verification code:{RESET} ").strip()
    if not otp_code:
        print_error("No code entered.")
        return False

    print_info("Verifying...")
    try:
        resp = requests.post(
            _api_url("/v1/auth/verify-otp"),
            json={"email": email, "otp": otp_code},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            api_key = data.get("api_key", "")
            if api_key:
                set_api_key(api_key)
                print_success("Email verified! API key saved.")
                print()
                print(f"  {DIM}Your API key has been stored in ~/.pacific/config.json{RESET}")
                print(f"  {DIM}You're ready to use Pacific.{RESET}")
                return True
            else:
                print_success("Email verified.")
                print(f"  {DIM}Sign in with 'pacific login' to get your API key.{RESET}")
                return True

        else:
            detail = _parse_error(resp)
            print_error(f"Verification failed: {detail}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("Cannot reach server.")
        return False


# ─── Login ───────────────────────────────────────────────────────────

def login_interactive() -> bool:
    """Interactive login: email + password → API key."""
    print_banner()
    print(f"\n{BOLD}🌊 Pacific — Sign In{RESET}")
    print_divider()

    email = input(f"{CYAN}Email:{RESET} ").strip()
    if not email:
        print_error("Email required.")
        return False

    password = getpass.getpass(f"{CYAN}Password:{RESET} ")
    if not password:
        print_error("Password required.")
        return False

    print_info("Signing in...")
    try:
        resp = requests.post(
            _api_url("/v1/auth/login"),
            json={"email": email, "password": password},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            api_key = data.get("api_key", "")
            subscription = data.get("subscription", {})

            set_api_key(api_key)
            print_success("Signed in! API key saved.")
            print()

            # Show subscription status
            status = subscription.get("status", "unknown")
            plan = subscription.get("plan", "trial")
            if status == "active":
                print(f"  {GREEN}Subscription: {plan} (active){RESET}")
            elif status == "trial":
                days = subscription.get("days_remaining", 0)
                print(f"  {YELLOW}Free trial: {days} days remaining{RESET}")
            elif status == "expired":
                print(f"  {RED}Subscription expired.{RESET}")
                print(f"  {DIM}Renew at: https://pacific.grrn.io/subscribe{RESET}")
            print()
            return True

        elif resp.status_code == 401:
            print_error("Invalid email or password.")
            return False

        elif resp.status_code == 403:
            detail = _parse_error(resp)
            print_error(f"Account locked: {detail}")
            print(f"  {DIM}Contact support@grrn.io{RESET}")
            return False

        else:
            detail = _parse_error(resp)
            print_error(f"Login failed: {detail}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("Cannot reach Pacific server.")
        return False
    except requests.exceptions.Timeout:
        print_error("Request timed out.")
        return False


# ─── Subscription Status ────────────────────────────────────────────

def check_subscription() -> dict:
    """Check current subscription status. Returns dict with status info."""
    api_key = get_api_key()
    if not api_key:
        return {"status": "no_key", "message": "Not signed in. Run 'pacific login'."}

    try:
        resp = requests.get(
            _api_url("/v1/auth/subscription"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 401:
            return {"status": "invalid_key", "message": "API key expired. Run 'pacific login'."}
        else:
            return {"status": "error", "message": "Could not check subscription."}

    except Exception:
        return {"status": "error", "message": "Cannot reach server."}


def print_subscription_status():
    """Display subscription status in terminal."""
    info = check_subscription()
    status = info.get("status", "unknown")

    print(f"\n{BOLD}🌊 Pacific — Subscription{RESET}")
    print_divider()

    if status == "active":
        plan = info.get("plan", "pro")
        renews = info.get("renews_at", "")
        print(f"  Status:  {GREEN}Active ✓{RESET}")
        print(f"  Plan:    {CYAN}{plan}{RESET}")
        if renews:
            print(f"  Renews:  {DIM}{renews}{RESET}")

    elif status == "trial":
        days = info.get("days_remaining", 0)
        print(f"  Status:  {YELLOW}Free Trial{RESET}")
        print(f"  Days:    {YELLOW}{days} days remaining{RESET}")
        print()
        print(f"  {DIM}Subscribe: https://pacific.grrn.io/subscribe{RESET}")

    elif status == "expired":
        print(f"  Status:  {RED}Expired{RESET}")
        print()
        print(f"  Renew:   https://pacific.grrn.io/subscribe")

    elif status == "no_key":
        print(f"  {DIM}Not signed in.{RESET}")
        print(f"  Run:     pacific login")

    else:
        print(f"  {RED}{info.get('message', 'Unknown status')}{RESET}")

    print_divider()
    print()


# ─── Logout ──────────────────────────────────────────────────────────

def logout():
    """Clear stored API key."""
    cfg = load_config()
    cfg["api_key"] = ""
    save_config(cfg)
    print_success("Signed out. API key removed.")


# ─── Auth Gate ───────────────────────────────────────────────────────

def require_auth() -> str:
    """
    Ensure user is authenticated. Returns API key or exits.
    Called before any command that needs auth.
    """
    api_key = get_api_key()
    if not api_key:
        print_error("Not signed in.")
        print()
        print(f"  Sign in:   {CYAN}pacific login{RESET}")
        print(f"  Register:  {CYAN}pacific register{RESET}")
        print()
        sys.exit(1)
    return api_key


# ─── Password Reset ─────────────────────────────────────────────────

def forgot_password_interactive():
    """Request password reset via email."""
    print(f"\n{BOLD}🌊 Pacific — Reset Password{RESET}")
    print_divider()

    email = input(f"{CYAN}Email:{RESET} ").strip()
    if not _validate_email(email):
        print_error("Invalid email format.")
        return

    print_info("Sending reset code...")
    try:
        resp = requests.post(
            _api_url("/v1/auth/forgot-password"),
            json={"email": email},
            timeout=15,
        )

        if resp.status_code == 200:
            print_success("Reset code sent! Check your email.")
            print()

            code = input(f"{CYAN}Reset code:{RESET} ").strip()
            new_pass = getpass.getpass(f"{CYAN}New password:{RESET} ")
            confirm = getpass.getpass(f"{CYAN}Confirm:{RESET} ")

            if new_pass != confirm:
                print_error("Passwords do not match.")
                return
            if len(new_pass) < 8:
                print_error("Password must be at least 8 characters.")
                return

            resp2 = requests.post(
                _api_url("/v1/auth/reset-password"),
                json={"email": email, "code": code, "new_password": new_pass},
                timeout=15,
            )

            if resp2.status_code == 200:
                print_success("Password reset! You can now sign in.")
            else:
                detail = _parse_error(resp2)
                print_error(f"Reset failed: {detail}")
        else:
            print_error("Could not send reset code. Check your email address.")

    except requests.exceptions.ConnectionError:
        print_error("Cannot reach server.")


# ─── Helpers ─────────────────────────────────────────────────────────

def _parse_error(resp) -> str:
    """Extract error message from API response."""
    try:
        data = resp.json()
        detail = data.get("detail", data.get("message", "Unknown error"))
        if isinstance(detail, dict):
            return detail.get("message", str(detail))
        return str(detail)
    except Exception:
        return resp.text[:200]
