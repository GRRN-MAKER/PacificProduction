"""
Pacific CLI — Windows Store License Token.

This module grabs the Microsoft Store Collection ID from the local Windows OS.
The token is a cryptographically signed proof that:
  1. The user is logged into a Microsoft account
  2. They have Pacific installed from the Microsoft Store
  3. Their subscription/trial status is embedded in the token

The CLI NEVER sees the subscription status directly.
It just passes the token to the proxy, and the proxy asks Microsoft.

REQUIRES: Windows 10/11 with Microsoft Store. Will not work on macOS/Linux.
For development/testing, set PACIFIC_DEV_TOKEN env var to bypass Windows APIs.
"""

import os
import sys
import platform
from typing import Optional

# Development bypass — lets you test the CLI on non-Windows machines
DEV_TOKEN = os.getenv("PACIFIC_DEV_TOKEN", "")


async def get_windows_store_token() -> Optional[str]:
    """
    Ask the local Windows OS for a Microsoft Store Collection ID token.

    This is a FREE, built-in Windows API call. No login screen pops up.
    Windows automatically uses the Microsoft account the user is signed into.

    Returns:
      - A cryptographically signed token string (if on Windows with valid Store install)
      - The DEV_TOKEN value (if set, for development/testing)
      - None (if on non-Windows or Store API fails)
    """
    # ── Development mode: bypass Windows APIs ──
    if DEV_TOKEN:
        return DEV_TOKEN

    # ── Platform check ──
    if platform.system() != "Windows":
        print("\033[1;31m✗ Pacific requires Windows 10 or later.\033[0m")
        print("  The Microsoft Store license system is only available on Windows.")
        print()
        print("  For development/testing on macOS/Linux:")
        print("    export PACIFIC_DEV_TOKEN='your-test-token'")
        return None

    # ── Windows Store token acquisition ──
    try:
        from winsdk.windows.services.store import StoreContext

        context = StoreContext.get_default()

        # Request the B2B Collection ID
        # The service_ticket identifies your app to Microsoft's backend
        # "anonymous" means we don't need a specific user identifier
        service_ticket = os.getenv("PACIFIC_SERVICE_TICKET", "")
        result = await context.get_customer_collections_id_async(
            service_ticket, "anonymous"
        )

        token = str(result)
        if not token or token == "None":
            return None

        return token

    except ImportError:
        print("\033[1;31m✗ Windows SDK not available.\033[0m")
        print("  Install with: pip install winsdk")
        print()
        print("  Or if you're developing on a non-Windows machine:")
        print("    export PACIFIC_DEV_TOKEN='your-test-token'")
        return None

    except Exception as e:
        # Common issues:
        # - User not signed into Microsoft account
        # - App not installed from Microsoft Store (sideloaded)
        # - Windows Store service not running
        error_str = str(e).lower()

        if "not found" in error_str or "not available" in error_str:
            print("\033[1;31m✗ Pacific is not registered with the Microsoft Store.\033[0m")
            print("  Make sure you installed Pacific from the Microsoft Store.")
            print()
            print("  Get Pacific:")
            print("    \033[1;36mms-windows-store://pdp/?productid=pacific\033[0m")
        elif "sign" in error_str or "account" in error_str:
            print("\033[1;31m✗ No Microsoft account detected.\033[0m")
            print("  Please sign into a Microsoft account in Windows Settings.")
        else:
            print(f"\033[1;31m✗ Store license error: {e}\033[0m")

        return None
