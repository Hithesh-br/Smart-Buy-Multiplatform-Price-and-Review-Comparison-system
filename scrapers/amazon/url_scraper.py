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

from search.url_resolver import is_short_or_share_url, resolve_product_url

AMAZON_API_URL = os.getenv("AMAZON_CREATORS_API_ENDPOINT") or os.getenv("AMAZON_API_URL", "").strip()
AMAZON_API_KEY = os.getenv("AMAZON_CREATORS_API_KEY") or os.getenv("AMAZON_API_KEY", "").strip()
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

        # Resolve short / mobile share URLs (e.g. amzn.in/d/..., amzn.to/...) first
        if is_short_or_share_url(clean_url):
            logger.info(f"[AmazonUrlScraper] Resolving short share URL: {clean_url}")
            resolved = resolve_product_url(clean_url, "amazon")
            if resolved and resolved != clean_url:
                logger.info(f"[AmazonUrlScraper] Resolved short URL to: {resolved}")
                clean_url = resolved

        # Extract ASIN
        asin = None
        m = re.search(r'/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})', clean_url, re.IGNORECASE)
        if m:
            asin = m.group(1).upper()

        # ── Level 1: Amazon Creators API (or configured authorized API) ─────
        if AMAZON_API_URL and AMAZON_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {AMAZON_API_KEY}",
                    "x-api-key": AMAZON_API_KEY,
                    "Accept": "application/json"
                }
                api_endpoint = AMAZON_API_URL
                if asin and "{asin}" in api_endpoint:
                    api_endpoint = api_endpoint.replace("{asin}", asin)
                params = {"asin": asin, "url": clean_url} if (asin and "{asin}" not in AMAZON_API_URL) else {"url": clean_url}
                resp = requests.get(api_endpoint, headers=headers, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    prod_raw = data.get("product") or data.get("item") or data
                    norm = normalize_canonical_product(prod_raw, "amazon", clean_url)
                    if norm:
                        logger.info(f"[AmazonUrlScraper] Successfully extracted via Creators API: '{norm['title'][:40]}'")
                        return norm, "success", None
            except Exception as e:
                logger.debug(f"[AmazonUrlScraper] API fallback failed: {e}")

        # ── Level 2: Playwright Browser Scraper ──────────────────────────────
        def _browser_task(page):
            try:
                page.goto(clean_url, wait_until="domcontentloaded", timeout=18000)
            except Exception:
                try:
                    page.goto(clean_url, wait_until="commit", timeout=12000)
                except Exception:
                    pass

            # Check captcha / blocking
            try:
                title_text = page.title().lower()
                if "robot check" in title_text or "access denied" in title_text or "503 service unavailable" in title_text:
                    raise RuntimeError("Amazon access blocked")
            except Exception as title_err:
                if "access blocked" in str(title_err).lower():
                    raise

            # Try to wait for key product elements
            try:
                page.wait_for_selector("#productTitle, #title, h1, #centerCol, #dp-container, #landingImage, .a-price", timeout=6000)
            except Exception:
                page.wait_for_timeout(1500)

            html = ""
            for _ in range(5):
                try:
                    html = page.content()
                    if html and len(html) > 1000:
                        break
                except Exception:
                    time.sleep(0.8)

            if "robot check" in html.lower() or "captcha" in html.lower():
                raise RuntimeError("Amazon CAPTCHA block detected")

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
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Cache-Control": "no-cache",
                "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
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
        status_code = "blocked" if ("captcha" in str(error_msg).lower() or "blocked" in str(error_msg).lower()) else "scraper_error"
        return None, status_code, error_msg

    def _parse_amazon_page_html(self, html: str, url: str, asin: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw Amazon product page HTML for title, price, specs, ratings, and image."""
        if not html:
            return None

        soup = bs4.BeautifulSoup(html, "html.parser")

        # 0. Check JSON-LD structured data first
        ld_data = None
        for s_tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s_tag.string or "")
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if isinstance(it, dict) and it.get("@type") == "Product":
                        ld_data = it
                        break
                if ld_data:
                    break
            except Exception:
                pass

        # 1. Product Title (prioritize genuine product title element, ignore cart drawers)
        invalid_titles = {
            "adding to cart...", "added to cart", "not added",
            "select delivery location", "robot check", "access denied",
            "page not found", "something went wrong"
        }

        title = ""
        # Selector 1: Explicit #productTitle element
        pt_elem = soup.select_one("#productTitle")
        if pt_elem:
            t = pt_elem.get_text(strip=True)
            if t and t.lower() not in invalid_titles and len(t) >= 4:
                title = t

        # Selector 2: CenterCol h1
        if not title:
            h1_elem = soup.select_one("#centerCol h1, h1#title")
            if h1_elem:
                t = h1_elem.get_text(strip=True)
                if t and t.lower() not in invalid_titles and len(t) >= 4:
                    title = t

        # Selector 3: JSON-LD title
        if not title and ld_data and ld_data.get("name"):
            t = str(ld_data["name"]).strip()
            if t and t.lower() not in invalid_titles and len(t) >= 4:
                title = t

        # Selector 4: meta og:title
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                t = og_title['content'].strip()
                # Clean Amazon suffix if present (e.g. "... : Amazon.in: Health & Personal Care")
                if " : Amazon.in" in t:
                    t = t.split(" : Amazon.in")[0].strip()
                elif " - Amazon.in" in t:
                    t = t.split(" - Amazon.in")[0].strip()
                if t and t.lower() not in invalid_titles and len(t) >= 4:
                    title = t

        if not title or len(title) < 4:
            return None

        # 2. Price
        price_num = 0
        price_selectors = [
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            ".priceToPay span.a-offscreen",
            "#corePrice_desktop .a-price .a-offscreen",
            "span.apexPriceToPay span.a-offscreen",
            "#corePrice_feature_div .a-price .a-offscreen",
            "#apex_desktop .a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#newBuyBoxPrice",
            "#sns-base-price",
            ".a-price.aok-align-center .a-offscreen",
            ".priceToPay .a-price-whole",
            "#corePriceDisplay_desktop_feature_div .a-price-whole",
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
                        p_val = int(float(clean_p))
                        if p_val > 0:
                            price_num = p_val
                            break
                    except Exception:
                        pass

        # Check JSON-LD for price fallback
        if price_num <= 0 and ld_data:
            offers = ld_data.get("offers")
            offer_obj = offers[0] if isinstance(offers, list) and offers else (offers if isinstance(offers, dict) else {})
            raw_p = offer_obj.get("price") or ld_data.get("price")
            if raw_p:
                clean_p = re.sub(r'[^\d.]', '', str(raw_p))
                if clean_p:
                    try:
                        price_num = int(float(clean_p))
                    except Exception:
                        pass

        # 3. MRP (Original Price)
        mrp_num = price_num
        mrp_selectors = [
            ".a-text-price .a-offscreen",
            "#basisPrice .a-offscreen",
            "span[data-a-strike='true'] .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-text-price span.a-offscreen"
        ]
        for sel in mrp_selectors:
            mrp_elem = soup.select_one(sel)
            if mrp_elem:
                clean_m = re.sub(r'[^\d.]', '', mrp_elem.get_text(strip=True))
                if clean_m:
                    try:
                        mrp_val = int(float(clean_m))
                        if mrp_val >= price_num:
                            mrp_num = mrp_val
                            break
                    except Exception:
                        pass

        # 4. Images (primary image + full images list)
        image_url = ""
        images_list = []

        img_elem = soup.select_one("#landingImage, #imgBlkFront, #main-image, img.a-dynamic-image")
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-old-hires') or ""
            dyn_data = img_elem.get('data-a-dynamic-image')
            if dyn_data:
                try:
                    dyn_map = json.loads(dyn_data)
                    if isinstance(dyn_map, dict):
                        for k in dyn_map.keys():
                            if k.startswith("http") and k not in images_list:
                                images_list.append(k)
                        if not image_url and images_list:
                            image_url = images_list[0]
                except Exception:
                    pass

        # Additional images from thumbnail carousel
        for th_img in soup.select("#altImages img, .imageThumbnail img"):
            th_src = th_img.get('src') or ""
            if th_src.startswith("http") and "sprite" not in th_src and "icon" not in th_src:
                hi_res = re.sub(r'\._[A-Z0-9_,]+_\.', '.', th_src)
                if hi_res not in images_list:
                    images_list.append(hi_res)

        if not image_url and ld_data:
            ld_img = ld_data.get("image")
            if isinstance(ld_img, list) and ld_img:
                image_url = ld_img[0]
            elif isinstance(ld_img, str):
                image_url = ld_img

        if not image_url:
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img and og_img.get('content'):
                image_url = og_img['content']

        if image_url and image_url not in images_list:
            images_list.insert(0, image_url)

        # 5. Rating & Review Count
        rating = None
        rate_elem = soup.select_one(
            "#acrPopover .a-icon-alt, span[data-hook='rating-out-of-text'], "
            "i[data-hook='average-star-rating'] span, span.a-icon-alt, "
            "#acrPopover, [aria-label*='out of 5 stars']"
        )
        if rate_elem:
            t_cand = rate_elem.get_text() or rate_elem.get("aria-label", "")
            m_r = re.search(r'([1-5](?:\.\d+)?)', t_cand)
            if m_r:
                try:
                    r_val = float(m_r.group(1))
                    if 0.0 <= r_val <= 5.0:
                        rating = r_val
                except Exception:
                    pass

        reviews = 0
        rev_elem = soup.select_one(
            "#acrCustomerReviewText, span[data-hook='total-review-count'], "
            "#ask_feature_div span.a-size-base, a[href*='#customerReviews']"
        )
        if rev_elem:
            m_rev = re.search(r'([\d,]+)', rev_elem.get_text())
            if m_rev:
                try:
                    reviews = int(m_rev.group(1).replace(',', ''))
                except Exception:
                    pass

        if (rating is None or reviews == 0) and ld_data and ld_data.get("aggregateRating"):
            agg = ld_data["aggregateRating"]
            if rating is None and agg.get("ratingValue"):
                try:
                    rating = float(agg["ratingValue"])
                except Exception:
                    pass
            if reviews == 0 and (agg.get("reviewCount") or agg.get("ratingCount")):
                try:
                    reviews = int(agg.get("reviewCount") or agg.get("ratingCount"))
                except Exception:
                    pass

        # 6. Specifications Table
        specifications: Dict[str, str] = {}

        # 6a. Product Overview Table (Top-of-page essential specs)
        for row in soup.select("#productOverview_feature_div tr"):
            tds = row.select("td")
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True)
                v = tds[1].get_text(strip=True)
                if k and v and len(k) < 50 and len(v) < 300:
                    specifications[k] = v

        # 6b. Technical Specifications Table
        for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_techSpec_section_2 tr, #prodDetails tr, .prodDetTable tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                k = th.get_text(strip=True)
                v = td.get_text(strip=True)
                if k and v and len(k) < 50 and len(v) < 300:
                    specifications[k] = v

        # 6c. Detail Bullets
        for li in soup.select("#detailBullets_feature_div li"):
            text = li.get_text(strip=True)
            if ":" in text:
                parts = [p.strip() for p in text.split(":", 1)]
                if len(parts) == 2 and 2 < len(parts[0]) < 40 and len(parts[1]) < 300:
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

        # 9. Brand
        brand = specifications.get("Brand") or specifications.get("Brand Name")
        if not brand:
            brand_elem = soup.select_one("#bylineInfo, a#bylineInfo")
            if brand_elem:
                b_txt = brand_elem.get_text(strip=True)
                m_b = re.search(r'(?:Visit the|Brand:)\s*([A-Za-z0-9\s&]+?)(?:\s*Store|\s*$)', b_txt, re.IGNORECASE)
                if m_b:
                    brand = m_b.group(1).strip()
                elif b_txt and not b_txt.startswith("http"):
                    brand = b_txt

        if not brand and ld_data and ld_data.get("brand"):
            b_obj = ld_data["brand"]
            brand = b_obj.get("name") if isinstance(b_obj, dict) else str(b_obj)

        # 10. Model
        model = specifications.get("Model Name") or specifications.get("Model")
        if not model:
            # Check title for human readable phone/device model
            m_phone = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|galaxy\s*[a-z]\d{1,2}(?:\s*5g|\s*4g)?|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|pixel\s*\d[a-z]?|t\d(?:\s*5g|\s*pro|\s*lite)?|nord(?:\s*ce)?\s*\d[a-z]?)\b', title, re.I)
            if m_phone:
                model = m_phone.group(0).strip()
            else:
                raw_mod = specifications.get("Model Number") or specifications.get("Item model number")
                if raw_mod and '/' not in str(raw_mod):
                    model = str(raw_mod).strip()
        if model:
            model = re.sub(r'[\u200b-\u200f\ufeff]', '', str(model)).strip()

        # 11. Warranty
        warranty = specifications.get("Warranty") or specifications.get("Warranty Description") or specifications.get("Manufacturer Warranty") or ""

        # Canonical product URL
        canonical_prod_url = f"https://www.amazon.in/dp/{asin}" if asin else url

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
            "images": images_list,
            "rating": rating,
            "review_count": reviews,
            "product_url": canonical_prod_url,
            "url": canonical_prod_url,
            "specifications": specifications,
            "key_features": features,
            "in_stock": in_stock,
            "brand": brand,
            "model": model,
            "warranty": warranty,
            "availability": "In Stock" if in_stock else "Out of Stock",
            "source": "live"
        }
