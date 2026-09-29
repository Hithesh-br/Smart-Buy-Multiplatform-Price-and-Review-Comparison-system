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
from scrapers.flipkart.parser import clean_flipkart_image_url
from scrapers.common_schema import get_platform_fallback_image
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

        # ── Level 2: Fast Direct HTTP & HTML / JSON-LD / is_script Parser ─────
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
            resp = requests.get(clean_url, headers=headers, timeout=12)
            if resp.status_code == 200 and resp.text:
                raw_data = self._parse_flipkart_page_html(resp.text, clean_url, pid)
                if raw_data and raw_data.get("title") and raw_data.get("price_num"):
                    norm = normalize_canonical_product(raw_data, "flipkart", clean_url)
                    if norm:
                        logger.info(f"[FlipkartUrlScraper] Successfully extracted via HTTP: '{norm['title'][:40]}'")
                        return norm, "success", None
        except Exception as http_err:
            logger.debug(f"[FlipkartUrlScraper] Direct HTTP fetch failed: {http_err}")

        # ── Level 3: Playwright Browser Scraper Fallback ─────────────────────
        def _browser_task(page):
            page.goto(clean_url, wait_until="domcontentloaded", timeout=28000)

            title_text = page.title().lower()
            if "access denied" in title_text or "blocked" in title_text or "challenge" in page.content().lower():
                raise RuntimeError("Flipkart anti-bot challenge detected")

            # Try to wait for key product elements
            try:
                page.wait_for_selector("span.VU-ZEz, span.B_NuCI, div.Nx9bqj, div._30jeq3, div.hZ3P6w", timeout=5000)
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

        # ── Level 4: Clear Failure ──────────────────────────────────────────
        error_msg = browser_err or "Unable to retrieve product from Flipkart URL"
        return None, "scraper_error", error_msg

    def _parse_flipkart_page_html(self, html: str, url: str, pid: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Flipkart product page HTML for title, price, specs, ratings, and image."""
        if not html:
            return None

        soup = bs4.BeautifulSoup(html, "html.parser")

        # 1. Structured JSON-LD Data
        ld_title = None
        ld_brand = None
        ld_price = None
        ld_rating = None
        ld_reviews = None
        ld_image = None
        ld_sku = None
        ld_desc = None

        s_ld = soup.find('script', id='jsonLD')
        if not s_ld:
            s_ld = soup.select_one('script[type="application/ld+json"]')

        if s_ld and s_ld.string:
            try:
                ld_data = json.loads(s_ld.string)
                items = ld_data if isinstance(ld_data, list) else [ld_data]
                for it in items:
                    if isinstance(it, dict) and it.get("@type") == "Product":
                        ld_title = it.get("name")
                        ld_desc = it.get("description")
                        if it.get("image"):
                            imgs = it.get("image") if isinstance(it.get("image"), list) else [it.get("image")]
                            if imgs:
                                ld_image = clean_flipkart_image_url(imgs[0])
                        if it.get("brand") and isinstance(it.get("brand"), dict):
                            ld_brand = it.get("brand", {}).get("name")
                        elif isinstance(it.get("brand"), str):
                            ld_brand = it.get("brand")
                        if it.get("aggregateRating") and isinstance(it["aggregateRating"], dict):
                            ar = it["aggregateRating"]
                            if ar.get("ratingValue") is not None:
                                try:
                                    ld_rating = float(ar.get("ratingValue"))
                                except Exception:
                                    pass
                            rev_c = ar.get("ratingCount") or ar.get("reviewCount")
                            if rev_c is not None:
                                try:
                                    ld_reviews = int(rev_c)
                                except Exception:
                                    pass
                        if it.get("offers") and isinstance(it["offers"], dict):
                            off_p = it["offers"].get("price")
                            if off_p is not None:
                                try:
                                    ld_price = int(float(off_p))
                                except Exception:
                                    pass
                        if it.get("sku"):
                            ld_sku = str(it.get("sku"))
                        break
            except Exception as e:
                logger.debug(f"[FlipkartUrlScraper] JSON-LD parse failed: {e}")

        # 2. Title
        title = ld_title or ""
        if not title:
            title_elem = soup.select_one("span.VU-ZEz, span.B_NuCI, h1._6EBuvT, h1.yhB1nd, h1.pIpigb")
            if title_elem:
                title = title_elem.get_text(strip=True)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()

        if not title or len(title) < 3:
            return None

        # 3. Price
        price_num = ld_price or 0
        if not price_num:
            price_elem = soup.select_one("div.Nx9bqj.CxhGGd, div.Nx9bqj, div.hZ3P6w, div._30jeq3._16Jk6d, div._30jeq3, div.hl05eU")
            if price_elem:
                clean_p = re.sub(r'[^\d.]', '', price_elem.get_text(strip=True))
                if clean_p:
                    try:
                        price_num = int(float(clean_p))
                    except Exception:
                        pass

        # 4. MRP
        mrp_num = price_num
        mrp_elem = soup.select_one("div.yRaY8j.A68aKn, div.yRaY8j, div.kRYCnD, div._27UcVY, div._3I9_wc._2p6cR8, div._3I9_wc")
        if mrp_elem:
            clean_m = re.sub(r'[^\d.]', '', mrp_elem.get_text(strip=True))
            if clean_m:
                try:
                    mrp_val = int(float(clean_m))
                    if mrp_val >= price_num:
                        mrp_num = mrp_val
                except Exception:
                    pass
        elif ld_desc:
            m_mrp = re.search(r'Rs\.?\s*(\d+(?:\.\d+)?)', ld_desc)
            if m_mrp:
                try:
                    mrp_val = int(float(m_mrp.group(1)))
                    if mrp_val >= price_num:
                        mrp_num = mrp_val
                except Exception:
                    pass

        # Discount
        discount_str = None
        disc_elem = soup.select_one("div.HQe8jr span, div.HQe8jr, div._3Ay6Sb span, div._3Ay6Sb")
        if disc_elem:
            d_txt = disc_elem.get_text(strip=True)
            if "%" in d_txt:
                discount_str = d_txt

        # 5. Image Extraction
        image_url = ld_image or ""
        if not image_url:
            for img in soup.select("img.DByuf4, img.UCc1lI, img._396cs4._2amPTt, img._396cs4, img._2r_T1I, img._0DkuPH, div._2r_T1I img"):
                cand = clean_flipkart_image_url(img.get('data-resolved-src') or img.get('src') or img.get('data-src') or img.get('srcset'))
                if cand:
                    image_url = cand
                    break

        if not image_url:
            og_img = soup.select_one('meta[property="og:image"], meta[name="og:image"], meta[name="twitter:image"]')
            if og_img and og_img.get('content'):
                cand = clean_flipkart_image_url(og_img['content'])
                if cand:
                    image_url = cand

        if not image_url:
            image_url = get_platform_fallback_image("flipkart")

        # 6. Rating & Reviews
        rating = ld_rating
        if rating is None:
            rate_elem = soup.select_one("div.XQDdHH, div.MKiFS6, div._3LWZlK, span.CjyrHS")
            if rate_elem:
                m_r = re.search(r'([\d.]+)', rate_elem.get_text())
                if m_r:
                    try:
                        rating = float(m_r.group(1))
                    except Exception:
                        pass

        reviews = ld_reviews or 0
        if not reviews:
            rev_elem = soup.select_one("span.Wphh3Z, span.PvbNMB, span._2_R_DZ")
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

        # 7. Specifications Extraction
        specifications: Dict[str, str] = {}

        # Method A: Extract from script#is_script JSON
        s_is = soup.find('script', id='is_script')
        if s_is and s_is.string:
            content = s_is.string
            # Reverse pattern: label_1 value then label_0 name
            for v, k in re.findall(r'"label_1":\{"value":\{"text":\["([^"]+)"\]\}\}[^\{\}]*?"label_0":\{"value":\{"text":"([^"]+)"\}\}', content):
                if k and v and k not in specifications:
                    specifications[k.strip()] = v.strip()
            # Direct pattern: label_0 name then label_1 value
            for k, v in re.findall(r'"label_0":\{"value":\{"text":"([^"]+)"\}\}[^\{\}]*?"label_1":\{"value":\{"text":\["([^"]+)"\]\}\}', content):
                if k and v and k not in specifications:
                    specifications[k.strip()] = v.strip()
            # Object pattern: "name":"xyz","values":["abc"]
            for k, v in re.findall(r'\{"name":"([^"]+)","values":\["([^"]+)"\]\}', content):
                if k and v and k not in specifications:
                    specifications[k.strip()] = v.strip()

        # Method B: Extract from standard Flipkart HTML tables
        for tr in soup.select("table._14cfVK tr, table tr, div._3k-BhJ tr, div.row._30-a, div.G6XhRU tr"):
            tds = tr.select("td")
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True)
                v = tds[1].get_text(strip=True)
                if k and v and k not in specifications:
                    specifications[k] = v

        # Method C: Extract from modern flex divs
        font_divs = soup.select('div[font="default-fk-font-l"]')
        if font_divs:
            known_keys = {
                'skin type', 'pack of', 'organic', 'ideal for', 'fragrance scent',
                'color', 'type', 'application area', 'quantity', 'weight',
                'processor', 'ram', 'storage', 'display', 'battery', 'warranty', 'operating system'
            }
            for i in range(0, len(font_divs) - 1):
                d1 = font_divs[i].get_text(strip=True)
                d2 = font_divs[i+1].get_text(strip=True)
                if d1.lower() in known_keys and d1 not in specifications:
                    specifications[d1] = d2

        # 8. Bullet Highlights / Features
        features = []
        for li in soup.select("ul.HwRTzP li, li.DTBslk, div._2418kt li, ul._1gHwDe li"):
            f_text = li.get_text(strip=True)
            if f_text and len(f_text) > 3 and f_text not in features:
                features.append(f_text)

        # 9. Brand & Key Identity Attributes
        brand = ld_brand
        if not brand:
            bc_brand = soup.select_one("div._75nlfW a, a.R0cyWM")
            if bc_brand and len(bc_brand.get_text(strip=True)) < 30:
                brand = bc_brand.get_text(strip=True)

        # 10. Extract Weight / Quantity / Pack from specifications or title
        weight = specifications.get("Weight") or specifications.get("Item Weight") or specifications.get("Quantity") or specifications.get("Net Weight")
        if not weight:
            w_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|kilograms?|ml|l|litres?)\b', title, re.I)
            if w_m:
                weight = f"{w_m.group(1)} {w_m.group(2).lower()}"

        pack_quantity = specifications.get("Pack of") or specifications.get("Pack Quantity") or specifications.get("Number of Contents in Sales Package")
        if not pack_quantity:
            pq_m = re.search(r'(?:pack\s*of\s*|pack-)(\d+)', title, re.I)
            if pq_m:
                pack_quantity = pq_m.group(1)

        skin_type = specifications.get("Skin Type") or specifications.get("Applied For")

        return {
            "platform": "flipkart",
            "title": title,
            "product_name": title,
            "product_id": pid or ld_sku or "",
            "price_num": price_num,
            "mrp_num": mrp_num,
            "discount": discount_str,
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
            "weight": weight,
            "pack_quantity": pack_quantity,
            "quantity": weight,
            "skin_type": skin_type,
            "availability": "In Stock",
            "source": "live"
        }
