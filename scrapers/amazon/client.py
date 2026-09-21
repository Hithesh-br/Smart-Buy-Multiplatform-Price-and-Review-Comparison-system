"""
scrapers/amazon/client.py
=========================
Independent HTTP & Browser connection manager for Amazon.in.
"""

import os
import time
import urllib.parse
import logging
from typing import Optional, Tuple, Dict, Any, List
import requests

from scrapers.browser_manager import BrowserManager

logger = logging.getLogger("smartbuy.scrapers.amazon.client")

AMAZON_API_URL = os.getenv("AMAZON_API_URL", "").strip()
AMAZON_API_KEY = os.getenv("AMAZON_API_KEY", "").strip()
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "45000"))


class AmazonClient:
    """Handles API requests, direct fetches, and browser sessions for Amazon."""

    def __init__(self):
        self.browser_manager = BrowserManager.get_instance()

    def fetch_api(self, query: str) -> Tuple[Optional[List[Dict[str, Any]]], str, Optional[str]]:
        """Call configured Amazon API if available."""
        if not AMAZON_API_URL or not AMAZON_API_KEY:
            return None, "api_unconfigured", "AMAZON_API_URL not set"

        headers = {"Authorization": f"Bearer {AMAZON_API_KEY}", "Accept": "application/json"}
        try:
            resp = requests.get(AMAZON_API_URL, headers=headers, params={"q": query}, timeout=SCRAPER_TIMEOUT / 1000)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products") or data.get("items") or []
                return products, "success", None
            return None, "scraper_error", f"HTTP {resp.status_code}"
        except Exception as e:
            return None, "scraper_error", str(e)

    def fetch_http(self, url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """Level 2: Direct HTTP extraction with standard browser headers."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                html = resp.text
                if "robot check" in html.lower() or "captcha" in html.lower():
                    return None, "blocked", "Amazon CAPTCHA in HTTP response"
                return html, "success", None
            elif resp.status_code in (403, 503):
                return None, "blocked", f"HTTP {resp.status_code} Access Blocked"
            return None, "scraper_error", f"HTTP {resp.status_code}"
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str:
                return None, "timeout", str(e)
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
            elif "blocked" in err_str or "captcha" in err_str or "access denied" in err_str:
                return None, "blocked", str(exc)
            return None, "scraper_error", str(exc)
