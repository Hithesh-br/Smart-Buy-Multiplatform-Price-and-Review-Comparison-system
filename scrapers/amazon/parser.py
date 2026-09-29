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

        # Extract Title:
        h2 = card.select_one('h2')
        brand_name = h2.get_text(strip=True) if h2 else ""

        title_candidates = []
        for a in card.select('a.a-link-normal[href*="/dp/"], a.a-link-normal[href*="/sspa/click"], a[href*="/dp/"]'):
            href = a.get('href', '')
            if '#customerReviews' in href or '/deals' in href:
                continue
            txt = a.get_text(' ', strip=True)
            if txt and len(txt) > 4 and not any(skip in txt.lower() for skip in ['stars', 'ratings', 'reviews', 'limited time', '₹', 'free delivery', 'sponsored']):
                title_candidates.append(txt)

        h2_title = ""
        if h2:
            a_in_h2 = h2.select_one('a')
            if a_in_h2:
                h2_title = a_in_h2.get_text(' ', strip=True)

        final_title = ""
        if h2_title and len(h2_title) > 5 and len(h2_title.split()) > 1:
            final_title = h2_title
        elif title_candidates:
            best_cand = max(title_candidates, key=len)
            if brand_name and brand_name.lower() not in best_cand.lower() and len(brand_name) < 25 and not any(phrase in brand_name.lower() for phrase in ('visit the store', 'explore the store', 'shop the store', 'brand store', 'sponsored')):
                final_title = f"{brand_name} {best_cand}".strip()
            else:
                final_title = best_cand
        elif brand_name:
            final_title = brand_name
        else:
            title_elem = card.select_one('h2 a span, h2 span, a.a-link-normal span.a-text-normal, span.a-size-medium, span.a-size-base-plus')
            final_title = title_elem.get_text(strip=True) if title_elem else ""

        title = final_title.strip()
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
        rating_selectors = [
            'i.a-icon-star-small span.a-icon-alt',
            'i.a-icon-star span.a-icon-alt',
            'span.a-icon-alt',
            'i[class*="a-icon-star"]',
            'i[class*="a-star-"]',
            '[aria-label*="out of 5 stars"]',
            '[aria-label*="stars"]',
            'a[title*="out of 5 stars"]',
            'span[title*="out of 5 stars"]',
        ]
        for sel in rating_selectors:
            for elem in card.select(sel):
                t = elem.get_text(strip=True)
                m = re.search(r'([1-5](?:\.\d+)?)\s*(?:out\s*of\s*5|\bstar|\bstars)?', t, re.IGNORECASE) if t else None
                if m:
                    val = float(m.group(1))
                    if 1.0 <= val <= 5.0:
                        rating = val
                        break
                aria = elem.get('aria-label', '')
                if aria:
                    m_a = re.search(r'([1-5](?:\.\d+)?)\s*out\s*of\s*5', aria, re.IGNORECASE)
                    if not m_a:
                        m_a = re.search(r'([1-5](?:\.\d+)?)', aria)
                    if m_a:
                        val = float(m_a.group(1))
                        if 1.0 <= val <= 5.0:
                            rating = val
                            break
                classes = ' '.join(elem.get('class', []))
                m_cls = re.search(r'a-star(?:-mini)?-(\d)(?:-(\d))?', classes)
                if m_cls:
                    main_d = m_cls.group(1)
                    sub_d = m_cls.group(2) or '0'
                    val = float(f"{main_d}.{sub_d}")
                    if 1.0 <= val <= 5.0:
                        rating = val
                        break
            if rating is not None:
                break

        # Review count
        reviews = 0
        for el in card.select('[aria-label*="review"], [aria-label*="ratings"]'):
            aria = el.get('aria-label', '')
            m_rev = re.search(r'by\s*([\d,]+)\s*(?:reviews|ratings)', aria, re.IGNORECASE)
            if m_rev:
                reviews = int(m_rev.group(1).replace(',', ''))
                break
        if not reviews:
            for sel in ['span.s-underline-text', 'a[href*="#customerReviews"]', 'span.a-size-base.s-underline-text', 'div._c2Itd_themeCollectionRating_2JUkb']:
                for el in card.select(sel):
                    t = el.get_text(strip=True)
                    m_k = re.search(r'([\d.]+)\s*k', t, re.IGNORECASE)
                    if m_k:
                        reviews = int(float(m_k.group(1)) * 1000)
                        break
                    m_num = re.search(r'([\d,]+)', t)
                    if m_num:
                        val = int(m_num.group(1).replace(',', ''))
                        if val > 0:
                            reviews = val
                            break
                if reviews:
                    break

        # Image Extraction with validation and cleanup
        image = ""
        img_elem = card.select_one('img.s-image, img[data-image-latency="s-product-image"]')
        if img_elem:
            cand = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('srcset')
            from scrapers.common_schema import clean_product_image_url, get_platform_fallback_image
            image = clean_product_image_url(cand, platform="amazon") or ""
        if not image:
            from scrapers.common_schema import get_platform_fallback_image
            image = get_platform_fallback_image("amazon")

        # Product URL - always prefer canonical /dp/{asin} to avoid broken /sspa/click redirection
        if asin:
            url = f"https://www.amazon.in/dp/{asin}"
        else:
            link_elem = card.select_one('h2 a.a-link-normal, a.a-link-normal.s-no-outline')
            href = link_elem.get('href') if link_elem else ""
            if href.startswith('/'):
                url = f"https://www.amazon.in{href.split('?')[0]}"
            elif href.startswith('http'):
                url = href.split('?')[0]
            else:
                url = ""

        # Seller / Prime / Delivery signals
        prime_elem = card.select_one('i.a-icon-prime, span.a-badge-text')
        seller_label = "Amazon Fulfilled (Prime)" if prime_elem else "Verified Amazon Merchant"
        del_elem = card.select_one('span.a-text-bold, span[aria-label*="delivery"], div.udm-delivery span')
        delivery_info = del_elem.get_text(strip=True) if del_elem else "Standard Delivery"

        # Specifications & Attribute Heuristics from Amazon card text
        specs_extracted: Dict[str, str] = {}
        raw_specs: Dict[str, str] = {}

        t_lower = title.lower()
        material_val = None
        capacity_val = None
        color_val = None

        mat_m = re.search(r'\b(aluminium|aluminum|stainless\s*steel|steel|cotton|polyester|linen|leather|plastic|copper|cast\s*iron)\b', t_lower)
        if mat_m:
            material_val = mat_m.group(1).title()
            specs_extracted['Material'] = material_val

        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)\b', t_lower)
        if cap_m:
            capacity_val = f"{cap_m.group(1)} Litres"
            specs_extracted['Capacity'] = capacity_val

        col_m = re.search(r'\b(black|white|silver|red|blue|grey|gray|green|yellow|pink|gold|navy|maroon|beige)\b', t_lower)
        if col_m:
            color_val = col_m.group(1).capitalize()
            specs_extracted['Color'] = color_val

        # Badge or feature bullet lines
        for b_idx, bullet in enumerate(card.select('div.a-section.a-spacing-none.a-spacing-top-micro span.a-size-base')):
            b_text = bullet.get_text(strip=True)
            if b_text and len(b_text) > 2:
                raw_specs[f'feature_{b_idx+1}'] = b_text

        return {
            "platform": "amazon",
            "asin": asin,
            "product_id": asin,
            "title": title,
            "product_name": title,
            "price": f"₹{price_num:,}",
            "price_num": price_num,
            "mrp": f"₹{mrp_num:,}" if mrp_num else f"₹{price_num:,}",
            "mrp_num": mrp_num or price_num,
            "original_price": f"₹{mrp_num:,}" if mrp_num else f"₹{price_num:,}",
            "discount": f"{discount}% off" if discount > 0 else None,
            "discount_percent": discount,
            "rating": rating,
            "review_count": reviews,
            "reviews": f"{reviews:,}" if reviews > 0 else "0",
            "image": image,
            "image_url": image,
            "url": url,
            "product_url": url,
            "link": url,
            "seller": seller_label,
            "delivery": delivery_info,
            "availability": "In Stock",
            "in_stock": True,
            "material": material_val,
            "capacity": capacity_val,
            "color": color_val,
            "specifications": specs_extracted,
            "raw_specifications": raw_specs if raw_specs else dict(specs_extracted),
            "data_source": "Amazon",
            "source": "amazon"
        }
    except Exception as e:
        logger.debug(f"[AmazonParser] Error parsing card: {e}")
        return None
