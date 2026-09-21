"""
scrapers/meesho/meesho_search.py
================================
Search Orchestrator for Meesho:
- Query Normalization
- Multi-tier search fallback:
    Level 1: Configured Third-Party API
    Level 2: Direct HTTP / JSON-LD / Next.js extraction
    Level 3: Playwright Browser Automation (Chromium with Firefox auto-fallback)
    Level 4: Structured error classification
- Candidate collection (target 10-20 products)
- Top candidate detail enrichment
- Audit logging to logs/scrapers.log
"""

import time
import urllib.parse
import logging
from typing import List, Dict, Any, Tuple, Optional

from scrapers.meesho.meesho_client import MeeshoClient
from scrapers.meesho.meesho_parser import parse_json_ld, parse_next_data, extract_title_from_slug
from scrapers.meesho.meesho_normalizer import normalize_meesho_product
from scrapers.meesho.meesho_product import MeeshoProductEnricher
from scrapers.scraper_logger import log_scraper_event
from search.normalizer import normalize_query

logger = logging.getLogger("smartbuy.scrapers.meesho.search")


class MeeshoSearch:
    """Executes multi-strategy searches for Meesho."""

    def __init__(self, client: Optional[MeeshoClient] = None):
        self.client = client or MeeshoClient()
        self.enricher = MeeshoProductEnricher(self.client)

    def search(self, query: str, limit: int = 15) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
        """
        Main entry point for Meesho search.
        Returns: (normalized_products_list, status_code, error_message)
        Possible status_code: 'success', 'no_products_found', 'blocked', 'timeout', 'scraper_error'.
        """
        start_time = time.time()
        norm_q = normalize_query(query)
        if not norm_q:
            return [], "no_products_found", "Empty search query"

        # ── LEVEL 1: Configured API Provider ─────────────────────────────────
        api_products, api_status, api_err = self.client.fetch_api(norm_q)
        if api_status == "success" and api_products:
            normalized = []
            for p in api_products:
                item = normalize_meesho_product(p, query=norm_q)
                if item:
                    normalized.append(item)
                if len(normalized) >= limit:
                    break

            if normalized:
                dur = time.time() - start_time
                log_scraper_event("meesho", norm_q, "success", retry=0, products_count=len(normalized), parsed_count=len(api_products), duration=dur)
                return normalized, "success", None

        # ── LEVEL 2: Direct HTTP / JSON-LD Extraction ─────────────────────────
        encoded_q = urllib.parse.quote_plus(norm_q)
        search_url = f"https://www.meesho.com/search?q={encoded_q}"
        html, http_status, http_err = self.client.fetch_html(search_url)

        if http_status == "success" and html:
            extracted = parse_next_data(html) or parse_json_ld(html)
            if extracted:
                normalized = []
                for p in extracted:
                    item = normalize_meesho_product(p, query=norm_q)
                    if item:
                        normalized.append(item)
                    if len(normalized) >= limit:
                        break

                if normalized:
                    dur = time.time() - start_time
                    log_scraper_event("meesho", norm_q, "success", retry=1, products_count=len(normalized), parsed_count=len(extracted), url=search_url, duration=dur)
                    return normalized, "success", None

        # ── LEVEL 3: Playwright Browser Automation ─────────────────────────────
        def _browser_task(page):
            logger.info(f"[MeeshoSearch] Navigating browser to {search_url}...")
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # Check if page is blocked
            content = page.content()
            if "Access Denied" in content or "Security Challenge" in content:
                raise RuntimeError("Access Denied by edge protection")

            # Wait for product anchors or content
            try:
                page.wait_for_selector('a[href*="/p/"]', timeout=15000)
            except Exception:
                pass

            # Scroll gradually to trigger lazy hydration
            page.evaluate("window.scrollBy(0, 800);")
            time.sleep(1.0)

            # Extract anchors with /p/
            anchors = page.query_selector_all('a[href*="/p/"]')
            collected = []
            seen_urls = set()

            for a in anchors:
                try:
                    href = a.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Extract text content for pricing and title
                    text = a.inner_text()
                    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

                    price_val = None
                    for line in lines:
                        if "₹" in line:
                            price_val = line
                            break

                    img_elem = a.query_selector("img")
                    img_src = img_elem.get_attribute("src") if img_elem else ""

                    title_recovered = extract_title_from_slug(href)
                    title = title_recovered or (lines[0] if lines else "Meesho Product")

                    if href and price_val:
                        collected.append({
                            "title": title,
                            "url": href,
                            "price": price_val,
                            "image": img_src,
                            "source": "playwright_browser"
                        })
                    if len(collected) >= limit:
                        break
                except Exception:
                    continue

            return collected

        browser_result, browser_status, browser_err = self.client.execute_browser_task(_browser_task, query=norm_q)

        dur = time.time() - start_time
        if browser_status == "success" and browser_result:
            normalized = []
            for raw_item in browser_result:
                item = normalize_meesho_product(raw_item, query=norm_q)
                if item:
                    normalized.append(item)

            if normalized:
                # Top candidate enrichment (enrich first 2 candidates for deeper specs)
                for i in range(min(2, len(normalized))):
                    normalized[i] = self.enricher.enrich_product(normalized[i])

                log_scraper_event("meesho", norm_q, "success", retry=2, products_count=len(normalized), parsed_count=len(browser_result), url=search_url, duration=dur)
                return normalized, "success", None
            else:
                log_scraper_event("meesho", norm_q, "no_products_found", retry=2, products_count=0, url=search_url, duration=dur)
                return [], "no_products_found", "No valid items parsed from browser page"

        # ── LEVEL 4: Structured Error Classification ──────────────────────────
        final_status = browser_status if browser_status in ("blocked", "timeout") else "scraper_error"
        final_err = browser_err or http_err or "Meesho scraper failed across all extraction layers"
        log_scraper_event("meesho", norm_q, final_status, retry=2, products_count=0, url=search_url, error=final_err, duration=dur)

        return [], final_status, final_err
