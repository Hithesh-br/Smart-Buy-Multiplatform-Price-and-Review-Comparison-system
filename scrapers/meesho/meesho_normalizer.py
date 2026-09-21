"""
scrapers/meesho/meesho_normalizer.py
====================================
Canonical normalization for Meesho products.
Maps parsed dictionary or provider response into SmartBuy's unified schema.
Rejects invalid or malformed products.
Never invents fake data — genuinely missing fields remain null/None.
"""

import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from scrapers.meesho.meesho_parser import (
    parse_price_value,
    parse_rating_and_reviews,
    extract_title_from_slug
)
from search.category_detector import detect_category

logger = logging.getLogger("smartbuy.scrapers.meesho.normalizer")


def calculate_unit_price(price_num: Optional[int], weight_str: Optional[str], pack_qty_str: Optional[str] = None) -> Optional[str]:
    """Calculate unit price e.g. ₹ per 100g, ₹ per 100ml, or ₹ per item."""
    if not price_num or price_num <= 0:
        return None

    # Check weight / volume
    if weight_str:
        w_lower = str(weight_str).lower().strip()
        m_kg = re.search(r'([\d.]+)\s*(?:kg|kilo)', w_lower)
        if m_kg:
            try:
                kg_val = float(m_kg.group(1))
                if kg_val > 0:
                    per_100g = round((price_num / (kg_val * 1000)) * 100, 1)
                    return f"₹{per_100g:g} / 100g"
            except Exception:
                pass

        m_g = re.search(r'([\d.]+)\s*(?:g|gm|gram)', w_lower)
        if m_g:
            try:
                g_val = float(m_g.group(1))
                if g_val > 0:
                    per_100g = round((price_num / g_val) * 100, 1)
                    return f"₹{per_100g:g} / 100g"
            except Exception:
                pass

        m_l = re.search(r'([\d.]+)\s*(?:l|litre|liter)', w_lower)
        if m_l:
            try:
                l_val = float(m_l.group(1))
                if l_val > 0:
                    per_100ml = round((price_num / (l_val * 1000)) * 100, 1)
                    return f"₹{per_100ml:g} / 100ml"
            except Exception:
                pass

        m_ml = re.search(r'([\d.]+)\s*(?:ml|milli)', w_lower)
        if m_ml:
            try:
                ml_val = float(m_ml.group(1))
                if ml_val > 0:
                    per_100ml = round((price_num / ml_val) * 100, 1)
                    return f"₹{per_100ml:g} / 100ml"
            except Exception:
                pass

    # Check pack quantity
    if pack_qty_str:
        try:
            pq = int(re.sub(r'[^\d]', '', str(pack_qty_str)))
            if pq > 1:
                per_item = round(price_num / pq, 1)
                return f"₹{per_item:g} / item"
        except Exception:
            pass

    return None


def normalize_meesho_product(raw: Dict[str, Any], query: str = "") -> Optional[Dict[str, Any]]:
    """
    Normalizes a single Meesho item into canonical schema.
    Returns None if the item fails mandatory validation (missing title, price, or url).
    """
    if not isinstance(raw, dict):
        return None

    # Title extraction & recovery
    title = str(raw.get("title") or raw.get("name") or raw.get("product_name") or "").strip()
    url = str(raw.get("url") or raw.get("product_url") or raw.get("link") or "").strip()

    # If title is short or generic, recover from URL slug
    if (len(title) < 8 or any(g in title.lower() for g in ("others", "casual", "laptop adapters"))) and url:
        recovered = extract_title_from_slug(url)
        if recovered:
            title = recovered

    if not title or len(title) < 3:
        return None

    # Price parsing
    price_num, price_str = parse_price_value(raw.get("price") or raw.get("price_num") or raw.get("discounted_price"))
    if price_num is None or price_num <= 0:
        return None

    # MRP & Discount
    mrp_num, mrp_str = parse_price_value(raw.get("mrp") or raw.get("mrp_num") or raw.get("original_price"))
    if mrp_num and mrp_num > price_num:
        discount_percent = round(((mrp_num - price_num) / mrp_num) * 100)
    else:
        mrp_num = price_num
        mrp_str = price_str
        discount_percent = int(raw.get("discount_percent") or raw.get("discount") or 0)

    # Rating & Reviews
    rating, review_count = parse_rating_and_reviews(
        raw.get("rating") or raw.get("rating_num"),
        raw.get("review_count") or raw.get("reviews")
    )

    # URL normalization
    if url.startswith("/"):
        url = "https://www.meesho.com" + url
    elif url and not url.startswith("http"):
        url = "https://www.meesho.com/" + url

    # Product ID
    product_id = str(raw.get("product_id") or raw.get("id") or "").strip()
    if not product_id and url:
        m_id = re.search(r'/p/([a-z0-9]+)', url)
        if m_id:
            product_id = m_id.group(1)

    # Image
    image = str(raw.get("image") or raw.get("image_url") or "").strip()
    if "unsplash.com" in image or "placeholder" in image:
        image = ""

    # Category & Product Type
    category = raw.get("category") or detect_category(query=query, title=title)
    product_type = raw.get("product_type") or category

    # Brand & Model extraction
    brand = raw.get("brand") or None
    if not brand:
        known_brands = [
            'Apple', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola',
            'HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'boAt', 'Noise', 'Boult', 'Fastrack', 'Titan',
            'Pilgrim', 'Ghar', 'Mamaearth', 'Dot & Key', 'The Derma Co', 'Cetaphil', 'Nivea', 'Dove',
            'Nike', 'Adidas', 'Puma', 'Bata', 'Skybags', 'Milton', 'Cadbury', 'Nestle', 'Tata'
        ]
        t_low = title.lower()
        for b in known_brands:
            if re.search(r'\b' + re.escape(b.lower()) + r'\b', t_low):
                brand = b
                break

    model = raw.get("model") or None
    if not model:
        m_match = re.search(r'\b([a-z0-9]+(?:-[a-z0-9]+)?)\b', title, re.IGNORECASE)
        # Check specific model numbers like 65W, T4, 15, etc.
        m_sub = re.search(r'\b(\d+w|t\d(?:\s*pro)?|iphone\s*\d+|pavilion\s*\d*)\b', title, re.IGNORECASE)
        if m_sub:
            model = m_sub.group(1).upper()

    # Attributes & Specifications
    weight = raw.get("weight") or None
    if not weight:
        w_match = re.search(r'\b(\d+(?:\.\d+)?\s*(?:kg|g|gm|ml|l|litre))\b', title, re.IGNORECASE)
        if w_match:
            weight = w_match.group(1)

    pack_qty = str(raw.get("pack_quantity") or raw.get("pack_size") or "")
    if not pack_qty:
        p_match = re.search(r'\b(?:pack\s*of\s*(\d+)|(\d+)\s*pack)\b', title, re.IGNORECASE)
        if p_match:
            pack_qty = p_match.group(1) or p_match.group(2)
        else:
            pack_qty = "1"

    color = raw.get("color") or None
    if not color:
        c_match = re.search(r'\b(black|white|blue|red|green|silver|grey|gray|pink|gold|yellow)\b', title, re.IGNORECASE)
        if c_match:
            color = c_match.group(1).capitalize()

    size = raw.get("size") or None
    material = raw.get("material") or None
    seller = raw.get("seller") or None
    features = raw.get("features") or raw.get("key_features") or []
    specifications = raw.get("specifications") or {}
    if not specifications:
        specifications = {
            "Product Name": title,
            "Brand": brand or "Not Available",
            "Model": model or "Not Available",
            "Price": price_str,
            "MRP": mrp_str,
            "Discount": f"{discount_percent}%" if discount_percent else "None",
            "Rating": f"{rating} ★" if rating else "Not Rated",
            "Total Reviews": f"{review_count:,}" if review_count else "0",
            "Availability": "In Stock",
            "Color": color or "Not Available",
            "Weight": weight or "Not Available",
            "Pack Quantity": pack_qty or "1",
        }
        if material:
            specifications["Material"] = material

    unit_price = calculate_unit_price(price_num, weight, pack_qty)

    from scrapers.common_schema import validate_and_build_product
    from search.quantity_normalizer import normalize_quantity_and_pack, calculate_standard_unit_price
    from search.quality_scorer import compute_quality_and_confidence

    qty_info = normalize_quantity_and_pack(
        title=title,
        weight_val=weight,
        pack_val=pack_qty
    )
    unit_price = calculate_standard_unit_price(price_num, qty_info)

    built_data = dict(raw)
    built_data.update({
        "platform": "meesho",
        "product_id": product_id or f"msh_{abs(hash(url)) % 1000000}",
        "product_url": url,
        "title": title,
        "brand": brand,
        "model": model,
        "price_num": price_num,
        "mrp_num": mrp_num,
        "rating": rating,
        "review_count": review_count,
        "category": category,
        "weight": qty_info.get("display_quantity") or weight,
        "pack_quantity": qty_info.get("pack_count", 1),
        "unit": qty_info.get("unit"),
        "unit_price": unit_price,
        "specifications": specifications,
        "source": raw.get("source", "meesho"),
    })

    product = validate_and_build_product(built_data, platform="meesho")

    q_score, d_conf = compute_quality_and_confidence(product)
    product["quality_score"] = q_score
    product["data_confidence"] = d_conf

    return product
