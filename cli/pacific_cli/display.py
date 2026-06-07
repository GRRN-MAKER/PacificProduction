"""
Pacific CLI — Rich terminal display formatting.

No usage tracking — Microsoft Store handles billing.
No tiered plans — one flat price: $40/month + 7-day free trial.
"""

import sys

# ─── ANSI Color Codes ────────────────────────────────────────────────

RESET    = "\033[0m"
BOLD     = "\033[1m"
DIM      = "\033[2m"
CYAN     = "\033[1;36m"
YELLOW   = "\033[1;33m"
GREEN    = "\033[1;32m"
RED      = "\033[1;31m"
BLUE     = "\033[1;34m"
MAGENTA  = "\033[1;35m"
WHITE    = "\033[1;37m"
OCEAN    = "\033[38;5;39m"
DEEP_BLUE = "\033[38;5;27m"


# ─── Banner ──────────────────────────────────────────────────────────

BANNER = f"""
{OCEAN}╔══════════════════════════════════════════════════════╗
║                                                      ║
║   {WHITE}🌊  P A C I F I C{OCEAN}                                  ║
║   {DIM}Elite Quantitative Financial AI{RESET}{OCEAN}                  ║
║                                                      ║
╚══════════════════════════════════════════════════════╝{RESET}
"""

BANNER_MINI = f"{OCEAN}🌊 Pacific{RESET} {DIM}v1.0.0{RESET}"


# ─── Output Helpers ──────────────────────────────────────────────────

def print_banner():
    print(BANNER)

def print_mini():
    print(BANNER_MINI)

def print_success(msg: str):
    print(f"{GREEN}✓{RESET} {msg}")

def print_error(msg: str):
    print(f"{RED}✗{RESET} {msg}")

def print_warning(msg: str):
    print(f"{YELLOW}⚠{RESET} {msg}")

def print_info(msg: str):
    print(f"{BLUE}ℹ{RESET} {msg}")

def print_user_prompt():
    """Print the user input prompt."""
    sys.stdout.write(f"\n{CYAN}You:{RESET} ")
    sys.stdout.flush()

def print_pacific_label():
    """Print the Pacific response label."""
    sys.stdout.write(f"\n{YELLOW}Pacific:{RESET} ")
    sys.stdout.flush()

def print_thinking_label():
    """Print thinking mode indicator."""
    sys.stdout.write(f"\n{MAGENTA}💭 Thinking...{RESET}\n")
    sys.stdout.flush()

def print_divider():
    print(f"{DIM}{'─' * 54}{RESET}")

def print_token(token: str):
    """Print a single streaming token."""
    sys.stdout.write(token)
    sys.stdout.flush()


# ─── Plans Display ───────────────────────────────────────────────────

def print_plans(data: dict):
    """Print pricing info. One flat plan, managed by Microsoft Store."""
    pricing = data.get("pricing", {})
    features = data.get("features", [])

    print(f"\n{BOLD}🌊 Pacific — Pricing{RESET}")
    print_divider()
    print(f"  Trial:     {GREEN}{pricing.get('trial', '7 days free')}{RESET}")
    print(f"  Monthly:   {CYAN}{pricing.get('monthly', '$40/month')}{RESET}")
    print(f"  Platform:  Microsoft Store")
    print_divider()

    if features:
        print(f"\n  {BOLD}Includes:{RESET}")
        for feat in features:
            print(f"    {GREEN}✓{RESET} {feat}")

    rate = data.get("rate_limit", "50 requests/minute")
    print(f"\n  {DIM}Rate limit: {rate}{RESET}")

    subscribe_url = data.get("subscribe_url", "ms-windows-store://pdp/?productid=pacific")
    print(f"\n  Get it: {CYAN}{subscribe_url}{RESET}")
    print()
