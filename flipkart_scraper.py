"""
flipkart_scraper.py
===================
Root module delegating to scrapers.flipkart_scraper for backward compatibility.
"""

from scrapers.flipkart_scraper import FlipkartScraper
from scrapers.scraper_result import ScrapeStatus

_default_scraper = FlipkartScraper()


def get_flipkart_products(query: str, return_status: bool = False):
    """
    Search Flipkart for ANY query.
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


def scrape_flipkart_url(url: str, return_status: bool = False):
    """
    Scrape canonical product from a Flipkart URL.
    """
    product, status, error_msg = _default_scraper.scrape_product_url(url)
    status_str = status.value if isinstance(status, ScrapeStatus) else str(status)
    if return_status:
        return product, status_str, error_msg, "live"
    return product
