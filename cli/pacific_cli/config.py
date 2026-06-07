"""
Pacific CLI — Configuration.

SECURITY MODEL:
  - CLI contains ZERO secrets. No API keys. No tokens. No passwords.
  - Authentication is handled by the Windows OS via Microsoft Store license.
  - Every request sends a Windows Store token → proxy validates with Microsoft.
  - No login. No registration. No accounts. No database.
  - User buys/trials through Microsoft Store → Windows knows → CLI works.

This file stores ONLY user preferences (temperature, max_tokens, etc.).
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".pacific"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Public proxy URL — contains zero secrets. Cloudflare tunnel endpoint.
PROXY_URL = "https://pacific-gateway.grrn.io"

DEFAULTS = {
    "proxy_url": PROXY_URL,
    "max_tokens": 8192,
    "temperature": 0.7,
    "thinking_enabled": False,
    "stream": True,
    "theme": "ocean",
    "history_enabled": True,
    "history_file": str(CONFIG_DIR / "history.jsonl"),
}


def ensure_config_dir():
    """Create ~/.pacific/ if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load user preferences from disk, merging with defaults."""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
            merged = {**DEFAULTS, **user_config}
            return merged
        except (json.JSONDecodeError, IOError):
            return dict(DEFAULTS)
    return dict(DEFAULTS)


def save_config(config: dict):
    """Save preferences to disk. NEVER stores secrets of any kind."""
    ensure_config_dir()
    # Explicitly strip anything that could be a secret
    safe_keys = {"proxy_url", "max_tokens", "temperature", "thinking_enabled",
                 "stream", "theme", "history_enabled", "history_file"}
    safe_config = {k: v for k, v in config.items() if k in safe_keys}
    with open(CONFIG_FILE, "w") as f:
        json.dump(safe_config, f, indent=2)


def get_proxy_url() -> str:
    """Get proxy URL from config. This is public, not a secret."""
    config = load_config()
    return config.get("proxy_url", PROXY_URL)
