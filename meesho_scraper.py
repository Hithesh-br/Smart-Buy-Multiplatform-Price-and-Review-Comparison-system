"""
meesho_scraper.py
=================
Dynamic Meesho product scraper using Playwright.
Accepts ANY search query — no product catalog or hardcoded items.

Selector strategy (updated for 2025 Meesho DOM — styled-components):
    - Product cards: div[class*="NewProductCardstyled__CardStyled"]
                  or div[class*="ProductListItem__GridCol"]
    - Title:         span[class*="Caption3"] or p containing title text
    - Price:         h5 (most reliable — Meesho always uses h5 for current price)
    - Orig price:    p[class*="bvkGfG"] or p[class*="drnSnt"]
    - Rating:        regex on card text
"""

from playwright.sync_api import sync_playwright
import bs4
import re
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meesho_scraper")

MAX_RESULTS = 20
MAX_ATTEMPTS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.64 Mobile Safari/537.36",
]


def _parse_price(text: str):
    """Extract numeric price from a price string."""
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None


def _extract_card_data(card) -> dict | None:
    """
    Extract product data from a Meesho product card element.
    Returns None if essential data (title) is missing.
    """
    card_text = card.get_text(separator=' ', strip=True)

    # ── TITLE ──────────────────────────────────────────────────────────────
    title = ''

    # Strategy 1: span[class*="Caption3"] — the title span in Meesho
    for elem in card.find_all('span'):
        cls = ' '.join(elem.get('class', []))
        if 'Caption3' in cls or 'ProductTitle' in cls or 'title' in cls.lower():
            t = elem.get_text(strip=True)
            if t and len(t) > 5:
                title = t
                break

    # Strategy 2: img[alt]
    if not title:
        img = card.find('img')
        if img:
            alt = img.get('alt', '').strip()
            if alt and len(alt) > 5:
                title = alt

    # Strategy 3: first p element with meaningful text
    if not title:
        for p in card.find_all('p'):
            t = p.get_text(strip=True)
            if (t and len(t) > 5
                    and not re.match(r'^[₹\d,]+', t)
                    and 'Review' not in t
                    and 'Rating' not in t):
                title = t
                break

    # Strategy 4: Parse the card text up to the first price signal
    if not title:
        m = re.match(r'^([^₹0-9]{6,80})', card_text)
        if m:
            title = m.group(1).strip()

    if not title or len(title) < 4:
        return None

    # ── IMAGE ───────────────────────────────────────────────────────────────
    img_src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300&auto=format&fit=crop&q=60'
    img = card.find('img')
    if img:
        src = img.get('src', '') or img.get('data-src', '') or img.get('srcset', '')
        if src:
            src = src.split(',')[0].split()[0]  # First URL if srcset
            if src.startswith('//'):
                src = 'https:' + src
            if not src.startswith('data:') and ('http' in src or 'meesho' in src or 'images' in src):
                img_src = src

    # ── PRICE ───────────────────────────────────────────────────────────────
    # Meesho reliably uses <h5> for current price
    price_str = "N/A"
    price_num = None

    h5s = card.find_all('h5')
    for h5 in h5s:
        txt = h5.get_text(strip=True)
        n = _parse_price(txt)
        if n and n > 0:
            price_str = f"₹{n:,}"
            price_num = n
            break

    # Fallback: any span/div that looks like a price
    if not price_num:
        for elem in card.find_all(['span', 'div']):
            txt = elem.get_text(strip=True)
            if re.match(r'^[₹]?[\d,]{2,7}$', txt):
                n = _parse_price(txt)
                if n and n > 0:
                    price_str = f"₹{n:,}"
                    price_num = n
                    break

    # Regex fallback on card text
    if not price_num:
        m = re.search(r'[₹]([\d,]+)', card_text)
        if m:
            n = _parse_price(m.group(1))
            if n and n > 0:
                price_str = f"₹{n:,}"
                price_num = n

    # ── ORIGINAL PRICE & DISCOUNT ────────────────────────────────────────────
    orig_str = "N/A"
    orig_num = None
    discount = "N/A"

    # p[class*="drnSnt"] or p[class*="bvkGfG"] = MRP in Meesho
    for p in card.find_all('p'):
        cls = ' '.join(p.get('class', []))
        if 'drnSnt' in cls or 'bvkGfG' in cls or 'OriginalPrice' in cls:
            txt = p.get_text(strip=True)
            n = _parse_price(txt)
            if n and price_num and n > price_num:
                orig_str = f"₹{n:,}"
                orig_num = n
                break

    # Discount from span[class*="Discount"] or regex
    for elem in card.find_all(['span', 'div']):
        cls = ' '.join(elem.get('class', []))
        txt = elem.get_text(strip=True)
        if ('Discount' in cls or 'discount' in cls) and '%' in txt:
            discount = txt
            break

    if discount == "N/A" and price_num and orig_num and orig_num > price_num:
        pct = round(((orig_num - price_num) / orig_num) * 100)
        discount = f"{pct}% off"

    # Regex discount fallback
    if discount == "N/A":
        d_m = re.search(r'(\d+)%\s*off', card_text, re.I)
        if d_m:
            discount = f"{d_m.group(1)}% off"

    # ── RATING & REVIEWS ─────────────────────────────────────────────────────
    rating = "N/A"
    reviews = "0"
    rat_m = re.search(r'\b([1-5]\.[0-9])\b', card_text)
    if rat_m:
        rating = rat_m.group(1)
    rev_m = re.search(r'([\d,]+)\s+(?:Reviews?|Ratings?)', card_text, re.I)
    if rev_m:
        reviews = rev_m.group(1)

    # ── LINK ─────────────────────────────────────────────────────────────────
    link_href = ''
    parent_a = card.find_parent('a')
    if parent_a:
        link_href = parent_a.get('href', '')
    if not link_href:
        a = card.find('a', href=True)
        if a:
            link_href = a.get('href', '')
    full_link = (f"https://www.meesho.com{link_href}"
                 if link_href and link_href.startswith('/') else link_href)

    # ── SELLER ───────────────────────────────────────────────────────────────
    seller = "N/A"
    s_m = re.search(r'(?:Supplier|Seller|Sold by)[:\s]+([A-Za-z][\w\s]{2,30})', card_text, re.I)
    if s_m:
        seller = s_m.group(1).strip()

    brand = title.split()[0] if title else "Generic"
    in_stock = price_num is not None
    availability_str = "In Stock" if in_stock else "Out of Stock"

    return {
        "platform":       "Meesho",
        "title":          title,
        "brand":          brand,
        "price":          price_str,
        "price_num":      price_num,
        "original_price": orig_str,
        "discount":       discount,
        "rating":         rating,
        "reviews":        reviews,
        "in_stock":       in_stock,
        "availability":   availability_str,
        "link":           full_link or "https://www.meesho.com",
        "image":          img_src,
        "seller":         seller,
        "is_sponsored":   False,
    }


def get_meesho_products(query: str) -> list:
    """
    Scrape Meesho search results for ANY query.
    Uses multiple selector strategies for resilience.
    """
    logger.info(f"[Meesho] Scraping for '{query}'...")
    results = []

    for attempt in range(MAX_ATTEMPTS):
        try:
            with sync_playwright() as p:
                # Use Firefox to bypass Akamai Bot Manager which heavily blocks Chromium
                browser = p.firefox.launch(headless=True)
                ua = USER_AGENTS[0] # Use the desktop user agent for Firefox
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                )
                page = context.new_page()

                # Try to mask webdriver for extra stealth
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                url = f"https://www.meesho.com/search?q={query.replace(' ', '%20')}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                except Exception as goto_err:
                    logger.warning(f"[Meesho] page.goto warning: {goto_err}")

                # Wait for product grid
                try:
                    page.wait_for_selector(
                        'div[class*="NewProductCard"], div[class*="ProductListItem"], h5',
                        timeout=5000
                    )
                except Exception:
                    pass

                # Scroll to trigger lazy loading
                try:
                    for scroll_y in [0.3, 0.6, 0.9]:
                        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll_y})")
                        page.wait_for_timeout(600)
                except Exception:
                    pass

                page.wait_for_timeout(1500)
                html = page.content()
                browser.close()

            soup = bs4.BeautifulSoup(html, 'html.parser')

            # ── STRATEGY A: styled-component card containers ────────────────
            # Meesho uses styled-components; class names contain readable substrings

            # Primary: CardStyled containers
            cards = soup.select('div[class*="NewProductCardstyled__CardStyled"]')

            # Fallback: GridCol containers (wraps each product)
            if not cards:
                cards = soup.select('div[class*="ProductListItem__GridCol"]')

            # Fallback: any div with NewProductCard in class
            if not cards:
                cards = soup.select('div[class*="NewProductCard"]')

            logger.info(f"[Meesho] Strategy A: {len(cards)} card containers")

            if cards:
                seen_titles = set()
                for card in cards:
                    if len(results) >= MAX_RESULTS:
                        break
                    data = _extract_card_data(card)
                    if data and data['title'] and data['title'] not in seen_titles:
                        # Filter out nav/menu items (very short titles or menu words)
                        if len(data['title']) >= 5:
                            seen_titles.add(data['title'])
                            results.append(data)

            # ── STRATEGY B: h5-based extraction ────────────────────────────
            # Each Meesho product has exactly one h5 (the price)
            # Find all h5 elements and walk up to find product container
            if not results:
                logger.info("[Meesho] Strategy B: h5-based extraction")
                h5_elements = soup.find_all('h5')
                seen_titles = set()

                for h5 in h5_elements:
                    if len(results) >= MAX_RESULTS:
                        break
                    # Walk up to find the product card
                    container = h5
                    for _ in range(8):
                        container = container.parent
                        if not container or container.name in ('body', 'html'):
                            break
                        cls = ' '.join(container.get('class', []))
                        # Stop at a likely product container
                        if ('Card' in cls or 'Product' in cls or 'Item' in cls
                                or 'Grid' in cls or 'VirtualItem' in cls):
                            break

                    if not container:
                        continue

                    data = _extract_card_data(container)
                    if data and data['title'] and data['title'] not in seen_titles:
                        if len(data['title']) >= 5 and data['price_num']:
                            seen_titles.add(data['title'])
                            results.append(data)

            # ── STRATEGY C: link-based ──────────────────────────────────────
            if not results:
                logger.info("[Meesho] Strategy C: link-based extraction")
                product_links = soup.select('a[href*="/p/"]')
                seen_titles = set()
                for a in product_links:
                    if len(results) >= MAX_RESULTS:
                        break
                    # Walk up to find the product card
                    container = a
                    for _ in range(6):
                        container = container.parent
                        if not container or container.name in ('body', 'html'):
                            break
                        # Look for h5 (price indicator) or sufficient text
                        if container.find('h5') or len(container.get_text(strip=True)) > 30:
                            break

                    data = _extract_card_data(container)
                    if data and data['title'] and data['title'] not in seen_titles:
                        if len(data['title']) >= 5:
                            seen_titles.add(data['title'])
                            results.append(data)

            if results:
                break

        except Exception as e:
            logger.error(f"[Meesho] Error on attempt {attempt + 1}: {e}", exc_info=True)
            time.sleep(2)

    logger.info(f"[Meesho] Returned {len(results)} items for '{query}'")
    return results
