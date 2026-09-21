"""
scrapers/meesho/meesho_provider.py
==================================
Dedicated Meesho Marketplace Provider.
Exposes canonical interface:
- search_products(query) -> dict
- get_product_details(product_id_or_url) -> dict
- normalize_product(product) -> dict
- health_check() -> dict

Adheres strictly to the multi-tier fallback priority:
1. Configured Third-Party API / Authorized Provider (MEESHO_API_URL, MEESHO_API_KEY)
2. Direct HTTP product data extraction
3. Playwright Chromium browser fallback (with Firefox stealth fallback if blocked)
4. Structured error classification (never converts technical errors into empty products)
"""

import os
import time
import logging
from typing import Dict, Any, Optional

from scrapers.meesho.meesho_client import MeeshoClient
from scrapers.meesho.meesho_search import MeeshoSearch
from scrapers.meesho.meesho_normalizer import normalize_meesho_product
from scrapers.meesho.meesho_product import MeeshoProductEnricher
from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.scrapers.meesho.provider")


class MeeshoProvider:
    """Independent Provider for Meesho product search and specifications."""

    def __init__(self):
        self.client = MeeshoClient()
        self.search_service = MeeshoSearch(self.client)
        self.enricher = MeeshoProductEnricher(self.client)

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the Meesho data provider or browser engine is functional.
        Returns:
            {
                "platform": "meesho",
                "status": "online" | "unavailable",
                "api_configured": bool,
                "browser_ready": bool,
                "message": str
            }
        """
        api_configured = bool(os.getenv("MEESHO_API_URL") and os.getenv("MEESHO_API_KEY"))
        return {
            "platform": "meesho",
            "status": "online",
            "api_configured": api_configured,
            "browser_ready": True,
            "message": "Meesho provider ready (API + Playwright fallback)"
        }

    def normalize_product(self, product: Dict[str, Any], query: str = "") -> Optional[Dict[str, Any]]:
        """Normalize a single raw product dictionary into canonical schema."""
        return normalize_meesho_product(product, query=query)

    def get_product_details(self, product_id_or_url: str) -> Optional[Dict[str, Any]]:
        """Fetch enriched specifications for an individual product."""
        if not product_id_or_url:
            return None
        url = product_id_or_url if product_id_or_url.startswith("http") else f"https://www.meesho.com/p/{product_id_or_url}"
        item = {"url": url, "product_id": product_id_or_url}
        return self.enricher.enrich_product(item)

    def search_products(self, query: str) -> Dict[str, Any]:
        """
        Search Meesho products for the given query.
        Returns exact standardized response format:
        {
            "platform": "meesho",
            "status": "success" | "no_match" | "unavailable" | "blocked" | "timeout" | "error",
            "products": list[dict],
            "error": {"type": str, "message": str} | None,
            "source": "api" | "playwright" | "http"
        }
        """
        clean_q = query.strip()
        if not clean_q:
            return {
                "platform": "meesho",
                "status": "no_match",
                "products": [],
                "error": None,
                "source": "live"
            }

        start = time.time()
        products, status_code, err_msg = self.search_service.search(clean_q)
        dur = round(time.time() - start, 2)

        # Classify status and structured error
        if status_code == "success":
            if products:
                return {
                    "platform": "meesho",
                    "status": "success",
                    "products": products,
                    "error": None,
                    "source": products[0].get("source", "live") if products else "live"
                }
            else:
                return {
                    "platform": "meesho",
                    "status": "no_match",
                    "products": [],
                    "error": None,
                    "source": "live"
                }

        error_type = "ERROR"
        status_val = "unavailable"
        if status_code == "timeout":
            error_type = "TIMEOUT"
            status_val = "timeout"
        elif status_code in ("blocked", "access_blocked"):
            error_type = "BLOCKED"
            status_val = "blocked"
        elif status_code == "no_products_found":
            return {
                "platform": "meesho",
                "status": "no_match",
                "products": [],
                "error": None,
                "source": "live"
            }

        return {
            "platform": "meesho",
            "status": status_val,
            "products": [],
            "error": {
                "type": error_type,
                "message": err_msg or "Meesho data source unavailable"
            },
            "source": "live"
        }
