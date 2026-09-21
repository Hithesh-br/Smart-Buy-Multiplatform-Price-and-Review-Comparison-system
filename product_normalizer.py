"""
product_normalizer.py
=====================
SmartBuy Canonical Product Normalizer.

Transforms raw product data from Amazon, Flipkart, and Meesho into a
unified, authoritative schema with normalized numbers, currency, ratings,
weights, pack quantities, variants, and specifications.
"""

import re
import datetime
from typing import Dict, Any, Optional

from search.category_detector import detect_category
from search.normalizer import (
    normalize_brand,
    normalize_model,
    normalize_title,
    normalize_weight,
    normalize_pack_quantity,
    normalize_price,
    normalize_rating,
    normalize_review_count,
    strip_marketing_words,
)


KNOWN_BRANDS = [
    'Apple', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola', 'Google', 'iQOO',
    'HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Sony', 'LG',
    'boAt', 'Noise', 'Boult', 'Fire-Boltt', 'Fastrack', 'Titan', 'JBL',
    'Pilgrim', 'Ghar', 'Ghar Soaps', 'Mamaearth', 'Dot & Key', 'The Derma Co', 'Cetaphil', 'Neutrogena', 'Himalaya', 'Nivea', 'Dove',
    'True Elements', 'Nutty Gritties', 'Neuherbs', 'Sorich Organics', 'Saffola', 'Tata', 'Fortune', 'Aashirvaad',
    'Nike', 'Adidas', 'Puma', 'Reebok', 'Campus', 'Bata', 'Sparx', 'Skybags', 'American Tourister', 'Safari', 'Wildcraft'
]


def extract_variant_attributes(title: str, specs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract storage, RAM, color, size, capacity from title and specifications."""
    specs = specs or {}
    t_lower = (title or "").lower()
    variant: Dict[str, Any] = {}

    # Storage
    st_match = re.search(r'\b(16|32|64|128|256|512)\s*gb\b', t_lower)
    if st_match:
        variant['storage'] = f"{st_match.group(1)}GB"
    elif re.search(r'\b(1|2)\s*tb\b', t_lower):
        variant['storage'] = f"{re.search(r'\b(1|2)\s*tb\b', t_lower).group(1)}TB"

    # RAM
    ram_match = re.search(r'\b(2|3|4|6|8|12|16|32)\s*gb\s*(?:ram|ddr\d)?\b', t_lower)
    if ram_match:
        ram_val = f"{ram_match.group(1)}GB"
        if 'storage' not in variant or variant['storage'] != ram_val:
            variant['ram'] = ram_val

    # Wattage / Power (critical for chargers)
    power_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:w|watt|watts)\b', t_lower)
    if power_match:
        variant['power'] = f"{power_match.group(1)}W"

    # Color
    color = specs.get('Color') or specs.get('Colour')
    if not color:
        colors_list = ['black', 'white', 'blue', 'red', 'green', 'silver', 'gold', 'grey', 'gray', 'pink', 'purple', 'yellow', 'orange', 'brown', 'navy']
        for c in colors_list:
            if re.search(r'\b' + re.escape(c) + r'\b', t_lower):
                color = c.capitalize()
                break
    if color:
        variant['color'] = str(color).capitalize()

    # Size (clothing/shoes)
    size = specs.get('Size') or specs.get('Shoe Size')
    if not size:
        sz_match = re.search(r'\bsize\s*[:\-]?\s*([a-z0-9]+)\b', t_lower)
        if sz_match:
            size = sz_match.group(1).upper()
        elif re.search(r'\b(uk|us|ind|eu)\s*(\d{1,2})\b', t_lower):
            m = re.search(r'\b(uk|us|ind|eu)\s*(\d{1,2})\b', t_lower)
            size = f"{m.group(1).upper()} {m.group(2)}"
        elif re.search(r'\b(xs|s|m|l|xl|xxl|3xl)\b', t_lower):
            size = re.search(r'\b(xs|s|m|l|xl|xxl|3xl)\b', t_lower).group(1).upper()
    if size:
        variant['size'] = str(size).upper()

    # Weight / Volume
    wt = specs.get('Weight') or specs.get('Net Weight') or specs.get('Item Weight') or normalize_weight(title)
    if wt:
        variant['weight'] = normalize_weight(str(wt))

    # Pack quantity
    pq = specs.get('Pack Quantity') or specs.get('Pack of') or normalize_pack_quantity(title)
    if pq:
        try:
            variant['pack_quantity'] = int(pq)
        except Exception:
            variant['pack_quantity'] = 1

    return variant


def extract_model_number(title: str, brand: Optional[str] = None, specs: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Extract model code or name from title or specifications."""
    specs = specs or {}
    for key in ('Model Name', 'Model Number', 'Model', 'Item Model Number'):
        if key in specs and specs[key] and str(specs[key]).strip() not in ('', 'N/A', 'None'):
            return str(specs[key]).strip()

    t_lower = (title or "").lower()

    # Phone models
    m_match = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|galaxy\s*[a-z]\d{1,2}(?:\s*5g|\s*4g)?|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|pixel\s*\d[a-z]?|t\d(?:\s*5g|\s*pro|\s*lite)?|nord(?:\s*ce)?\s*\d[a-z]?)\b', t_lower)
    if m_match:
        return m_match.group(1).title()

    # Laptop models
    l_match = re.search(r'\b(macbook\s*(?:air|pro)|thinkpad|ideapad|vivobook|zenbook|tuf|rog|victus|pavilion|omen|aspire|galaxy\s*book)\b', t_lower)
    if l_match:
        return l_match.group(1).title()

    # Charger / Power models (e.g. 44W, 67W, 120W, SuperVOOC, FlashCharge)
    c_match = re.search(r'\b(\d+w(?:\s*flashcharge|\s*supervooc|\s*fast\s*charger)?)\b', t_lower)
    if c_match:
        return c_match.group(1).upper()

    return None


def normalize_canonical_product(raw: Dict[str, Any], platform: str, source_url: str = "") -> Optional[Dict[str, Any]]:
    """
    Produce the common normalized SmartBuy product schema.
    Returns None only if essential product identifiers (title, price, url) are missing.
    """
    if not isinstance(raw, dict):
        return None

    title = str(raw.get('title') or raw.get('product_name') or raw.get('name') or '').strip()
    if not title:
        return None

    # Price Normalization
    price_num = normalize_price(raw.get('price_num') or raw.get('price'))
    mrp_num = normalize_price(raw.get('mrp_num') or raw.get('mrp') or raw.get('original_price'))

    if price_num is None or price_num <= 0:
        # If raw price was missing or zero, check if mrp exists
        if mrp_num and mrp_num > 0:
            price_num = mrp_num
        else:
            price_num = 0

    if not mrp_num or mrp_num < price_num:
        mrp_num = price_num

    price_str = f"₹{price_num:,}" if price_num > 0 else "Price Unavailable"
    mrp_str = f"₹{mrp_num:,}" if mrp_num > 0 else price_str

    # Discount Normalization
    discount = raw.get('discount') or raw.get('discount_percent')
    if not discount and mrp_num > price_num and mrp_num > 0:
        pct = round(((mrp_num - price_num) / mrp_num) * 100)
        discount = f"{pct}% off"
    elif isinstance(discount, (int, float)):
        discount = f"{int(discount)}% off"
    elif not discount:
        discount = "0% off"

    # Rating & Reviews
    rating = normalize_rating(raw.get('rating'))
    review_count = normalize_review_count(raw.get('review_count') or raw.get('reviews') or raw.get('total_reviews'))

    # Availability
    in_stock = raw.get('in_stock', True) if 'in_stock' in raw else (price_num > 0)
    avail_raw = raw.get('availability') or ''
    if 'out of stock' in avail_raw.lower() or 'currently unavailable' in avail_raw.lower():
        in_stock = False
    availability = "In Stock" if in_stock else "Out of Stock"

    # Images
    image_url = raw.get('image_url') or raw.get('image') or ''
    if "unsplash.com" in image_url or "placeholder" in image_url:
        image_url = ""

    # URLs
    product_url = raw.get('product_url') or raw.get('url') or raw.get('link') or source_url or ''

    # Specifications
    specs = raw.get('specifications') or {}
    if not specs and isinstance(raw.get('specs'), dict):
        specs = raw.get('specs', {}).get('category_specs', {})

    # Brand
    brand = normalize_brand(raw.get('brand'))
    if not brand:
        t_low = title.lower()
        for kb in KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(kb.lower()) + r'\b', t_low):
                brand = kb
                break
    if not brand:
        first_token = title.split()[0] if title.split() else "Generic"
        if first_token[0].isupper() and len(first_token) > 1:
            brand = first_token
        else:
            brand = "Generic"

    # Category / Product Type
    category = raw.get('category') or raw.get('product_type') or detect_category(title=title)

    # Variant attributes
    variant = extract_variant_attributes(title, specs)
    if 'variant' in raw and isinstance(raw['variant'], dict):
        variant.update(raw['variant'])

    # Model
    model = raw.get('model') or extract_model_number(title, brand, specs) or "Standard"

    # Weight and pack quantity shortcuts
    weight = variant.get('weight') or normalize_weight(specs.get('Weight') or specs.get('Net Quantity') or title)
    pack_qty = str(variant.get('pack_quantity') or normalize_pack_quantity(specs.get('Pack Quantity') or title) or "1")
    color = variant.get('color') or specs.get('Color') or None
    size = variant.get('size') or specs.get('Size') or None

    # Key Features
    key_features = raw.get('key_features') or raw.get('features') or []
    if not key_features and specs:
        # Select first 3 meaningful specifications as key features
        key_features = [f"{k}: {v}" for k, v in list(specs.items())[:3] if v and str(v).strip() not in ('', 'N/A')]

    plat_clean = platform.lower()
    plat_name = plat_clean.capitalize()

    return {
        "platform": plat_clean,
        "platform_name": plat_name,
        "product_id": raw.get('product_id') or raw.get('asin') or "",
        "asin": raw.get('asin') or "",
        "product_name": title,
        "title": title,
        "brand": brand,
        "model": model,
        "product_type": category,
        "category": category,
        "price": price_str,
        "price_num": price_num,
        "mrp": mrp_str,
        "mrp_num": mrp_num,
        "discount": discount,
        "discount_percent": discount,
        "rating": rating,
        "review_count": review_count,
        "reviews": f"{review_count:,}" if review_count > 0 else "0",
        "availability": availability,
        "in_stock": in_stock,
        "image_url": image_url,
        "image": image_url,
        "product_url": product_url,
        "url": product_url,
        "link": product_url,
        "color": color,
        "size": size,
        "weight": weight,
        "pack_quantity": pack_qty,
        "variant": variant,
        "key_features": key_features,
        "specifications": specs,
        "seller": raw.get('seller') or None,
        "source": raw.get('source', 'live'),
        "scrape_status": raw.get('scrape_status', 'success'),
        "scraped_at": raw.get('scraped_at') or datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
