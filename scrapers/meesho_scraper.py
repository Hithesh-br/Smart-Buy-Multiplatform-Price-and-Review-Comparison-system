"""
scrapers/meesho_scraper.py
==========================
Dedicated Meesho marketplace scraper adapter.
Delegates to the modular scrapers.meesho package:
- meesho_client.py (connection & fallback)
- meesho_parser.py (multi-strategy HTML / JSON-LD / hydration parsing)
- meesho_normalizer.py (canonical schema & unit price)
- meesho_product.py (detail enrichment)
- meesho_search.py (search orchestration)
- url_scraper.py (direct product page extraction)
"""

import time
import logging
from typing import Optional

from scrapers.base_scraper import BaseScraper
from scrapers.scraper_result import ScrapeStatus
from scrapers.meesho import (
    MeeshoScraper as ModularMeeshoScraper,
    normalize_meesho_product,
    MeeshoProductEnricher
)

logger = logging.getLogger("smartbuy.scrapers.meesho")


class MeeshoScraper(BaseScraper):
    """
    Adapter integrating scrapers.meesho with SmartBuy's BaseScraper interface.
    """

    def __init__(self):
        super().__init__("meesho")
        self.modular_scraper = ModularMeeshoScraper()
        self.enricher = MeeshoProductEnricher()
        self.url_scraper = None

    def _get_url_scraper(self):
        if self.url_scraper is None:
            from scrapers.meesho.url_scraper import MeeshoUrlScraper
            self.url_scraper = MeeshoUrlScraper(client=self.modular_scraper.search_service.client)
        return self.url_scraper

    def search_products(self, query: str) -> tuple[list[dict], ScrapeStatus, Optional[str]]:
        start_time = time.time()
        clean_query = query.strip()
        if not clean_query:
            return [], ScrapeStatus.NO_RESULTS, "Empty search query"

        items, status_enum, err_msg = self.modular_scraper.search_products(clean_query)
        dur = round(time.time() - start_time, 2)

        if items:
            self.log_scrape_event(clean_query, ScrapeStatus.SUCCESS, dur, len(items), len(items), selector_used="modular_meesho")
            return items, ScrapeStatus.SUCCESS, None

        self.log_scrape_event(clean_query, status_enum, dur, 0, 0, selector_used="modular_meesho", error_msg=err_msg)
        return [], status_enum, err_msg

    def scrape_product_url(self, url: str) -> tuple[Optional[dict], ScrapeStatus, Optional[str]]:
        """Scrape canonical product details from a specific Meesho product URL."""
        start_time = time.time()
        url_scraper = self._get_url_scraper()
        product, status_code, err_msg = url_scraper.scrape_url(url)
        dur = round(time.time() - start_time, 2)

        status_map = {
            "success": ScrapeStatus.SUCCESS,
            "blocked": ScrapeStatus.BLOCKED,
            "timeout": ScrapeStatus.TIMEOUT,
            "scraper_error": ScrapeStatus.SCRAPER_ERROR,
        }
        status_enum = status_map.get(status_code, ScrapeStatus.SCRAPER_ERROR)

        if product:
            self.log_scrape_event(url, ScrapeStatus.SUCCESS, dur, 1, 1, selector_used="meesho_url_scraper")
            return product, ScrapeStatus.SUCCESS, None

        self.log_scrape_event(url, status_enum, dur, 0, 0, selector_used="meesho_url_scraper", error_msg=err_msg)
        return None, status_enum, err_msg

    def get_product_details(self, url: str) -> Optional[dict]:
        """Fetch additional specifications for a specific product page."""
        if not url:
            return None
        prod, _, _ = self.scrape_product_url(url)
        if prod:
            return prod
        return self.enricher.enrich_product({"url": url})

    def extract_product_data(self, element) -> Optional[dict]:
        """Extract normalized product data from a single product card element or dict."""
        if isinstance(element, dict):
            return normalize_meesho_product(element)
        return None
