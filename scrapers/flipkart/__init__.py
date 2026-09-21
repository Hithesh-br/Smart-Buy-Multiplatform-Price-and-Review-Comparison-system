"""
scrapers/flipkart/__init__.py
=============================
Independent Flipkart Marketplace Package.
"""

from typing import Dict, Any, List, Tuple, Optional

from scrapers.flipkart.client import FlipkartClient
from scrapers.flipkart.parser import parse_flipkart_card
from scrapers.flipkart.normalizer import normalize_flipkart_product
from scrapers.flipkart.search import FlipkartSearch
from scrapers.scraper_result import ScrapeStatus


class FlipkartProvider:
    """Independent Provider for Flipkart search and specifications."""

    def __init__(self):
        self.client = FlipkartClient()
        self.search_service = FlipkartSearch(self.client)

    def health_check(self) -> Dict[str, Any]:
        return {
            "platform": "flipkart",
            "status": "online",
            "message": "Flipkart provider ready"
        }

    def search_products(self, query: str) -> Dict[str, Any]:
        """Returns standard {platform, status, products, error, source} structure."""
        items, status_code, err_msg = self.search_service.search(query)
        if status_code == "success":
            return {
                "platform": "flipkart",
                "status": "success" if items else "no_match",
                "products": items,
                "error": None,
                "source": "live"
            }
        return {
            "platform": "flipkart",
            "status": status_code,
            "products": [],
            "error": {"type": status_code.upper(), "message": err_msg or "Flipkart provider unavailable"},
            "source": "live"
        }


__all__ = [
    "FlipkartProvider",
    "FlipkartClient",
    "FlipkartSearch",
    "FlipkartParser",
    "normalize_flipkart_product"
]
