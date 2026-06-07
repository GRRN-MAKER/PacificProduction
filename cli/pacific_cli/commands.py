"""
Pacific CLI — Command implementations.

SECURITY MODEL:
  - ZERO secrets in this file. ZERO hardcoded keys. ZERO user accounts.
  - Authentication = Windows Store token sent with every AI request.
  - No login. No registration. No logout. No sessions.
  - User just opens the CLI and types. Windows handles the license.

Commands:
  pacific [message]              Quick single query (default)
  pacific chat [message]         Interactive chat or single query
  pacific analyze [query]        Financial analysis query
  pacific sentiment [headline]   Classify financial sentiment
  pacific portfolio [action]     Portfolio optimization
  pacific plans                  Show pricing info
  pacific config                 Configure CLI preferences
  pacific health                 Check server status
"""

import sys
import json
from datetime import datetime
from pathlib import Path

from .client import PacificClient
from .config import load_config, save_config
from .display import (
    print_banner, print_mini, print_success, print_error, print_warning,
    print_info, print_user_prompt, print_pacific_label, print_thinking_label,
    print_divider, print_token, print_plans,
    CYAN, YELLOW, GREEN, RED, RESET, BOLD, DIM,
)


SYSTEM_PROMPTS = {
    "chat": "You are Pacific, an elite quantitative financial AI. You provide precise, data-driven analysis with institutional-grade insights.",
    "analyze": "You are Pacific, an elite quantitative financial AI. Provide detailed technical and fundamental analysis. Include specific indicators, levels, and actionable insights. Format with clear sections.",
    "sentiment": "You are Pacific, a financial sentiment classifier. Classify the given text as BULLISH, BEARISH, or NEUTRAL. Then provide a brief explanation of key sentiment drivers. Format: [SENTIMENT] followed by analysis.",
    "portfolio": "You are Pacific, a portfolio optimization engine. Analyze portfolio composition, suggest rebalancing, calculate risk metrics (Sharpe, VaR, CVaR), and provide allocation recommendations.",
}


# ─── Interactive Chat ────────────────────────────────────────────────

def cmd_chat(args):
    """Interactive chat or single query mode. No login required — Windows handles auth."""
    config = load_config()
    client = PacificClient()

    # Single query mode
    if args.message:
        query = " ".join(args.message)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["chat"]},
            {"role": "user", "content": query},
        ]
        print_pacific_label()
        full_reply = ""
        for token in client.chat(messages, thinking=args.think):
            print_token(token)
            full_reply += token
        print("\n")
        return

    # Interactive mode
    print_banner()
    thinking = args.think or config.get("thinking_enabled", False)
    print_info(f"Thinking: {'✅ ENABLED' if thinking else '❌ DISABLED'}")
    print_info("Type 'exit' to quit, '/think' to toggle thinking")
    print_divider()

    messages = [{"role": "system", "content": SYSTEM_PROMPTS["chat"]}]
    history_file = config.get("history_file")

    while True:
        try:
            print_user_prompt()
            user_input = input()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye! 🌊{RESET}")
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() in ("exit", "quit", "q"):
            print(f"{DIM}Goodbye! 🌊{RESET}")
            break

        # Slash commands
        if stripped == "/think":
            thinking = not thinking
            print_info(f"Thinking: {'✅ ENABLED' if thinking else '❌ DISABLED'}")
            continue
        elif stripped == "/clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPTS["chat"]}]
            print_success("Conversation cleared")
            continue
        elif stripped == "/help":
            print_info("Commands: /think, /clear, /help, exit")
            continue

        messages.append({"role": "user", "content": stripped})

        if thinking:
            print_thinking_label()

        print_pacific_label()
        full_reply = ""
        try:
            for token in client.chat(messages, thinking=thinking):
                print_token(token)
                full_reply += token
            print()
        except Exception as e:
            print_error(str(e))
            continue

        messages.append({"role": "assistant", "content": full_reply})

        # Save to history
        if history_file and config.get("history_enabled"):
            try:
                Path(history_file).parent.mkdir(parents=True, exist_ok=True)
                with open(history_file, "a") as f:
                    record = {
                        "ts": datetime.utcnow().isoformat(),
                        "user": stripped,
                        "assistant": full_reply[:500],
                    }
                    f.write(json.dumps(record) + "\n")
            except IOError:
                pass


# ─── Analyze ─────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Financial analysis query."""
    if not args.query:
        print_error("Usage: pacific analyze 'Analyze AAPL earnings beat'")
        sys.exit(1)

    query = " ".join(args.query)
    client = PacificClient()

    enriched = query
    if args.ticker:
        enriched = f"Ticker: {args.ticker.upper()}. {enriched}"
    if args.timeframe:
        enriched = f"{enriched} Timeframe: {args.timeframe}."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["analyze"]},
        {"role": "user", "content": enriched},
    ]

    print_mini()
    print(f"{DIM}Analyzing: {query}{RESET}")
    print_divider()

    full_reply = ""
    for token in client.chat(messages, thinking=args.think):
        print_token(token)
        full_reply += token
    print("\n")


# ─── Sentiment ───────────────────────────────────────────────────────

def cmd_sentiment(args):
    """Classify financial sentiment."""
    if not args.text:
        print_error("Usage: pacific sentiment 'Fed announces rate pause'")
        sys.exit(1)

    text = " ".join(args.text)
    client = PacificClient()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["sentiment"]},
        {"role": "user", "content": f"Classify: {text}"},
    ]

    print_mini()
    full_reply = ""
    for token in client.chat(messages, max_tokens=512, temperature=0.3):
        print_token(token)
        full_reply += token
    print("\n")


# ─── Portfolio ───────────────────────────────────────────────────────

def cmd_portfolio(args):
    """Portfolio optimization and analysis."""
    client = PacificClient()

    action = args.action or "analyze"
    query_parts = [f"Action: {action}"]

    if args.holdings:
        query_parts.append(f"Current holdings: {args.holdings}")
    if args.risk:
        query_parts.append(f"Risk tolerance: {args.risk}")
    if args.goal:
        query_parts.append(f"Investment goal: {args.goal}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["portfolio"]},
        {"role": "user", "content": " | ".join(query_parts)},
    ]

    print_mini()
    print(f"{DIM}Portfolio {action}...{RESET}")
    print_divider()

    full_reply = ""
    for token in client.chat(messages, thinking=True):
        print_token(token)
        full_reply += token
    print("\n")


# ─── Plans ───────────────────────────────────────────────────────────

def cmd_plans(args):
    """Show pricing info. Subscription managed by Microsoft Store."""
    client = PacificClient()
    try:
        data = client.get_plans()
        pricing = data.get("pricing", {})

        print(f"\n{BOLD}🌊 Pacific — Pricing{RESET}")
        print_divider()
        print(f"  Trial:     {GREEN}{pricing.get('trial', '7 days free')}{RESET}")
        print(f"  Monthly:   {CYAN}{pricing.get('monthly', '$40/month')}{RESET}")
        print(f"  Platform:  Microsoft Store")
        print_divider()

        features = data.get("features", [])
        for feat in features:
            print(f"  {feat}")

        print()
        rate = data.get("rate_limit", "50 requests/minute")
        print(f"  {DIM}Rate limit: {rate}{RESET}")
        print()
        subscribe_url = data.get("subscribe_url", "ms-windows-store://pdp/?productid=pacific")
        print(f"  Subscribe: {CYAN}{subscribe_url}{RESET}")
        print()
    except Exception as e:
        print_error(f"Could not fetch plans: {e}")
        sys.exit(1)


# ─── Config ──────────────────────────────────────────────────────────

def cmd_config(args):
    """Configure CLI preferences. ZERO secrets stored."""
    config = load_config()
    changed = False

    if args.proxy_url:
        config["proxy_url"] = args.proxy_url
        changed = True
        print_success(f"Proxy URL set to {args.proxy_url}")

    if args.max_tokens:
        config["max_tokens"] = args.max_tokens
        changed = True

    if args.temperature:
        config["temperature"] = args.temperature
        changed = True

    if args.thinking is not None:
        config["thinking_enabled"] = args.thinking.lower() in ("true", "1", "yes", "on")
        changed = True

    if changed:
        save_config(config)
        print_success("Configuration saved to ~/.pacific/config.json")
    else:
        print(f"\n{BOLD}⚙️  Pacific CLI Configuration{RESET}")
        print_divider()
        print(f"  Auth:        {GREEN}Microsoft Store License (automatic){RESET}")
        print(f"  Proxy URL:   {config.get('proxy_url', 'N/A')}")
        print(f"  Max Tokens:  {config.get('max_tokens', 'N/A')}")
        print(f"  Temperature: {config.get('temperature', 'N/A')}")
        print(f"  Thinking:    {'✅' if config.get('thinking_enabled') else '❌'}")
        print(f"  Streaming:   {'✅' if config.get('stream', True) else '❌'}")
        print(f"  History:     {config.get('history_file', 'N/A')}")
        print()
        print(f"  {DIM}Config file: ~/.pacific/config.json{RESET}")
        print(f"  {DIM}No secrets of any kind are stored locally.{RESET}")
        print(f"  {DIM}Authentication is handled by Windows automatically.{RESET}")
        print()


# ─── Health ──────────────────────────────────────────────────────────

def cmd_health(args):
    """Check server health (public endpoint, no auth needed)."""
    client = PacificClient()
    try:
        health = client.health_check()
        status = health.get("status", "unknown")
        backend = health.get("backend_connected", False)
        auth_method = health.get("auth_method", "unknown")

        if status == "healthy":
            print_success(f"Gateway:  {GREEN}healthy{RESET}")
            print_success(f"Backend:  {GREEN}connected{RESET}")
            print_info(f"Auth:     {auth_method}")
            print_info(f"Version:  {health.get('version', 'N/A')}")
        else:
            print_warning(f"Gateway:  {YELLOW}{status}{RESET}")
            print_error(f"Backend:  {'connected' if backend else RED + 'disconnected' + RESET}")
    except Exception as e:
        print_error(f"Cannot reach gateway: {e}")
        sys.exit(1)
