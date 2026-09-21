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

        # Extract Meesho Product ID from path
        pid = ""
        m = re.search(r'/(?:s/)?p/([a-zA-Z0-9]+)', clean_url)
        if m:
            pid = m.group(1)

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
            page.goto(clean_url, wait_until="domcontentloaded", timeout=28000)

            title_text = page.title().lower()
            if "access denied" in title_text or "security challenge" in page.content().lower():
                raise RuntimeError("Meesho anti-bot challenge detected")

            try:
                page.wait_for_selector("h1, h4", timeout=6000)
            except Exception:
                pass

            html = page.content()
            return self._parse_meesho_page_html(html, clean_url, pid)

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        if browser_stat == "success" and browser_res:
            norm = normalize_canonical_product(browser_res, "meesho", clean_url)
            if norm:
                logger.info(f"[MeeshoUrlScraper] Successfully extracted via Playwright: '{norm['title'][:40]}'")
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
        except Exception as http_err:
            logger.debug(f"[MeeshoUrlScraper] HTTP fallback failed: {http_err}")

        # ── Level 4: Clear Failure ──────────────────────────────────────────
        error_msg = browser_err or "Unable to retrieve product from Meesho URL"
        return None, "scraper_error", error_msg

    def _parse_meesho_page_html(self, html: str, url: str, pid: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Meesho product page HTML and embedded JSON-LD for product details."""
        if not html:
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

        if not title or len(title) < 3:
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
            rate_elem = soup.select_one("span[class*='Rating']")
            if rate_elem:
                m_r = re.search(r'([\d.]+)', rate_elem.get_text())
                if m_r:
                    try:
                        rating = float(m_r.group(1))
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
