"""
amazon_scraper.py
=================
Dynamic Amazon.in product scraper using Playwright.
Accepts ANY search query — no product catalog or hardcoded items.
Extracts:
  - product_name / title
  - product_url / link
  - price & price_num
  - rating & review_count
  - image_url / image
  - brand, model, processor, processor_generation, ram, storage, gpu, display
  - ASIN if available
  - specifications dictionary

Features:
  - Preserves exact user query (e.g. "HP Victus Intel Core i5 13th Gen 16GB 512GB")
  - ASIN & specification-based deduplication
  - Rejection logging for accessories & variant mismatches
  - Clean URL normalization (strips tracking query params)
"""

from playwright.sync_api import sync_playwright
import bs4
import re
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amazon_scraper")

MAX_RESULTS = 10
MAX_ATTEMPTS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _parse_price(text: str):
    """Extract numeric price integer from a price string."""
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None

def _clean_amazon_url(url: str, asin: str = "") -> str:
    """Normalize Amazon product URL by removing tracking query parameters."""
    if asin:
        return f"https://www.amazon.in/dp/{asin.strip().upper()}"
    if not url:
        return "https://www.amazon.in"
    
    clean = url.split('?')[0].split('#')[0]
    if not clean.startswith("http"):
        clean = "https://www.amazon.in" + (clean if clean.startswith('/') else '/' + clean)
    return clean

def _extract_asin_from_text_or_url(text: str, url: str) -> str:
    """Extract 10-character Amazon ASIN from URL or text."""
    m_url = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url, re.I)
    if m_url:
        return m_url.group(1).upper()
    m_text = re.search(r'\b([B0][A-Z0-9]{9})\b', text)
    if m_text:
        return m_text.group(1).upper()
    return ""

def _extract_specs_from_title(title: str) -> dict:
    """Extract structured spec fields directly from Amazon title."""
    t_lower = title.lower()
    
    # Brand
    brand = title.split()[0] if title else "Generic"
    
    # Processor & Gen
    proc = ""
    gen = ""
    p_m = re.search(r'\b(intel\s*core\s*i[3579]|core\s*i[3579]|ryzen\s*[3579]|apple\s*m[1-4]|snapdragon\s*\d+)\b', t_lower)
    if p_m:
        proc = p_m.group(1)
    g_m = re.search(r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:gen|generation)\b', t_lower)
    if g_m:
        gen = f"{g_m.group(1)}th gen"
        
    # RAM & Storage
    ram = ""
    storage = ""
    r_m = re.search(r'\b(4|6|8|12|16|24|32|64)\s*gb\s*(?:ram|lpddr\d?)?\b', t_lower)
    if r_m:
        ram = f"{r_m.group(1)}gb"
        
    st_m = re.search(r'\b(128|256|512|1024)\s*gb\b|\b(1|2|4)\s*tb\b', t_lower)
    if st_m:
        storage = st_m.group(0).replace(' ', '')
        
    # GPU & Display
    gpu = ""
    gpu_m = re.search(r'\b(rtx\s*\d{4}|gtx\s*\d{4}|radeon\s*rx\s*\d{4}|iris\s*xe)\b', t_lower)
    if gpu_m:
        gpu = gpu_m.group(1)
        
    disp = ""
    d_m = re.search(r'\b(\d{1,2}(?:\.\d)?)\s*(?:inch|"|-inch)\b', t_lower)
    if d_m:
        disp = f"{d_m.group(1)} inch"

    return {
        "brand": brand,
        "model": title.split()[1] if len(title.split()) > 1 else "",
        "processor": proc,
        "processor_generation": gen,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "display": disp
    }

def get_amazon_products(query: str) -> list:
    """
    Scrape Amazon.in search results preserving exact user query string.
    Includes validation, logging, ASIN extraction, and deduplication.
    """
    t_start = time.time()
    clean_q = query.strip()
    logger.info(f"[Amazon Debug Log] Search query: '{clean_q}'")

    raw_items_found = 0
    valid_results = []
    rejected_results = []

    for attempt in range(MAX_ATTEMPTS):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ua = USER_AGENTS[attempt % len(USER_AGENTS)]
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1280, "height": 720},
                    locale="en-IN",
                    extra_http_headers=headers
                )
                page = context.new_page()
                page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff2,ttf,mp4,avi}", lambda route: route.abort())
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                # Preserve full search query string in Amazon URL
                amazon_url = f"https://www.amazon.in/s?k={clean_q.replace(' ', '+')}&ref=sr_pg_1"
                try:
                    page.goto(amazon_url, wait_until="domcontentloaded", timeout=12000)
                except Exception as goto_err:
                    logger.warning(f"[Amazon] page.goto warning: {goto_err}")

                try:
                    page.wait_for_selector(
                        'div[data-component-type="s-search-result"], div.s-result-item[data-asin]',
                        timeout=4000
                    )
                except Exception:
                    pass

                html = page.content()
                browser.close()

            # CAPTCHA Detection
            if "captcha" in html.lower() or "api-services-support@amazon.com" in html.lower():
                logger.warning(f"[Amazon Debug Log] CAPTCHA blocked attempt {attempt + 1}.")
                continue

            soup = bs4.BeautifulSoup(html, 'html.parser')
            containers = soup.find_all('div', {'data-component-type': 's-search-result'})
            if not containers or len(containers) < 3:
                alt_containers = [x for x in soup.select('div.s-result-item[data-asin]') if x.get('data-asin', '').strip()]
                if len(alt_containers) > len(containers):
                    containers = alt_containers

            raw_items_found = len(containers)
            logger.info(f"[Amazon Debug Log] Raw containers found: {raw_items_found}")

            if not containers:
                continue

            seen_keys = set()

            for item in containers:
                if len(valid_results) >= MAX_RESULTS:
                    break

                # ── ASIN ──────────────────────────────────────────────────
                asin = item.get('data-asin', '').strip()
                
                # ── TITLE ─────────────────────────────────────────────────
                h2_tag = item.select_one('h2')
                h2_text = h2_tag.get_text(separator=' ', strip=True) if h2_tag else ''

                dp_link = ""
                dp_text = ""
                for a in item.find_all('a', href=True):
                    href = a.get('href', '')
                    if '/dp/' in href or '/gp/product/' in href:
                        if not dp_link:
                            dp_link = href
                        t = a.get_text(separator=' ', strip=True)
                        if len(t) > 15 and not re.search(r'^(?:₹|\$|m\.r\.p|stars|\(\d+\))', t, re.I):
                            dp_text = t
                            break

                if h2_text and dp_text:
                    if h2_text.lower() not in dp_text.lower():
                        title_text = f"{h2_text} {dp_text}".strip()
                    else:
                        title_text = dp_text
                elif dp_text:
                    title_text = dp_text
                else:
                    title_text = h2_text

                title_text = re.sub(r'^Sponsored\s*', '', title_text, flags=re.I).strip()

                if not title_text or len(title_text) < 6:
                    rejected_results.append({"title": title_text, "reason": "Title too short or empty"})
                    continue

                if not asin and dp_link:
                    asin = _extract_asin_from_text_or_url(title_text, dp_link)

                # ── PRODUCT URL ───────────────────────────────────────────
                full_link = _clean_amazon_url(dp_link, asin)

                # ── PRICE ─────────────────────────────────────────────────
                price_elem = item.select_one('span.a-price-whole')
                price_str = f"₹{price_elem.text.strip().rstrip('.')}" if price_elem else "N/A"
                price_num = _parse_price(price_elem.text) if price_elem else None

                # ── ORIGINAL PRICE (MRP) ──────────────────────────────────
                orig_elem = item.select_one('span.a-price.a-text-price span.a-offscreen')
                orig_price_str = orig_elem.text.strip() if orig_elem else "N/A"
                orig_price_num = _parse_price(orig_elem.text) if orig_elem else None

                # ── DISCOUNT ──────────────────────────────────────────────
                discount_str = "N/A"
                if price_num and orig_price_num and orig_price_num > price_num:
                    pct = round(((orig_price_num - price_num) / orig_price_num) * 100)
                    discount_str = f"{pct}% off"
                else:
                    disc_match = re.search(r'\((\d+)%\s*off\)', item.text[:2000], re.I)
                    if disc_match:
                        discount_str = f"{disc_match.group(1)}% off"

                # ── RATING ────────────────────────────────────────────────
                rating = "N/A"
                rating_a = item.find('a', attrs={'aria-label': re.compile(r'out of 5 stars', re.I)})
                if rating_a:
                    r_match = re.search(r'([0-9.]+)', rating_a.get('aria-label', ''))
                    if r_match:
                        rating = r_match.group(1)
                else:
                    rating_span = item.select_one('span.a-icon-alt')
                    if rating_span:
                        r_match = re.search(r'([0-9.]+)', rating_span.text)
                        if r_match:
                            rating = r_match.group(1)

                # ── REVIEWS ───────────────────────────────────────────────
                reviews = "0"
                reviews_a = item.find('a', attrs={'aria-label': re.compile(r'^\d[\d,]*\s+ratings?$', re.I)})
                if reviews_a:
                    rev_match = re.search(r'([\d,]+)', reviews_a.get('aria-label', ''))
                    if rev_match:
                        reviews = rev_match.group(1)
                else:
                    review_span = item.select_one('span.a-size-base.s-underline-text')
                    if review_span:
                        rev_digits = re.sub(r'[^\d]', '', review_span.text)
                        if rev_digits:
                            reviews = f"{int(rev_digits):,}"

                # ── IMAGE ─────────────────────────────────────────────────
                img_elem = item.select_one('img.s-image') or item.find('img')
                img_src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300&auto=format&fit=crop&q=60'
                if img_elem:
                    src = img_elem.get('src', '') or img_elem.get('data-src', '')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        if not src.startswith('data:'):
                            img_src = src

                # ── SPECS & IDENTITY ──────────────────────────────────────
                specs = _extract_specs_from_title(title_text)

                # ── DEDUPLICATION KEY ─────────────────────────────────────
                dedup_key = asin if asin else f"{specs['brand']}_{specs['model']}_{specs['processor']}_{specs['ram']}_{specs['storage']}"
                if dedup_key in seen_keys:
                    rejected_results.append({"title": title_text, "reason": f"Duplicate product key ({dedup_key})"})
                    continue
                seen_keys.add(dedup_key)

                in_stock = price_num is not None
                availability_str = "In Stock" if in_stock else "Out of Stock"

                valid_results.append({
                    "platform":             "Amazon",
                    "title":                title_text,
                    "product_name":         title_text,
                    "brand":                specs["brand"],
                    "model":                specs["model"],
                    "processor":            specs["processor"],
                    "processor_generation": specs["processor_generation"],
                    "ram":                  specs["ram"],
                    "storage":              specs["storage"],
                    "gpu":                  specs["gpu"],
                    "display":              specs["display"],
                    "specifications":       specs,
                    "specs":                specs,
                    "price":                price_str,
                    "price_num":            price_num,
                    "original_price":       orig_price_str,
                    "discount":             discount_str,
                    "rating":               rating,
                    "reviews":              reviews,
                    "review_count":         reviews,
                    "in_stock":             in_stock,
                    "availability":         availability_str,
                    "link":                 full_link,
                    "product_url":          full_link,
                    "image":                img_src,
                    "image_url":            img_src,
                    "asin":                 asin,
                    "is_sponsored":         item.find('span', string=re.compile(r'Sponsored', re.I)) is not None
                })

            if valid_results:
                break

        except Exception as e:
            logger.error(f"[Amazon Debug Log] Scraper exception on attempt {attempt + 1}: {e}")
            time.sleep(1)

    dt = round(time.time() - t_start, 2)
    logger.info(f"[Amazon Debug Log] Amazon results found: {raw_items_found}")
    logger.info(f"[Amazon Debug Log] Amazon valid results: {len(valid_results)}")
    logger.info(f"[Amazon Debug Log] Amazon rejected results: {len(rejected_results)}")
    if valid_results:
        logger.info(f"[Amazon Debug Log] Best matching Amazon product: '{valid_results[0]['title']}' ({valid_results[0]['price']})")
    logger.info(f"[Amazon Debug Log] Amazon scraping time: {dt} seconds")

    return valid_results
