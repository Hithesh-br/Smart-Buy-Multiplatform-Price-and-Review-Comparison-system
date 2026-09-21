"""
scrapers/base_scraper.py
========================
Abstract Base Class for marketplace scraper adapters.
Enforces standard interfaces, structured failure classification,
dedicated logging to logs/scraper.log, and optional debug dumps.
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from scrapers.scraper_result import ScrapeStatus
from scrapers.browser_manager import BrowserManager

# Configure dedicated scraper logger
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
SCRAPER_LOG_FILE = os.path.join(LOG_DIR, "scraper.log")

scraper_logger = logging.getLogger("smartbuy.scraper")
scraper_logger.setLevel(logging.INFO)
if not scraper_logger.handlers:
    fh = logging.FileHandler(SCRAPER_LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    fh.setFormatter(formatter)
    scraper_logger.addHandler(fh)


class BaseScraper(ABC):
    """
    Standard interface for all platform scrapers (Amazon, Flipkart, Meesho).
    """

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.browser_manager = BrowserManager.get_instance()
        self.max_results = 20
        self.debug_mode = os.getenv("SCRAPER_DEBUG", "false").lower() in ("true", "1", "yes")
        self.debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug", platform_name.lower())
        if self.debug_mode:
            os.makedirs(self.debug_dir, exist_ok=True)

    @abstractmethod
    def search_products(self, query: str) -> tuple[list[dict], ScrapeStatus, Optional[str]]:
        """
        Search marketplace for query.
        Returns:
            (products: list[dict], status: ScrapeStatus, error_message: str | None)
        """
        pass

    @abstractmethod
    def get_product_details(self, url: str) -> Optional[dict]:
        """
        Fetch additional specifications for a specific product page.
        """
        pass

    @abstractmethod
    def extract_product_data(self, element) -> Optional[dict]:
        """
        Extract normalized product data from a single product card element.
        """
        pass

    def log_scrape_event(
        self,
        query: str,
        status: ScrapeStatus,
        duration: float,
        detected_count: int = 0,
        extracted_count: int = 0,
        page_loaded: bool = True,
        selector_used: str = "primary",
        retry_count: int = 0,
        error_msg: Optional[str] = None
    ):
        """Log structured scrape summary to logs/scraper.log."""
        msg = (
            f"{self.platform_name.upper()}\n"
            f"Query: {query}\n"
            f"Search page: {'loaded' if page_loaded else 'failed'}\n"
            f"Selector used: {selector_used}\n"
            f"Products detected: {detected_count}\n"
            f"Products extracted: {extracted_count}\n"
            f"Status: {status.value.upper()}\n"
            f"Duration: {duration:.2f} sec"
        )
        if retry_count > 0:
            msg += f"\nRetry count: {retry_count}"
        if error_msg:
            msg += f"\nError: {error_msg}"
        scraper_logger.info(msg)

    def save_debug_dump(self, page, query: str, tag: str = "dump"):
        """Save HTML and screenshot when SCRAPER_DEBUG=true."""
        if not self.debug_mode or not page:
            return
        try:
            timestamp = int(time.time())
            safe_q = "".join(c if c.isalnum() else "_" for c in query)[:20]
            base_path = os.path.join(self.debug_dir, f"{safe_q}_{tag}_{timestamp}")
            
            html_content = page.content()
            with open(f"{base_path}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
                
            page.screenshot(path=f"{base_path}.png")
            scraper_logger.info(f"[{self.platform_name}] Saved debug dump to {base_path}")
        except Exception as e:
            scraper_logger.warning(f"[{self.platform_name}] Failed to save debug dump: {e}")
