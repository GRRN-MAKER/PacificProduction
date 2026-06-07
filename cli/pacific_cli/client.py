"""
Pacific CLI — API Client.

SECURITY MODEL:
  - Client ships with ZERO secrets. No API keys. No tokens. Nothing.
  - Authentication is handled by the Windows OS via Microsoft Store license.
  - Every request: CLI asks Windows for a Store token → sends to proxy.
  - Proxy asks Microsoft: "Is this token active?" → YES = proxy to AI, NO = 403.
  - No login. No registration. No accounts. No database.
  - User's only interaction: buy/trial from Microsoft Store → open CLI → use it.
"""

import json
import sys
import asyncio
from typing import Generator, Optional

import requests

from .config import load_config, get_proxy_url
from .license import get_windows_store_token


class PacificClient:
    """
    Client for the Pacific API Gateway.
    Contains ZERO hardcoded keys.
    Authentication = Windows Store token sent with every request.
    """

    def __init__(self):
        self.proxy_url = get_proxy_url().rstrip("/")
        self.config = load_config()

    def _get_token(self) -> str:
        """
        Get the Microsoft Store Collection ID token from the local Windows OS.
        This is a cryptographically signed identity — NOT a secret API key.
        Windows generates it on-demand from the logged-in Microsoft account.
        """
        try:
            token = asyncio.run(get_windows_store_token())
        except RuntimeError:
            # Already inside an event loop (e.g., Jupyter)
            loop = asyncio.get_event_loop()
            token = loop.run_until_complete(get_windows_store_token())

        if not token:
            print("\033[1;31m✗ Could not verify Microsoft Store license.\033[0m")
            print()
            print("  Possible causes:")
            print("    • You are not signed into a Microsoft account on this PC")
            print("    • Pacific was not installed from the Microsoft Store")
            print("    • Your 7-day free trial has not started yet")
            print()
            print("  Get Pacific from the Microsoft Store:")
            print("    \033[1;36mms-windows-store://pdp/?productid=pacific\033[0m")
            sys.exit(1)

        return token

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
          1. Ask Windows OS for Store token (proves subscription is active)
          2. Send token + messages to proxy
          3. Proxy validates with Microsoft in real-time
          4. If active → proxy calls AI with hidden key → returns response
          5. If inactive → proxy returns 403 → we tell user to renew
        """
        max_tokens = max_tokens or self.config.get("max_tokens", 8192)
        temperature = temperature if temperature is not None else self.config.get("temperature", 0.7)
        stream = stream if stream is not None else self.config.get("stream", True)
        thinking = thinking if thinking is not None else self.config.get("thinking_enabled", False)

        # Get Windows Store token (proves active subscription)
        token = self._get_token()

        payload = {
            "windowsToken": token,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            "enable_thinking": thinking,
        }

        try:
            resp = requests.post(
                f"{self.proxy_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=120,
            )

            # ── Handle errors ──
            if resp.status_code == 401:
                detail = self._parse_error_detail(resp)
                print("\033[1;31m✗ License verification failed.\033[0m")
                print(f"  {detail.get('message', 'Could not verify Windows Store license.')}")
                print()
                print("  Make sure Pacific was installed from the Microsoft Store.")
                sys.exit(1)

            elif resp.status_code == 403:
                detail = self._parse_error_detail(resp)
                print("\033[1;31m✗ Subscription inactive.\033[0m")
                print(f"  {detail.get('message', 'Your trial or subscription has ended.')}")
                print()
                renew_url = detail.get("renew_url", "ms-windows-store://pdp/?productid=pacific")
                print(f"  Renew in Microsoft Store:")
                print(f"    \033[1;36m{renew_url}\033[0m")
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

    # ─── Public endpoints (no token needed) ──────────────────────────

    def get_plans(self) -> dict:
        """Fetch pricing info (public, no auth)."""
        resp = requests.get(f"{self.proxy_url}/v1/plans", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> dict:
        """Check gateway and backend health (public, no auth)."""
        resp = requests.get(f"{self.proxy_url}/health", timeout=10)
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
