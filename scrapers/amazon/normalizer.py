"""
scrapers/amazon/normalizer.py
=============================
Canonical product normalizer for Amazon.in items.
"""

import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from search.category_detector import detect_category
from scrapers.common_schema import validate_and_build_product
from search.quantity_normalizer import normalize_quantity_and_pack, calculate_standard_unit_price
from search.quality_scorer import compute_quality_and_confidence

logger = logging.getLogger("smartbuy.scrapers.amazon.normalizer")


def normalize_amazon_product(raw: Dict[str, Any], query: str = "") -> Optional[Dict[str, Any]]:
    """Normalize raw Amazon product dictionary into SmartBuy authoritative schema."""
    if not isinstance(raw, dict):
        return None

    title = str(raw.get('title') or '').strip()
    price_num = raw.get('price_num')
    url = str(raw.get('url') or raw.get('product_url') or '').strip()

    if not title or price_num is None or price_num <= 0 or not url:
        return None

    category = raw.get('category') or detect_category(query=query, title=title)
    asin = raw.get('asin') or raw.get('product_id') or ""

    # Brand extraction (no fake 'Generic')
    brand = raw.get('brand')
    if not brand or str(brand).strip().lower() in ('generic', 'unknown', 'none', 'n/a'):
        brand = None
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

    # Quantity and pack normalization
    qty_info = normalize_quantity_and_pack(
        title=title,
        weight_val=raw.get('weight'),
        pack_val=raw.get('pack_quantity')
    )
    unit_price = calculate_standard_unit_price(price_num, qty_info)

    # Build schema
    built_data = dict(raw)
    built_data.update({
        "platform": "amazon",
        "product_id": asin,
        "product_url": url,
        "title": title,
        "brand": brand,
        "category": category,
        "price_num": price_num,
        "weight": qty_info.get("display_quantity") or raw.get("weight"),
        "pack_quantity": qty_info.get("pack_count", 1),
        "unit": qty_info.get("unit"),
        "unit_price": unit_price,
        "source": raw.get("source") or "amazon",
    })

    product = validate_and_build_product(built_data, platform="amazon")

    # Compute quality and confidence
    q_score, d_conf = compute_quality_and_confidence(product)
    product["quality_score"] = q_score
    product["data_confidence"] = d_conf

    return product
