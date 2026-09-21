"""
scrapers/amazon/parser.py
=========================
Independent DOM & HTML parser for Amazon search results.
"""

import re
import logging
from typing import Dict, Any, Optional
import bs4

logger = logging.getLogger("smartbuy.scrapers.amazon.parser")


def parse_amazon_card(card: bs4.element.Tag) -> Optional[Dict[str, Any]]:
    """Extract product data from a single Amazon card element."""
    try:
        # ASIN
        asin = card.get('data-asin')
        if not asin:
            return None

        # Ignore purely sponsored ads that lack main title
        title_elem = card.select_one('h2 a span, h2 span, a.a-link-normal span.a-text-normal')
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if not title or len(title) < 4:
            return None

        # Section 3: Do not accept a generic Amazon title such as 'vivo' as an exact match
        words = [w for w in re.findall(r'[a-zA-Z0-9]+', title) if len(w) > 1]
        if len(words) <= 1 and title.lower() in ('vivo', 'samsung', 'apple', 'oppo', 'hp', 'dell', 'lenovo', 'asus', 'boat', 'noise', 'realme', 'redmi'):
            return None
        if any(phrase in title.lower() for phrase in ('visit the store', 'explore the store', 'shop the store', 'brand store')):
            return None

        # Price
        price_elem = card.select_one('span.a-price span.a-offscreen, span.a-price-whole')
        price_str = price_elem.get_text(strip=True) if price_elem else None
        if not price_str:
            return None

        cleaned_p = re.sub(r'[^\d.]', '', price_str)
        try:
            price_num = int(float(cleaned_p))
        except (ValueError, TypeError):
            return None

        # MRP
        mrp_elem = card.select_one('span.a-price.a-text-price span.a-offscreen')
        mrp_str = mrp_elem.get_text(strip=True) if mrp_elem else None
        mrp_num = None
        if mrp_str:
            cleaned_m = re.sub(r'[^\d.]', '', mrp_str)
            try:
                mrp_num = int(float(cleaned_m))
            except Exception:
                pass

        # Discount
        discount = 0
        if mrp_num and mrp_num > price_num:
            discount = round(((mrp_num - price_num) / mrp_num) * 100)

        # Rating
        rating = None
        rating_elem = card.select_one('i.a-icon-star-small span.a-icon-alt, span[aria-label*="stars"]')
        if rating_elem:
            r_match = re.search(r'([\d.]+)', rating_elem.get_text())
            if r_match:
                try:
                    rating = float(r_match.group(1))
                except Exception:
                    pass

        # Review count
        reviews = 0
        rev_elem = card.select_one('span.s-underline-text, a[href*="#customerReviews"] span')
        if rev_elem:
            rv_match = re.search(r'([\d,]+)', rev_elem.get_text())
            if rv_match:
                try:
                    reviews = int(rv_match.group(1).replace(',', ''))
                except Exception:
                    pass

        # Image
        img_elem = card.select_one('img.s-image')
        image = img_elem.get('src') if img_elem else ""

        # Product URL
        link_elem = card.select_one('h2 a.a-link-normal, a.a-link-normal.s-no-outline')
        href = link_elem.get('href') if link_elem else ""
        if href.startswith('/'):
            url = f"https://www.amazon.in{href.split('?')[0]}"
        elif href.startswith('http'):
            url = href.split('?')[0]
        else:
            url = f"https://www.amazon.in/dp/{asin}"

        return {
            "platform": "amazon",
            "asin": asin,
            "product_id": asin,
            "title": title,
            "price": f"₹{price_num:,}",
            "price_num": price_num,
            "mrp": f"₹{mrp_num:,}" if mrp_num else f"₹{price_num:,}",
            "mrp_num": mrp_num or price_num,
            "original_price": f"₹{mrp_num:,}" if mrp_num else f"₹{price_num:,}",
            "discount": discount,
            "discount_percent": discount,
            "rating": rating,
            "review_count": reviews,
            "reviews": f"{reviews:,}" if reviews > 0 else "0",
            "image": image,
            "image_url": image,
            "url": url,
            "product_url": url,
            "link": url,
            "availability": "In Stock",
            "in_stock": True,
            "source": "amazon"
        }
    except Exception as e:
        logger.debug(f"[AmazonParser] Error parsing card: {e}")
        return None
