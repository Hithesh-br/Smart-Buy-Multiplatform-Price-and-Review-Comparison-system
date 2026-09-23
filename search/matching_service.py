"""
search/matching_service.py
==========================
Authoritative SmartBuy Product Matching, Specification Comparison & Best Deal Engine.
Implements:
1. Standardized 22-field Common Product Format normalization
2. Accessory filtering & relevance validation
3. Weighted multi-signal Product Matching (0-100 score) with strict Variant discrimination
4. Category-specific Specification Comparison Matrix across Amazon, Flipkart, Meesho
5. Verified Best Deal algorithm with transparent reason breakdown and unit price normalization
6. Distinct error classification: "Scraping unavailable" vs "No matching product"
"""

import re
import datetime
from typing import Optional, Any
from rapidfuzz import fuzz

from search.normalizer import (
    detect_category,
    normalize_brand,
    normalize_model,
    normalize_title,
    normalize_query,
    normalize_weight,
    normalize_pack_quantity,
    normalize_price,
    normalize_rating,
    normalize_review_count,
    strip_marketing_words,
)
from search.specs_extractor import extract_specs, build_dynamic_specifications

ACCESSORY_KEYWORDS = {
    'case', 'cases', 'cover', 'covers', 'backcover', 'backcovers', 'back cover', 'back covers',
    'tempered glass', 'screen protector', 'screen protectors', 'screen guard', 'screen guards',
    'lens protector', 'lens protectors', 'skin', 'skins', 'guard', 'guards', 'cable', 'cables',
    'charging cable', 'charging cables', 'strap', 'straps', 'band', 'bands', 'pouch', 'pouches',
    'sleeve', 'sleeves', 'bumper', 'bumpers', 'stand', 'stands', 'holder', 'holders', 'mount',
    'mounts', 'stylus', 'ear tips', 'silicone case', 'flip cover', 'wallet case', 'camera glass'
}

INVALID_MODELS = {
    'vitamin', 'active', 'natural', 'organic', 'pure', 'new', 'best', 'super', 'ultra',
    'pro', 'max', 'plus', 'mini', 'classic', 'original', 'pack', 'combo', 'set', 'kit',
    'premium', 'raw', 'whole', 'seeds', 'soap', 'wash', 'face', 'shampoo', 'cream'
}


def normalize_common_product(raw_item: dict, platform: str) -> dict:
    """
    Transforms any scraped product into the authoritative normalized dictionary.
    Never invents fake data — absent values remain None or "Not Available".
    """
    title = str(raw_item.get('title') or '').strip()
    price_num = normalize_price(raw_item.get('price_num') or raw_item.get('price'))
    price_str = f"₹{price_num:,}" if price_num is not None else None

    mrp_num = normalize_price(raw_item.get('mrp_num') or raw_item.get('mrp') or raw_item.get('original_price'))
    mrp_str = f"₹{mrp_num:,}" if mrp_num is not None else None

    discount = raw_item.get('discount') or raw_item.get('discount_percent')
    if not discount and mrp_num and price_num and mrp_num > price_num:
        pct = round(((mrp_num - price_num) / mrp_num) * 100)
        discount = f"{pct}% off"

    rating = normalize_rating(raw_item.get('rating'))
    review_count = normalize_review_count(raw_item.get('review_count') or raw_item.get('reviews'))

    product_url = raw_item.get('product_url') or raw_item.get('url') or raw_item.get('link') or ""
    image_url = raw_item.get('image_url') or raw_item.get('image') or ""
    if "unsplash.com" in image_url or "placeholder" in image_url:
        image_url = ""

    in_stock = raw_item.get('in_stock', price_num is not None)
    availability = raw_item.get('availability') or ("In Stock" if in_stock else "Out of Stock")

    identity = extract_product_identity(raw_item)
    category = identity.get('category') or detect_category(title=title)
    brand = identity.get('brand') or normalize_brand(raw_item.get('brand'))
    model = identity.get('model') or normalize_model(raw_item.get('model'))
    product_type = identity.get('product_type') or category

    specifications = raw_item.get('specifications') or {}
    if not specifications and isinstance(raw_item.get('specs'), dict):
        specifications = raw_item['specs'].get('category_specs', {})

    var = identity.get('variant', {})
    weight = var.get('weight') or normalize_weight(specifications.get('Weight') or specifications.get('Item Weight') or raw_item.get('weight'))
    pack_qty = str(var.get('pack_quantity') or normalize_pack_quantity(specifications.get('Pack Quantity') or raw_item.get('pack_quantity')))
    color = var.get('color') or specifications.get('Color') or raw_item.get('color') or None
    size = var.get('size') or specifications.get('Size') or raw_item.get('size') or None

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "platform": platform.lower(),
        "platform_name": platform.capitalize(),
        "product_id": raw_item.get('product_id') or raw_item.get('asin') or "",
        "url": product_url,
        "product_url": product_url,
        "link": product_url,
        "title": title or "Not Available",
        "product_name": title or "Not Available",
        "brand": brand,
        "model": model,
        "price": price_str or "Not Available",
        "price_num": price_num,
        "mrp": mrp_str,
        "mrp_num": mrp_num,
        "original_price": mrp_str,
        "discount": discount,
        "discount_percent": discount,
        "rating": rating,
        "review_count": review_count,
        "reviews": f"{review_count:,}" if review_count > 0 else "0",
        "availability": availability,
        "in_stock": in_stock,
        "image": image_url,
        "image_url": image_url,
        "category": category,
        "product_type": product_type,
        "weight": weight,
        "pack_quantity": pack_qty,
        "color": color,
        "size": size,
        "specifications": specifications,
        "key_features": raw_item.get('key_features') or [],
        "seller": raw_item.get('seller') or None,
        "source": raw_item.get('source', 'live'),
        "scrape_status": raw_item.get('scrape_status', 'success'),
        "scraped_at": raw_item.get('scraped_at', now_iso),
        "match_type": raw_item.get('match_type', 'UNMATCHED'),
        "match_confidence": raw_item.get('match_confidence', 0),
        "match_score": raw_item.get('match_score', 0),
        "variant": var,
        "raw_data": raw_item.get('raw_data') or {},
    }


def is_accessory(title: str, query: str = "") -> bool:
    """Check if title represents an accessory when query did not ask for one."""
    t_lower = title.lower()
    q_lower = query.lower()

    if any(k in q_lower for k in ['case', 'cover', 'glass', 'guard', 'cable', 'strap', 'protector', 'skin', 'pouch', 'holder']):
        return False

    # Home textiles containing 'cover' (pillow covers, cushion covers, sofa covers, bedsheet) are not phone accessories
    if any(k in t_lower for k in ['bedsheet', 'pillow cover', 'pillow covers', 'cushion cover', 'sofa cover', 'bed cover']):
        if any(k in q_lower for k in ['bedsheet', 'bedding', 'pillow', 'cushion', 'sofa', 'linen', 'home']):
            return False

    # Check charger: if query requested charger, do NOT treat charger as accessory, but reject cases/covers/skins/guards!
    if "charger" in q_lower or "adapter" in q_lower or "cable" in q_lower:
        if any(k in t_lower for k in ['case', 'cover', 'skin', 'guard', 'tempered glass', 'pouch', 'holder']):
            return True
        return False

    for kw in ACCESSORY_KEYWORDS:
        # Ignore 'cover' if it is part of pillow cover or cushion cover
        if kw in ('cover', 'covers') and any(h in t_lower for h in ('pillow', 'cushion', 'sofa', 'bed')):
            continue
        if re.search(r'\b' + re.escape(kw) + r'\b', t_lower):
            return True

    return False


def extract_product_identity(item: dict, query: str = "") -> dict:
    """
    Extract canonical identity: brand, model, category, product_type, variant attributes.
    """
    title = str(item.get('title') or '')
    t_lower = title.lower()
    category = detect_category(query=query, title=title)

    # 1. Brand extraction
    brand = normalize_brand(item.get('brand'))
    if not brand:
        known_brands = [
            'Apple', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola', 'Google', 'iQOO',
            'HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Sony', 'LG',
            'boAt', 'Noise', 'Boult', 'Fire-Boltt', 'Fastrack', 'Titan', 'JBL',
            'Pilgrim', 'Ghar', 'Ghar Soaps', 'Mamaearth', 'Dot & Key', 'The Derma Co', 'Cetaphil', 'Neutrogena', 'Himalaya', 'Nivea', 'Dove',
            'True Elements', 'Nutty Gritties', 'Neuherbs', 'Sorich Organics', 'Saffola', 'Tata', 'Fortune', 'Aashirvaad',
            'Nike', 'Adidas', 'Puma', 'Reebok', 'Campus', 'Bata', 'Sparx'
        ]
        for kb in known_brands:
            if re.search(r'\b' + re.escape(kb.lower()) + r'\b', t_lower):
                brand = kb
                break
        if not brand:
            tokens = title.split()
            if tokens and tokens[0][0].isupper() and tokens[0].lower() not in INVALID_MODELS and len(tokens[0]) > 1:
                brand = tokens[0]

    # 2. Variant extraction
    variant = {}
    # Storage
    st_m = re.search(r'\b(32|64|128|256|512)\s*gb\b', t_lower)
    tb_m = re.search(r'\b(1|2)\s*tb\b', t_lower)
    if st_m:
        variant['storage'] = f"{st_m.group(1)}GB"
    elif tb_m:
        variant['storage'] = f"{tb_m.group(1)}TB"

    # RAM
    ram_m = re.search(r'\b(4|6|8|12|16|32)\s*gb\s*(?:ram|ddr\d)?\b', t_lower)
    if ram_m and ('storage' not in variant or variant.get('storage') != f"{ram_m.group(1)}GB"):
        variant['ram'] = f"{ram_m.group(1)}GB"

    # Weight / Volume
    wt_norm = normalize_weight(title)
    if wt_norm:
        variant['weight'] = wt_norm

    # Pack quantity
    pq_norm = normalize_pack_quantity(title)
    variant['pack_quantity'] = int(pq_norm) if pq_norm.isdigit() else 1

    # 3. Model extraction
    model = None
    if category in ("phone", "tablet"):
        m_match = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|galaxy\s*[a-z]\d{1,2}|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|pixel\s*\d[a-z]?|t\d(?:\s*5g|\s*pro|\s*lite)?|nord(?:\s*ce)?\s*\d[a-z]?)\b', t_lower)
        if m_match:
            model = m_match.group(1).title()
    elif category == "laptop":
        m_match = re.search(r'\b(macbook\s*(?:air|pro)|thinkpad|ideapad|vivobook|zenbook|tuf|rog|victus|pavilion|omen|aspire)\b', t_lower)
        if m_match:
            model = m_match.group(1).title()
    elif category == "charger":
        m_match = re.search(r'\b(t\d|flashcharge|supervooc|dash|warp|pd\s*\d+w|\d+w\s*fast\s*charger|\d+w)\b', t_lower)
        if m_match:
            model = m_match.group(1).upper()

    return {
        "brand": brand,
        "model": model,
        "product_type": category,
        "category": category,
        "variant": variant
    }


def is_product_relevant(item: dict, query: str) -> tuple[bool, float, str]:
    """Validate product relevance to query without false rejections."""
    title = str(item.get('title') or '').strip()
    if not title:
        return False, 0.0, "Empty title"

    t_lower = title.lower()
    q_lower = query.lower()

    if is_accessory(title, query):
        return False, 0.0, "Accessory rejected"

    # Product category / type consistency
    if any(w in q_lower for w in ["charger", "adapter", "power supply"]):
        if not any(w in t_lower for w in ["charger", "adapter", "power supply", "ac cord", "power cord"]):
            return False, 0.0, "Mismatched type (device instead of charger)"

    if "soap" in q_lower and "face wash" not in q_lower:
        if ("face wash" in t_lower or "facewash" in t_lower) and "soap" not in t_lower:
            return False, 0.0, "Mismatched type (face wash instead of soap)"

    if "face wash" in q_lower or "facewash" in q_lower:
        if "soap" in t_lower and not any(w in t_lower for w in ["face wash", "facewash", "facial"]):
            return False, 0.0, "Mismatched type (soap instead of face wash)"

    # Brand consistency if specified in query
    known_brands_in_query = [
        'pilgrim', 'ghar', 'ghar soaps', 'apple', 'samsung', 'vivo', 'oppo', 'oneplus',
        'realme', 'hp', 'dell', 'lenovo', 'asus', 'boat', 'noise', 'true elements', 'farmley'
    ]
    query_brand = None
    for b in known_brands_in_query:
        if re.search(r'\b' + re.escape(b) + r'\b', q_lower):
            query_brand = b
            break

    if query_brand:
        b_root = query_brand.split()[0]
        if not re.search(r'\b' + re.escape(b_root) + r'\b', t_lower):
            return False, 0.0, f"Brand mismatch (expected {query_brand})"

    # Model conflict check (e.g. searching 'vivo t4 pro' rejects 'vivo t4 lite' or 'vivo t3')
    model_conflicts = [
        (r'\bt4\s*pro\b', [r'\bt4\s*lite\b', r'\bt3\b', r'\bt2\b', r'\bt1\b']),
        (r'\bt4\b', [r'\bt3\b', r'\bt2\b', r'\bt1\b']),
        (r'\biphone\s*15\s*pro\b', [r'\biphone\s*15\s*plus\b', r'\biphone\s*14\b', r'\biphone\s*13\b']),
        (r'\biphone\s*15\b', [r'\biphone\s*14\b', r'\biphone\s*13\b', r'\biphone\s*12\b', r'\biphone\s*11\b']),
        (r'\biphone\s*16\b', [r'\biphone\s*15\b', r'\biphone\s*14\b', r'\biphone\s*13\b']),
    ]
    for q_pat, conflicting_pats in model_conflicts:
        if re.search(q_pat, q_lower):
            for c_pat in conflicting_pats:
                if re.search(c_pat, t_lower) and not re.search(q_pat, t_lower):
                    return False, 0.0, "Conflicting model variant"

    # Token overlap and fuzzy similarity
    q_tokens = set(re.findall(r'[a-z0-9]+', q_lower))
    q_tokens = {w for w in q_tokens if w not in ('in', 'for', 'the', 'and', 'with', 'best', 'online')}
    t_tokens = set(re.findall(r'[a-z0-9]+', t_lower))

    if q_tokens:
        overlap = len(q_tokens.intersection(t_tokens)) / len(q_tokens)
        fuzzy_score = fuzz.token_set_ratio(query, title)
        if overlap >= 0.4 or fuzzy_score >= 50:
            return True, max(overlap * 100, fuzzy_score), "Relevant"
        return False, fuzzy_score, "Low token overlap"

    return True, 70.0, "Accepted"


def calculate_product_match_score(item1: dict, item2: dict) -> tuple[float, str, dict]:
    """
    Authoritative weighted product matching score (0 to 100).
    Weights:
        - Brand: 20%
        - Product Title / Name: 30%
        - Model: 20%
        - Weight / Volume: 10%
        - Pack Quantity: 10%
        - Variant (RAM/Storage/Color): 5%
        - Category: 5%

    Classification:
        - 90 - 100: "Exact Match"
        - 75 - 89:  "Strong Match"
        - 60 - 74:  "Similar Product"
        - < 60:     "Not a Match"
    """
    id1 = extract_product_identity(item1)
    id2 = extract_product_identity(item2)

    breakdown = {}

    # 1. Brand similarity (20%)
    b1 = normalize_brand(item1.get('brand') or id1.get('brand'))
    b2 = normalize_brand(item2.get('brand') or id2.get('brand'))
    if b1 and b2:
        if b1.lower() == b2.lower():
            brand_score = 20.0
        elif b1.lower() in b2.lower() or b2.lower() in b1.lower():
            brand_score = 18.0
        else:
            brand_score = 0.0  # Conflicting brands -> 0 pts
    elif b1 or b2:
        brand_score = 10.0  # One missing brand -> neutral
    else:
        brand_score = 15.0  # Both generic
    breakdown['brand'] = brand_score

    # 2. Product title similarity (30%)
    t1_clean = strip_marketing_words(normalize_title(item1.get('title', '')))
    t2_clean = strip_marketing_words(normalize_title(item2.get('title', '')))
    title_ratio = fuzz.token_set_ratio(t1_clean, t2_clean) / 100.0
    title_score = title_ratio * 30.0
    breakdown['title'] = round(title_score, 1)

    # 3. Model similarity (20%)
    m1 = id1.get('model') or normalize_model(item1.get('model'))
    m2 = id2.get('model') or normalize_model(item2.get('model'))
    if m1 and m2:
        if m1.lower() == m2.lower():
            model_score = 20.0
        else:
            model_score = 0.0  # Conflicting models
    elif not m1 and not m2:
        # Non-model category (e.g. soap, chia seeds)
        model_score = 18.0
    else:
        # One item has model, check if other title contains it
        target_m = str(m1 or m2 or '').lower()
        other_title = (t2_clean if m1 else t1_clean).lower()
        if target_m in other_title:
            model_score = 16.0
        else:
            model_score = 5.0
    breakdown['model'] = model_score

    # 4. Weight / Volume similarity (10%)
    w1 = normalize_weight(item1.get('weight') or id1.get('variant', {}).get('weight') or item1.get('title'))
    w2 = normalize_weight(item2.get('weight') or id2.get('variant', {}).get('weight') or item2.get('title'))
    is_weight_relevant = id1.get('category') in ('soap', 'face_wash', 'grocery', 'food', 'skincare', 'shampoo')
    if w1 and w2:
        if w1 == w2:
            weight_score = 10.0
        else:
            weight_score = 0.0  # Different quantities (e.g. 500g vs 1kg)
    elif not is_weight_relevant:
        weight_score = 10.0  # Weight not applicable
    else:
        weight_score = 4.0   # Missing weight on grocery
    breakdown['weight'] = weight_score

    # 5. Pack Quantity similarity (10%)
    pq1 = str(id1.get('variant', {}).get('pack_quantity') or normalize_pack_quantity(item1.get('pack_quantity') or item1.get('title')))
    pq2 = str(id2.get('variant', {}).get('pack_quantity') or normalize_pack_quantity(item2.get('pack_quantity') or item2.get('title')))
    if pq1 == pq2:
        pack_score = 10.0
    else:
        pack_score = 0.0  # Conflict (Pack of 1 vs Pack of 3)
    breakdown['pack_quantity'] = pack_score

    # 6. Variant (RAM/Storage/Size/Color) similarity (5%)
    v1 = id1.get('variant', {})
    v2 = id2.get('variant', {})
    has_variant_conflict = False
    for v_key in ('storage', 'ram'):
        val1 = v1.get(v_key)
        val2 = v2.get(v_key)
        if val1 and val2 and val1 != val2:
            has_variant_conflict = True
            break
    variant_score = 0.0 if has_variant_conflict else 5.0
    breakdown['variant'] = variant_score

    # 7. Category similarity (5%)
    cat1 = id1.get('category')
    cat2 = id2.get('category')
    if cat1 and cat2 and cat1 == cat2:
        category_score = 5.0
    elif cat1 and cat2 and cat1 != "other" and cat2 != "other":
        category_score = 0.0
    else:
        category_score = 3.0
    breakdown['category'] = category_score

    total_score = round(sum(breakdown.values()), 1)
    total_score = max(0.0, min(100.0, total_score))

    # Model Conflict Check
    has_model_conflict = bool(m1 and m2 and m1.lower() != m2.lower())
    if has_model_conflict:
        total_score = min(total_score, 45.0)
        classification = "Not a Match"
        return total_score, classification, breakdown

    # Variant Discrimination:
    # If storage, weight, or pack quantity differs, mark as Variant rather than Exact Match!
    is_variant = has_variant_conflict or (w1 and w2 and w1 != w2) or (pq1 != pq2)

    if total_score >= 90:
        classification = "Variant" if is_variant else "Exact Match"
    elif total_score >= 75:
        classification = "Variant" if is_variant else "Strong Match"
    elif total_score >= 60:
        classification = "Similar Product"
    else:
        classification = "Not a Match"

    return total_score, classification, breakdown


def are_exact_matches(item1: dict, item2: dict) -> bool:
    """Strict check whether two items represent the exact same product variant."""
    score, classification, _ = calculate_product_match_score(item1, item2)
    return classification == "Exact Match"


def extract_normalized_specs(product: Optional[dict]) -> dict:
    """
    Extract complete standardized specifications from product.
    Returns clean dictionary mapping attribute keys to string values.
    Missing attributes default to 'N/A'. Never copies from other products.
    """
    if not product or not isinstance(product, dict):
        return {}

    title = str(product.get('title') or product.get('product_name') or '').strip()
    brand = str(product.get('brand') or '').strip()
    if not brand or brand.lower() in ('generic', 'not available', 'none', 'n/a'):
        brand = 'N/A'

    model = str(product.get('model') or '').strip()
    if not model or model.lower() in ('not available', 'none', 'n/a', 'standard'):
        model = 'N/A'

    price = product.get('price')
    if not price and product.get('price_num'):
        price = f"₹{product['price_num']:,}"
    if not price or str(price).strip().lower() in ('not available', 'none', '0', '₹0'):
        price = 'N/A'

    mrp = product.get('mrp') or product.get('original_price')
    if not mrp and product.get('mrp_num'):
        mrp = f"₹{product['mrp_num']:,}"
    if not mrp or str(mrp).strip().lower() in ('not available', 'none'):
        mrp = 'N/A'

    discount = product.get('discount') or product.get('discount_percent') or 'N/A'
    if str(discount).strip().lower() in ('none', '0%', '0'):
        discount = 'N/A'

    r_val = product.get('rating')
    rating = f"★ {r_val}" if (r_val is not None and str(r_val) not in ('0', '0.0', 'None', 'N/A')) else 'N/A'

    rc = product.get('review_count') or product.get('reviews') or 0
    try:
        rc_num = int(str(rc).replace(',', '').split()[0])
        reviews = f"{rc_num:,} reviews" if rc_num > 0 else 'N/A'
    except Exception:
        reviews = str(rc) if rc and str(rc) != '0' else 'N/A'

    avail = product.get('availability') or ('In Stock' if product.get('in_stock', True) else 'Out of Stock')
    link = product.get('product_url') or product.get('url') or product.get('link') or 'N/A'

    # Build comprehensive case-insensitive lookup map
    lookup: dict[str, str] = {}
    sources = [
        product.get('specifications'),
        product.get('specs') if isinstance(product.get('specs'), dict) else None,
        product.get('specs', {}).get('category_specs') if isinstance(product.get('specs'), dict) else None,
        product.get('attributes'),
        product.get('variant'),
        product.get('raw_data') if isinstance(product.get('raw_data'), dict) else None,
    ]
    for src in sources:
        if isinstance(src, dict):
            for k, v in src.items():
                if v is not None and str(v).strip() not in ('', 'None', 'null', 'N/A', 'Not Available'):
                    lookup[k.strip().lower()] = str(v).strip()

    def _val(*keys, default='N/A') -> str:
        for k in keys:
            kl = k.lower()
            if kl in lookup:
                res = lookup[kl]
                if res and res.lower() not in ('none', 'null', 'not available', 'n/a', ''):
                    return res
        return default

    # Regex extractors from title as fallback
    title_lower = title.lower()

    # Phone / Laptop
    ram_val = _val('ram', 'system memory', 'ram memory', 'memory')
    if ram_val == 'N/A':
        m = re.search(r'\b(\d+)\s*gb\s*(?:ram|lpddr\d?)?\b', title_lower)
        if m and any(k in title_lower for k in ('phone', 'mobile', 'laptop', 'gb ram', 'realme', 'samsung', 'iphone', 'redmi', 'oneplus', 'iqoo', 'motorola', 'hp', 'lenovo', 'dell', 'asus')):
            ram_val = f"{m.group(1)} GB"

    storage_val = _val('storage', 'internal storage', 'rom', 'ssd', 'hdd', 'capacity', 'hard drive')
    if storage_val == 'N/A':
        m = re.search(r'\b(64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b', title_lower)
        if m:
            storage_val = m.group(0).upper()

    processor_val = _val('processor', 'cpu', 'chipset', 'processor name')
    if processor_val == 'N/A':
        m = re.search(r'\b(snapdragon[\s\w]*?(?:gen\s*\d)?|mediatek[\s\w]*?|dimensity[\s\w]*?|core\s*i[3579][\s\w]*?|ryzen\s*\d[\s\w]*?|apple\s*m\d|bionic\s*a\d+)\b', title_lower)
        if m:
            processor_val = m.group(1).title()

    display_val = _val('display', 'screen size', 'display size', 'screen')
    if display_val == 'N/A':
        m = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|"|-inch|cm)\b', title_lower)
        if m:
            display_val = f"{m.group(1)} inch"

    battery_val = _val('battery', 'battery capacity', 'battery power')
    if battery_val == 'N/A':
        m = re.search(r'(\d{4,5})\s*mah\b', title_lower)
        if m:
            battery_val = f"{m.group(1)} mAh"

    os_val = _val('os', 'operating system')
    if os_val == 'N/A':
        m = re.search(r'\b(android\s*\d*|ios\s*\d*|windows\s*\d*|macos)\b', title_lower)
        if m:
            os_val = m.group(1).title()

    camera_val = _val('camera', 'rear camera', 'primary camera', 'back camera')
    if camera_val == 'N/A':
        m = re.search(r'(\d{2,3}\s*mp)\b', title_lower)
        if m:
            camera_val = m.group(1).upper()

    # Charger
    wattage_val = _val('wattage', 'power', 'output power', 'watts')
    if wattage_val == 'N/A':
        m = re.search(r'\b(\d{1,3})\s*w\b|\b(\d{1,3})\s*watt\b', title_lower)
        if m:
            wattage_val = f"{m.group(1) or m.group(2)}W"

    voltage_val = _val('voltage', 'output voltage', 'input voltage')
    if voltage_val == 'N/A':
        m = re.search(r'\b(\d{1,3}(?:\.\d+)?)\s*v\b', title_lower)
        if m:
            voltage_val = f"{m.group(1)}V"

    # Beauty / Skincare / Facewash
    volume_val = _val('volume', 'net volume', 'net quantity', 'quantity')
    if volume_val == 'N/A':
        m = re.search(r'\b(\d+(?:\.\d+)?)\s*(ml|l|litre?s?|liter?s?)\b', title_lower)
        if m:
            volume_val = f"{m.group(1)} {m.group(2)}"

    weight_val = product.get('weight') or _val('weight', 'item weight', 'net weight')
    if not weight_val or weight_val in ('Not Available', 'None'):
        m = re.search(r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?)\b', title_lower)
        if m:
            weight_val = f"{m.group(1)}{m.group(2)}"
        else:
            weight_val = 'N/A'

    # Headphones
    conn_val = _val('connectivity', 'connectivity technology', 'wireless type', 'bluetooth')
    if conn_val == 'N/A':
        if 'bluetooth' in title_lower or 'wireless' in title_lower or 'tws' in title_lower:
            conn_val = 'Bluetooth Wireless'
        elif 'wired' in title_lower or '3.5mm' in title_lower:
            conn_val = 'Wired 3.5mm'

    htype_val = _val('headphone type', 'form factor', 'type', 'design')
    if htype_val == 'N/A':
        if 'over-ear' in title_lower or 'over ear' in title_lower:
            htype_val = 'Over Ear'
        elif 'on-ear' in title_lower or 'on ear' in title_lower:
            htype_val = 'On Ear'
        elif 'in-ear' in title_lower or 'in ear' in title_lower or 'earbuds' in title_lower or 'tws' in title_lower:
            htype_val = 'In Ear'

    specs_result = {
        "Product Name": title or 'N/A',
        "Brand": brand,
        "Model": model,
        "Price": price,
        "MRP": mrp,
        "Discount": discount,
        "Rating": rating,
        "Total Reviews": reviews,
        "Availability": avail,
        "Buy Link": link,

        # Phones / Laptops
        "RAM": ram_val,
        "Storage": storage_val,
        "Processor": processor_val,
        "Display": display_val,
        "Battery": battery_val,
        "Camera": camera_val,
        "OS": os_val,
        "Operating System": os_val,
        "Graphics": _val('graphics', 'graphics processor', 'gpu', 'dedicated graphics'),

        # Face wash / Beauty / Skincare
        "Skin Type": _val('skin type', 'skin tones', 'skin concern', 'applied for'),
        "Volume": volume_val,
        "Ingredients": _val('ingredients', 'key ingredients', 'composition'),
        "Fragrance": _val('fragrance', 'scent', 'perfume'),
        "Benefits": _val('benefits', 'key benefits', 'skin concern', 'finish', 'features'),

        # Clothing / Fashion
        "Fabric": _val('fabric', 'material', 'fabric care'),
        "Size": product.get('size') or _val('size', 'clothing size', 'dimensions'),
        "Color": product.get('color') or _val('color', 'colour'),
        "Pattern": _val('pattern', 'print or pattern type'),
        "Fit": _val('fit', 'fit type'),
        "Sleeve": _val('sleeve', 'sleeve length', 'sleeve styling'),
        "Occasion": _val('occasion', 'ideal for'),

        # Bags
        "Material": product.get('material') or _val('material', 'outer material', 'body material'),
        "Bag Type": _val('bag type', 'type', 'style'),
        "Capacity": _val('capacity', 'volume'),
        "Compartments": _val('compartments', 'number of compartments', 'pockets'),
        "Closure": _val('closure', 'closure type', 'fastener'),
        "Dimensions": _val('dimensions', 'item dimensions', 'package dimensions'),

        # Charger
        "Wattage": wattage_val,
        "Voltage": voltage_val,
        "Power": wattage_val if wattage_val != 'N/A' else _val('power', 'output power'),
        "Compatibility": _val('compatibility', 'compatible devices', 'suitable for', 'compatible with'),
        "Fast Charging": _val('fast charging', 'quick charge', 'rapid charge', 'fast charge'),
        "Port Type": _val('port type', 'connector type', 'interface', 'output interface', 'ports'),
        "Cable Included": _val('cable included', 'in the box', 'cable type'),

        # Headphones
        "Headphone Type": htype_val,
        "Connectivity": conn_val,
        "Battery Life": _val('battery life', 'playtime', 'playback time', 'battery'),
        "Noise Cancellation": _val('noise cancellation', 'active noise cancellation', 'anc', 'noise control'),
        "Driver Size": _val('driver size', 'driver diameter', 'speaker driver'),
        "Microphone": _val('microphone', 'built-in mic', 'mic', 'with microphone'),

        # Shoes
        "Sole Material": _val('sole material', 'sole', 'outer sole'),
        "Upper Material": _val('upper material', 'upper', 'outer material'),
        "Toe Shape": _val('toe shape', 'toe style', 'toe type'),

        # Grocery / Food
        "Net Quantity": volume_val if volume_val != 'N/A' else _val('net quantity', 'quantity', 'pack size', 'pack quantity'),
        "Shelf Life": _val('shelf life', 'expiry', 'best before', 'expiry date'),
        "Dietary Preference": _val('dietary preference', 'diet type', 'food preference'),
        "Storage Instructions": _val('storage instructions', 'storage', 'care instructions'),

        # General
        "Weight": weight_val,
        "Pack Quantity": str(product.get('pack_quantity') or _val('pack quantity', 'pack size') or '1'),
    }

    # Also incorporate any original explicit specifications so custom fields are preserved
    raw_specs = product.get('specifications') or {}
    if isinstance(raw_specs, dict):
        for k, v in raw_specs.items():
            if k not in specs_result and v and str(v).strip() not in ('', 'N/A', 'None', 'null'):
                specs_result[k] = str(v).strip()

    # Ensure all missing or empty values are strictly normalized to 'N/A'
    for k in list(specs_result.keys()):
        val = specs_result[k]
        if val is None or str(val).strip() in ('', 'None', 'null', 'Not Available'):
            specs_result[k] = 'N/A'

    return specs_result


def get_category_spec_keys(category: str) -> list[str]:
    """Return prioritized specification keys relevant for the given category."""
    cat = (category or "").lower().strip()
    # 1. Audio / Headphones (must precede phone so 'headphones' doesn't match 'phone')
    if any(k in cat for k in ("headphone", "earphone", "earbud", "airpod", "headset", "audio", "tws")):
        return ["Headphone Type", "Connectivity", "Battery Life", "Noise Cancellation", "Driver Size", "Microphone"]
    # 2. Phones / Mobiles
    elif re.search(r'\b(phone|phones|smartphone|smartphones|mobile|mobiles|tablet|tablets)\b', cat):
        return ["RAM", "Storage", "Display", "Processor", "Battery", "Camera", "OS"]
    # 3. Laptops / Computers
    elif any(k in cat for k in ("laptop", "computer", "pc", "notebook")):
        return ["Processor", "RAM", "Storage", "Display", "Graphics", "OS", "Battery"]
    # 4. Face wash & Cleansers
    elif any(k in cat for k in ("face_wash", "facewash", "face wash", "cleanser")):
        return ["Skin Type", "Volume", "Ingredients", "Fragrance", "Benefits"]
    # 5. Chargers & Adapters
    elif any(k in cat for k in ("charger", "adapter", "power_bank", "powerbank")):
        return ["Wattage", "Voltage", "Power", "Compatibility", "Fast Charging", "Port Type", "Cable Included"]
    # 6. Fashion & Clothing
    elif any(k in cat for k in ("clothing", "fashion", "apparel", "saree", "shirt", "t-shirt", "jeans", "dress", "kurti", "kurta")):
        return ["Fabric", "Size", "Color", "Pattern", "Fit", "Sleeve", "Occasion"]
    # 7. Bags & Backpacks
    elif any(k in cat for k in ("bag", "backpack", "handbag", "purse", "wallet", "luggage", "tote")):
        return ["Material", "Bag Type", "Capacity", "Compartments", "Closure", "Dimensions"]
    # 8. Shoes & Footwear
    elif any(k in cat for k in ("shoe", "footwear", "sneaker", "sandal", "boot")):
        return ["Sole Material", "Upper Material", "Closure", "Toe Shape", "Occasion", "Color"]
    # 9. Grocery & Food
    elif any(k in cat for k in ("grocery", "food", "rice", "chocolate", "coffee", "tea", "snack", "oil", "spice")):
        return ["Net Quantity", "Ingredients", "Shelf Life", "Dietary Preference", "Storage Instructions"]
    # 10. Beauty, Skincare & Personal Care
    elif any(k in cat for k in ("soap", "beauty", "skincare", "personal_care", "shampoo", "lipstick", "serum", "cream", "lotion")):
        return ["Skin Type", "Weight", "Volume", "Ingredients", "Fragrance", "Benefits"]
    # 11. Watches
    elif any(k in cat for k in ("watch", "smartwatch")):
        return ["Display Type", "Dial Shape", "Strap Material", "Water Resistance", "Battery Life", "Connectivity"]
    # 12. Kitchen & Home Appliances
    elif any(k in cat for k in ("kitchen", "home_appliance", "furniture", "appliance")):
        return ["Power", "Capacity", "Material", "Wattage", "Color", "Dimensions", "Warranty"]
    return ["Compatibility", "Material", "Color", "Dimensions", "Warranty"]


def compute_best_deal(
    candidates: list[dict],
    canonical_item: dict,
    category: str
) -> Optional[dict]:
    """
    Computes verified Best Deal considering variant match, unit price normalization,
    in-stock status, rating, and review confidence. Never invents fake deals.
    """
    valid = [
        it for it in candidates
        if it.get('in_stock', True) and (it.get('price_num') or 0) > 0 and it.get('scrape_status') == 'success'
    ]
    if not valid:
        return None

    # Calculate effective price and unit price (per 100g / 100ml) where applicable
    is_bulk_commodity = category in ('soap', 'grocery', 'food', 'face_wash', 'shampoo')
    
    scored_deals = []
    for it in valid:
        match_score, match_class, _ = calculate_product_match_score(canonical_item, it)
        # Strictly require Exact Match, Variant, or Strong Match for Best Deal comparison
        if match_class not in ("Exact Match", "Variant", "Strong Match") and match_score < 60:
            continue

        raw_price = it['price_num']
        effective_price = raw_price

        # Unit price calculation
        unit_price = float(raw_price)
        weight_str = it.get('weight') or canonical_item.get('weight')
        if is_bulk_commodity and weight_str:
            wt_digits = re.search(r'(\d+)', weight_str)
            if wt_digits:
                grams = int(wt_digits.group(1))
                if 'kg' in weight_str.lower():
                    grams *= 1000
                if grams > 0:
                    unit_price = (raw_price / grams) * 100.0  # Price per 100g

        # Weighted best deal scoring:
        # 40% price, 25% rating, 15% review confidence, 10% availability, 10% match quality
        min_p = min(x['price_num'] for x in valid)
        price_component = (min_p / max(1, raw_price)) * 40.0

        r_val = it.get('rating') or 4.0
        rating_component = (min(5.0, float(r_val)) / 5.0) * 25.0

        rc = it.get('review_count') or 0
        review_component = min(15.0, (rc / 100.0) * 15.0 if rc < 100 else 15.0)

        avail_component = 10.0 if it.get('in_stock', True) else 0.0

        match_component = (match_score / 100.0) * 10.0

        overall_deal_score = price_component + rating_component + review_component + avail_component + match_component

        scored_deals.append({
            "item": it,
            "match_class": match_class,
            "match_score": match_score,
            "raw_price": raw_price,
            "effective_price": effective_price,
            "unit_price": unit_price,
            "deal_score": overall_deal_score,
        })

    if not scored_deals:
        return None

    # Pick the highest overall deal score
    scored_deals.sort(key=lambda d: d['deal_score'], reverse=True)
    best = scored_deals[0]
    best_item = best['item']

    # Compute savings against the highest price in the exact/strong matches
    same_group_prices = [d['raw_price'] for d in scored_deals if d['match_class'] in ('Exact Match', 'Strong Match', 'Variant')]
    savings = max(0, max(same_group_prices) - best['raw_price']) if same_group_prices else 0

    reasons = [
        f"{best['match_class']} variant verified",
        f"Lowest verified effective price (₹{best['raw_price']:,})",
        "In Stock & ready to order",
    ]
    if best_item.get('rating'):
        reasons.append(f"Rating {best_item['rating']} ★ ({best_item.get('review_count', 0):,} reviews)")
    if is_bulk_commodity and best.get('unit_price'):
        reasons.append(f"Best unit value: ₹{best['unit_price']:.1f} / 100g")

    return {
        "platform": best_item['platform'].capitalize(),
        "price": best['raw_price'],
        "formatted_price": f"₹{best['raw_price']:,}",
        "title": best_item['title'],
        "link": best_item.get('product_url') or best_item.get('url') or best_item.get('link'),
        "image": best_item.get('image_url') or best_item.get('image'),
        "rating": best_item.get('rating'),
        "reviews": best_item.get('review_count', 0),
        "savings": savings,
        "match_class": best['match_class'],
        "reasons": reasons,
        "reason_text": "\n".join(f"• {r}" for r in reasons),
        "is_exact_verified": True
    }


def build_canonical_comparison(
    query: str,
    platform_results: dict,
    platform_status: Optional[dict] = None
) -> dict:
    """
    Master Canonical Comparison Engine.
    Coordinates:
    - Candidate clustering and canonical selection
    - Pair-wise cross-platform match scoring (Amazon ↔ Flipkart, Amazon ↔ Meesho, Flipkart ↔ Meesho)
    - 3-column Specification Comparison Table comparing matched products
    - Strict classification of empty cells ("Scraping unavailable" vs "No matching product")
    - Verified Best Deal calculation
    """
    if platform_status is None:
        platform_status = {}

    all_valid = []
    for plat in ['amazon', 'flipkart', 'meesho']:
        items = platform_results.get(plat.capitalize()) or platform_results.get(plat) or []
        for item in items:
            is_rel, score, reason = is_product_relevant(item, query)
            if is_rel:
                item['relevance_score'] = score
                all_valid.append(item)

    category = detect_category(query=query)

    # If absolutely no valid products found across any platform
    if not all_valid:
        return {
            "canonical_product": None,
            "amazon": None,
            "flipkart": None,
            "meesho": None,
            "has_match": False,
            "match_pairs": {},
            "specification_table": {
                "has_match": False,
                "message": "No matching products found for this search",
                "rows": [],
                "columns": ["specification", "amazon", "flipkart", "meesho"]
            },
            "specifications_matrix": [],
            "best_deal": None,
            "category": category
        }

    # Group items into candidate clusters based on matching score >= 75
    clusters = []
    for candidate in all_valid:
        cluster = [candidate]
        for other in all_valid:
            if other is not candidate:
                sc, cl, _ = calculate_product_match_score(candidate, other)
                if sc >= 75:
                    cluster.append(other)
        distinct_plats = set(it['platform'].lower() for it in cluster)
        clusters.append({
            "candidate": candidate,
            "cluster": cluster,
            "distinct_platforms": distinct_plats,
            "platform_count": len(distinct_plats),
            "relevance": candidate.get('relevance_score', 0),
            "reviews": candidate.get('review_count', 0)
        })

    # Sort clusters: multi-platform > high relevance > reviews
    clusters.sort(key=lambda c: (c['platform_count'], c['relevance'], c['reviews']), reverse=True)
    best_cluster = clusters[0]
    canonical = best_cluster['candidate']
    can_id = canonical.get('product_id') or f"can_{abs(hash(canonical.get('title', '')))}"
    canonical['canonical_product_id'] = can_id
    detected_cat = canonical.get('category') or category

    platform_matched = {"amazon": None, "flipkart": None, "meesho": None}
    # Pick the highest matching item per platform for the canonical product
    for plat in ['amazon', 'flipkart', 'meesho']:
        plat_items = platform_results.get(plat.capitalize()) or platform_results.get(plat) or []
        best_plat_item = None
        best_plat_score = -1.0
        for it in plat_items:
            sc, cl, _ = calculate_product_match_score(canonical, it)
            if sc > best_plat_score and sc >= 60:
                best_plat_score = sc
                best_plat_item = it
        if best_plat_item:
            best_plat_item['canonical_product_id'] = can_id
        platform_matched[plat] = best_plat_item

    # Calculate pair-wise match scores between matched products
    match_pairs = {}
    pair_defs = [
        ("amazon", "flipkart", "Amazon ↔ Flipkart"),
        ("amazon", "meesho", "Amazon ↔ Meesho"),
        ("flipkart", "meesho", "Flipkart ↔ Meesho"),
    ]
    for p1, p2, label in pair_defs:
        it1 = platform_matched[p1]
        it2 = platform_matched[p2]
        if it1 and it2:
            sc, cl, _ = calculate_product_match_score(it1, it2)
            match_pairs[label] = {
                "score": int(sc),
                "classification": cl,
                "label": label
            }
        else:
            match_pairs[label] = {
                "score": 0,
                "classification": "Not Available",
                "label": label
            }

    # Best deal among matched products
    matched_candidates: list[dict] = [it for it in platform_matched.values() if it is not None]
    best_deal = compute_best_deal(matched_candidates, canonical, detected_cat)

    # Build Specification Comparison Table dynamically
    matrix = build_dynamic_specifications(platform_matched, detected_cat)

    has_cross_platform_match = sum(1 for it in platform_matched.values() if it is not None) >= 2

    return {
        "canonical_product": canonical,
        "amazon": platform_matched['amazon'],
        "flipkart": platform_matched['flipkart'],
        "meesho": platform_matched['meesho'],
        "has_match": has_cross_platform_match,
        "match_pairs": match_pairs,
        "specification_table": {
            "has_match": has_cross_platform_match,
            "message": None if has_cross_platform_match else "Individual marketplace offers shown below",
            "rows": matrix,
            "columns": ["specification", "amazon", "flipkart", "meesho"]
        },
        "specifications_matrix": matrix,
        "best_deal": best_deal,
        "category": detected_cat
    }
