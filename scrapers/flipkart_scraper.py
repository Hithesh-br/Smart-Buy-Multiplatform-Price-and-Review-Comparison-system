"""
scrapers/flipkart_scraper.py
============================
Dedicated Flipkart marketplace scraper adapter.
Delegates to the modular scrapers.flipkart package:
- client.py (connection & fallback)
- parser.py (HTML / grid / list parsing)
- normalizer.py (canonical schema & unit price)
- search.py (search orchestration)
- url_scraper.py (direct product page extraction)
"""

import time
import logging
from typing import Optional

from scrapers.base_scraper import BaseScraper
from scrapers.scraper_result import ScrapeStatus
from scrapers.flipkart.search import FlipkartSearch
from scrapers.flipkart.normalizer import normalize_flipkart_product

logger = logging.getLogger("smartbuy.scrapers.flipkart")


class FlipkartScraper(BaseScraper):
    """
    Adapter integrating scrapers.flipkart with SmartBuy's BaseScraper interface.
    """

    def __init__(self):
        super().__init__("flipkart")
        self.max_results = 20
        self.search_service = FlipkartSearch()
        self.url_scraper = None

    def _get_url_scraper(self):
        if self.url_scraper is None:
            from scrapers.flipkart.url_scraper import FlipkartUrlScraper
            self.url_scraper = FlipkartUrlScraper(client=self.search_service.client)
        return self.url_scraper

    def search_products(self, query: str) -> tuple[list[dict], ScrapeStatus, Optional[str]]:
        start_time = time.time()
        clean_query = query.strip()
        if not clean_query:
            return [], ScrapeStatus.NO_RESULTS, "Empty search query"

        items, status_code, err_msg = self.search_service.search(clean_query, limit=self.max_results)
        dur = round(time.time() - start_time, 2)

        status_map = {
            "success": ScrapeStatus.SUCCESS,
            "no_match": ScrapeStatus.NO_RESULTS,
            "blocked": ScrapeStatus.BLOCKED,
            "timeout": ScrapeStatus.TIMEOUT,
            "unavailable": ScrapeStatus.SCRAPER_ERROR,
        }
        status_enum = status_map.get(status_code, ScrapeStatus.UNKNOWN_ERROR)

        if items:
            self.log_scrape_event(clean_query, ScrapeStatus.SUCCESS, dur, len(items), len(items), selector_used="modular_flipkart")
            return items, ScrapeStatus.SUCCESS, None

        self.log_scrape_event(clean_query, status_enum, dur, 0, 0, selector_used="modular_flipkart", error_msg=err_msg)
        return [], status_enum, err_msg

    def scrape_product_url(self, url: str) -> tuple[Optional[dict], ScrapeStatus, Optional[str]]:
        """Scrape canonical product details from a specific Flipkart product URL."""
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
            self.log_scrape_event(url, ScrapeStatus.SUCCESS, dur, 1, 1, selector_used="flipkart_url_scraper")
            return product, ScrapeStatus.SUCCESS, None

        self.log_scrape_event(url, status_enum, dur, 0, 0, selector_used="flipkart_url_scraper", error_msg=err_msg)
        return None, status_enum, err_msg

    def get_product_details(self, url: str) -> Optional[dict]:
        """Fetch additional specifications for a specific product page."""
        prod, _, _ = self.scrape_product_url(url)
        return prod

    def extract_product_data(self, element) -> Optional[dict]:
        """Extract normalized product data from a single product card element or dict."""
        if isinstance(element, dict):
            return normalize_flipkart_product(element)
        return None
