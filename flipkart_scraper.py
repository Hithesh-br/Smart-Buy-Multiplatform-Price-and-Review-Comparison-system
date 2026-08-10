"""
flipkart_scraper.py
===================
Dynamic Flipkart product scraper using Playwright.
Accepts ANY search query — no product catalog or hardcoded items.

Selector strategy (updated for 2025 Flipkart DOM):
    - Product cards: div.jIjQ8S  (or parent div.nZIRY7)
    - Title:         img[alt] inside /p/ links (most reliable)
    - Price:         div.hZ3P6w  (primary), regex fallback
    - Orig price:    div.kRYCnD  or div.HZ0E6r (MRP strikethrough)
    - Rating:        regex on card text
    - Image:         img[src] inside /p/ link
"""

from playwright.sync_api import sync_playwright
import bs4
import re
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flipkart_scraper")

MAX_RESULTS = 20
MAX_ATTEMPTS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def _parse_price(text: str):
    """Extract numeric price from a price string."""
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None


def _find_price_in_container(container) -> tuple:
    """
    Try multiple price selector strategies within a product container.
    Returns (price_str, price_num, orig_price_str, orig_price_num).
    """
    price_str = "N/A"
    price_num = None
    orig_str   = "N/A"
    orig_num   = None

    # Strategy 1: Known current price classes
    for cls in ['hZ3P6w', 'Nx9bqj', '_30jeq3', '_1_WHN1', 'hl05eU']:
        elems = container.select(f'.{cls}')
        for e in elems:
            txt = e.get_text(strip=True)
            n = _parse_price(txt)
            if n and n > 10:
                price_str = f"₹{n:,}"
                price_num = n
                break
        if price_num:
            break

    # Strategy 2: Any element whose text is purely a price (₹XXXXX or XXXXX)
    if not price_num:
        for elem in container.find_all(['div', 'span']):
            txt = elem.get_text(strip=True)
            if re.match(r'^[₹]?[\d,]{3,8}$', txt):
                n = _parse_price(txt)
                if n and n > 10:
                    price_str = f"₹{n:,}"
                    price_num = n
                    break

    # Strategy 3: Regex fallback on entire container text
    if not price_num:
        txt_all = container.get_text(separator=' ')
        m = re.search(r'[₹]\s*([\d,]+)', txt_all)
        if m:
            n = _parse_price(m.group(1))
            if n and n > 10:
                price_str = f"₹{n:,}"
                price_num = n

    # Original price (MRP / strikethrough)
    for cls in ['kRYCnD', 'HZ0E6r', '_3I9_wc', 'yRaBr', '_25b18h']:
        elems = container.select(f'.{cls}')
        for e in elems:
            txt = e.get_text(strip=True)
            n = _parse_price(txt)
            if n and price_num and n > price_num:
                orig_str = f"₹{n:,}"
                orig_num = n
                break
        if orig_num:
            break

    return price_str, price_num, orig_str, orig_num


def get_flipkart_products(query: str) -> list:
    """
    Scrape Flipkart search results for ANY query.
    """
    logger.info(f"[Flipkart] Scraping for '{query}'...")
    results = []

    for attempt in range(MAX_ATTEMPTS):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ua = USER_AGENTS[attempt % len(USER_AGENTS)]
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                )
                page = context.new_page()

                url = f"https://www.flipkart.com/search?q={query.replace(' ', '%20')}&sort=relevance"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                except Exception as e:
                    logger.warning(f"[Flipkart] goto: {e}")

                # Close login popup if present
                try:
                    for btn_sel in ['button._2KpZ6l._2doB4z', 'button[class*="close"]', 'span._30XB9F']:
                        try:
                            btn = page.locator(btn_sel).first
                            if btn.is_visible(timeout=1500):
                                btn.click()
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

                # Wait for product results
                try:
                    page.wait_for_selector(
                        'div.jIjQ8S, div._1AtVbE, a[href*="/p/"]',
                        timeout=5000
                    )
                except Exception:
                    pass

                page.wait_for_timeout(1000)
                html = page.content()
                browser.close()

            soup = bs4.BeautifulSoup(html, 'html.parser')

            # Helper to extract clean title from URL slug if alt text is generic/missing
            def _title_from_slug(href_str):
                m = re.search(r'/([^/]+)/p/', href_str)
                if m:
                    slug = m.group(1)
                    words = [w.capitalize() for w in slug.split('-') if w and not re.match(r'^itm[a-z0-9]+$', w, re.I)]
                    if len(words) >= 2:
                        return ' '.join(words)
                return ""

            # ── STRATEGY A: List View containers (mobiles, laptops, TVs) ───────────
            cards_list = soup.select('div.jIjQ8S')
            seen_links = set()

            if cards_list and len(cards_list) >= 4:
                logger.info(f"[Flipkart] Processing {len(cards_list)} List View containers")
                for card in cards_list:
                    if len(results) >= MAX_RESULTS:
                        break

                    link_elem = card.select_one('a[href*="/p/"]')
                    if not link_elem:
                        continue
                    link_href = link_elem.get('href', '')
                    if not link_href or link_href in seen_links:
                        continue

                    # Exact image for list view
                    img_elem = card.select_one('img')
                    img_src = ""
                    if img_elem:
                        img_src = img_elem.get('src', '') or img_elem.get('data-src', '')
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src

                    # Exact title for list view
                    title_elem = card.select_one('div.KzBfT8, div._4rR01T, a[title]') or card.find('img', alt=True)
                    title = ""
                    if title_elem:
                        title = title_elem.get('title', '') or title_elem.get('alt', '') or title_elem.get_text(strip=True)

                    if not title or len(title) < 5 or 'showing' in title.lower():
                        title = _title_from_slug(link_href)

                    if not title or len(title) < 4:
                        continue

                    seen_links.add(link_href)
                    price_str, price_num, orig_str, orig_num = _find_price_in_container(card)

                    discount = "N/A"
                    for cls in ['Uk9rWs', '_3Ay6B8', 'UkUFwK', '_1x_m-r']:
                        d_elem = card.select_one(f'.{cls}')
                        if d_elem and '%' in d_elem.text:
                            discount = d_elem.text.strip()
                            break
                    if discount == "N/A" and price_num and orig_num and orig_num > price_num:
                        pct = round(((orig_num - price_num) / orig_num) * 100)
                        discount = f"{pct}% off"

                    card_text = card.get_text(separator=' ', strip=True)
                    rating = "N/A"
                    reviews = "0"
                    rat_m = re.search(r'\b([1-5]\.[0-9])\b', card_text)
                    if rat_m:
                        rating = rat_m.group(1)
                    rev_m = re.search(r'([\d,]+)\s+(?:Ratings?|Reviews?)', card_text, re.I)
                    if rev_m:
                        reviews = rev_m.group(1)

                    in_stock = price_num is not None and 'out of stock' not in card_text.lower()
                    if not img_src:
                        img_src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300&auto=format&fit=crop&q=60'

                    full_link = f"https://www.flipkart.com{link_href}" if link_href.startswith('/') else link_href

                    results.append({
                        "platform":       "Flipkart",
                        "title":          title,
                        "price":          price_str,
                        "price_num":      price_num,
                        "original_price": orig_str,
                        "discount":       discount,
                        "rating":         rating,
                        "reviews":        reviews,
                        "in_stock":       in_stock,
                        "link":           full_link,
                        "image":          img_src,
                        "seller":         "N/A",
                    })

            # ── STRATEGY B: Grid View link binding (shoes, shirts, watches, etc.) ───
            if not results:
                p_links = soup.find_all('a', href=lambda h: h and '/p/' in h)
                logger.info(f"[Flipkart] Processing Grid View: {len(p_links)} product links")

                for a in p_links:
                    if len(results) >= MAX_RESULTS:
                        break

                    link_href = a.get('href', '')
                    if not link_href or link_href in seen_links:
                        continue

                    # The image MUST come directly from this link's img tag
                    img_elem = a.find('img')
                    if not img_elem:
                        continue

                    img_src = img_elem.get('src', '') or img_elem.get('data-src', '')
                    if not img_src or img_src.startswith('data:'):
                        continue
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src

                    alt = img_elem.get('alt', '').strip()

                    # Container for price & details
                    card_container = a.parent
                    for _ in range(4):
                        if card_container and card_container.name in ('div', 'td') and len(card_container.find_all('a', href=lambda h: h and '/p/' in h)) <= 2:
                            break
                        if card_container:
                            card_container = card_container.parent

                    if not card_container:
                        card_container = a

                    # Title resolution directly bound to this product link
                    title = alt
                    if not title or len(title) < 5 or 'showing' in title.lower():
                        title_elem = card_container.select_one('div[class*="title"], div._4rR01T, div.KzBfT8, a[title]')
                        if title_elem:
                            title = title_elem.get('title', '') or title_elem.get_text(strip=True)

                    if not title or len(title) < 5 or 'showing' in title.lower():
                        title = _title_from_slug(link_href)

                    if not title or len(title) < 4 or 'showing' in title.lower():
                        continue

                    seen_links.add(link_href)

                    # Extract price from card container
                    price_str, price_num, orig_str, orig_num = _find_price_in_container(card_container)

                    discount = "N/A"
                    for cls in ['Uk9rWs', '_3Ay6B8', 'UkUFwK', '_1x_m-r']:
                        d_elem = card_container.select_one(f'.{cls}')
                        if d_elem and '%' in d_elem.text:
                            discount = d_elem.text.strip()
                            break
                    if discount == "N/A" and price_num and orig_num and orig_num > price_num:
                        pct = round(((orig_num - price_num) / orig_num) * 100)
                        discount = f"{pct}% off"

                    card_text = card_container.get_text(separator=' ', strip=True)
                    rating = "N/A"
                    reviews = "0"
                    rat_m = re.search(r'\b([1-5]\.[0-9])\b', card_text)
                    if rat_m:
                        rating = rat_m.group(1)
                    rev_m = re.search(r'([\d,]+)\s+(?:Ratings?|Reviews?)', card_text, re.I)
                    if rev_m:
                        reviews = rev_m.group(1)

                    in_stock = price_num is not None and 'out of stock' not in card_text.lower()

                    full_link = f"https://www.flipkart.com{link_href}" if link_href.startswith('/') else link_href

                    results.append({
                        "platform":       "Flipkart",
                        "title":          title,
                        "price":          price_str,
                        "price_num":      price_num,
                        "original_price": orig_str,
                        "discount":       discount,
                        "rating":         rating,
                        "reviews":        reviews,
                        "in_stock":       in_stock,
                        "link":           full_link,
                        "image":          img_src,
                        "seller":         "N/A",
                    })

                if results:
                    break

            # ── STRATEGY B: Link-group extraction (fallback) ───────────────
            if not results:
                logger.info("[Flipkart] Strategy A failed — trying link-group strategy")
                links = soup.find_all('a', href=True)
                product_groups: dict = {}
                for l in links:
                    href = l.get('href', '')
                    if '/p/' in href:
                        clean_href = href.split('?')[0]
                        product_groups.setdefault(clean_href, []).append(l)

                seen_titles = set()
                for clean_href, group in product_groups.items():
                    if len(results) >= MAX_RESULTS:
                        break

                    # Title
                    title = ''
                    img_src = ''
                    for l in group:
                        img = l.find('img')
                        if img:
                            alt = img.get('alt', '').strip()
                            if alt and len(alt) > 8:
                                title = alt
                            src = img.get('src', '') or img.get('data-src', '')
                            if src and not src.startswith('data:'):
                                img_src = src
                            break

                    if not title:
                        for l in group:
                            txt = l.get_text(separator=' ', strip=True)
                            if len(txt) > 10 and 'Add to Compare' not in txt:
                                title = txt[:200]
                                break

                    if not title or len(title) < 5 or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # Find parent container for price
                    parent_container = group[0].parent
                    for _ in range(6):
                        if not parent_container or parent_container.name in ('body','html'):
                            break
                        price_str, price_num, orig_str, orig_num = _find_price_in_container(parent_container)
                        if price_num:
                            break
                        parent_container = parent_container.parent

                    if not price_num:
                        combined = ' '.join(l.get_text() for l in group)
                        m = re.search(r'[₹]([\d,]+)', combined)
                        if m:
                            price_num = _parse_price(m.group(1))
                            price_str = f"₹{price_num:,}" if price_num else "N/A"

                    discount = "N/A"
                    if price_num and orig_num and orig_num > price_num:
                        pct = round(((orig_num - price_num) / orig_num) * 100)
                        discount = f"{pct}% off"

                    combined_text = ' '.join(l.get_text(separator=' ', strip=True) for l in group)
                    rating = "N/A"
                    reviews = "0"
                    rat_m = re.search(r'\b([1-5]\.[0-9])\b', combined_text)
                    if rat_m:
                        rating = rat_m.group(1)
                    rev_m = re.search(r'([\d,]+)\s+(?:Ratings?|Reviews?)', combined_text, re.I)
                    if rev_m:
                        reviews = rev_m.group(1)

                    first_href = group[0].get('href', '')
                    full_link = (f"https://www.flipkart.com{first_href}"
                                 if first_href.startswith('/') else first_href)
                    if not img_src:
                        img_src = 'https://via.placeholder.com/200x200?text=Flipkart'

                    brand = title.split()[0] if title else "Generic"
                    in_stock = price_num is not None
                    availability_str = "In Stock" if in_stock else "Out of Stock"

                    results.append({
                        "platform":       "Flipkart",
                        "title":          title,
                        "brand":          brand,
                        "price":          price_str,
                        "price_num":      price_num,
                        "original_price": orig_str or "N/A",
                        "discount":       discount,
                        "rating":         rating,
                        "reviews":        reviews,
                        "in_stock":       in_stock,
                        "availability":   availability_str,
                        "link":           full_link,
                        "image":          img_src,
                        "seller":         "N/A",
                        "is_sponsored":   False,
                    })

                if results:
                    break

        except Exception as e:
            logger.error(f"[Flipkart] Error on attempt {attempt + 1}: {e}", exc_info=True)
            time.sleep(2)

    logger.info(f"[Flipkart] Returned {len(results)} items for '{query}'")
    return results
