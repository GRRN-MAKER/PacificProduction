"""PACIFIC — Microsoft Store License Verification (Windows MSIX only).

This module handles subscription verification through the Microsoft Store
billing system. It ONLY applies to Windows Store (MSIX) builds. All other
platforms (macOS, pip install, direct EXE) continue using the gateway auth.

Architecture:
  1. On startup, detect if running as MSIX package (Windows Store install)
  2. If MSIX: use Windows.Services.Store APIs to check subscription license
  3. If not MSIX: fall through to normal gateway auth (pac_* keys)

Microsoft Store subscription add-on:
  - Created in Partner Center as "Durable" type with subscription period
  - Store ID configured via SUBSCRIPTION_STORE_ID constant
  - License checked via StoreContext.GetAppLicenseAsync()
  - Purchase triggered via StoreProduct.RequestPurchaseAsync()

References:
  - https://learn.microsoft.com/en-us/windows/uwp/monetize/enable-subscription-add-ons-for-your-app
  - https://learn.microsoft.com/en-us/uwp/api/windows.services.store
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger("pacific.store_license")

# ── Store Configuration ──────────────────────────────────────────────
# These values are from Partner Center — DO NOT CHANGE.
#
# Package/Identity/Name:       GRRN.5777388E64F5A
# Package/Identity/Publisher:  CN=6B45C4FB-290E-4232-B46B-3CE2666272FE
# PublisherDisplayName:         GRRN
# PFN:                          GRRN.5777388E64F5A_sb6f4xrssv4qr
# Package SID:                  S-1-15-2-1969302025-2603506272-201964528-1659907639-2394225809-2543558335-3452666749
# Store ID:                     9NMR6VG01Q0B
# Store URL:                    https://apps.microsoft.com/detail/9NMR6VG01Q0B
# Store protocol:               ms-windows-store://pdp/?productid=9NMR6VG01Q0B
# MSA App ID:                   ba02d693-bcac-43fe-8c11-470983bb25f4

STORE_APP_ID = "9NMR6VG01Q0B"
STORE_PFN = "GRRN.5777388E64F5A_sb6f4xrssv4qr"
STORE_PACKAGE_SID = "S-1-15-2-1969302025-2603506272-201964528-1659907639-2394225809-2543558335-3452666749"
STORE_MSA_APP_ID = "ba02d693-bcac-43fe-8c11-470983bb25f4"
STORE_URL = "https://apps.microsoft.com/detail/9NMR6VG01Q0B"
STORE_PROTOCOL_LINK = "ms-windows-store://pdp/?productid=9NMR6VG01Q0B"

# Subscription add-on Store IDs (from Partner Center > Your App > Add-ons)
# Set these env vars AFTER creating subscription add-ons in Partner Center.
SUBSCRIPTION_MONTHLY_STORE_ID = os.getenv(
    "PACIFIC_STORE_MONTHLY_ID", ""
)
SUBSCRIPTION_ANNUAL_STORE_ID = os.getenv(
    "PACIFIC_STORE_ANNUAL_ID", ""
)

# All known subscription Store IDs
SUBSCRIPTION_STORE_IDS = [
    sid for sid in [SUBSCRIPTION_MONTHLY_STORE_ID, SUBSCRIPTION_ANNUAL_STORE_ID] if sid
]

# License cache to avoid hitting the Store API on every call
_LICENSE_CACHE_FILE = Path.home() / ".pacific" / "store_license_cache.json"
_LICENSE_CACHE_TTL = 3600  # 1 hour cache


# ── Platform Detection ───────────────────────────────────────────────

def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def is_msix_package() -> bool:
    """Check if running as an MSIX-packaged app (Windows Store install).

    MSIX packages have a Package identity. We detect this by checking:
    1. The Windows.ApplicationModel.Package.Current property
    2. Fallback: check for the MSIX identity environment markers
    """
    if not is_windows():
        return False

    try:
        # Try the WinRT API first
        from winrt.windows.applicationmodel import Package  # type: ignore
        pkg = Package.current
        identity = pkg.id
        # If we get here without error, we're running as a packaged app
        return identity is not None and identity.name != ""
    except Exception:
        pass

    # Fallback: check for package identity via environment
    # MSIX apps have LOCALAPPDATA pointing inside WindowsApps
    local = os.environ.get("LOCALAPPDATA", "")
    if "WindowsApps" in local or "Packages" in local:
        return True

    # Fallback: check for package family name in registry-like paths
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_unicode_buffer(1024)
        length = ctypes.c_uint32(1024)
        # GetCurrentPackageFullName returns 0 (ERROR_SUCCESS) for packaged apps
        result = kernel32.GetCurrentPackageFullName(ctypes.byref(length), buf)
        return result == 0  # 0 = success = packaged app
    except Exception:
        return False


def get_package_info() -> Optional[dict]:
    """Get MSIX package identity info (name, publisher, version)."""
    if not is_msix_package():
        return None

    try:
        from winrt.windows.applicationmodel import Package  # type: ignore
        pkg = Package.current
        identity = pkg.id
        return {
            "name": identity.name,
            "publisher": identity.publisher,
            "version": f"{identity.version.major}.{identity.version.minor}.{identity.version.build}.{identity.version.revision}",
            "full_name": pkg.id.full_name,
            "family_name": identity.family_name if hasattr(identity, "family_name") else "",
        }
    except Exception as e:
        logger.debug(f"Could not get package info: {e}")
        return None


# ── License Cache ────────────────────────────────────────────────────

def _load_license_cache() -> Optional[dict]:
    """Load cached license info if still valid."""
    try:
        if not _LICENSE_CACHE_FILE.exists():
            return None
        data = json.loads(_LICENSE_CACHE_FILE.read_text())
        cached_at = data.get("cached_at", 0)
        if (datetime.now().timestamp() - cached_at) < _LICENSE_CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _save_license_cache(data: dict):
    """Save license info to cache."""
    try:
        _LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data["cached_at"] = datetime.now().timestamp()
        _LICENSE_CACHE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _clear_license_cache():
    """Clear the license cache."""
    try:
        if _LICENSE_CACHE_FILE.exists():
            _LICENSE_CACHE_FILE.unlink()
    except Exception:
        pass


# ── Store License Checking ───────────────────────────────────────────

async def _check_store_license_async() -> dict:
    """Check the Microsoft Store license for subscription add-ons.

    Uses Windows.Services.Store.StoreContext to query the current user's
    license. Returns a dict with subscription status info.

    This is an async WinRT call — must be awaited.
    """
    try:
        from winrt.windows.services.store import StoreContext  # type: ignore

        context = StoreContext.get_default()

        # For Desktop Bridge / MSIX desktop apps, associate with window handle
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # Initialize with window handle for desktop apps
                from winrt.windows.services.store import StoreContext  # type: ignore
                # Use interop to set the window handle
                init = None
                try:
                    from winrt.windows.ui.core import CoreWindow  # type: ignore
                    # For packaged desktop apps, we may need IInitializeWithWindow
                    pass
                except Exception:
                    pass
        except Exception:
            pass

        # Get the app license (includes add-on licenses)
        license_result = await context.get_app_license_async()
        app_license = license_result

        if app_license is None:
            return {
                "status": "error",
                "message": "Could not retrieve Store license.",
                "is_store": True,
            }

        # Check if the main app license is active
        result = {
            "is_store": True,
            "app_is_active": app_license.is_active,
            "is_trial": app_license.is_trial if hasattr(app_license, "is_trial") else False,
        }

        # Check add-on licenses for subscription
        subscription_active = False
        subscription_info = {}

        if app_license.add_on_licenses:
            for addon_entry in app_license.add_on_licenses:
                license_obj = addon_entry.value
                sku_store_id = license_obj.sku_store_id

                # Check if this is one of our subscription add-ons
                is_our_subscription = any(
                    sku_store_id.startswith(sid) for sid in SUBSCRIPTION_STORE_IDS
                ) if SUBSCRIPTION_STORE_IDS else True  # If no IDs configured, accept any

                if is_our_subscription and license_obj.is_active:
                    subscription_active = True
                    subscription_info = {
                        "sku_store_id": sku_store_id,
                        "is_active": True,
                        "expiration_date": str(license_obj.expiration_date) if hasattr(license_obj, "expiration_date") else "",
                    }
                    break

        if subscription_active:
            result.update({
                "status": "active",
                "plan": "Microsoft Store Subscription",
                "subscription": subscription_info,
                "message": "Subscription active via Microsoft Store.",
            })
        elif result.get("is_trial"):
            # App itself is in trial mode (free trial from Store)
            trial_info = {}
            if hasattr(app_license, "trial_time_remaining"):
                remaining = app_license.trial_time_remaining
                days = remaining.days if hasattr(remaining, "days") else 0
                trial_info["days_remaining"] = days
            result.update({
                "status": "trial",
                "plan": "Microsoft Store Trial",
                "days_remaining": trial_info.get("days_remaining", 0),
                "message": "Free trial via Microsoft Store.",
            })
        else:
            result.update({
                "status": "no_subscription",
                "message": "No active subscription. Subscribe via Microsoft Store.",
            })

        return result

    except ImportError:
        return {
            "status": "error",
            "is_store": False,
            "message": "Windows Store APIs not available (not running as MSIX package).",
        }
    except Exception as e:
        logger.error(f"Store license check failed: {e}")
        return {
            "status": "error",
            "is_store": True,
            "message": f"License check failed: {str(e)[:100]}",
        }


def check_store_license() -> dict:
    """Synchronous wrapper for Store license check.

    Returns dict with keys:
      - status: "active" | "trial" | "no_subscription" | "error"
      - is_store: bool (True if running as MSIX Store app)
      - plan: str (subscription plan name)
      - message: str (human-readable status)
    """
    # Check cache first
    cached = _load_license_cache()
    if cached and cached.get("status") in ("active", "trial"):
        return cached

    if not is_msix_package():
        return {
            "status": "not_store",
            "is_store": False,
            "message": "Not running as Microsoft Store app.",
        }

    # Run the async WinRT call
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_check_store_license_async())
        loop.close()

        # Cache successful results
        if result.get("status") in ("active", "trial"):
            _save_license_cache(result)

        return result
    except Exception as e:
        logger.error(f"Store license sync check failed: {e}")
        return {
            "status": "error",
            "is_store": True,
            "message": f"License check failed: {str(e)[:100]}",
        }


# ── Store Purchase Flow ──────────────────────────────────────────────

async def _request_purchase_async(store_id: str = "") -> dict:
    """Trigger the Microsoft Store purchase UI for a subscription.

    This opens the native Windows Store purchase dialog.
    The user pays through their Microsoft account — no Stripe/PayPal needed.
    """
    try:
        from winrt.windows.services.store import StoreContext  # type: ignore

        context = StoreContext.get_default()

        # Get subscription product
        product_kinds = ["Durable"]
        result = await context.get_associated_store_products_async(product_kinds)

        if result.extended_error:
            return {
                "success": False,
                "message": f"Store error: {result.extended_error.message}",
            }

        # Find the subscription product
        target_product = None
        for item_key in result.products:
            product = result.products[item_key]
            if store_id and product.store_id == store_id:
                target_product = product
                break
            # If no specific store_id, find any subscription
            for sku in product.skus:
                if sku.is_subscription:
                    target_product = product
                    break
            if target_product:
                break

        if not target_product:
            return {
                "success": False,
                "message": "No subscription product found in Store.",
            }

        # Request purchase — opens native Store UI
        purchase_result = await target_product.request_purchase_async()

        status_map = {
            0: ("success", "Subscription purchased successfully!"),
            1: ("cancelled", "Purchase was cancelled."),
            2: ("error", "Server error during purchase."),
            3: ("error", "Network error during purchase."),
            4: ("already_owned", "You already own this subscription."),
        }

        status_code = purchase_result.status
        success_flag, msg = status_map.get(status_code, ("error", "Unknown purchase status."))

        if success_flag == "success" or success_flag == "already_owned":
            _clear_license_cache()  # Force re-check

        return {
            "success": success_flag in ("success", "already_owned"),
            "status": success_flag,
            "message": msg,
        }

    except ImportError:
        return {
            "success": False,
            "message": "Windows Store APIs not available.",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Purchase failed: {str(e)[:100]}",
        }


def request_store_purchase(store_id: str = "") -> dict:
    """Synchronous wrapper to trigger Microsoft Store purchase UI."""
    if not is_msix_package():
        return {
            "success": False,
            "message": "Store purchase only available on Windows Store version.",
        }

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_request_purchase_async(store_id))
        loop.close()
        return result
    except Exception as e:
        return {
            "success": False,
            "message": f"Purchase failed: {str(e)[:100]}",
        }


# ── Store Subscription Info ──────────────────────────────────────────

async def _get_store_plans_async() -> list:
    """Get available subscription plans from the Microsoft Store."""
    try:
        from winrt.windows.services.store import StoreContext  # type: ignore

        context = StoreContext.get_default()
        result = await context.get_associated_store_products_async(["Durable"])

        plans = []
        if result.extended_error:
            return plans

        for item_key in result.products:
            product = result.products[item_key]
            for sku in product.skus:
                if sku.is_subscription:
                    info = sku.subscription_info
                    plan = {
                        "store_id": product.store_id,
                        "title": product.title,
                        "description": product.description,
                        "price": sku.price.formatted_price if sku.price else "N/A",
                        "billing_period": info.billing_period,
                        "billing_period_unit": str(info.billing_period_unit),
                        "has_trial": info.has_trial_period,
                    }
                    if info.has_trial_period:
                        plan["trial_period"] = info.trial_period
                        plan["trial_period_unit"] = str(info.trial_period_unit)
                    plans.append(plan)

        return plans
    except Exception as e:
        logger.debug(f"Could not get store plans: {e}")
        return []


def get_store_plans() -> list:
    """Synchronous wrapper to get Store subscription plans."""
    if not is_msix_package():
        return []

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_get_store_plans_async())
        loop.close()
        return result
    except Exception:
        return []


# ── Convenience ──────────────────────────────────────────────────────

def is_store_subscription_active() -> bool:
    """Quick check: does the current user have an active Store subscription?

    Returns True if:
      - Running as MSIX AND has active subscription or trial
    Returns False if:
      - Not MSIX (caller should fall through to gateway auth)
      - MSIX but no active subscription
    """
    if not is_msix_package():
        return False

    info = check_store_license()
    return info.get("status") in ("active", "trial")


def should_use_store_billing() -> bool:
    """Determine if this build should use Microsoft Store billing.

    Returns True ONLY for Windows MSIX packages (Store installs).
    All other platforms use the normal gateway auth flow.
    """
    return is_msix_package()
