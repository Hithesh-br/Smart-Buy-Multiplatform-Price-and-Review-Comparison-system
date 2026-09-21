"""
scrapers/meesho/__init__.py
===========================
Dedicated Meesho Scraper Package:
- meesho_client.py: Connection mechanics & multi-layer fallback
- meesho_parser.py: HTML, JSON-LD, Next.js hydration state parser
- meesho_normalizer.py: Canonical product normalizer & unit price calculator
- meesho_product.py: Deep detail specification enricher
- meesho_search.py: Search orchestrator
"""

from typing import List, Dict, Any, Tuple, Optional

from scrapers.meesho.meesho_client import MeeshoClient
from scrapers.meesho.meesho_parser import (
    extract_title_from_slug,
    parse_json_ld,
    parse_next_data,
    parse_price_value,
    parse_rating_and_reviews
)
from scrapers.meesho.meesho_normalizer import (
    normalize_meesho_product,
    calculate_unit_price
)
from scrapers.meesho.meesho_product import MeeshoProductEnricher
from scrapers.meesho.meesho_search import MeeshoSearch
from scrapers.scraper_result import ScrapeStatus


class MeeshoScraper:
    """
    Standard SmartBuy scraper interface for Meesho.
    Provides isolated search execution via search_products(query).
    """

    def __init__(self):
        self.search_service = MeeshoSearch()

    def search_products(self, query: str) -> Tuple[List[Dict[str, Any]], Any, Optional[str]]:
        """
        Executes multi-tier Meesho search.
        Returns: (products, status, error_message)
        """
        items, status_str, err_msg = self.search_service.search(query)

        # Map string status to ScrapeStatus enum
        if status_str == "success":
            status_enum = ScrapeStatus.SUCCESS if items else ScrapeStatus.NO_PRODUCTS_FOUND
        elif status_str == "blocked":
            status_enum = ScrapeStatus.ACCESS_BLOCKED
        elif status_str == "timeout":
            status_enum = ScrapeStatus.TIMEOUT
        elif status_str == "no_products_found":
            status_enum = ScrapeStatus.NO_PRODUCTS_FOUND
        else:
            status_enum = getattr(ScrapeStatus, "SCRAPER_ERROR", ScrapeStatus.UNAVAILABLE)

        return items, status_enum, err_msg


from scrapers.meesho.meesho_provider import MeeshoProvider


__all__ = [
    "MeeshoProvider",
    "MeeshoScraper",
    "MeeshoSearch",
    "MeeshoClient",
    "MeeshoProductEnricher",
    "normalize_meesho_product",
    "extract_title_from_slug",
    "calculate_unit_price",
    "parse_json_ld",
    "parse_next_data"
]
