"""
scrapers/amazon/__init__.py
===========================
Independent Amazon Marketplace Package.
"""

from typing import Dict, Any, List, Tuple, Optional

from scrapers.amazon.client import AmazonClient
from scrapers.amazon.parser import parse_amazon_card
from scrapers.amazon.normalizer import normalize_amazon_product
from scrapers.amazon.search import AmazonSearch
from scrapers.scraper_result import ScrapeStatus


class AmazonProvider:
    """Independent Provider for Amazon.in search and specifications."""

    def __init__(self):
        self.client = AmazonClient()
        self.search_service = AmazonSearch(self.client)

    def health_check(self) -> Dict[str, Any]:
        return {
            "platform": "amazon",
            "status": "online",
            "message": "Amazon provider ready"
        }

    def search_products(self, query: str) -> Dict[str, Any]:
        """Returns standard {platform, status, products, error, source} structure."""
        items, status_code, err_msg = self.search_service.search(query)
        if status_code == "success":
            return {
                "platform": "amazon",
                "status": "success" if items else "no_match",
                "products": items,
                "error": None,
                "source": "live"
            }
        return {
            "platform": "amazon",
            "status": status_code,
            "products": [],
            "error": {"type": status_code.upper(), "message": err_msg or "Amazon provider unavailable"},
            "source": "live"
        }


__all__ = [
    "AmazonProvider",
    "AmazonClient",
    "AmazonSearch",
    "AmazonParser",
    "normalize_amazon_product"
]
