"""
scrapers/amazon/url_scraper.py
==============================
Amazon.in Product URL Extractor with 4-Tier Fallback:
1. Configured Amazon API (Level 1)
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

from scrapers.amazon.client import AmazonClient
from product_normalizer import normalize_canonical_product
from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.scrapers.amazon.url")

AMAZON_API_URL = os.getenv("AMAZON_API_URL", "").strip()
AMAZON_API_KEY = os.getenv("AMAZON_API_KEY", "").strip()
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "45000"))


class AmazonUrlScraper:
    """Extracts authentic product details directly from an Amazon.in product URL."""

    def __init__(self, client: Optional[AmazonClient] = None):
        self.client = client or AmazonClient()

    def scrape_url(self, url: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """
        Execute fallback sequence for Amazon product URL:
        API -> Playwright -> HTTP fallback.
        Returns: (normalized_product_dict, status_code, error_message)
        """
        clean_url = url.strip()
        logger.info(f"[AmazonUrlScraper] Fetching product from URL: {clean_url}")

        # Extract ASIN
        asin = None
        m = re.search(r'/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})', clean_url, re.IGNORECASE)
        if m:
            asin = m.group(1).upper()

        # ── Level 1: Configured API ──────────────────────────────────────────
        if AMAZON_API_URL and AMAZON_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {AMAZON_API_KEY}", "Accept": "application/json"}
                params = {"asin": asin, "url": clean_url} if asin else {"url": clean_url}
                resp = requests.get(AMAZON_API_URL, headers=headers, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    prod_raw = data.get("product") or data.get("item") or data
                    norm = normalize_canonical_product(prod_raw, "amazon", clean_url)
                    if norm:
                        logger.info(f"[AmazonUrlScraper] Successfully extracted via API: '{norm['title'][:40]}'")
                        return norm, "success", None
            except Exception as e:
                logger.debug(f"[AmazonUrlScraper] API fallback failed: {e}")

        # ── Level 2: Playwright Browser Scraper ──────────────────────────────
        def _browser_task(page):
            page.goto(clean_url, wait_until="domcontentloaded", timeout=28000)
            
            # Check captcha / blocking
            title_text = page.title().lower()
            if "robot check" in title_text or "captcha" in page.content().lower():
                raise RuntimeError("Amazon CAPTCHA block detected")
            if "access denied" in title_text or "503 service unavailable" in title_text:
                raise RuntimeError("Amazon access blocked")

            # Try to wait for key product elements
            try:
                page.wait_for_selector("#productTitle, #title, .a-price", timeout=5000)
            except Exception:
                pass

            html = page.content()
            return self._parse_amazon_page_html(html, clean_url, asin)

        browser_res, browser_stat, browser_err = self.client.execute_browser_task(_browser_task)
        if browser_stat == "success" and browser_res:
            norm = normalize_canonical_product(browser_res, "amazon", clean_url)
            if norm:
                logger.info(f"[AmazonUrlScraper] Successfully extracted via Playwright: '{norm['title'][:40]}'")
                return norm, "success", None

        logger.warning(f"[AmazonUrlScraper] Playwright attempt failed ({browser_stat}: {browser_err}). Trying HTTP parser...")

        # ── Level 3: Direct HTTP & HTML / JSON-LD Parser Fallback ───────────
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Cache-Control": "no-cache",
            }
            resp = requests.get(clean_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                raw_data = self._parse_amazon_page_html(resp.text, clean_url, asin)
                if raw_data:
                    norm = normalize_canonical_product(raw_data, "amazon", clean_url)
                    if norm:
                        logger.info(f"[AmazonUrlScraper] Successfully extracted via HTTP fallback: '{norm['title'][:40]}'")
                        return norm, "success", None
        except Exception as http_err:
            logger.debug(f"[AmazonUrlScraper] HTTP fallback failed: {http_err}")

        # ── Level 4: Clear Failure ──────────────────────────────────────────
        error_msg = browser_err or "Unable to retrieve product from Amazon URL"
        return None, "scraper_error", error_msg

    def _parse_amazon_page_html(self, html: str, url: str, asin: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Amazon product page HTML for title, price, specs, ratings, and image."""
        if not html:
            return None

        soup = bs4.BeautifulSoup(html, "html.parser")

        # 1. Product Title
        title = ""
        title_tag = soup.select_one("#productTitle, #title, h1.a-size-large")
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()

        if not title or len(title) < 4:
            return None

        # 2. Price
        price_num = 0
        price_selectors = [
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#apex_desktop .a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price-whole",
            'meta[property="product:price:amount"]'
        ]
        for sel in price_selectors:
            p_elem = soup.select_one(sel)
            if p_elem:
                val = p_elem.get('content') if p_elem.name == 'meta' else p_elem.get_text(strip=True)
                clean_p = re.sub(r'[^\d.]', '', val)
                if clean_p:
                    try:
                        price_num = int(float(clean_p))
                        if price_num > 0:
                            break
                    except Exception:
                        pass

        # 3. MRP (Original Price)
        mrp_num = price_num
        mrp_elem = soup.select_one(".a-text-price .a-offscreen, #basisPrice .a-offscreen")
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
        img_elem = soup.select_one("#landingImage, #imgBlkFront, #main-image, img.a-dynamic-image")
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-old-hires') or ""
            if not image_url and img_elem.get('data-a-dynamic-image'):
                try:
                    dyn_map = json.loads(img_elem['data-a-dynamic-image'])
                    if dyn_map:
                        image_url = list(dyn_map.keys())[0]
                except Exception:
                    pass
        if not image_url:
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img and og_img.get('content'):
                image_url = og_img['content']

        # 5. Rating & Review Count
        rating = None
        rate_elem = soup.select_one("#acrPopover .a-icon-alt, span[data-hook='rating-out-of-text']")
        if rate_elem:
            m_r = re.search(r'([\d.]+)', rate_elem.get_text())
            if m_r:
                try:
                    rating = float(m_r.group(1))
                except Exception:
                    pass

        reviews = 0
        rev_elem = soup.select_one("#acrCustomerReviewText, span[data-hook='total-review-count']")
        if rev_elem:
            m_rev = re.search(r'([\d,]+)', rev_elem.get_text())
            if m_rev:
                try:
                    reviews = int(m_rev.group(1).replace(',', ''))
                except Exception:
                    pass

        # 6. Specifications Table
        specifications: Dict[str, str] = {}
        # Tech spec table
        for row in soup.select("#productDetails_techSpec_section_1 tr, #prodDetails tr, .prodDetTable tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                k = th.get_text(strip=True)
                v = td.get_text(strip=True)
                if k and v:
                    specifications[k] = v

        # Bullet details
        for li in soup.select("#detailBullets_feature_div li"):
            text = li.get_text(strip=True)
            if ":" in text:
                parts = [p.strip() for p in text.split(":", 1)]
                if len(parts) == 2 and 2 < len(parts[0]) < 40 and len(parts[1]) < 200:
                    specifications[parts[0]] = parts[1]

        # 7. Key Features / Bullets
        features = []
        for li in soup.select("#feature-bullets li span.a-list-item"):
            feat = li.get_text(strip=True)
            if feat and len(feat) > 5 and not feat.startswith("Make sure this fits"):
                features.append(feat)

        # 8. Availability
        in_stock = True
        avail_elem = soup.select_one("#availability")
        if avail_elem:
            avail_txt = avail_elem.get_text(strip=True).lower()
            if "currently unavailable" in avail_txt or "out of stock" in avail_txt:
                in_stock = False

        # Brand
        brand = None
        brand_elem = soup.select_one("#bylineInfo, a#bylineInfo")
        if brand_elem:
            b_txt = brand_elem.get_text(strip=True)
            m_b = re.search(r'(?:Visit the|Brand:)\s*([A-Za-z0-9\s&]+?)(?:\s*Store|\s*$)', b_txt, re.IGNORECASE)
            if m_b:
                brand = m_b.group(1).strip()
            elif b_txt and not b_txt.startswith("http"):
                brand = b_txt

        return {
            "platform": "amazon",
            "title": title,
            "product_name": title,
            "asin": asin or "",
            "product_id": asin or "",
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
            "in_stock": in_stock,
            "brand": brand,
            "availability": "In Stock" if in_stock else "Out of Stock",
            "source": "live"
        }
