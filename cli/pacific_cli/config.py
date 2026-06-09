"""
Pacific CLI — Configuration.

Stores user preferences and authentication credentials.
API key is obtained after login/registration and stored locally.
"""

import json
import os
from pathlib import Path
from typing import Optional

# ── Directories ──────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".pacific"
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = CONFIG_DIR / "outputs"
CACHE_DIR = CONFIG_DIR / "cache"

# Pacific API Gateway — Cloudflare tunnel endpoint
API_BASE_URL = "https://pacific-gateway.grrn.io"

DEFAULTS = {
    "api_base_url": API_BASE_URL,
    "api_key": "",
    "model_name": "pacific",
    "max_tokens": 8192,
    "temperature": 0.7,
    "thinking_enabled": False,
    "stream": True,
    "theme": "ocean",
    "default_period": "3mo",
    "chart_style": "file",
    "ticker_refresh_secs": 5,
    "output_dir": str(OUTPUT_DIR),
    "history_enabled": True,
    "history_file": str(CONFIG_DIR / "history.jsonl"),
}


def _ensure_dirs():
    """Create config / output / cache directories."""
    for d in (CONFIG_DIR, OUTPUT_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load user preferences from disk, merging with defaults."""
    _ensure_dirs()
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
    """Save preferences to disk."""
    _ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_api_key() -> Optional[str]:
    """Return API key from env → config file, or None."""
    key = os.environ.get("PACIFIC_API_KEY")
    if key:
        return key
    cfg = load_config()
    return cfg.get("api_key") or None


def set_api_key(key: str):
    """Store API key in config."""
    cfg = load_config()
    cfg["api_key"] = key
    save_config(cfg)


def get_api_base_url() -> str:
    """Get the API base URL."""
    cfg = load_config()
    return cfg.get("api_base_url", API_BASE_URL)


def get_config_value(key: str):
    """Get a single config value."""
    return load_config().get(key)


def set_config_value(key: str, value):
    """Set a single config value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
