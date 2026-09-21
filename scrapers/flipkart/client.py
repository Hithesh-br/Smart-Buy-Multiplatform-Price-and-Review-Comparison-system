"""
scrapers/flipkart/client.py
===========================
Independent HTTP & Browser connection manager for Flipkart.com.
"""

import os
import time
import urllib.parse
import logging
from typing import Optional, Tuple, Dict, Any, List
import requests

from scrapers.browser_manager import BrowserManager

logger = logging.getLogger("smartbuy.scrapers.flipkart.client")

FLIPKART_API_URL = os.getenv("FLIPKART_API_URL", "").strip()
FLIPKART_API_KEY = os.getenv("FLIPKART_API_KEY", "").strip()
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "45000"))


class FlipkartClient:
    """Handles API requests, direct fetches, and browser sessions for Flipkart."""

    def __init__(self):
        self.browser_manager = BrowserManager.get_instance()

    def fetch_api(self, query: str) -> Tuple[Optional[List[Dict[str, Any]]], str, Optional[str]]:
        """Call configured Flipkart API if available."""
        if not FLIPKART_API_URL or not FLIPKART_API_KEY:
            return None, "api_unconfigured", "FLIPKART_API_URL not set"

        headers = {"Authorization": f"Bearer {FLIPKART_API_KEY}", "Accept": "application/json"}
        try:
            resp = requests.get(FLIPKART_API_URL, headers=headers, params={"q": query}, timeout=SCRAPER_TIMEOUT / 1000)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products") or data.get("items") or []
                return products, "success", None
            return None, "scraper_error", f"HTTP {resp.status_code}"
        except Exception as e:
            return None, "scraper_error", str(e)

    def execute_browser_task(self, task_callable) -> Tuple[Any, str, Optional[str]]:
        """Execute task on Playwright Chromium browser."""
        try:
            page, context = self.browser_manager.new_page(engine="chromium")
            try:
                result = task_callable(page)
                return result, "success", None
            finally:
                if context:
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as exc:
            err_str = str(exc).lower()
            if "timeout" in err_str:
                return None, "timeout", str(exc)
            elif "blocked" in err_str or "access denied" in err_str or "captcha" in err_str:
                return None, "blocked", str(exc)
            return None, "scraper_error", str(exc)
