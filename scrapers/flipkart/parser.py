"""
scrapers/flipkart/parser.py
===========================
Independent DOM & HTML parser for Flipkart search results.
"""

import re
import logging
from typing import Dict, Any, Optional
import bs4

logger = logging.getLogger("smartbuy.scrapers.flipkart.parser")


def parse_flipkart_card(card: bs4.element.Tag) -> Optional[Dict[str, Any]]:
    """Extract product data from a Flipkart card or container."""
    try:
        # Title
        title_elem = card.select_one('div.KzDlHZ, a.wjcEIp, a.WKTcLC, div._4rR01T, a.s1Q9rs, div._2W96wQ, a.IRpwTa, div.RG5Slk, div.nZIRY7')
        if not title_elem:
            title_elem = card.select_one('a[title]')
        if not title_elem:
            return None

        title = title_elem.get('title') or title_elem.get_text(strip=True)
        if not title or len(title) < 4:
            return None

        # Price
        price_elem = card.select_one('div.Nx9bqj, div._30jeq3, div.hl05eU, div.hZ3P6w')
        if not price_elem:
            return None
        price_str = price_elem.get_text(strip=True)
        cleaned_p = re.sub(r'[^\d.]', '', price_str)
        try:
            price_num = int(float(cleaned_p))
        except (ValueError, TypeError):
            return None

        # MRP
        mrp_elem = card.select_one('div.yRaY8j, div._3I9_wc, div.y739f8')
        mrp_str = mrp_elem.get_text(strip=True) if mrp_elem else None
        mrp_num = None
        if mrp_str:
            cleaned_m = re.sub(r'[^\d.]', '', mrp_str)
            try:
                mrp_num = int(float(cleaned_m))
            except Exception:
                pass

        # Discount
        disc_elem = card.select_one('div.UkUFwK span, div._3Ay6Sb span, div.UkUFwK')
        discount = 0
        if disc_elem:
            d_match = re.search(r'(\d+)%', disc_elem.get_text())
            if d_match:
                discount = int(d_match.group(1))
        elif mrp_num and mrp_num > price_num:
            discount = round(((mrp_num - price_num) / mrp_num) * 100)

        # Rating
        rating = None
        rate_elem = card.select_one('div.XQDdHH, div._3LWZlK, div.hGSR34, div.Wphh3Z')
        if rate_elem:
            r_match = re.search(r'([\d.]+)', rate_elem.get_text())
            if r_match:
                try:
                    rating = float(r_match.group(1))
                except Exception:
                    pass

        # Reviews
        reviews = 0
        rev_elem = card.select_one('span.Wphh3Z, span._2_R_DZ, div.a7saXW')
        if rev_elem:
            rv_match = re.search(r'([\d,]+)\s*Reviews?', rev_elem.get_text(), re.IGNORECASE)
            if not rv_match:
                rv_match = re.search(r'([\d,]+)', rev_elem.get_text())
            if rv_match:
                try:
                    reviews = int(rv_match.group(1).replace(',', ''))
                except Exception:
                    pass

        # Image extraction with multi-layer fallback
        image = ""
        # 1. Primary product image selector for Flipkart
        img_elem = card.select_one('img.UCc1lI, img.DByuf4, img._396cs4, img._2r_T1I, img._530RAn, img._0DkuPH, img.q6DClP')
        if img_elem:
            for attr in ('src', 'data-src', 'srcset'):
                val = img_elem.get(attr)
                if val:
                    if attr == 'srcset':
                        val = val.split(',')[0].strip().split(' ')[0]
                    if val.startswith('//'):
                        val = 'https:' + val
                    if not val.startswith('data:') and 'static-assets' not in val:
                        image = val
                        break

        # 2. Search all img tags in card for Flipkart CDN product images
        if not image:
            for img in card.select('img'):
                for attr in ('src', 'data-src', 'srcset'):
                    val = img.get(attr)
                    if not val:
                        continue
                    if attr == 'srcset':
                        val = val.split(',')[0].strip().split(' ')[0]
                    if val.startswith('//'):
                        val = 'https:' + val
                    if ('rukminim' in val or 'flixcart.com/image/' in val) and not val.startswith('data:'):
                        image = val
                        break
                if image:
                    break

        # 3. Fallback to any non-static, non-data img tag
        if not image:
            for img in card.select('img'):
                val = img.get('src') or img.get('data-src') or ''
                if val.startswith('//'):
                    val = 'https:' + val
                if val and not val.startswith('data:') and 'static-assets' not in val and 'fa_9e47c1' not in val:
                    image = val
                    break

        # Product Link
        link_elem = card.select_one('a.CGtC5Q, a._1fQZEK, a.s1Q9rs, a.VJA3rP, a.k7wcnx, a[href*="/p/"]')
        href = link_elem.get('href') if link_elem else ""
        if href.startswith('/'):
            url = f"https://www.flipkart.com{href.split('?')[0]}"
        elif href.startswith('http'):
            url = href.split('?')[0]
        else:
            url = "https://www.flipkart.com"

        # Product ID
        product_id = ""
        m_pid = re.search(r'pid=([A-Z0-9]+)', href)
        if m_pid:
            product_id = m_pid.group(1)
        elif "/p/" in url:
            m_pid2 = re.search(r'/p/([a-zA-Z0-9]+)', url)
            if m_pid2:
                product_id = m_pid2.group(1)
        if not product_id:
            product_id = f"fk_{abs(hash(title)) % 1000000}"

        return {
            "platform": "flipkart",
            "product_id": product_id,
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
            "source": "flipkart"
        }
    except Exception as e:
        logger.debug(f"[FlipkartParser] Error parsing card: {e}")
        return None
