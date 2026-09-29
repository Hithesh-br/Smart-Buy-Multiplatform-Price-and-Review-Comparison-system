"""
scrapers/flipkart/parser.py
===========================
Independent DOM & HTML parser for Flipkart search results.
"""

import re
import logging
from typing import Dict, Any, Optional
import bs4

from scrapers.common_schema import clean_product_image_url, get_platform_fallback_image

logger = logging.getLogger("smartbuy.scrapers.flipkart.parser")


def clean_flipkart_image_url(url: Optional[str]) -> Optional[str]:
    """
    Validates, extracts, and standardizes Flipkart image URLs:
    - Strips srcset descriptor resolutions (e.g., ' 1x', ' 2x', ' 312w')
    - Converts protocol-relative (//rukminim...) to https://
    - Converts root-relative (/image/...) to https://rukminim1.flixcart.com/image/...
    - Replaces template strings {@width} and {@height} with standard 312x312 dimensions
    - Rejects Flipkart Assured badges (fa_9e47c1), coin badges, and blank SVG/GIF placeholders
    """
    if not url or not isinstance(url, str):
        return None
    cleaned = clean_product_image_url(url, platform="flipkart")
    return cleaned


def parse_flipkart_card(card: bs4.element.Tag) -> Optional[Dict[str, Any]]:
    """Extract product data from a Flipkart card or container."""
    try:
        # Brand extraction (Flipkart displays brand in separate element for bags/fashion/footwear)
        brand_elem = card.select_one('div.Fo1I0b, div.syl9yP, div._2W96wQ, div.yKfJA4, div._2WkVRV, div.G6XhRU, span._2I90We, div._2B_ZTg')
        brand = brand_elem.get_text(strip=True) if brand_elem else ""

        # Title
        title_elem = card.select_one('a.pIpigb, div.KzDlHZ, a.wjcEIp, a.WKTcLC, div._4rR01T, a.s1Q9rs, div._2W96wQ, a.IRpwTa, div.RG5Slk, div.nZIRY7, a.atJtCj, a[title]')
        if not title_elem:
            return None

        title = title_elem.get('title') or title_elem.get_text(strip=True)
        if not title or len(title) < 4:
            return None

        if brand and not title.lower().startswith(brand.lower()):
            title = f"{brand} {title}"

        # Price
        price_elem = card.select_one('div.Nx9bqj, div._30jeq3, div.hl05eU, div.hZ3P6w, div.QiMO5r div:first-child')
        if not price_elem:
            return None
        price_str = price_elem.get_text(strip=True)
        cleaned_p = re.sub(r'[^\d.]', '', price_str)
        try:
            price_num = int(float(cleaned_p))
        except (ValueError, TypeError):
            return None

        # MRP
        mrp_elem = card.select_one('div.kRYCnD, div._27UcVY, div.yRaY8j, div._3I9_wc, div.y739f8')
        mrp_str = mrp_elem.get_text(strip=True) if mrp_elem else None
        mrp_num = None
        if mrp_str:
            cleaned_m = re.sub(r'[^\d.]', '', mrp_str)
            try:
                mrp_num = int(float(cleaned_m))
            except Exception:
                pass

        # Discount
        disc_elem = card.select_one('div.HQe8jr span, div.HQe8jr, div.UkUFwK span, div._3Ay6Sb span, div.UkUFwK, div._3Ay6Sb')
        discount = 0
        if disc_elem:
            d_match = re.search(r'(\d+)%', disc_elem.get_text())
            if d_match:
                discount = int(d_match.group(1))
        elif mrp_num and mrp_num > price_num:
            discount = round(((mrp_num - price_num) / mrp_num) * 100)

        # Rating
        rating = None
        rate_elem = card.select_one('div.MKiFS6, div.XQDdHH, div._3LWZlK, div.hGSR34, span.CjyrHS')
        if rate_elem:
            r_match = re.search(r'([\d.]+)', rate_elem.get_text())
            if r_match:
                try:
                    rating = float(r_match.group(1))
                except Exception:
                    pass

        # Reviews
        reviews = 0
        rev_elem = card.select_one('span.PvbNMB, span.Wphh3Z, span._2_R_DZ')
        if rev_elem:
            rv_match = re.search(r'([\d,]+)\s*Reviews?', rev_elem.get_text(), re.IGNORECASE)
            if not rv_match:
                rv_match = re.search(r'([\d,]+)', rev_elem.get_text())
            if rv_match:
                try:
                    reviews = int(rv_match.group(1).replace(',', ''))
                except Exception:
                    pass

        # Subtitle (grid cards: weight / pack / volume / size / quantity)
        sub_elem = card.select_one('div.U_GKRr, div.NqBawx, div.fMghAE, div._3Djpdu, div.f5VCIL, div._1W9tFd')
        subtitle = sub_elem.get_text(strip=True) if sub_elem else ""

        # Weight & Pack extraction
        weight_val = None
        pack_qty = 1
        quantity_val = None

        if subtitle:
            quantity_val = subtitle
            # e.g. "5 x 125 g"
            m_mult = re.search(r'(\d+)\s*[xX*]\s*(\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|l|ltr|litres?))\b', subtitle, re.I)
            if m_mult:
                pack_qty = int(m_mult.group(1))
                weight_val = m_mult.group(2)
            else:
                m_single = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|l|ltr|litres?))\b', subtitle, re.I)
                if m_single:
                    weight_val = m_single.group(1)
                m_pk = re.search(r'(?:pack\s*of\s*|pack-)(\d+)', subtitle, re.I)
                if m_pk:
                    pack_qty = int(m_pk.group(1))

        # Check title if not found in subtitle
        t_low = title.lower()
        if not weight_val:
            m_tw = re.search(r'(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|kilograms?|ml|l|litres?)\b', t_low)
            if m_tw:
                weight_val = f"{m_tw.group(1)} {m_tw.group(2)}"
        if pack_qty == 1:
            m_tp = re.search(r'(?:pack\s*of\s*|pack-)(\d+)', t_low)
            if m_tp:
                pack_qty = int(m_tp.group(1))

        # ── Comprehensive Multi-Tier Image Extraction ────────────────────────
        image = ""

        # 1. Check primary Flipkart product image classes
        img_elem = card.select_one(
            'img.UCc1lI, img.DByuf4, img._396cs4, img._2r_T1I, img._530RAn, '
            'img._0DkuPH, img.q6DClP, img.CXW8mj, img.vU5WPw, img._1a80eN, img._3exPp9'
        )
        if img_elem:
            for attr in ('src', 'data-src', 'srcset', 'data-resolved-src'):
                val = img_elem.get(attr)
                cand = clean_flipkart_image_url(val)
                if cand:
                    image = cand
                    break

        # 2. Check picture source[srcset]
        if not image:
            for pic_src in card.select('picture source[srcset], picture img'):
                cand = clean_flipkart_image_url(pic_src.get('srcset') or pic_src.get('src') or pic_src.get('data-src'))
                if cand:
                    image = cand
                    break

        # 3. Search all img tags in card for Flipkart CDN product images
        if not image:
            for img in card.select('img'):
                for attr in ('src', 'data-src', 'srcset', 'data-resolved-src'):
                    cand = clean_flipkart_image_url(img.get(attr))
                    if cand and ('rukminim' in cand or 'flixcart.com/image/' in cand):
                        image = cand
                        break
                if image:
                    break

        # 4. Regex search in card HTML for Flipkart CDN URLs
        if not image:
            card_html = str(card)
            m_cdn = re.search(r'https?://(?:rukminim\d*|rukminim)\.flixcart\.com/image/[^"\'\s<>&]+', card_html)
            if m_cdn:
                cand = clean_flipkart_image_url(m_cdn.group(0))
                if cand:
                    image = cand

        # 5. Check data-resolved-src (Playwright DOM execution)
        if not image:
            resolved_img = card.select_one('img[data-resolved-src]')
            if resolved_img:
                candidate = clean_flipkart_image_url(resolved_img.get('data-resolved-src'))
                if candidate:
                    image = candidate

        # 6. Fallback to Flipkart-branded clean SVG if no product image could be extracted
        if not image:
            image = get_platform_fallback_image("flipkart")

        # Product Link
        link_elem = card.select_one('a.GnxRXv, a.pIpigb, a.CGtC5Q, a._1fQZEK, a.s1Q9rs, a.VJA3rP, a.k7wcnx, a[href*="/p/"]')
        href = link_elem.get('href') if link_elem else ""
        if href.startswith('/'):
            url = f"https://www.flipkart.com{href.split('?')[0]}"
        elif href.startswith('http'):
            url = href.split('?')[0]
        else:
            url = "https://www.flipkart.com"

        # Product ID
        product_id = card.get('data-id') or ""
        if not product_id:
            m_pid = re.search(r'pid=([A-Z0-9]+)', href)
            if m_pid:
                product_id = m_pid.group(1)
            elif "/p/" in url:
                m_pid2 = re.search(r'/p/([a-zA-Z0-9]+)', url)
                if m_pid2:
                    product_id = m_pid2.group(1)
            else:
                product_id = f"fk_{abs(hash(url)) % 1000000}"

        # ── Specifications & Raw Specifications Extraction ────────────────────
        specs_extracted: Dict[str, str] = {}
        raw_specs: Dict[str, str] = {}

        if subtitle:
            specs_extracted['Net Quantity'] = subtitle
            raw_specs['subtitle'] = subtitle
        if weight_val:
            specs_extracted['Weight'] = weight_val
        if pack_qty > 1:
            specs_extracted['Pack Quantity'] = f"Pack of {pack_qty}"

        warr_val = None
        material_val = None
        capacity_val = None
        color_val = None

        # Check title for key attributes
        mat_m = re.search(r'\b(aluminium|aluminum|stainless\s*steel|steel|cotton|polyester|linen|leather|plastic|copper|cast\s*iron)\b', t_low)
        if mat_m:
            material_val = mat_m.group(1).title()
            specs_extracted['Material'] = material_val

        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)\b', t_low)
        if cap_m:
            capacity_val = f"{cap_m.group(1)} Litres"
            specs_extracted['Capacity'] = capacity_val

        col_m = re.search(r'\b(black|white|silver|red|blue|grey|gray|green|yellow|pink|gold|navy|maroon|beige)\b', t_low)
        if col_m:
            color_val = col_m.group(1).capitalize()
            specs_extracted['Color'] = color_val

        # Bullet specifications (e.g. laptops, electronics, appliances)
        spec_items = card.select('ul.HwRTzP li, li.DTBslk, ul._1xgFaf li, li.rgWa7D, ul.G4BRas li, div._21AqiJ')
        for s_idx, sp in enumerate(spec_items):
            s_text = sp.get_text(strip=True)
            if not s_text:
                continue
            raw_specs[f'bullet_{s_idx+1}'] = s_text
            s_low = s_text.lower()

            if 'ram' in s_low or 'rom' in s_low or 'storage' in s_low or 'ssd' in s_low or 'hdd' in s_low:
                if 'ssd' in s_low or 'hdd' in s_low or 'storage' in s_low:
                    specs_extracted['Storage'] = s_text
                if 'ram' in s_low:
                    specs_extracted['RAM'] = s_text
                if 'RAM / Storage' not in specs_extracted:
                    specs_extracted['RAM / Storage'] = s_text
            elif 'processor' in s_low:
                specs_extracted['Processor'] = s_text
            elif 'operating system' in s_low or 'windows' in s_low or 'android' in s_low or 'ios' in s_low:
                specs_extracted['Operating System'] = s_text
            elif 'display' in s_low or 'inch' in s_low or 'cm' in s_low:
                specs_extracted['Display'] = s_text
            elif 'camera' in s_low or 'mp' in s_low:
                specs_extracted['Camera'] = s_text
            elif 'battery' in s_low or 'mah' in s_low:
                specs_extracted['Battery'] = s_text
            elif 'warranty' in s_low or 'guarantee' in s_low:
                clean_warr = re.sub(r'^(?:warranty\s*[:\-]\s*)', '', s_text, flags=re.IGNORECASE).strip()
                warr_val = clean_warr
                specs_extracted['Warranty'] = clean_warr
            elif 'capacity' in s_low or 'litre' in s_low or 'liter' in s_low:
                clean_cap = re.sub(r'^(?:capacity\s*[:\-]\s*)', '', s_text, flags=re.IGNORECASE).strip()
                capacity_val = clean_cap
                specs_extracted['Capacity'] = clean_cap
            elif 'material' in s_low or 'aluminium' in s_low or 'steel' in s_low:
                clean_mat = re.sub(r'^(?:material\s*[:\-]\s*)', '', s_text, flags=re.IGNORECASE).strip()
                material_val = clean_mat
                specs_extracted['Material'] = clean_mat
            else:
                specs_extracted[f'Feature {s_idx+1}'] = s_text

        # Detect Skin Type for soaps/skincare if present in text
        if 'all skin' in t_low or 'all skin' in str(raw_specs).lower():
            specs_extracted['Skin Type'] = 'All Skin Types'
        elif 'dry skin' in t_low:
            specs_extracted['Skin Type'] = 'Dry Skin'
        elif 'oily skin' in t_low:
            specs_extracted['Skin Type'] = 'Oily Skin'

        return {
            "platform": "flipkart",
            "product_id": product_id,
            "title": title,
            "product_name": title,
            "brand": brand or None,
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
            "availability": "In Stock",
            "in_stock": True,
            "weight": weight_val,
            "pack_quantity": pack_qty,
            "quantity": quantity_val or weight_val,
            "subtitle": subtitle,
            "material": material_val,
            "capacity": capacity_val,
            "color": color_val,
            "warranty": warr_val,
            "specifications": specs_extracted,
            "raw_specifications": raw_specs if raw_specs else dict(specs_extracted),
            "data_source": "Flipkart",
            "source": "flipkart"
        }
    except Exception as e:
        logger.debug(f"[FlipkartParser] Error parsing card: {e}")
        return None

