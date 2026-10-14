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

import re
import time
import urllib.parse
import logging
from typing import List, Dict, Any, Tuple, Optional
import bs4

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
        logger.info("[MEESHO] Starting search")
        logger.info(f"[MEESHO] Search query: {query}")
        logger.info("[MEESHO] Request started")

        start_time = time.time()
        norm_q = normalize_query(query)
        if not norm_q:
            logger.info("[MEESHO] Final status: no_products_found (empty query)")
            return [], "no_products_found", "Empty search query"

        # ── LEVEL 1: Configured API Provider ─────────────────────────────────
        api_products, api_status, api_err = self.client.fetch_api(norm_q)
        if api_status == "success" and api_products:
            logger.info(f"[MEESHO] Response status: 200 (Configured API)")
            logger.info(f"[MEESHO] Product candidates found: {len(api_products)}")
            normalized = []
            for p in api_products:
                item = normalize_meesho_product(p, query=norm_q)
                if item:
                    normalized.append(item)
                if len(normalized) >= limit:
                    break

            if normalized:
                dur = time.time() - start_time
                logger.info(f"[MEESHO] Matching product candidates ({len(normalized)} normalized)")
                logger.info("[MEESHO] Final status: success")
                log_scraper_event("meesho", norm_q, "success", retry=0, products_count=len(normalized), parsed_count=len(api_products), duration=dur)
                return normalized, "success", None

        # ── LEVEL 2: Direct HTTP / JSON-LD Extraction ─────────────────────────
        encoded_q = urllib.parse.quote_plus(norm_q)
        search_url = f"https://www.meesho.com/search?q={encoded_q}"
        logger.info(f"[MEESHO] Search URL generated: {search_url}")
        html, http_status, http_err = self.client.fetch_html(search_url)

        if http_status == "success" and html:
            logger.info("[MEESHO] Response status: 200 (Direct HTTP)")
            logger.info("[MEESHO] Content type: text/html")
            logger.info(f"[MEESHO] Response length: {len(html)}")
            extracted = parse_next_data(html) or parse_json_ld(html)
            if extracted:
                logger.info(f"[MEESHO] Product candidates found: {len(extracted)}")
                normalized = []
                for p in extracted:
                    item = normalize_meesho_product(p, query=norm_q)
                    if item:
                        normalized.append(item)
                    if len(normalized) >= limit:
                        break

                if normalized:
                    dur = time.time() - start_time
                    logger.info("[MEESHO] Matching product candidates")
                    logger.info("[MEESHO] Final status: success")
                    log_scraper_event("meesho", norm_q, "success", retry=1, products_count=len(normalized), parsed_count=len(extracted), url=search_url, duration=dur)
                    return normalized, "success", None

        # ── LEVEL 3: Playwright Browser Automation ─────────────────────────────
        def _browser_task(page):
            # Build query cascade:
            # 1. Normalized query
            # 2. Query without parentheses/specs
            # 3. Clean model/brand core tokens
            queries_to_try = [norm_q]

            clean_simplified = re.sub(r'\(.*?\)', '', norm_q)
            clean_simplified = re.sub(r'[,/|\-]+', ' ', clean_simplified).strip()
            clean_simplified = re.sub(r'\s+', ' ', clean_simplified)

            # Strip color, storage, and ram tokens which cause Meesho accessories/covers to miss
            no_specs = re.sub(r'\b(\d+\s*(gb|tb|mb|ram|rom|mah)|silver|green|blue|black|gold|white|red|grey|gray)\b', '', clean_simplified, flags=re.I).strip()
            no_specs = re.sub(r'\s+', ' ', no_specs)
            if no_specs and no_specs.lower() not in [q.lower() for q in queries_to_try]:
                queries_to_try.append(no_specs)

            core_tokens = no_specs.split() if no_specs else clean_simplified.split()
            if len(core_tokens) >= 2:
                core_q = " ".join(core_tokens[:3])
                if core_q.lower() not in [q.lower() for q in queries_to_try]:
                    queries_to_try.append(core_q)

            collected = []
            seen_urls = set()

            for q_attempt in queries_to_try:
                curr_url = f"https://www.meesho.com/search?q={urllib.parse.quote_plus(q_attempt)}"
                logger.info(f"[MEESHO] Navigating browser to {curr_url}...")
                try:
                    page.goto(curr_url, wait_until="commit", timeout=14000)
                except Exception as goto_err:
                    logger.warning(f"[MEESHO] Navigation attempt error: {goto_err}")
                    continue

                # Check edge protection block
                title_text = page.title().lower()
                content = page.content().lower()
                if (
                    "access denied" in title_text
                    or "access denied" in content
                    or "security challenge" in content
                    or "sec-if-cpt-container" in content
                ):
                    logger.warning("[MEESHO] Access Denied by edge protection challenge")
                    raise RuntimeError("Access Denied: Meesho edge protection challenge detected")

                try:
                    page.wait_for_selector('a[href*="/p/"]', timeout=7000)
                except Exception:
                    page.wait_for_timeout(1500)

                try:
                    page.evaluate("window.scrollBy(0, 450);")
                    page.wait_for_timeout(400)
                except Exception:
                    pass

                soup = bs4.BeautifulSoup(page.content(), "html.parser")
                anchors = soup.find_all("a", href=lambda h: h and "/p/" in h)

                for a in anchors:
                    try:
                        href = a.get("href") or ""
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        text = a.get_text(separator=" | ", strip=True)
                        lines = [ln.strip() for ln in text.split(" | ") if ln.strip()]

                        price_val = None
                        for line in lines:
                            if "₹" in line:
                                price_val = line
                                break

                        img_elem = a.find("img")
                        img_src = img_elem.get("src") if img_elem else ""

                        full_url = urllib.parse.urljoin("https://www.meesho.com", href)
                        title_recovered = extract_title_from_slug(href)
                        title = title_recovered or (lines[0] if lines else "Meesho Product")

                        rating_val = None
                        review_count = 0
                        for line in lines:
                            m_r = re.search(r'^([1-5](?:\.\d+)?)\s*(?:★|\b)', line)
                            if m_r and not rating_val:
                                val = float(m_r.group(1))
                                if 1.0 <= val <= 5.0:
                                    rating_val = val
                            m_rev = re.search(r'([\d,]+)\s*(?:Reviews?|Ratings?)', line, re.I)
                            if m_rev and not review_count:
                                review_count = int(m_rev.group(1).replace(',', ''))

                        if not rating_val:
                            rate_el = a.select_one('[class*="Rating"], [class*="rating"], [class*="Pill"]')
                            if rate_el:
                                m_r2 = re.search(r'([1-5](?:\.\d+)?)', rate_el.get_text(strip=True))
                                if m_r2:
                                    val2 = float(m_r2.group(1))
                                    if 1.0 <= val2 <= 5.0:
                                        rating_val = val2

                        if href and price_val:
                            collected.append({
                                "title": title,
                                "url": full_url,
                                "price": price_val,
                                "image": img_src,
                                "rating": rating_val,
                                "review_count": review_count,
                                "reviews": f"{review_count:,}" if review_count else "0",
                                "source": "playwright_browser"
                            })
                        if len(collected) >= limit:
                            break
                    except Exception:
                        continue

                if collected:
                    logger.info(f"[MEESHO] DOM product candidates found: {len(collected)} (query: '{q_attempt}')")
                    break

            return collected

        browser_result, browser_status, browser_err = self.client.execute_browser_task(_browser_task, query=norm_q)

        dur = time.time() - start_time
        if browser_status == "success" and browser_result:
            logger.info("[MEESHO] Matching product candidates")
            normalized = []
            for raw_item in browser_result:
                item = normalize_meesho_product(raw_item, query=norm_q)
                if item:
                    normalized.append(item)

            if normalized:
                # Top candidate enrichment (enrich first 2 candidates for deeper specs)
                for i in range(min(2, len(normalized))):
                    normalized[i] = self.enricher.enrich_product(normalized[i])

                best_score = normalized[0].get("quality_score") or normalized[0].get("rating") or "N/A"
                logger.info(f"[MEESHO] Best match score: {best_score}")
                logger.info("[MEESHO] Final status: success")
                log_scraper_event("meesho", norm_q, "success", retry=2, products_count=len(normalized), parsed_count=len(browser_result), url=search_url, duration=dur)
                return normalized, "success", None
            else:
                logger.info("[MEESHO] Final status: no_products_found")
                log_scraper_event("meesho", norm_q, "no_products_found", retry=2, products_count=0, url=search_url, duration=dur)
                return [], "no_products_found", "No valid items parsed from browser page"

        # ── LEVEL 4: Structured Error Classification ──────────────────────────
        if browser_status in ("blocked", "timeout", "no_products_found"):
            final_status = browser_status
        elif not browser_result and browser_status == "success":
            final_status = "no_products_found"
        else:
            final_status = "scraper_error"

        final_err = browser_err or http_err or f"Meesho search ended with status '{final_status}'"
        logger.info(f"[MEESHO] Final status: {final_status} ({final_err})")
        log_scraper_event("meesho", norm_q, final_status, retry=2, products_count=0, url=search_url, error=final_err, duration=dur)

        return [], final_status, final_err
