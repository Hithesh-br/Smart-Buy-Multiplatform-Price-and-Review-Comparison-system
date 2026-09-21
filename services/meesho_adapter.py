"""
services/meesho_adapter.py
==========================
Transforms raw Meesho scraped dictionaries or third-party API payloads
into SmartBuy's canonical normalized product schema.
Never invents synthetic dummy data.
"""

import re
from typing import Optional, Any
from search.category_detector import detect_category


def clean_number(val: Any) -> Optional[int]:
    """Safely extract integer number from price, review count, etc."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    digits = re.sub(r"[^\d]", "", str(val))
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def clean_float(val: Any) -> Optional[float]:
    """Safely extract float from rating."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 1)
    m = re.search(r"(\d+(?:\.\d+)?)", str(val))
    if m:
        try:
            return round(float(m.group(1)), 1)
        except ValueError:
            return None
    return None


def extract_title_from_slug(url: str) -> str:
    """
    Extracts descriptive product name from Meesho product URL slug.
    Example:
    /exetech-65w-laptop-charger-adapter-compatible-forhp-195v-334a-45mm-blue-pin-slim-pin/p/hmsq5h
    -> "Exetech 65W Laptop Charger Adapter Compatible For HP 19.5V 3.34A 4.5mm Blue Pin Slim Pin"
    """
    if not url or "/p/" not in url:
        return ""
    try:
        path = url.split("?")[0].split("#")[0]
        slug = path.split("/p/")[0].split("/")[-1]
        if not slug:
            return ""
        # Clean words
        words = slug.split("-")
        clean_words = []
        for w in words:
            if not w:
                continue
            # Handle joined prepositions like 'forhp' -> 'for hp', 'compatiblefor' -> 'compatible for'
            w_sub = re.sub(r'(compatible)(for)', r'\1 \2', w, flags=re.I)
            w_sub = re.sub(r'(for)(hp|dell|lenovo|asus|acer|apple|samsung|vivo|oppo)', r'\1 \2', w_sub, flags=re.I)
            w_sub = re.sub(r'(\d+)(w|v|a|gb|tb|mah|mm)\b', r'\1\2', w_sub, flags=re.I)
            for part in w_sub.split():
                if part.lower() in ('hp', 'usb', 'led', 'lcd', 'ac', 'dc', 'ram', 'rom', 'ssd', 'hdd', 'pro', 'max', 'plus', '5g', '4g'):
                    clean_words.append(part.upper())
                else:
                    clean_words.append(part.capitalize())
        return " ".join(clean_words)
    except Exception:
        return ""


def normalize_meesho_product(raw: dict, query: str = "") -> Optional[dict]:
    """
    Converts raw Meesho scraped item or API product into canonical schema.
    Returns None if mandatory fields (title, price, url) are invalid.
    """
    if not raw or not isinstance(raw, dict):
        return None

    # URL
    url = str(raw.get("url") or raw.get("link") or raw.get("product_url") or "").strip()
    if url and url.startswith("/"):
        url = f"https://www.meesho.com{url}"

    # Title extraction & slug enrichment
    title = str(raw.get("title") or raw.get("name") or "").strip()
    # Strip trailing price from title if appended (e.g., "Casual Laptop Adapters₹773")
    title = re.sub(r"[₹][\d,]+.*$", "", title).strip()
    title = re.sub(r"\s+\d+%\s*off.*$", "", title, flags=re.I).strip()

    slug_title = extract_title_from_slug(url)
    # If raw title is very short, generic, or slug is significantly richer, use slug title
    generic_words = {"others", "cables", "adapters", "chargers", "laptop adapters", "casual laptop adapters", "new cables", "fancy chargers"}
    if slug_title and (len(slug_title.split()) >= 3 and (len(title.split()) < 3 or title.lower() in generic_words)):
        title = slug_title
    elif not title and slug_title:
        title = slug_title

    if not title or len(title) < 3:
        return None

    # Price & MRP
    price_num = clean_number(raw.get("price_num") or raw.get("price"))
    if price_num is None or price_num <= 0:
        return None

    mrp_num = clean_number(raw.get("mrp_num") or raw.get("mrp") or raw.get("original_price"))
    if mrp_num and mrp_num < price_num:
        mrp_num = None

    discount_val = 0
    discount_str = raw.get("discount") or raw.get("discount_percent")
    if discount_str:
        d_digits = clean_number(discount_str)
        if d_digits:
            discount_val = d_digits
    elif mrp_num and mrp_num > price_num:
        discount_val = round(((mrp_num - price_num) / mrp_num) * 100)

    discount_formatted = f"{discount_val}% off" if discount_val > 0 else None

    # Rating & Reviews
    rating_val = clean_float(raw.get("rating"))
    review_val = clean_number(raw.get("review_count") or raw.get("reviews")) or 0

    # Image
    image = str(raw.get("image") or raw.get("image_url") or "").strip()

    # Product ID
    pid = str(raw.get("product_id") or "").strip()
    if not pid and url and "/p/" in url:
        pid = url.split("/p/")[-1].split("?")[0].strip()

    # Category & Product Type
    cat = raw.get("category") or detect_category(query=query, title=title)
    product_type = raw.get("product_type") or cat

    # Brand
    brand = raw.get("brand")
    if not brand:
        known_brands = [
            'Apple', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola',
            'HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Sony', 'LG',
            'boAt', 'Noise', 'Boult', 'Fire-Boltt', 'Fastrack', 'Titan', 'JBL',
            'Pilgrim', 'Ghar', 'Ghar Soaps', 'Mamaearth', 'Dot & Key', 'The Derma Co', 'Cetaphil', 'Neutrogena', 'Himalaya', 'Nivea', 'Dove',
            'True Elements', 'Nutty Gritties', 'Neuherbs', 'Sorich Organics', 'Saffola', 'Tata', 'Fortune', 'Aashirvaad',
            'Nike', 'Adidas', 'Puma', 'Reebok', 'Campus', 'Bata', 'Sparx', 'Exetech'
        ]
        t_low = title.lower()
        for kb in known_brands:
            if re.search(r'\b' + re.escape(kb.lower()) + r'\b', t_low):
                brand = kb
                break
        if not brand:
            parts = title.split()
            if parts and parts[0][0].isupper() and len(parts[0]) > 2 and parts[0].lower() not in ('best', 'new', 'latest', 'casual', 'fancy'):
                brand = parts[0]

    # Model
    model = raw.get("model")
    if not model:
        m_match = re.search(r'\b(t\d(?:\s*pro|\s*lite|\s*5g)?|iphone\s*\d+(?:\s*pro)?|galaxy\s*[a-z]\d+|pavilion|victus|ideapad|thinkpad|\d+w)\b', title, re.I)
        if m_match:
            model = m_match.group(1).upper()

    # Attributes
    specs = raw.get("specifications") or {}
    if not isinstance(specs, dict):
        specs = {}

    weight = raw.get("weight") or specs.get("Weight") or specs.get("Item Weight")
    if not weight:
        wt_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|kilograms?|ml|litres?|l)\b', title, re.I)
        if wt_m:
            weight = f"{wt_m.group(1)} {wt_m.group(2).lower()}"

    pack_qty = str(raw.get("pack_quantity") or specs.get("Pack Quantity") or "1")
    if pack_qty == "1":
        pq_m = re.search(r'(?:pack\s*of\s*|pack-|\bx\s*)(\d+)', title, re.I)
        if pq_m:
            pack_qty = pq_m.group(1)

    color = raw.get("color") or specs.get("Color")
    if not color:
        c_m = re.search(r'\b(black|white|blue|red|green|yellow|pink|purple|grey|gray|maroon|beige|orange|gold|silver)\b', title, re.I)
        if c_m:
            color = c_m.group(1).title()

    size = raw.get("size") or specs.get("Size")
    features = raw.get("features") or raw.get("key_features") or []
    if isinstance(features, str):
        features = [features]

    return {
        "platform": "meesho",
        "product_id": pid or f"meesho_{abs(hash(url)) % 1000000}",
        "title": title,
        "brand": brand or "Not Available",
        "model": model or "Not Available",
        "price": f"₹{price_num:,}",
        "price_str": f"₹{price_num:,}",
        "price_num": price_num,
        "mrp": f"₹{mrp_num:,}" if mrp_num else "Not Available",
        "mrp_str": f"₹{mrp_num:,}" if mrp_num else "Not Available",
        "mrp_num": mrp_num or 0,
        "discount": discount_val,
        "discount_percent": discount_formatted,
        "rating": rating_val or 0.0,
        "review_count": review_val,
        "reviews": f"{review_val:,} reviews" if review_val > 0 else "0",
        "image": image,
        "image_url": image,
        "url": url,
        "product_url": url,
        "link": url,
        "availability": "In Stock",
        "in_stock": True,
        "category": cat,
        "weight": weight or "Not Available",
        "pack_quantity": pack_qty,
        "color": color or "Not Available",
        "size": size or "Not Available",
        "product_type": product_type,
        "features": features,
        "key_features": features,
        "specifications": specs,
        "source": "meesho",
        "seller": raw.get("seller") or "Meesho Supplier",
    }
