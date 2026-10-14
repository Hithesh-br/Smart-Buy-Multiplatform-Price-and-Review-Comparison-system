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
        logger.info(f"[Amazon] Search started for '{clean_q}'")
        logger.info(f"[Amazon] Search URL generated: {search_url}")

        # Level 2: Direct HTTP extraction where permitted
        http_html, http_stat, http_err = self.client.fetch_http(search_url)
        if http_stat == "success" and http_html:
            logger.info(f"[Amazon] Response received via HTTP")
            logger.info(f"[Amazon] Product extraction started")
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
                logger.info(f"[Amazon] Specifications extracted for {len(parsed_http)} products")
                norm_list = [normalize_amazon_product(p, query=clean_q) for p in parsed_http]
                valid = [p for p in norm_list if p is not None]
                if valid:
                    dur = time.time() - start_time
                    log_scraper_event("amazon", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
                    logger.info(f"[Amazon] Result returned: {len(valid)} valid products")
                    return valid, "success", None

        # Level 3: Playwright browser search fallback
        def _browser_task(page):
            # Try primary clean query, and if needed a simplified query
            queries_to_try = [clean_q]
            # If query has parentheses, commas, or extra tokens, add simplified version
            clean_simplified = re.sub(r'\(.*?\)', '', clean_q)
            clean_simplified = re.sub(r'[,/|\-]+', ' ', clean_simplified).strip()
            clean_simplified = re.sub(r'\s+', ' ', clean_simplified)
            if clean_simplified and clean_simplified.lower() != clean_q.lower() and len(clean_simplified.split()) >= 2:
                queries_to_try.append(clean_simplified)
            # Core 2-3 words fallback
            core_words = clean_simplified.split()
            if len(core_words) > 3:
                queries_to_try.append(" ".join(core_words[:3]))

            for q_attempt in queries_to_try:
                curr_url = f"https://www.amazon.in/s?k={urllib.parse.quote(q_attempt)}"
                logger.info(f"[Amazon] Navigating browser to {curr_url}...")
                try:
                    page.goto(curr_url, wait_until="commit", timeout=14000)
                except Exception:
                    try:
                        page.goto(curr_url, wait_until="domcontentloaded", timeout=15000)
                    except Exception as goto_err:
                        logger.warning(f"[Amazon] Navigation attempt error: {goto_err}")
                        continue

                try:
                    title = page.title().lower()
                    if "robot check" in title or "access denied" in title or "503 service unavailable" in title:
                        logger.warning("[Amazon] Access blocked (Title indicates block/challenge)")
                        raise RuntimeError("Amazon access blocked")
                except Exception as title_err:
                    if "access blocked" in str(title_err).lower():
                        raise

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=6000)
                except Exception:
                    pass

                try:
                    page.wait_for_selector('div[data-component-type="s-search-result"], div[data-asin]:not([data-asin=""])', timeout=6000)
                except Exception:
                    page.wait_for_timeout(1500)

                try:
                    page.evaluate("window.scrollBy(0, 350)")
                    page.wait_for_timeout(300)
                except Exception:
                    pass

                try:
                    page.wait_for_load_state("networkidle", timeout=2500)
                except Exception:
                    pass
                time.sleep(0.5)

                html_content = ""
                for _ in range(5):
                    try:
                        html_content = page.content()
                        if html_content and len(html_content) > 1000:
                            break
                    except Exception:
                        time.sleep(0.8)

                if not html_content:
                    continue

                if "robot check" in html_content.lower() or "captcha" in html_content.lower():
                    logger.warning("[Amazon] Access blocked or CAPTCHA detected")
                    raise RuntimeError("Amazon CAPTCHA detected")

                soup = bs4.BeautifulSoup(html_content, "html.parser")
                cards = soup.select('div[data-component-type="s-search-result"]')
                if not cards:
                    cards = [d for d in soup.select('div.s-result-item') if d.get('data-asin') and (d.select_one('h2') or d.select_one('.a-price'))]

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

                if parsed:
                    logger.info(f"[Amazon] Specifications extracted for {len(parsed)} products (query: '{q_attempt}')")
                    return parsed

            return []

        import re
        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        dur = time.time() - start_time

        if browser_stat == "success" and browser_res:
            norm_list = [normalize_amazon_product(p, query=clean_q) for p in browser_res]
            valid = [p for p in norm_list if p is not None]
            log_scraper_event("amazon", clean_q, "success", retry=0, products_count=len(valid), url=search_url, duration=dur)
            logger.info(f"[Amazon] Result returned: {len(valid)} valid products")
            return valid, "success", None

        if browser_stat == "timeout":
            logger.warning(f"[Amazon] Timeout after configured limit: {browser_err}")
        elif browser_stat == "blocked":
            logger.warning(f"[Amazon] Access blocked: {browser_err}")
        else:
            logger.warning(f"[Amazon] Scraper error: {browser_err}")

        status_val = browser_stat if browser_stat in ("blocked", "timeout") else "unavailable"
        log_scraper_event("amazon", clean_q, status_val, retry=0, products_count=0, url=search_url, error=browser_err, duration=dur)
        return [], status_val, browser_err
