"""
Pacific CLI — API Client.

Authentication: API key stored in ~/.pacific/config.json.
User registers/logs in → receives API key → key sent with every request.
Server validates key + checks subscription status.
"""

import json
import sys
from typing import Generator, Optional

import requests

from .config import load_config, get_api_key, get_api_base_url


class PacificClient:
    """
    Client for the Pacific API.
    Uses API key authentication (obtained via login/register).
    """

    def __init__(self):
        self.base_url = get_api_base_url().rstrip("/")
        self.config = load_config()

    def _get_headers(self) -> dict:
        """Build request headers with API key."""
        api_key = get_api_key()
        if not api_key:
            print("\033[1;31m✗ Not signed in.\033[0m")
            print()
            print("  Sign in:   \033[1;36mpacific login\033[0m")
            print("  Register:  \033[1;36mpacific register\033[0m")
            print()
            sys.exit(1)

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    # ─── Chat (Main Method) ──────────────────────────────────────────

    def chat(
        self,
        messages: list,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: Optional[bool] = None,
        thinking: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        """
        Send a chat request. Yields tokens if streaming.

        Flow:
          1. Get API key from config
          2. Send key + messages to server
          3. Server validates key + checks subscription
          4. If active → proxy to AI backend → stream response
          5. If inactive → 403 → tell user to renew
        """
        max_tokens = max_tokens or self.config.get("max_tokens", 8192)
        temperature = temperature if temperature is not None else self.config.get("temperature", 0.7)
        stream = stream if stream is not None else self.config.get("stream", True)
        thinking = thinking if thinking is not None else self.config.get("thinking_enabled", False)

        headers = self._get_headers()

        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            "enable_thinking": thinking,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers=headers,
                stream=stream,
                timeout=120,
            )

            # ── Handle errors ──
            if resp.status_code == 401:
                detail = self._parse_error_detail(resp)
                print("\033[1;31m✗ Authentication failed.\033[0m")
                print(f"  {detail.get('message', 'Invalid or expired API key.')}")
                print()
                print("  Sign in again:  \033[1;36mpacific login\033[0m")
                sys.exit(1)

            elif resp.status_code == 403:
                detail = self._parse_error_detail(resp)
                print("\033[1;31m✗ Subscription inactive.\033[0m")
                print(f"  {detail.get('message', 'Your trial or subscription has ended.')}")
                print()
                print("  Subscribe:  \033[1;36mhttps://pacific.grrn.io/subscribe\033[0m")
                sys.exit(1)

            elif resp.status_code == 429:
                detail = self._parse_error_detail(resp)
                retry = detail.get("retry_after_seconds", 60)
                print(f"\033[1;33m⏳ Rate limited. Please wait {retry} seconds.\033[0m")
                sys.exit(1)

            elif resp.status_code == 503:
                detail = self._parse_error_detail(resp)
                print(f"\033[1;33m⚠ {detail.get('message', 'Service temporarily unavailable.')}\033[0m")
                print("  Please try again in a moment.")
                sys.exit(1)

            resp.raise_for_status()

            # ── Stream or return full response ──
            if stream:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
            else:
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
                yield content

        except requests.exceptions.ConnectionError:
            print("\033[1;31m✗ Cannot reach Pacific server. Check your internet connection.\033[0m")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("\033[1;31m✗ Request timed out. The server may be busy — please retry.\033[0m")
            sys.exit(1)

    # ─── Simple prompt (single turn) ─────────────────────────────────

    def prompt(self, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """Convenience: single-turn prompt without building messages list."""
        messages = [
            {
                "role": "system",
                "content": "You are Pacific, an elite quantitative financial AI. "
                           "You provide precise, data-driven analysis with institutional-grade insights.",
            },
            {"role": "user", "content": user_prompt},
        ]
        yield from self.chat(messages, **kwargs)

    # ─── Image Analysis ──────────────────────────────────────────────

    def analyze_image(
        self,
        image_path: str,
        prompt: str = "Analyze this financial chart. Identify patterns, trends, key levels, and provide a trading outlook.",
        **kwargs,
    ) -> Generator[str, None, None]:
        """Analyze an image (chart, screenshot) with AI vision."""
        import base64
        from pathlib import Path

        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            print(f"\033[1;31m✗ Image not found: {path}\033[0m")
            return

        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = path.suffix.lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")

        messages = [
            {"role": "system", "content": "You are Pacific, an elite quantitative financial AI with vision capabilities."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ]
        yield from self.chat(messages, **kwargs)

    # ─── Public endpoints (no auth needed) ───────────────────────────

    def get_plans(self) -> dict:
        """Fetch pricing info (public, no auth)."""
        resp = requests.get(f"{self.base_url}/v1/plans", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> dict:
        """Check gateway and backend health (public, no auth)."""
        resp = requests.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ─── Error Helpers ───────────────────────────────────────────────

    def _parse_error_detail(self, resp) -> dict:
        try:
            data = resp.json()
            detail = data.get("detail", {})
            return detail if isinstance(detail, dict) else {"message": str(detail)}
        except Exception:
            return {"message": resp.text[:200]}
