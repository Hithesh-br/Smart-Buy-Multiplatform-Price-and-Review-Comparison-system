"""
scrapers/flipkart/url_scraper.py
================================
Flipkart.com Product URL Extractor with 4-Tier Fallback:
1. Configured Flipkart API (Level 1)
2. Playwright Chromium Browser Scraper (Level 2)
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

from scrapers.flipkart.client import FlipkartClient
from product_normalizer import normalize_canonical_product
from search.url_resolver import is_short_or_share_url, resolve_product_url

logger = logging.getLogger("smartbuy.scrapers.flipkart.url")

FLIPKART_API_URL = os.getenv("FLIPKART_API_URL", "").strip()
FLIPKART_API_KEY = os.getenv("FLIPKART_API_KEY", "").strip()


class FlipkartUrlScraper:
    """Extracts authentic product details directly from a Flipkart.com product URL."""

    def __init__(self, client: Optional[FlipkartClient] = None):
        self.client = client or FlipkartClient()

    def scrape_url(self, url: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """
        Execute fallback sequence for Flipkart product URL:
        API -> Playwright -> HTTP fallback.
        Returns: (normalized_product_dict, status_code, error_message)
        """
        clean_url = url.strip()
        logger.info(f"[FlipkartUrlScraper] Fetching product from URL: {clean_url}")

        # Resolve short / mobile share URLs (e.g. dl.flipkart.com/s/XXXX) first
        if is_short_or_share_url(clean_url):
            logger.info(f"[FlipkartUrlScraper] Resolving short share URL: {clean_url}")
            resolved = resolve_product_url(clean_url, "flipkart")
            if resolved and resolved != clean_url:
                logger.info(f"[FlipkartUrlScraper] Resolved short URL to: {resolved}")
                clean_url = resolved

        # Extract PID
        pid = None
        parsed = urllib.parse.urlparse(clean_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'pid' in qs and qs['pid']:
            pid = qs['pid'][0]
        elif '/p/' in clean_url:
            m = re.search(r'/p/([a-zA-Z0-9]+)', clean_url)
            if m:
                pid = m.group(1)

        # ── Level 1: Configured API ──────────────────────────────────────────
        if FLIPKART_API_URL and FLIPKART_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {FLIPKART_API_KEY}", "Accept": "application/json"}
                params = {"pid": pid, "url": clean_url} if pid else {"url": clean_url}
                resp = requests.get(FLIPKART_API_URL, headers=headers, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    prod_raw = data.get("product") or data.get("item") or data
                    norm = normalize_canonical_product(prod_raw, "flipkart", clean_url)
                    if norm:
                        logger.info(f"[FlipkartUrlScraper] Successfully extracted via API: '{norm['title'][:40]}'")
                        return norm, "success", None
            except Exception as e:
                logger.debug(f"[FlipkartUrlScraper] API fallback failed: {e}")

        # ── Level 2: Playwright Browser Scraper ──────────────────────────────
        def _browser_task(page):
            page.goto(clean_url, wait_until="domcontentloaded", timeout=28000)

            title_text = page.title().lower()
            if "access denied" in title_text or "blocked" in title_text or "challenge" in page.content().lower():
                raise RuntimeError("Flipkart anti-bot challenge detected")

            # Try to wait for key product elements
            try:
                page.wait_for_selector("span.VU-ZEz, span.B_NuCI, div.Nx9bqj, div._30jeq3", timeout=5000)
            except Exception:
                pass

            html = page.content()
            return self._parse_flipkart_page_html(html, clean_url, pid)

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        if browser_stat == "success" and browser_res:
            norm = normalize_canonical_product(browser_res, "flipkart", clean_url)
            if norm:
                logger.info(f"[FlipkartUrlScraper] Successfully extracted via Playwright: '{norm['title'][:40]}'")
                return norm, "success", None

        logger.warning(f"[FlipkartUrlScraper] Playwright attempt failed ({browser_stat}: {browser_err}). Trying HTTP parser...")

        # ── Level 3: Direct HTTP & HTML / JSON-LD Parser Fallback ───────────
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            resp = requests.get(clean_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                raw_data = self._parse_flipkart_page_html(resp.text, clean_url, pid)
                if raw_data:
                    norm = normalize_canonical_product(raw_data, "flipkart", clean_url)
                    if norm:
                        logger.info(f"[FlipkartUrlScraper] Successfully extracted via HTTP fallback: '{norm['title'][:40]}'")
                        return norm, "success", None
        except Exception as http_err:
            logger.debug(f"[FlipkartUrlScraper] HTTP fallback failed: {http_err}")

        # ── Level 4: Clear Failure ──────────────────────────────────────────
        error_msg = browser_err or "Unable to retrieve product from Flipkart URL"
        return None, "scraper_error", error_msg

    def _parse_flipkart_page_html(self, html: str, url: str, pid: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Flipkart product page HTML for title, price, specs, ratings, and image."""
        if not html:
            return None

        soup = bs4.BeautifulSoup(html, "html.parser")

        # 1. Title
        title = ""
        title_elem = soup.select_one("span.VU-ZEz, span.B_NuCI, h1._6EBuvT, h1.yhB1nd")
        if title_elem:
            title = title_elem.get_text(strip=True)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()

        if not title or len(title) < 4:
            return None

        # 2. Price
        price_num = 0
        price_elem = soup.select_one("div.Nx9bqj.CxhGGd, div.Nx9bqj, div._30jeq3._16Jk6d, div._30jeq3, div.hl05eU")
        if price_elem:
            clean_p = re.sub(r'[^\d.]', '', price_elem.get_text(strip=True))
            if clean_p:
                try:
                    price_num = int(float(clean_p))
                except Exception:
                    pass

        # 3. MRP
        mrp_num = price_num
        mrp_elem = soup.select_one("div.yRaY8j.A68aKn, div.yRaY8j, div._3I9_wc._2p6cR8, div._3I9_wc")
        if mrp_elem:
            clean_m = re.sub(r'[^\d.]', '', mrp_elem.get_text(strip=True))
            if clean_m:
                try:
                    mrp_val = int(float(clean_m))
                    if mrp_val >= price_num:
                        mrp_num = mrp_val
                except Exception:
                    pass

        # 4. Image
        image_url = ""
        img_elem = soup.select_one("img.DByuf4, img._396cs4._2amPTt, img._396cs4, img._2r_T1I, img._0DkuPH")
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-src') or ""
        if not image_url or "data:" in image_url:
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img and og_img.get('content'):
                image_url = og_img['content']

        # 5. Rating & Review Count
        rating = None
        rate_elem = soup.select_one("div.XQDdHH, div._3LWZlK")
        if rate_elem:
            m_r = re.search(r'([\d.]+)', rate_elem.get_text())
            if m_r:
                try:
                    rating = float(m_r.group(1))
                except Exception:
                    pass

        reviews = 0
        rev_elem = soup.select_one("span.Wphh3Z, span._2_R_DZ")
        if rev_elem:
            rev_text = rev_elem.get_text()
            m_rev = re.search(r'([\d,]+)\s*Reviews?', rev_text, re.IGNORECASE)
            if not m_rev:
                m_rev = re.search(r'([\d,]+)\s*Ratings?', rev_text, re.IGNORECASE)
            if m_rev:
                try:
                    reviews = int(m_rev.group(1).replace(',', ''))
                except Exception:
                    pass

        # 6. Specifications Table
        specifications: Dict[str, str] = {}
        for tr in soup.select("table._14cfVK tr, div._3k-BhJ tr, div.row._30-a, div.G6XhRU tr"):
            tds = tr.select("td")
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True)
                v = tds[1].get_text(strip=True)
                if k and v:
                    specifications[k] = v

        # Key Highlights
        features = []
        for li in soup.select("div._2418kt li, ul._1gHwDe li"):
            f_text = li.get_text(strip=True)
            if f_text and len(f_text) > 3:
                features.append(f_text)

        # Brand
        brand = None
        # Brand from title or breadcrumb
        bc_brand = soup.select_one("div._75nlfW a, a.R0cyWM")
        if bc_brand and len(bc_brand.get_text(strip=True)) < 30:
            brand = bc_brand.get_text(strip=True)

        return {
            "platform": "flipkart",
            "title": title,
            "product_name": title,
            "product_id": pid or "",
            "price_num": price_num,
            "mrp_num": mrp_num,
            "image_url": image_url,
            "image": image_url,
            "rating": rating,
            "review_count": reviews,
            "product_url": url,
            "url": url,
            "specifications": specifications,
            "key_features": features,
            "in_stock": True,
            "brand": brand,
            "availability": "In Stock",
            "source": "live"
        }
