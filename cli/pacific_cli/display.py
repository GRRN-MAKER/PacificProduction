"""
Pacific CLI — Rich terminal display formatting.
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
    """Print pricing info."""
    pricing = data.get("pricing", {})
    features = data.get("features", [])

    print(f"\n{BOLD}🌊 Pacific — Pricing{RESET}")
    print_divider()
    print(f"  Trial:     {GREEN}{pricing.get('trial', '7 days free')}{RESET}")
    print(f"  Monthly:   {CYAN}{pricing.get('monthly', '$40/month')}{RESET}")
    print(f"  Annual:    {CYAN}{pricing.get('annual', '$399/year')}{RESET}")
    print_divider()

    if features:
        print(f"\n  {BOLD}Includes:{RESET}")
        for feat in features:
            print(f"    {GREEN}✓{RESET} {feat}")

    rate = data.get("rate_limit", "50 requests/minute")
    print(f"\n  {DIM}Rate limit: {rate}{RESET}")

    subscribe_url = data.get("subscribe_url", "https://pacific.grrn.io/subscribe")
    print(f"\n  Subscribe: {CYAN}{subscribe_url}{RESET}")
    print()


# ─── Help Panel ──────────────────────────────────────────────────────

def print_help_panel():
    """Print the full in-chat help panel with all slash commands."""
    print(f"""
{BOLD}Chat Commands:{RESET}
  {CYAN}/clear{RESET}              Reset conversation history
  {CYAN}/history{RESET}            Show message count
  {CYAN}/think on|off{RESET}       Toggle thinking/reasoning mode
  {CYAN}exit{RESET}                End session

{BOLD}File Operations:{RESET}
  {CYAN}/file ~/report.pdf{RESET}  Send file to Pacific for AI analysis
  {CYAN}/open ~/file.pdf{RESET}    Open file with system default app
  {CYAN}/read ~/data.csv{RESET}    Display file contents in terminal
  {CYAN}/image chart.png{RESET}    Analyze chart image with AI
  {DIM}  Supports: .txt, .csv, .json, .py, .pdf, and more{RESET}

{BOLD}Market & Charts:{RESET}
  {CYAN}/chart AAPL 3mo volume sma20{RESET}    Candlestick chart (PNG)
  {CYAN}/compare NVDA TSLA AAPL 1y{RESET}      Comparison chart (PNG)
  {CYAN}/quote AAPL{RESET}                      Quick stock quote
  {CYAN}/stream AAPL NVDA TSLA [-r 2]{RESET}    Live price stream

{BOLD}Export:{RESET}
  {CYAN}/export pdf{RESET}                 Save last response as PDF
  {CYAN}/export json{RESET}                Save last response as JSON
  {CYAN}/export json AAPL [3mo]{RESET}     Export stock data to JSON
  {CYAN}/export excel AAPL{RESET}          Export stock data to Excel
""")
