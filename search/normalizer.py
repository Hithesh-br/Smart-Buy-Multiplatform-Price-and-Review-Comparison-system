"""
search/normalizer.py
====================
Query and title normalization utilities.
No hardcoded product names, brands, or categories.
"""

import re

# Generic English stop words to strip from queries (not product terms)
_STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
    'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it',
    'they', 'them', 'their', 'this', 'that', 'these', 'those', 'buy',
    'get', 'find', 'show', 'best', 'cheap', 'good', 'nice', 'new'
}

# Marketing filler words often embedded in product titles (not useful for matching)
_MARKETING_WORDS = {
    'official', 'genuine', 'original', 'authentic', 'combo', 'pack',
    'set', 'kit', 'bundle', 'deal', 'offer', 'sale', 'discount',
    'limited', 'edition', 'special', 'exclusive', 'certified', 'brand',
    'new', 'fresh', 'hot', 'trending', 'popular', 'bestseller',
    'top', 'rated', 'quality', 'premium', 'luxury', 'imported',
    'with', 'free', 'shipping', 'delivery', 'warranty', 'guarantee'
}

# Regex patterns for unit normalization (run on titles before comparison)
_UNIT_PATTERNS = [
    (r'(\d+)\s*gb\b',  r'\1gb'),
    (r'(\d+)\s*tb\b',  r'\1tb'),
    (r'(\d+)\s*mb\b',  r'\1mb'),
    (r'(\d+)\s*mah\b', r'\1mah'),
    (r'(\d+)\s*ml\b',  r'\1ml'),
    (r'(\d+)\s*l\b',   r'\1l'),
    (r'(\d+)\s*kg\b',  r'\1kg'),
    (r'(\d+)\s*g\b(?!b)', r'\1g'),
    (r'(\d+)\s*mg\b',  r'\1mg'),
    (r'(\d+)\s*w\b',   r'\1w'),
    (r'(\d+)\s*inch\b', r'\1inch'),
    (r'(\d+)\s*"\b',   r'\1inch'),
    (r'(\d+)\s*hz\b',  r'\1hz'),
    (r'(\d+)\s*mp\b',  r'\1mp'),
]

# Measurement / quantity units — these should NOT be treated as model codes
# e.g. "5kg", "1L", "500ml", "250g", "100mg", "2TB", "16gb" would falsely
# classify grocery queries as brand_model and over-filter them.
_UNIT_SUFFIXES = re.compile(
    r'^(\d+(\.\d+)?)(kg|g|gm|mg|ml|l|ltr|lt|litre|liter|oz|lb|lbs|'  
    r'km|m|cm|mm|ft|inch|in|pc|pcs|pack|pair|set|piece|nos|unit|'       
    r'tablet|capsule|sachet|strip)$',
    re.I
)

# Patterns that indicate a query is model-specific (has alphanumeric model codes)
_MODEL_CODE_PATTERN = re.compile(
    r'\b([a-zA-Z]{1,4}\d+[a-zA-Z]?\d*|'   # e.g. S24, A55, M34, i7, RX7
    r'\d+[a-zA-Z]{1,3}\d*)\b'              # e.g. 12Pro, 15Plus
)

# Patterns indicating electronics/tech context
_TECH_INDICATORS = re.compile(
    r'\b(gb|tb|ram|ssd|hdd|ghz|mhz|4k|hd|oled|amoled|lcd|ips|mah|'
    r'processor|snapdragon|mediatek|intel|ryzen|apple|silicon|bionic|'
    r'android|ios|windows|linux|wifi|bluetooth|5g|4g|lte|nfc|'
    r'iphone|ipad|macbook|galaxy|pixel|redmi|poco|realme|oneplus|'
    r'vivo|oppo|motorola|nokia|asus|lenovo|hp|dell|acer|msi|sony|'
    r'boat|noise|jbl|bose)\b',
    re.I
)


def normalize_title(text: str) -> str:
    """
    Normalize a product title for comparison:
    1. Lowercase
    2. Collapse unit abbreviations (e.g. "256 GB" → "256gb")
    3. Strip special characters (keep alphanumerics and spaces)
    4. Collapse extra whitespace
    """
    if not text:
        return ""
    text = text.lower()
    for pattern, repl in _UNIT_PATTERNS:
        text = re.sub(pattern, repl, text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_query(query: str) -> str:
    """
    Normalize a user search query:
    1. Apply same normalization as normalize_title()
    2. Remove pure stop words (keep all product-relevant terms)
    Returns normalized string.
    """
    if not query:
        return ""
    norm = normalize_title(query)
    tokens = norm.split()
    # Only remove stop words if the query has more than 2 tokens
    # (preserves short product names like "milk", "rice", "soap")
    if len(tokens) > 2:
        tokens = [t for t in tokens if t not in _STOP_WORDS]
    return ' '.join(tokens) if tokens else norm


def strip_marketing_words(title: str) -> str:
    """
    Remove marketing filler words from a normalized title before scoring.
    Used only during similarity computation, not for display.
    """
    tokens = normalize_title(title).split()
    return ' '.join(t for t in tokens if t not in _MARKETING_WORDS)


def _contains_only_units(tokens: list) -> bool:
    """
    Check if ALL non-word tokens in the query are measurement units.
    Used to prevent grocery queries like 'rice 5kg' from being classified
    as brand_model just because '5kg' matches the alphanumeric pattern.
    """
    non_stop = [t for t in tokens if t not in ('and', 'of', 'in', 'with', 'pack')]
    return all(bool(_UNIT_SUFFIXES.match(t)) for t in non_stop if re.search(r'\d', t))


def detect_query_type(query: str) -> str:
    """
    Classify the query to choose appropriate similarity threshold.

    Returns:
        "generic"      — 1–2 word general queries (milk, rice, soap, shoes)
        "category"     — 2–3 word category searches (running shoes, gaming laptop)
        "brand_model"  — queries with brand+model codes (Samsung Galaxy S24, iPhone 15 Pro)
        "specific"     — detailed product descriptions (3+ words, no model codes)
    """
    norm = normalize_query(query)
    if not norm:
        return "generic"

    tokens = norm.split()
    token_count = len(tokens)

    has_model_code = bool(_MODEL_CODE_PATTERN.search(norm))
    has_tech_terms = bool(_TECH_INDICATORS.search(query))
    has_standalone_number = any(t.isdigit() for t in tokens)

    # If it has tech terms and a standalone number (e.g. "iPhone 15"), treat as brand_model
    if has_tech_terms and has_standalone_number:
        has_model_code = True

    # Check if all numeric parts are just quantity/measurement units
    # e.g. "rice 5kg", "milk 500ml", "protein 1kg" — should be 'category', not 'brand_model'
    if has_model_code and _contains_only_units(tokens):
        has_model_code = False

    # Short queries (1-2 meaningful words) with no model code → generic
    if token_count <= 2 and not has_model_code:
        return "generic"

    # Must have at least 2 tokens and a genuine model code to be brand_model
    if has_model_code and token_count >= 2:
        return "brand_model"

    # 3+ token queries with no model code but tech terms
    if has_tech_terms and token_count >= 2:
        return "specific"

    return "category"


def build_search_query(brand: str = '', category: str = '',
                       ram: str = '', storage: str = '',
                       processor: str = '', appliance_type: str = '',
                       type_val: str = '', q: str = '', **kwargs) -> str:
    """
    Construct a clean, highly effective e-commerce search query from user-selected
    specifications and category parameters to send to Amazon, Flipkart, and Meesho scrapers.
    """
    clean_brand = brand.strip() if brand and brand.lower() not in ('any', 'all', 'all brands', '') else ''
    clean_cat   = category.strip() if category and category.lower() not in ('any', 'all', '') else ''
    clean_q     = q.strip() if q and q.lower() not in ('any', 'all', '') else ''

    parts = []

    if clean_brand:
        parts.append(clean_brand)

    if clean_q:
        if clean_brand and clean_brand.lower() in clean_q.lower():
            parts = [clean_q]
        else:
            parts.append(clean_q)
    else:
        if clean_cat:
            cat_lower = clean_cat.lower()
            if bool(re.search(r'\b(mobile|mobiles|phone|phones|smartphone|smartphones)\b', cat_lower)):
                if clean_brand.lower() == 'apple':
                    parts.append('iPhone')
                elif clean_brand.lower() == 'samsung':
                    parts.append('Galaxy Phone')
                else:
                    parts.append('Phone')
            elif 'laptop' in cat_lower:
                parts.append('Laptop')
            elif 'headphone' in cat_lower:
                if type_val and 'tws' in type_val.lower():
                    parts.append('TWS Wireless Earbuds')
                else:
                    parts.append('Headphones')
            elif 'watch' in cat_lower:
                parts.append('Smartwatch')
            elif 'appliance' in cat_lower:
                if appliance_type and appliance_type.lower() not in ('any', 'all', ''):
                    parts.append(appliance_type)
                else:
                    parts.append('Appliance')

    # Add core primary specs (appliance_type, storage, ram)
    if appliance_type and appliance_type.lower() not in ('any', 'all', '') and appliance_type not in parts:
        parts.append(appliance_type)

    if storage and storage.lower() not in ('any', 'all', 'any storage', ''):
        m_s = re.search(r'(\d+)\s*(gb|tb)?', storage, re.I)
        s_norm = f"{m_s.group(1)}{m_s.group(2).upper() if m_s and m_s.group(2) else 'GB'}" if m_s else re.sub(r'\s+', '', storage)
        if s_norm.lower() not in ' '.join(parts).lower():
            parts.append(s_norm)

    if ram and ram.lower() not in ('any', 'all', 'any ram', ''):
        m_r = re.search(r'(\d+)\s*(gb|tb)?', ram, re.I)
        r_norm = f"{m_r.group(1)}{m_r.group(2).upper() if m_r and m_r.group(2) else 'GB'}" if m_r else re.sub(r'\s+', '', ram)
        if r_norm.lower() not in ' '.join(parts).lower():
            parts.append(r_norm)

    result_query = ' '.join(parts).strip()
    return result_query if result_query else (clean_q or 'Products')


def build_search_query_chain(brand: str = '', category: str = '',
                             ram: str = '', storage: str = '',
                             processor: str = '', appliance_type: str = '',
                             type_val: str = '', q: str = '', **kwargs) -> list[str]:
    """
    Generate an ordered list of fallback search queries from specific to broad
    to guarantee scrapers return products across Amazon, Flipkart, and Meesho.
    """
    queries = []
    
    # 1. Main Broad Query
    q1 = build_search_query(brand=brand, category=category, ram=ram, storage=storage,
                            processor=processor, appliance_type=appliance_type,
                            type_val=type_val, q=q, **kwargs)
    if q1:
        queries.append(q1)

    # 2. Fallback A: Brand + Storage
    if storage and storage.lower() not in ('any', 'all', 'any storage', ''):
        q2 = build_search_query(brand=brand, category=category, storage=storage, q=q, **kwargs)
        if q2 and q2 not in queries:
            queries.append(q2)

    # 3. Fallback B: Brand + RAM
    if ram and ram.lower() not in ('any', 'all', 'any ram', ''):
        q3 = build_search_query(brand=brand, category=category, ram=ram, q=q, **kwargs)
        if q3 and q3 not in queries:
            queries.append(q3)

    # 4. Fallback C: Brand + Category / Product Name
    q4 = build_search_query(brand=brand, category=category, q=q, **kwargs)
    if q4 and q4 not in queries:
        queries.append(q4)

    # 5. Fallback D: Brand alone or Product Name alone
    clean_brand = brand.strip() if brand and brand.lower() not in ('any', 'all', 'all brands', '') else ''
    if clean_brand and clean_brand not in queries:
        queries.append(clean_brand)

    clean_q = q.strip() if q and q.lower() not in ('any', 'all', '') else ''
    if clean_q and clean_q not in queries:
        queries.append(clean_q)

    return queries if queries else ['Products']



