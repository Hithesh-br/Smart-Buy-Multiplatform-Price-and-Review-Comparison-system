"""
amazon_scraper.py
=================
Dynamic Amazon.in product scraper using Playwright.
Accepts ANY search query — no product catalog or hardcoded items.
Includes retry logic, CAPTCHA detection, and graceful fallback.
"""

from playwright.sync_api import sync_playwright
import bs4
import re
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amazon_scraper")

MAX_RESULTS = 40
MAX_ATTEMPTS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _parse_price(text: str):
    """Extract numeric price from a price string."""
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def get_amazon_products(query: str) -> list:
    """
    Scrape Amazon.in search results for ANY query.

    Args:
        query: Any product name (milk, rice, iPhone 15, Gaming Chair, etc.)

    Returns:
        list of product dicts with: platform, title, price, price_num,
        original_price, discount, rating, reviews, in_stock, link, image, seller
    """
    logger.info(f"[Amazon] Scraping for '{query}'...")
    results = []

    for attempt in range(MAX_ATTEMPTS):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ua = USER_AGENTS[attempt % len(USER_AGENTS)]
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1"
                }
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    extra_http_headers=headers
                )
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}&ref=sr_pg_1"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                except Exception as goto_err:
                    logger.warning(f"[Amazon] page.goto warning: {goto_err}")

                try:
                    page.wait_for_selector(
                        'div[data-component-type="s-search-result"], div.s-result-item[data-asin]',
                        timeout=5000
                    )
                except Exception:
                    pass

                try:
                    page.evaluate("window.scrollBy(0, 1000)")
                except Exception:
                    pass

                page.wait_for_timeout(1000)
                html = page.content()
                browser.close()

            # CAPTCHA detection
            if "captcha" in html.lower() or "api-services-support@amazon.com" in html.lower():
                logger.warning(f"[Amazon] CAPTCHA detected on attempt {attempt + 1}. Retrying...")
                time.sleep(2)
                continue

            soup = bs4.BeautifulSoup(html, 'html.parser')
            containers = soup.find_all('div', {'data-component-type': 's-search-result'})
            if not containers or len(containers) < 5:
                alt_containers = [x for x in soup.select('div.s-result-item[data-asin]') if x.get('data-asin', '').strip()]
                if len(alt_containers) > len(containers):
                    containers = alt_containers

            if not containers:
                logger.warning(f"[Amazon] No result containers found on attempt {attempt + 1}.")
                continue

            for item in containers:
                if len(results) >= MAX_RESULTS:
                    break

                # Skip sponsored-only banner items (very short titles)
                sponsored_flag = item.get('data-component-id', '')
                ad_label = item.find('span', string=re.compile(r'Sponsored', re.I))

                # ── TITLE ──────────────────────────────────────────────
                brand_tag = item.select_one('h2')
                brand_name = brand_tag.get_text(strip=True) if brand_tag else ''

                title_text = ''
                links = item.find_all('a', href=True)
                for a in links:
                    t = a.get_text(separator=' ', strip=True)
                    href = a.get('href', '')
                    if '/dp/' in href and len(t) >= 10:
                        title_text = t
                        break
                    if len(t) > len(title_text) and not t.lower().endswith('stars') and not t.startswith('('):
                        title_text = t

                if not title_text or len(title_text) < 5:
                    if brand_tag:
                        title_text = brand_tag.get_text(separator=' ', strip=True)

                if brand_name and brand_name.lower() not in title_text.lower() and len(brand_name) < 15:
                    title_text = f"{brand_name} {title_text}".strip()

                title_text = re.sub(r'^Sponsored\s*', '', title_text, flags=re.I).strip()

                if not title_text or len(title_text) < 6:
                    continue

                # ── ASIN / LINK ─────────────────────────────────────────
                asin_div = item.find(attrs={'data-asin': True})
                asin = asin_div.get('data-asin', '').strip() if asin_div else ''
                if asin:
                    full_link = f"https://www.amazon.in/dp/{asin}"
                else:
                    link_elem = next(
                        (a for a in item.find_all('a', href=True) if '/dp/' in a.get('href', '')),
                        None
                    )
                    if link_elem:
                        href = link_elem.get('href', '')
                        full_link = ("https://www.amazon.in" + href) if href.startswith('/') else href
                    else:
                        full_link = url

                # ── CURRENT PRICE ────────────────────────────────────────
                price_elem = item.select_one('span.a-price-whole')
                price_str = f"₹{price_elem.text.strip().rstrip('.')}" if price_elem else "N/A"
                price_num = _parse_price(price_elem.text) if price_elem else None

                # ── ORIGINAL PRICE (MRP) ─────────────────────────────────
                orig_elem = item.select_one('span.a-price.a-text-price span.a-offscreen')
                orig_price_str = orig_elem.text.strip() if orig_elem else "N/A"
                orig_price_num = _parse_price(orig_elem.text) if orig_elem else None

                # ── DISCOUNT ─────────────────────────────────────────────
                discount_str = "N/A"
                if price_num and orig_price_num and orig_price_num > price_num:
                    pct = round(((orig_price_num - price_num) / orig_price_num) * 100)
                    discount_str = f"{pct}% off"
                else:
                    disc_match = re.search(r'\((\d+)%\s*off\)', item.text[:2000], re.I)
                    if disc_match:
                        discount_str = f"{disc_match.group(1)}% off"

                # ── RATING ───────────────────────────────────────────────
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

                # ── REVIEWS ──────────────────────────────────────────────
                reviews = "0"
                reviews_a = item.find(
                    'a', attrs={'aria-label': re.compile(r'^\d[\d,]*\s+ratings?$', re.I)}
                )
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

                # ── AVAILABILITY ─────────────────────────────────────────
                item_text = item.text.lower()
                in_stock = not (
                    "currently unavailable" in item_text
                    or "out of stock" in item_text
                    or price_num is None
                )

                # ── IMAGE ────────────────────────────────────────────────
                img_elem = item.select_one('img.s-image') or item.find('img')
                img_src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300&auto=format&fit=crop&q=60'
                if img_elem:
                    src = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-old-hires', '')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        if not src.startswith('data:'):
                            img_src = src

                # ── SELLER (if available) ────────────────────────────────
                seller = "N/A"
                seller_elem = item.select_one('span.a-size-small')
                if seller_elem and 'by' in seller_elem.text.lower():
                    seller = seller_elem.text.strip()

                # Extract brand (first word of title)
                brand = title_text.split()[0] if title_text else "Generic"
                availability_str = "In Stock" if in_stock else "Out of Stock"

                results.append({
                    "platform":       "Amazon",
                    "title":          title_text,
                    "brand":          brand,
                    "price":          price_str,
                    "price_num":      price_num,
                    "original_price": orig_price_str,
                    "discount":       discount_str,
                    "rating":         rating,
                    "reviews":        reviews,
                    "in_stock":       in_stock,
                    "availability":   availability_str,
                    "link":           full_link,
                    "image":          img_src,
                    "seller":         seller,
                    "is_sponsored":   ad_label is not None,
                })

            if results:
                break

        except Exception as e:
            logger.error(f"[Amazon] Error on attempt {attempt + 1}: {e}")
            time.sleep(1)

    # Filter out sponsored-only results if we have enough organic results
    organic = [r for r in results if not r.get('is_sponsored', False)]
    final = organic if len(organic) >= 3 else results

    logger.info(f"[Amazon] Returned {len(final)} items for '{query}'")
    return final
