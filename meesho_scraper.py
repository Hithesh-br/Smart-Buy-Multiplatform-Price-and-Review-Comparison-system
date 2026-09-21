"""
meesho_scraper.py
=================
Root module delegating to scrapers.meesho_scraper for backward compatibility.
"""

from scrapers.meesho_scraper import MeeshoScraper
from scrapers.scraper_result import ScrapeStatus

_default_scraper = MeeshoScraper()


def get_meesho_products(query: str, return_status: bool = False):
    """
    Search Meesho for ANY query.
    Returns:
        If return_status is True: tuple (products, status_string, error_msg, source)
        Otherwise: list of products
    """
    products, status, error_msg = _default_scraper.search_products(query)
    source = "live"
    status_str = status.value if isinstance(status, ScrapeStatus) else str(status)

    if return_status:
        return products, status_str, error_msg, source
    return products


def scrape_meesho_url(url: str, return_status: bool = False):
    """
    Scrape canonical product from a Meesho URL.
    """
    product, status, error_msg = _default_scraper.scrape_product_url(url)
    status_str = status.value if isinstance(status, ScrapeStatus) else str(status)
    if return_status:
        return product, status_str, error_msg, "live"
    return product
