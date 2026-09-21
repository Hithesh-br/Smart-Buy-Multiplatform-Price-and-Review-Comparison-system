"""
services/meesho_api_client.py
=============================
Configured Third-Party / Official Meesho API Client.
Reads MEESHO_API_URL and MEESHO_API_KEY from environment variables.
Never uses hardcoded API keys or synthetic mock data.
If not configured or if any error occurs, cleanly returns None so the
Playwright / HTTP fallback chain engages automatically.
"""

import os
import logging
from typing import Optional
import requests
from services.meesho_adapter import normalize_meesho_product

logger = logging.getLogger("smartbuy.meesho_api")


class MeeshoAPIClient:
    def __init__(self):
        self.api_url = os.getenv("MEESHO_API_URL", "").strip()
        self.api_key = os.getenv("MEESHO_API_KEY", "").strip()
        self.timeout = int(os.getenv("MEESHO_API_TIMEOUT", "8"))

    def is_configured(self) -> bool:
        """Returns True only when both API URL and Key are explicitly provided."""
        return bool(self.api_url and self.api_key)

    def search_products(self, query: str, limit: int = 10) -> Optional[list[dict]]:
        """
        Executes search against configured Meesho product API.
        Returns list of normalized products on success, or None on failure/bypass.
        """
        if not self.is_configured():
            logger.debug("[MEESHO API] API not configured in .env; skipping to Playwright.")
            return None

        clean_q = query.strip()
        if not clean_q:
            return None

        logger.info(f"[MEESHO API] Querying configured API for '{clean_q}'...")
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "SmartBuy/2.0",
                "Accept": "application/json"
            }
            params = {"q": clean_q, "limit": limit}

            resp = requests.get(self.api_url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"[MEESHO API] Provider returned status {resp.status_code}: {resp.text[:120]}")
                return None

            data = resp.json()
            raw_items = data.get("products") or data.get("items") or data.get("data") or []
            if not isinstance(raw_items, list) or len(raw_items) == 0:
                logger.warning(f"[MEESHO API] Provider returned 0 products for '{clean_q}'")
                return None

            normalized_list = []
            for item in raw_items:
                norm = normalize_meesho_product(item, query=clean_q)
                if norm:
                    normalized_list.append(norm)

            if normalized_list:
                logger.info(f"[MEESHO API] Successfully extracted {len(normalized_list)} valid products from API.")
                return normalized_list
            return None

        except requests.exceptions.Timeout:
            logger.warning("[MEESHO API] Request timed out. Proceeding to Playwright fallback.")
            return None
        except Exception as exc:
            logger.warning(f"[MEESHO API] Error executing API query: {exc}. Proceeding to Playwright fallback.")
            return None
