"""PACIFIC — Authentication: Register, Login, OTP, Subscription.

Auth flow:
  1. User registers with email + password → server sends OTP to email
  2. User verifies OTP → server issues API key (pac_...)
  3. API key stored in ~/.pacific/config.json
  4. Every AI request includes API key in Authorization header
  5. Gateway validates key + checks subscription status

Local tools (quote, chart, market, excel, pdf, json) do NOT need auth.
Only AI chat endpoints require a valid subscription.
"""

import getpass
import re
import sys
from typing import Optional

import requests

from pacific.config import (
    load_config, save_config, get_api_key, set_api_key,
    GATEWAY_URL,
)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ── Helpers ──────────────────────────────────────────────────────────

def _gw(path: str) -> str:
    """Build full gateway URL."""
    return f"{GATEWAY_URL}{path}"


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


def _parse_error(resp) -> str:
    """Extract error message from API response."""
    try:
        data = resp.json()
        detail = data.get("detail", data.get("message", data.get("error", "Unknown error")))
        if isinstance(detail, dict):
            return detail.get("message", str(detail))
        return str(detail)
    except Exception:
        return resp.text[:200]


# ── Registration ─────────────────────────────────────────────────────

def register_interactive():
    """Interactive registration: email + password → OTP → API key."""
    console.print(Panel(
        "[bold cyan]🌊 Pacific — Create Account[/bold cyan]",
        border_style="cyan",
    ))

    # Email
    try:
        email = console.input("[cyan]Email:[/cyan] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Cancelled.[/dim]")
        return False

    if not email or not _validate_email(email):
        console.print("[red]✗ Invalid email format.[/red]")
        return False

    # Password
    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        console.print("[red]✗ Password must be at least 8 characters.[/red]")
        return False

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        console.print("[red]✗ Passwords do not match.[/red]")
        return False

    # Register
    console.print("[dim]Creating account...[/dim]")
    try:
        resp = requests.post(
            _gw("/v1/auth/register"),
            json={"email": email, "password": password},
            timeout=15,
        )

        if resp.status_code == 201:
            console.print("[green]✓ Account created! Check your email for the verification code.[/green]")
            console.print()
            return verify_otp_interactive(email)

        elif resp.status_code == 409:
            console.print("[yellow]Account already exists.[/yellow] Use [cyan]pacific login[/cyan] to sign in.")
            return False

        elif resp.status_code == 429:
            console.print("[red]✗ Too many attempts. Try again later.[/red]")
            return False

        else:
            console.print(f"[red]✗ Registration failed: {_parse_error(resp)}[/red]")
            return False

    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot reach Pacific server. Check your internet.[/red]")
        return False
    except requests.exceptions.Timeout:
        console.print("[red]✗ Request timed out. Try again.[/red]")
        return False


# ── OTP Verification ─────────────────────────────────────────────────

def verify_otp_interactive(email: str = None) -> bool:
    """Verify email with 6-digit OTP code."""
    if not email:
        try:
            email = console.input("[cyan]Email:[/cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled.[/dim]")
            return False

    try:
        otp_code = console.input("[cyan]Enter verification code:[/cyan] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Cancelled.[/dim]")
        return False

    if not otp_code:
        console.print("[red]✗ No code entered.[/red]")
        return False

    console.print("[dim]Verifying...[/dim]")
    try:
        resp = requests.post(
            _gw("/v1/auth/verify-otp"),
            json={"email": email, "otp": otp_code},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            api_key = data.get("api_key", "")
            if api_key:
                set_api_key(api_key)
                console.print("[green]✓ Email verified! API key saved.[/green]")
                console.print("[dim]You're ready to use Pacific.[/dim]")
                return True
            else:
                console.print("[green]✓ Email verified.[/green]")
                console.print("[dim]Now sign in with [cyan]pacific login[/cyan][/dim]")
                return True
        else:
            console.print(f"[red]✗ Verification failed: {_parse_error(resp)}[/red]")
            return False

    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot reach Pacific server.[/red]")
        return False
    except requests.exceptions.Timeout:
        console.print("[red]✗ Request timed out.[/red]")
        return False


# ── Login ────────────────────────────────────────────────────────────

def login_interactive() -> bool:
    """Interactive login: email + password → API key saved."""
    console.print(Panel(
        "[bold cyan]🌊 Pacific — Sign In[/bold cyan]",
        border_style="cyan",
    ))

    try:
        email = console.input("[cyan]Email:[/cyan] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Cancelled.[/dim]")
        return False

    if not email:
        console.print("[red]✗ Email required.[/red]")
        return False

    password = getpass.getpass("Password: ")
    if not password:
        console.print("[red]✗ Password required.[/red]")
        return False

    console.print("[dim]Signing in...[/dim]")
    try:
        resp = requests.post(
            _gw("/v1/auth/login"),
            json={"email": email, "password": password},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            api_key = data.get("api_key", "")
            subscription = data.get("subscription", {})

            set_api_key(api_key)
            console.print("[green]✓ Signed in! API key saved.[/green]")
            console.print()

            # Show subscription status
            status = subscription.get("status", "unknown")
            plan = subscription.get("plan", "trial")
            if status == "active":
                console.print(f"  [green]Subscription: {plan} (active)[/green]")
            elif status == "trial":
                days = subscription.get("days_remaining", 0)
                console.print(f"  [yellow]Free trial: {days} days remaining[/yellow]")
            elif status == "expired":
                console.print(f"  [red]Subscription expired.[/red]")
                console.print(f"  [dim]Renew at: https://pacific.grrn.io/subscribe[/dim]")
            console.print()
            return True

        elif resp.status_code == 401:
            console.print("[red]✗ Invalid email or password.[/red]")
            return False

        elif resp.status_code == 403:
            detail = _parse_error(resp)
            console.print(f"[red]✗ {detail}[/red]")
            return False

        elif resp.status_code == 429:
            console.print("[red]✗ Too many login attempts. Try again later.[/red]")
            return False

        else:
            console.print(f"[red]✗ Login failed: {_parse_error(resp)}[/red]")
            return False

    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot reach Pacific server. Check your internet.[/red]")
        return False
    except requests.exceptions.Timeout:
        console.print("[red]✗ Request timed out. Try again.[/red]")
        return False


# ── Logout ───────────────────────────────────────────────────────────

def logout():
    """Clear stored API key."""
    cfg = load_config()
    cfg["api_key"] = ""
    save_config(cfg)
    console.print("[green]✓ Signed out. API key removed.[/green]")


# ── Subscription Status ─────────────────────────────────────────────

def check_subscription() -> dict:
    """Check subscription status. Returns dict with status info.

    On Windows MSIX builds (Store installs), checks the Microsoft Store
    license instead of the gateway. All other platforms use gateway auth.
    """
    # Windows Store builds → check MS Store license
    try:
        from pacific.store_license import should_use_store_billing, check_store_license
        if should_use_store_billing():
            return check_store_license()
    except ImportError:
        pass

    # Non-Store builds → standard gateway auth
    api_key = get_api_key()
    if not api_key:
        return {"status": "no_key", "message": "Not signed in. Run 'pacific login'."}

    # Direct vLLM keys (non-gateway) are always "active"
    if not api_key.startswith("pac_"):
        return {"status": "active", "plan": "developer", "message": "Direct API key (no subscription needed)."}

    try:
        resp = requests.get(
            _gw("/v1/auth/subscription"),
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
        return {"status": "error", "message": "Cannot reach Pacific server."}


def print_subscription_status():
    """Display subscription status in a nice panel."""
    info = check_subscription()
    status = info.get("status", "unknown")
    is_store = info.get("is_store", False)

    table = Table(show_header=False, border_style="cyan", padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    # Show billing source
    if is_store:
        table.add_row("Billing", "[bold]Microsoft Store[/bold]")

    if status == "active":
        plan = info.get("plan", "monthly")
        renews = info.get("renews_at", "")
        expiration = info.get("subscription", {}).get("expiration_date", "")
        table.add_row("Status", "[green]● Active[/green]")
        table.add_row("Plan", plan.title())
        if renews:
            table.add_row("Renews", renews)
        if expiration and is_store:
            table.add_row("Expires", expiration)
    elif status == "trial":
        days = info.get("days_remaining", 0)
        table.add_row("Status", f"[yellow]● Free Trial ({days} days left)[/yellow]")
        table.add_row("Plan", "Trial")
    elif status == "expired":
        table.add_row("Status", "[red]● Expired[/red]")
        if is_store:
            try:
                from pacific.store_license import STORE_URL
                table.add_row("Renew", f"[cyan]pacific subscribe[/cyan] or {STORE_URL}")
            except ImportError:
                table.add_row("Renew", "Open Microsoft Store → Pacific → Subscribe")
        else:
            table.add_row("Renew", "https://pacific.grrn.io/subscribe")
    elif status == "no_subscription" and is_store:
        table.add_row("Status", "[yellow]● No Subscription[/yellow]")
        try:
            from pacific.store_license import STORE_URL
            table.add_row("Subscribe", f"[cyan]pacific subscribe[/cyan] or {STORE_URL}")
        except ImportError:
            table.add_row("Subscribe", "[cyan]pacific subscribe[/cyan] or via Microsoft Store")
    elif status == "no_key":
        table.add_row("Status", "[dim]Not signed in[/dim]")
        table.add_row("Sign in", "[cyan]pacific login[/cyan]")
        table.add_row("Register", "[cyan]pacific register[/cyan]")
    elif status == "developer":
        table.add_row("Status", "[green]● Developer Mode[/green]")
        table.add_row("Plan", "Direct API key")
    else:
        table.add_row("Status", f"[red]{info.get('message', 'Unknown')}[/red]")

    console.print(Panel(table, title="[bold cyan]Pacific Subscription[/bold cyan]", border_style="cyan"))


# ── Plans ────────────────────────────────────────────────────────────

def print_plans():
    """Display pricing plans.

    On Windows MSIX builds, shows Store subscription plans fetched
    from the Microsoft Store. On other platforms, shows gateway plans.
    """
    # Windows Store builds → show Store plans
    try:
        from pacific.store_license import should_use_store_billing, get_store_plans
        if should_use_store_billing():
            store_plans = get_store_plans()
            if store_plans:
                table = Table(title="[bold cyan]Pacific Plans — Microsoft Store[/bold cyan]", border_style="cyan")
                table.add_column("Plan", style="cyan bold")
                table.add_column("Price", style="green bold")
                table.add_column("Trial", style="yellow")
                for p in store_plans:
                    trial_str = f"{p.get('trial_period', '')} {p.get('trial_period_unit', '')}" if p.get("has_trial") else "—"
                    table.add_row(p.get("title", "Subscription"), p.get("price", "N/A"), trial_str)
                console.print(table)
                console.print()
                console.print("[dim]Subscribe with:[/dim] [cyan]pacific subscribe[/cyan]")
                try:
                    from pacific.store_license import STORE_URL
                    console.print(f"[dim]Or visit:[/dim] [cyan underline]{STORE_URL}[/cyan underline]")
                except ImportError:
                    console.print("[dim]Or open the Microsoft Store → Pacific → Subscribe[/dim]")
                console.print()
                return
    except ImportError:
        pass

    # Non-Store platforms → gateway plans
    try:
        resp = requests.get(_gw("/v1/plans"), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            pricing = data.get("pricing", {})
            features = data.get("features", [])
        else:
            pricing = {}
            features = []
    except Exception:
        pricing = {}
        features = []

    # Fallback to hardcoded if gateway is unreachable
    if not pricing:
        pricing = {
            "trial": "7 days free",
            "monthly": "$40/month",
            "annual": "$399/year (save 17%)",
        }
        features = [
            "Unlimited AI financial analysis",
            "Real-time market data",
            "Chart generation (candlestick, comparison, interactive)",
            "PDF / Excel / JSON exports",
            "File & image analysis",
            "Portfolio optimization",
            "Live price streaming",
        ]

    table = Table(title="[bold cyan]Pacific Plans[/bold cyan]", border_style="cyan")
    table.add_column("Plan", style="cyan bold")
    table.add_column("Price", style="green bold")
    table.add_row("Free Trial", pricing.get("trial", "7 days free"))
    table.add_row("Monthly", pricing.get("monthly", "$40/month"))
    table.add_row("Annual", pricing.get("annual", "$399/year"))

    console.print(table)
    console.print()

    if features:
        console.print("[bold cyan]All plans include:[/bold cyan]")
        for f in features:
            console.print(f"  [dim]✓[/dim] {f}")
        console.print()

    console.print("[dim]Subscribe at:[/dim] [cyan underline]https://pacific.grrn.io/subscribe[/cyan underline]")
    console.print()


# ── Store Subscribe (Windows MSIX only) ──────────────────────────────

def subscribe_via_store():
    """Trigger Microsoft Store purchase UI for subscription.

    Only works on Windows MSIX builds. Opens the native Store
    purchase dialog — user pays via their Microsoft account.
    On non-MSIX Windows or non-Windows, directs to the Store URL.
    """
    try:
        from pacific.store_license import (
            should_use_store_billing, request_store_purchase,
            STORE_URL, STORE_PROTOCOL_LINK, STORE_APP_ID,
        )

        if not should_use_store_billing():
            console.print(
                Panel(
                    "[bold]Store subscription is for the Windows Store version.[/bold]\n\n"
                    f"[cyan]Get it here:[/cyan] {STORE_URL}\n\n"
                    "[dim]Or use [cyan]pacific register[/cyan] + [cyan]pacific login[/cyan] "
                    "to subscribe via pacific.grrn.io[/dim]",
                    title="[bold cyan]📦 Microsoft Store[/bold cyan]",
                    border_style="cyan",
                )
            )
            return

        console.print("[dim]Opening Microsoft Store subscription...[/dim]")
        result = request_store_purchase()

        if result.get("success"):
            console.print(f"[green]✓ {result.get('message', 'Subscription activated!')}[/green]")
            console.print("[dim]Use [cyan]pacific chat[/cyan] to start.[/dim]")
        else:
            msg = result.get("message", "Subscription not completed.")
            if result.get("status") == "cancelled":
                console.print(f"[yellow]{msg}[/yellow]")
            else:
                console.print(f"[red]✗ {msg}[/red]")
                # Fallback: try opening the Store via protocol link
                console.print(f"\n[dim]You can also subscribe directly:[/dim]")
                console.print(f"  [cyan]{STORE_URL}[/cyan]")
                try:
                    import subprocess
                    subprocess.Popen(
                        ["start", STORE_PROTOCOL_LINK],
                        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
    except ImportError:
        console.print("[dim]Store billing not available on this platform.[/dim]")
        console.print("[dim]Use [cyan]pacific register[/cyan] to create an account.[/dim]")


# ── Forgot Password ──────────────────────────────────────────────────

def forgot_password_interactive():
    """Send password reset code to email."""
    try:
        email = console.input("[cyan]Email:[/cyan] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Cancelled.[/dim]")
        return

    if not email or not _validate_email(email):
        console.print("[red]✗ Invalid email format.[/red]")
        return

    console.print("[dim]Sending reset code...[/dim]")
    try:
        resp = requests.post(
            _gw("/v1/auth/forgot-password"),
            json={"email": email},
            timeout=15,
        )
        console.print("[green]✓ If that email exists, a reset code has been sent.[/green]")
        console.print()

        # Prompt for reset code
        try:
            code = console.input("[cyan]Enter reset code:[/cyan] ").strip()
            new_pw = getpass.getpass("New password (min 8 chars): ")
            if len(new_pw) < 8:
                console.print("[red]✗ Password must be at least 8 characters.[/red]")
                return

            resp2 = requests.post(
                _gw("/v1/auth/reset-password"),
                json={"email": email, "code": code, "new_password": new_pw},
                timeout=15,
            )
            if resp2.status_code == 200:
                console.print("[green]✓ Password reset successfully. Sign in with [cyan]pacific login[/cyan][/green]")
            else:
                console.print(f"[red]✗ Reset failed: {_parse_error(resp2)}[/red]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled.[/dim]")

    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot reach Pacific server.[/red]")
    except requests.exceptions.Timeout:
        console.print("[red]✗ Request timed out.[/red]")


# ── Auth Gate ────────────────────────────────────────────────────────

def require_auth() -> str:
    """Ensure user is authenticated. Returns API key or exits.

    On Windows MSIX builds (Store installs), checks the Microsoft Store
    subscription license instead of requiring a pac_* API key.
    If the Store license is active, returns a placeholder key so the
    engine routes through the gateway with Store-validated access.

    All other platforms require a gateway API key as before.
    """
    # Windows Store builds → check MS Store license
    try:
        from pacific.store_license import should_use_store_billing, is_store_subscription_active
        if should_use_store_billing():
            if is_store_subscription_active():
                # Store subscription is active — return a placeholder key
                # The engine will detect this and route accordingly
                return "store_licensed"
            else:
                console.print(Panel(
                    "[bold yellow]No active subscription.[/bold yellow]\n\n"
                    "  Subscribe:  [cyan]pacific subscribe[/cyan]\n"
                    "  Status:     [cyan]pacific status[/cyan]\n"
                    "  Plans:      [cyan]pacific plans[/cyan]\n\n"
                    "[dim]Subscribe through the Microsoft Store to unlock AI features.[/dim]",
                    title="[bold yellow]⚠ Subscription Required[/bold yellow]",
                    border_style="yellow",
                ))
                sys.exit(1)
    except ImportError:
        pass

    # Non-Store builds → standard API key check
    api_key = get_api_key()
    if not api_key:
        console.print(Panel(
            "[bold red]Not signed in.[/bold red]\n\n"
            "  Sign in:    [cyan]pacific login[/cyan]\n"
            "  Register:   [cyan]pacific register[/cyan]\n"
            "  Set key:    [cyan]pacific config set-key YOUR_KEY[/cyan]",
            title="[bold red]⚠ Authentication Required[/bold red]",
            border_style="red",
        ))
        sys.exit(1)
    return api_key


def is_authenticated() -> bool:
    """Check if user has valid auth (non-blocking).

    On Windows MSIX builds, checks Store license.
    On other platforms, checks for API key.
    """
    try:
        from pacific.store_license import should_use_store_billing, is_store_subscription_active
        if should_use_store_billing():
            return is_store_subscription_active()
    except ImportError:
        pass
    return bool(get_api_key())
