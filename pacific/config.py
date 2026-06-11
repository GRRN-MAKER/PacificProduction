"""PACIFIC configuration — API keys, paths, defaults."""

import json
import os
from pathlib import Path
from typing import Optional

# ── Directories ──────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".pacific"
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = CONFIG_DIR / "outputs"
CACHE_DIR = CONFIG_DIR / "cache"

# ── Gateway (auth + subscription enforcement) ────────────────────────
GATEWAY_URL = "https://pacific-gateway.grrn.io"

DEFAULT_CONFIG = {
    "api_key": "",
    "api_base_url": "https://pacific.grrn.io/v1",
    "model_name": "pacific",
    "default_period": "3mo",
    "chart_style": "terminal",        # terminal | file | both
    "ticker_refresh_secs": 5,
    "output_dir": str(OUTPUT_DIR),
    "theme": "dark",
    "max_tokens": 8192,
    "temperature": 0.7,
    "enable_thinking": False,
}


def _ensure_dirs():
    """Create config / output / cache directories if they don't exist."""
    for d in (CONFIG_DIR, OUTPUT_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load config from disk, creating defaults if missing."""
    _ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
        # Merge with defaults so new keys are always present
        merged = {**DEFAULT_CONFIG, **saved}
        return merged
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    """Persist config to disk."""
    _ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


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


def get_config_value(key: str):
    """Get a single config value."""
    return load_config().get(key)


def set_config_value(key: str, value):
    """Set a single config value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
