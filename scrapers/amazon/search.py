"""
scrapers/amazon/search.py
=========================
Independent search orchestrator for Amazon.in.
"""

import time
import urllib.parse
import logging
from typing import List, Dict, Any, Tuple, Optional
import bs4

from scrapers.amazon.client import AmazonClient
from scrapers.amazon.parser import parse_amazon_card
from scrapers.amazon.normalizer import normalize_amazon_product
from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.scrapers.amazon.search")


class AmazonSearch:
    """Executes Amazon search via API or Playwright browser."""

    def __init__(self, client: Optional[AmazonClient] = None):
        self.client = client or AmazonClient()

    def search(self, query: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
        start_time = time.time()
        clean_q = query.strip()
        if not clean_q:
            return [], "no_match", "Empty query"

        # Level 1: Try configured Amazon API first
        api_prods, api_stat, api_err = self.client.fetch_api(clean_q)
        if api_stat == "success" and api_prods:
            norm_list = [normalize_amazon_product(p, query=clean_q) for p in api_prods]
            valid = [p for p in norm_list if p is not None][:limit]
            dur = time.time() - start_time
            log_scraper_event("amazon", clean_q, "success", retry=0, products_count=len(valid), duration=dur)
            return valid, "success", None

        search_url = f"https://www.amazon.in/s?k={urllib.parse.quote(clean_q)}"

        # Level 2: Direct HTTP extraction where permitted
        http_html, http_stat, http_err = self.client.fetch_http(search_url)
        if http_stat == "success" and http_html:
            soup = bs4.BeautifulSoup(http_html, "html.parser")
            cards = soup.select('div[data-component-type="s-search-result"]')
            if not cards:
                cards = [d for d in soup.select('div.s-result-item') if d.get('data-asin')]
            parsed_http = []
            seen_asins = set()
            for c in cards:
                data = parse_amazon_card(c)
                if data and data['asin'] not in seen_asins:
                    seen_asins.add(data['asin'])
                    data['source'] = 'http'
                    parsed_http.append(data)
                if len(parsed_http) >= limit:
                    break
            if parsed_http:
                norm_list = [normalize_amazon_product(p, query=clean_q) for p in parsed_http]
                valid = [p for p in norm_list if p is not None]
                if valid:
                    dur = time.time() - start_time
                    log_scraper_event("amazon", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
                    return valid, "success", None

        # Level 3: Playwright browser search fallback
        def _browser_task(page):
            page.goto(search_url, wait_until="domcontentloaded", timeout=28000)
            page.wait_for_timeout(1000)

            title = page.title().lower()
            content = page.content().lower()
            if "robot check" in title or "captcha" in content:
                raise RuntimeError("Amazon CAPTCHA detected")
            if "access denied" in title or "503 service unavailable" in title:
                raise RuntimeError("Amazon access blocked")

            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.35)")
                page.wait_for_timeout(300)
            except Exception:
                pass

            soup = bs4.BeautifulSoup(page.content(), "html.parser")
            cards = soup.select('div[data-component-type="s-search-result"]')
            if not cards:
                cards = [d for d in soup.select('div.s-result-item') if d.get('data-asin')]

            parsed = []
            seen_asins = set()
            for c in cards:
                data = parse_amazon_card(c)
                if data and data['asin'] not in seen_asins:
                    seen_asins.add(data['asin'])
                    data['source'] = 'browser'
                    parsed.append(data)
                if len(parsed) >= limit:
                    break
            return parsed

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        dur = time.time() - start_time

        if browser_stat == "success" and browser_res:
            norm_list = [normalize_amazon_product(p, query=clean_q) for p in browser_res]
            valid = [p for p in norm_list if p is not None]
            log_scraper_event("amazon", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
            return valid, "success", None

        status_val = browser_stat if browser_stat in ("blocked", "timeout") else "unavailable"
        log_scraper_event("amazon", clean_q, status_val, retry=0, products_count=0, url=search_url, error=browser_err, duration=dur)
        return [], status_val, browser_err
