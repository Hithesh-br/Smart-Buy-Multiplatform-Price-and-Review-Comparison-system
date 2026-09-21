"""
scrapers/meesho/meesho_client.py
================================
Client handling connection mechanics for Meesho:
- Configured API provider (Level 1)
- Direct HTTP requests & JSON-LD extraction (Level 2)
- Playwright Chromium / Firefox engine with anti-bot resistance (Level 3)
- Error classification and structured failures (Level 4)
"""

import os
import time
import json
import logging
import urllib.parse
from typing import Optional, Tuple, Dict, Any, List
import requests

from scrapers.browser_manager import BrowserManager
from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.scrapers.meesho.client")

MEESHO_TIMEOUT_MS = int(os.getenv("MEESHO_TIMEOUT_MS", "45000"))
MEESHO_HEADLESS = os.getenv("MEESHO_HEADLESS", "true").lower() in ("true", "1", "yes")
MEESHO_API_URL = os.getenv("MEESHO_API_URL", "").strip()
MEESHO_API_KEY = os.getenv("MEESHO_API_KEY", "").strip()

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


class MeeshoClient:
    """Manages connections, API calls, and browser sessions for Meesho."""

    def __init__(self):
        self.browser_manager = BrowserManager.get_instance()
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_api(self, query: str) -> Tuple[Optional[List[Dict[str, Any]]], str, Optional[str]]:
        """
        Level 1: Call configured third-party product data API if keys exist in .env.
        Returns (raw_items, status, error_message).
        """
        if not MEESHO_API_URL or not MEESHO_API_KEY:
            return None, "api_unconfigured", "MEESHO_API_URL or MEESHO_API_KEY not set"

        headers = {
            "Authorization": f"Bearer {MEESHO_API_KEY}",
            "X-API-Key": MEESHO_API_KEY,
            "Accept": "application/json"
        }
        params = {"q": query, "limit": 15}

        for attempt in range(2):
            try:
                resp = requests.get(MEESHO_API_URL, headers=headers, params=params, timeout=MEESHO_TIMEOUT_MS / 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("products") or data.get("items") or data.get("data")
                    if isinstance(products, list) and len(products) > 0:
                        return products, "success", None
                    return [], "no_products_found", "API returned empty product list"
                elif resp.status_code in (401, 403):
                    return None, "blocked", f"API Authentication failed ({resp.status_code})"
                elif resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None, "scraper_error", f"API HTTP status {resp.status_code}"
            except requests.Timeout:
                return None, "timeout", "API request timed out"
            except Exception as e:
                return None, "scraper_error", f"API error: {e}"

        return None, "scraper_error", "API request failed after retries"

    def fetch_html(self, url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Level 2: Direct HTTP fetch with requests.
        Returns (html_content, status, error_message).
        """
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                if "Access Denied" in resp.text or "Security Challenge" in resp.text:
                    return None, "blocked", "Meesho edge firewall blocked direct HTTP"
                return resp.text, "success", None
            elif resp.status_code in (403, 401):
                return None, "blocked", f"HTTP {resp.status_code} Forbidden"
            return None, "scraper_error", f"HTTP {resp.status_code}"
        except requests.Timeout:
            return None, "timeout", "HTTP request timed out"
        except Exception as e:
            return None, "scraper_error", str(e)

    def execute_browser_task(self, task_callable, query: str = "") -> Tuple[Any, str, Optional[str]]:
        """
        Level 3: Run task in browser. Attempts Chromium first, auto-falling back to
        Firefox stealth context if Akamai CDN blocks or challenges Chromium.
        """
        engines = ["chromium", "firefox"]
        last_error = None
        last_status = "scraper_error"

        for engine in engines:
            page, context = None, None
            try:
                page, context = self.browser_manager.new_page(engine=engine)
                result = task_callable(page)
                if result:
                    return result, "success", None
            except Exception as exc:
                err_str = str(exc).lower()
                last_error = str(exc)
                if "timeout" in err_str:
                    last_status = "timeout"
                elif "access denied" in err_str or "forbidden" in err_str or "403" in err_str:
                    last_status = "blocked"
                    logger.warning(f"[MeeshoClient] {engine} blocked by edge protection; trying fallback engine...")
                else:
                    last_status = "scraper_error"
            finally:
                if context:
                    try:
                        context.close()
                    except Exception:
                        pass

        return None, last_status, last_error
