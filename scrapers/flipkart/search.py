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

        search_url = f"https://www.flipkart.com/search?q={urllib.parse.quote(clean_q)}"
        logger.info(f"[Flipkart] Search started for '{clean_q}'")
        logger.info(f"[Flipkart] Search URL generated: {search_url}")

        # ── Tier 1: Fast Direct HTTP Fetch ───────────────────────────────────
        # Flipkart returns full server-rendered HTML with CDN images in < 2 seconds via standard HTTP
        try:
            import requests
            http_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
            logger.info(f"[Flipkart] Attempting fast HTTP fetch for '{clean_q}'...")
            resp = requests.get(search_url, headers=http_headers, timeout=12)
            if resp.status_code == 200 and len(resp.text) > 10000:
                soup = bs4.BeautifulSoup(resp.text, "html.parser")
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

                if parsed:
                    norm_list = [normalize_flipkart_product(p, query=clean_q) for p in parsed]
                    valid = [p for p in norm_list if p is not None]
                    if valid:
                        dur = time.time() - start_time
                        log_scraper_event("flipkart", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
                        logger.info(f"[Flipkart] Fast HTTP fetch successful: {len(valid)} valid products in {dur:.2f}s")
                        return valid, "success", None
        except Exception as http_exc:
            logger.warning(f"[Flipkart] Fast HTTP fetch encountered exception: {http_exc}")

        # ── Tier 2: Playwright Headless Browser Fallback ─────────────────────
        logger.info(f"[Flipkart] Executing Playwright browser search fallback for '{clean_q}'...")

        def _browser_task(page):
            logger.info(f"[Flipkart] Navigating browser to {search_url}...")
            page.goto(search_url, wait_until="domcontentloaded", timeout=18000)
            logger.info(f"[Flipkart] Response received")
            page.wait_for_timeout(800)

            title = page.title().lower()
            if "access denied" in title or "503 service unavailable" in title:
                logger.warning("[Flipkart] Access restricted (HTTP 503 / Access Denied)")
                raise RuntimeError("Flipkart access restricted")

            try:
                page.wait_for_selector('div[data-id], div.slAVV4, div.jIjQ8S, div._4ddWXP, div._1xHGKq, div._75nlfW, div.cPHDOP, div._1AtVbE', timeout=4000)
            except Exception:
                pass

            try:
                page.evaluate("window.scrollBy(0, 350)")
                page.wait_for_timeout(300)
            except Exception:
                pass

            try:
                page.evaluate("""() => {
                    document.querySelectorAll('img').forEach(img => {
                        const resolved = img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('srcset') || '';
                        if (resolved) {
                            img.setAttribute('data-resolved-src', resolved);
                        }
                    });
                }""")
            except Exception:
                pass

            logger.info(f"[Flipkart] Product extraction started")
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
            logger.info(f"[Flipkart] Specifications extracted for {len(parsed)} products")
            return parsed

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        dur = time.time() - start_time

        if browser_stat == "success" and browser_res:
            norm_list = [normalize_flipkart_product(p, query=clean_q) for p in browser_res]
            valid = [p for p in norm_list if p is not None]
            log_scraper_event("flipkart", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
            logger.info(f"[Flipkart] Result returned: {len(valid)} valid products")
            return valid, "success", None

        if browser_stat == "timeout":
            logger.warning(f"[Flipkart] Timeout after configured limit: {browser_err}")
        elif browser_stat == "blocked":
            logger.warning(f"[Flipkart] Access blocked: {browser_err}")
        else:
            logger.warning(f"[Flipkart] Scraper error: {browser_err}")

        status_val = browser_stat if browser_stat in ("blocked", "timeout") else "unavailable"
        log_scraper_event("flipkart", clean_q, status_val, retry=0, products_count=0, url=search_url, error=browser_err, duration=dur)
        return [], status_val, browser_err
