"""
scrapers/flipkart/search.py
===========================
Independent search orchestrator for Flipkart.com.
"""

import time
import urllib.parse
import logging
from typing import List, Dict, Any, Tuple, Optional
import bs4

from scrapers.flipkart.client import FlipkartClient
from scrapers.flipkart.parser import parse_flipkart_card
from scrapers.flipkart.normalizer import normalize_flipkart_product
from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.scrapers.flipkart.search")


class FlipkartSearch:
    """Executes Flipkart search via API or Playwright browser."""

    def __init__(self, client: Optional[FlipkartClient] = None):
        self.client = client or FlipkartClient()

    def search(self, query: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
        start_time = time.time()
        clean_q = query.strip()
        if not clean_q:
            return [], "no_match", "Empty query"

        # Try configured API first
        api_prods, api_stat, api_err = self.client.fetch_api(clean_q)
        if api_stat == "success" and api_prods:
            norm_list = [normalize_flipkart_product(p, query=clean_q) for p in api_prods]
            valid = [p for p in norm_list if p is not None][:limit]
            dur = time.time() - start_time
            log_scraper_event("flipkart", clean_q, "success", retry=0, products_count=len(valid), duration=dur)
            return valid, "success", None

        # Playwright browser search
        search_url = f"https://www.flipkart.com/search?q={urllib.parse.quote(clean_q)}"

        def _browser_task(page):
            page.goto(search_url, wait_until="domcontentloaded", timeout=28000)
            page.wait_for_timeout(1000)

            title = page.title().lower()
            if "access denied" in title or "503 service unavailable" in title:
                raise RuntimeError("Flipkart access restricted")

            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.35)")
                page.wait_for_timeout(300)
            except Exception:
                pass

            soup = bs4.BeautifulSoup(page.content(), "html.parser")
            cards = soup.select('div[data-id], div.slAVV4, div.jIjQ8S, div._4ddWXP, div._1xHGKq, div._75nlfW, div.cPHDOP, div._1AtVbE')
            if not cards:
                cards = soup.select('div[data-id]')

            parsed = []
            seen_ids = set()
            for c in cards:
                data = parse_flipkart_card(c)
                if data and data['product_id'] not in seen_ids:
                    seen_ids.add(data['product_id'])
                    parsed.append(data)
                if len(parsed) >= limit:
                    break
            return parsed

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        dur = time.time() - start_time

        if browser_stat == "success" and browser_res:
            norm_list = [normalize_flipkart_product(p, query=clean_q) for p in browser_res]
            valid = [p for p in norm_list if p is not None]
            log_scraper_event("flipkart", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
            return valid, "success", None

        status_val = browser_stat if browser_stat in ("blocked", "timeout") else "unavailable"
        log_scraper_event("flipkart", clean_q, status_val, retry=0, products_count=0, url=search_url, error=browser_err, duration=dur)
        return [], status_val, browser_err
