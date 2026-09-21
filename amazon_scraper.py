"""
amazon_scraper.py
=================
Root module delegating to scrapers.amazon_scraper for backward compatibility.
"""

from scrapers.amazon_scraper import AmazonScraper
from scrapers.scraper_result import ScrapeStatus

_default_scraper = AmazonScraper()


def get_amazon_products(query: str, return_status: bool = False):
    """
    Search Amazon for ANY query.
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


def scrape_amazon_url(url: str, return_status: bool = False):
    """
    Scrape canonical product from an Amazon URL.
    """
    product, status, error_msg = _default_scraper.scrape_product_url(url)
    status_str = status.value if isinstance(status, ScrapeStatus) else str(status)
    if return_status:
        return product, status_str, error_msg, "live"
    return product
