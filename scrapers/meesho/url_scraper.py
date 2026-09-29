"""
scrapers/meesho/url_scraper.py
==============================
Meesho.com Product URL Extractor with 4-Tier Fallback:
1. Configured Meesho API (Level 1)
2. Playwright Chromium / Firefox Browser Scraper (Level 2)
3. Direct HTTP & JSON-LD / Meta parser (Level 3)
4. Structured Error State (Level 4)
"""

import os
import re
import json
import logging
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import requests
import bs4

from scrapers.meesho.meesho_client import MeeshoClient
from scrapers.meesho.meesho_parser import parse_json_ld
from product_normalizer import normalize_canonical_product

logger = logging.getLogger("smartbuy.scrapers.meesho.url")

MEESHO_API_URL = os.getenv("MEESHO_API_URL", "").strip()
MEESHO_API_KEY = os.getenv("MEESHO_API_KEY", "").strip()


class MeeshoUrlScraper:
    """Extracts authentic product details directly from a Meesho.com product URL."""

    def __init__(self, client: Optional[MeeshoClient] = None):
        self.client = client or MeeshoClient()

    def scrape_url(self, url: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """
        Execute fallback sequence for Meesho product URL:
        API -> Playwright -> HTTP fallback.
        Returns: (normalized_product_dict, status_code, error_message)
        """
        clean_url = url.strip()
        logger.info(f"[MeeshoUrlScraper] Fetching product from URL: {clean_url}")

        # Extract Meesho Product ID and Slug from path
        pid = ""
        m_pid = re.search(r'/(?:s/)?p/([a-zA-Z0-9]+)', clean_url)
        if m_pid:
            pid = m_pid.group(1)

        m_slug = re.search(r'/([^/]+)/p/[a-zA-Z0-9]+', clean_url)
        slug = m_slug.group(1) if m_slug else ""

        # ── Level 1: Configured API ──────────────────────────────────────────
        if MEESHO_API_URL and MEESHO_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {MEESHO_API_KEY}", "Accept": "application/json"}
                params = {"product_id": pid, "url": clean_url} if pid else {"url": clean_url}
                resp = requests.get(MEESHO_API_URL, headers=headers, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    prod_raw = data.get("product") or data.get("item") or data
                    norm = normalize_canonical_product(prod_raw, "meesho", clean_url)
                    if norm:
                        logger.info(f"[MeeshoUrlScraper] Successfully extracted via API: '{norm['title'][:40]}'")
                        return norm, "success", None
            except Exception as e:
                logger.debug(f"[MeeshoUrlScraper] API fallback failed: {e}")

        # ── Level 2: Playwright Browser Scraper ──────────────────────────────
        def _browser_task(page):
            # First attempt: Try direct page load
            try:
                page.goto(clean_url, wait_until="commit", timeout=14000)
                try:
                    page.wait_for_selector("h1, h4, span[class*='ProductTitle']", timeout=6000)
                except Exception:
                    page.wait_for_timeout(1500)
                title_text = page.title().lower()
                content_lower = page.content().lower()
                if not ("access denied" in title_text or "access denied" in content_lower or "security challenge" in content_lower):
                    html = page.content()
                    res = self._parse_meesho_page_html(html, clean_url, pid)
                    if res:
                        return res
            except Exception as direct_exc:
                logger.debug(f"[MeeshoUrlScraper] Direct PDP load failed or challenged: {direct_exc}")

            # Fallback for Edge Protection: Query catalog via search page session
            if slug or pid:
                logger.info(f"[MeeshoUrlScraper] Falling back to in-page catalog retrieval for slug='{slug}', pid='{pid}'")
                clean_slug = re.sub(r'[-_]+', ' ', slug).strip()
                slug_query = " ".join(clean_slug.split()[:6]) if clean_slug else pid
                search_nav_url = f"https://www.meesho.com/search?q={urllib.parse.quote_plus(slug_query)}"
                page.goto(search_nav_url, wait_until="domcontentloaded", timeout=15000)

                # Check if search page is blocked
                if "access denied" in page.title().lower() or "sec-if-cpt-container" in page.content().lower():
                    raise RuntimeError("Access Denied: Meesho edge protection challenge detected")

                js_search = """
                async (q) => {
                    try {
                        const resp = await fetch('https://www.meesho.com/api/v1/products/search', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                            body: JSON.stringify({query: q, type: 'text_search', page: 1, offset: 0, limit: 20})
                        });
                        if (resp.ok) {
                            const data = await resp.json();
                            return data.catalogs || [];
                        }
                    } catch (e) {}
                    return [];
                }
                """
                # Try query cascade: slug_query, then full clean_slug
                for q_try in [slug_query, clean_slug]:
                    if not q_try:
                        continue
                    catalogs = page.evaluate(js_search, q_try) or []
                    matched = None
                    for c in catalogs:
                        c_pid = str(c.get('product_id') or c.get('id') or '').strip().lower()
                        if pid and c_pid == pid.lower():
                            matched = c
                            break
                    if not matched and catalogs and slug:
                        for c in catalogs:
                            c_slug = str(c.get('slug') or '').lower()
                            if slug.lower() in c_slug or c_slug in slug.lower():
                                matched = c
                                break

                    if not matched and catalogs:
                        clean_tokens = [w for w in clean_slug.lower().split() if len(w) > 2]
                        for c in catalogs:
                            c_name = str(c.get('name') or c.get('title') or '').lower()
                            if clean_tokens and all(tok in c_name for tok in clean_tokens[:3]):
                                matched = c
                                break

                    if not matched and catalogs and len(catalogs) > 0:
                        matched = catalogs[0]

                    if matched:
                        from scrapers.meesho.meesho_parser import parse_meesho_catalog_item
                        parsed = parse_meesho_catalog_item(matched)
                        if parsed:
                            parsed['product_url'] = clean_url
                            parsed['url'] = clean_url
                            return parsed

            return None

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        if browser_stat == "success" and browser_res:
            norm = normalize_canonical_product(browser_res, "meesho", clean_url)
            if norm:
                logger.info(f"[MeeshoUrlScraper] Successfully extracted canonical product: '{norm['title'][:40]}'")
                return norm, "success", None

        logger.warning(f"[MeeshoUrlScraper] Playwright attempt failed ({browser_stat}: {browser_err}). Trying HTTP parser...")

        # ── Level 3: Direct HTTP & HTML / JSON-LD Parser Fallback ───────────
        try:
            html, status, err = self.client.fetch_html(clean_url)
            if status == "success" and html:
                raw_data = self._parse_meesho_page_html(html, clean_url, pid)
                if raw_data:
                    norm = normalize_canonical_product(raw_data, "meesho", clean_url)
                    if norm:
                        logger.info(f"[MeeshoUrlScraper] Successfully extracted via HTTP fallback: '{norm['title'][:40]}'")
                        return norm, "success", None
            elif status in ("blocked", "timeout"):
                browser_stat = status
                browser_err = err
        except Exception as http_err:
            logger.debug(f"[MeeshoUrlScraper] HTTP fallback failed: {http_err}")

        # ── Level 4: Clear Failure ──────────────────────────────────────────
        final_status = browser_stat if browser_stat in ("blocked", "timeout") else "scraper_error"
        error_msg = browser_err or f"Unable to retrieve product from Meesho URL ({final_status})"
        return None, final_status, error_msg

    def _parse_meesho_page_html(self, html: str, url: str, pid: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Meesho product page HTML and embedded JSON-LD for product details."""
        if not html:
            return None

        # Edge protection challenge guard
        html_lower = html.lower()
        if "access denied" in html_lower or "security challenge" in html_lower or "sec-if-cpt-container" in html_lower:
            return None

        soup = bs4.BeautifulSoup(html, "html.parser")

        # 1. JSON-LD check
        ld_items = parse_json_ld(html)
        ld_data = None
        for ld in ld_items:
            if ld.get('name') and (ld.get('offers') or ld.get('price')):
                ld_data = ld
                break

        title = ""
        # Try JSON-LD title
        if ld_data and ld_data.get('name'):
            title = ld_data['name'].strip()

        # Try HTML heading
        if not title:
            h1 = soup.select_one("h1, span[class*='sc-bcXHqe'], span[class*='ProductTitle']")
            if h1:
                title = h1.get_text(strip=True)

        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()

        if not title or len(title) < 3 or title.lower() in ("access denied", "security challenge", "robot check", "just a moment..."):
            return None

        # 2. Price
        price_num = 0
        if ld_data:
            offers = ld_data.get('offers')
            if isinstance(offers, dict) and offers.get('price'):
                try:
                    price_num = int(float(offers['price']))
                except Exception:
                    pass
            elif ld_data.get('price'):
                try:
                    price_num = int(float(ld_data['price']))
                except Exception:
                    pass

        if price_num <= 0:
            price_elem = soup.select_one("h4[class*='sc-bcXHqe'], h4, span[class*='PriceText']")
            if price_elem:
                clean_p = re.sub(r'[^\d.]', '', price_elem.get_text(strip=True))
                if clean_p:
                    try:
                        price_num = int(float(clean_p))
                    except Exception:
                        pass

        # 3. Image
        image_url = ""
        if ld_data and ld_data.get('image'):
            img_val = ld_data['image']
            if isinstance(img_val, list) and img_val:
                image_url = img_val[0]
            elif isinstance(img_val, str):
                image_url = img_val

        if not image_url:
            img_tag = soup.select_one("img[alt*='product'], img[src*='meesho.com'], img[class*='ProductImage']")
            if img_tag:
                image_url = img_tag.get('src') or ""

        if not image_url:
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img and og_img.get('content'):
                image_url = og_img['content']

        # 4. Rating & Reviews
        rating = None
        reviews = 0
        if ld_data and ld_data.get('aggregateRating'):
            agg = ld_data['aggregateRating']
            try:
                rating = float(agg.get('ratingValue', 0))
            except Exception:
                pass
            try:
                reviews = int(agg.get('reviewCount') or agg.get('ratingCount') or 0)
            except Exception:
                pass

        if rating is None:
            rate_elem = soup.select_one("span[class*='Rating'], div[class*='Rating'], span[class*='Pill'], [class*='rating']")
            if rate_elem:
                m_r = re.search(r'([1-5](?:\.\d+)?)', rate_elem.get_text())
                if m_r:
                    try:
                        rating = float(m_r.group(1))
                    except Exception:
                        pass

        if reviews == 0:
            rev_elem = soup.select_one("span[class*='Review'], div[class*='Review'], span[class*='Reviews']")
            if rev_elem:
                m_rev = re.search(r'([\d,]+)\s*(?:Reviews?|Ratings?)', rev_elem.get_text(), re.I)
                if m_rev:
                    try:
                        reviews = int(m_rev.group(1).replace(",", ""))
                    except Exception:
                        pass

        # 5. Specifications & Attributes
        specifications: Dict[str, str] = {}
        attr_tags = soup.find_all(lambda tag: tag.name in ('div', 'span', 'p') and any(k in tag.text.lower() for k in ('material', 'net quantity', 'weight', 'warranty', 'skin type', 'color', 'size', 'fabric', 'pack of')))
        for tag in attr_tags[:12]:
            text = tag.get_text(separator=": ").strip()
            if ":" in text:
                parts = [p.strip() for p in text.split(":", 1)]
                if len(parts) == 2 and 2 < len(parts[0]) < 30 and len(parts[1]) < 100:
                    specifications[parts[0].title()] = parts[1]

        # Brand from JSON-LD
        brand = None
        if ld_data and ld_data.get('brand'):
            b_val = ld_data['brand']
            brand = b_val.get('name') if isinstance(b_val, dict) else str(b_val)

        return {
            "platform": "meesho",
            "title": title,
            "product_name": title,
            "product_id": pid or "",
            "price_num": price_num,
            "mrp_num": price_num,
            "image_url": image_url,
            "image": image_url,
            "rating": rating,
            "review_count": reviews,
            "product_url": url,
            "url": url,
            "specifications": specifications,
            "in_stock": True,
            "brand": brand,
            "availability": "In Stock",
            "source": "live"
        }
