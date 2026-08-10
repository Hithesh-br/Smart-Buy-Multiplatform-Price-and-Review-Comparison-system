"""
search/filters.py
=================
Fully dynamic filter generation from actual scraped results.
No hardcoded filter options — everything is derived from the data.
"""

import re
from search.normalizer import normalize_title


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert any rating or float string (e.g. '4.2 out of 5', 'N/A', None) to float without raising ValueError."""
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str or val_str.upper() in ('N/A', 'NONE', 'NOT AVAILABLE', 'NULL', ''):
        return default
    try:
        m = re.search(r'(\d+(?:\.\d+)?)', val_str)
        return float(m.group(1)) if m else default
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Dynamic filter extraction
# ---------------------------------------------------------------------------

def extract_filters_from_results(products: list) -> dict:
    """
    Scan actual scraped products and return available filter options.
    All options are derived from the real data — nothing is hardcoded.

    Returns a dict with these keys (each a sorted list of unique values):
        brands          : list[str]
        price_ranges    : list[dict]  (label, min, max)
        ratings         : list[str]   ("3.5+", "4.0+", "4.5+")
        discounts       : list[str]   ("10%+", "20%+", "30%+", "40%+", "50%+")
        platforms       : list[str]
        specs           : dict[str, list[str]]  — any extracted spec key → unique values
    """
    if not products:
        return {}

    brands    = set()
    prices    = []
    ratings   = []
    platforms = set()
    spec_map  = {}   # e.g. {"ram": {"4 GB", "8 GB"}, "storage": {...}}

    for item in products:
        # Brands
        brand = item.get('brand') or item.get('specs', {}).get('brand', '')
        if brand and brand not in ('N/A', '', None):
            brands.add(brand.strip())

        # Prices
        pn = item.get('price_num')
        if pn:
            prices.append(pn)

        # Ratings
        r = _safe_float(item.get('rating'))
        if r > 0:
            ratings.append(r)

        # Platforms
        plat = item.get('platform', '')
        if plat:
            platforms.add(plat)

        # Dynamic specs from specs dict
        specs = item.get('specs', {})
        for key, val in specs.items():
            if key in ('brand', 'price_num', 'rating_num') or not val or val == 'N/A':
                continue
            spec_map.setdefault(key, set()).add(str(val))

    # Build price range buckets from actual price distribution
    price_ranges = _build_price_ranges(prices)

    # Rating filter options (static thresholds, always useful)
    rating_options = []
    for threshold in (3.0, 3.5, 4.0, 4.5):
        if any(r >= threshold for r in ratings):
            rating_options.append(f"{threshold}+")

    # Discount filter options
    discount_options = _extract_discount_options(products)

    # Clean up spec_map — sort values, limit to reasonable set size
    clean_specs = {}
    for key, vals in spec_map.items():
        sorted_vals = sorted(
            [v for v in vals if v and v != 'N/A'],
            key=lambda x: (len(x), x)
        )
        if sorted_vals:
            clean_specs[key] = sorted_vals[:15]  # cap at 15 values per spec

    return {
        'brands':       sorted(brands),
        'price_ranges': price_ranges,
        'ratings':      rating_options,
        'discounts':    discount_options,
        'platforms':    sorted(platforms),
        'specs':        clean_specs,
    }


def _build_price_ranges(prices: list) -> list:
    """Generate contextual price bucket ranges from actual price data."""
    if not prices:
        return []

    min_p = min(prices)
    max_p = max(prices)

    # Define candidate bucket boundaries
    all_buckets = [
        (0,       500,    'Under ₹500'),
        (0,       1000,   'Under ₹1,000'),
        (0,       5000,   'Under ₹5,000'),
        (0,       10000,  'Under ₹10,000'),
        (1000,    5000,   '₹1,000 – ₹5,000'),
        (5000,    10000,  '₹5,000 – ₹10,000'),
        (10000,   20000,  '₹10,000 – ₹20,000'),
        (20000,   30000,  '₹20,000 – ₹30,000'),
        (30000,   50000,  '₹30,000 – ₹50,000'),
        (50000,   100000, '₹50,000 – ₹1,00,000'),
        (100000,  999999, 'Above ₹1,00,000'),
    ]

    result = []
    for lo, hi, label in all_buckets:
        # Only include buckets where at least one product falls within range
        if any(lo <= p <= hi for p in prices):
            result.append({'label': label, 'min': lo, 'max': hi})

    return result


def _extract_discount_options(products: list) -> list:
    """Return discount filter options based on actual discount data in products."""
    discounts = set()
    for item in products:
        disc = item.get('discount', 'N/A')
        if not disc or disc == 'N/A':
            continue
        m = re.search(r'(\d+)', str(disc))
        if m:
            pct = int(m.group(1))
            if pct >= 10:
                discounts.add(pct)

    if not discounts:
        return []

    options = []
    for threshold in (10, 20, 30, 40, 50, 60, 70):
        if any(d >= threshold for d in discounts):
            options.append(f"{threshold}%+")

    return options


# ---------------------------------------------------------------------------
# Filter application
# ---------------------------------------------------------------------------

BRAND_SYNONYMS = {
    'apple': {'apple', 'iphone', 'ipad', 'macbook', 'airpods', 'iwatch'},
    'samsung': {'samsung', 'galaxy'},
    'xiaomi': {'xiaomi', 'redmi', 'poco', 'mi'},
    'redmi': {'xiaomi', 'redmi', 'mi'},
    'poco': {'xiaomi', 'poco'},
    'oneplus': {'oneplus', '1plus'},
    'motorola': {'motorola', 'moto'},
    'hp': {'hp', 'hewlett'},
    'lenovo': {'lenovo', 'thinkpad', 'ideapad'},
    'asus': {'asus', 'rog', 'tuf', 'zenbook', 'vivobook'},
    'acer': {'acer', 'aspire', 'nitro', 'predator'},
    'sony': {'sony', 'bravia'},
}


def _brand_matches(brand_filter: str, title_lower: str, item_brand: str) -> bool:
    bf = brand_filter.lower().strip()
    if not bf or bf in ('any', 'all', 'all brands', ''):
        return True
    
    synonyms = BRAND_SYNONYMS.get(bf, {bf})
    text_to_check = f"{title_lower} {item_brand.lower()}"
    return any(syn in text_to_check for syn in synonyms)


def _spec_matches(spec_key: str, spec_val: str, title_lower: str, item_specs: dict) -> bool:
    sv = str(spec_val).strip().lower()
    if not sv or sv in ('any', 'all', 'any ram', 'any storage', 'any processor', 'any battery', 'any display size', 'any color', 'any rating', 'any type', 'any feature', 'any connectivity', 'any mic', 'any shape', 'any strap', 'any appliance', 'any star rating', 'any capacity', 'any tech', 'any warranty', ''):
        return True

    item_spec_val = str(item_specs.get(spec_key, '') or '').lower()
    combined_text = f"{title_lower} {item_spec_val}"

    # Direct substring or normalized substring check
    sv_no_space = re.sub(r'\s+', '', sv)
    if sv in combined_text or sv_no_space in combined_text:
        return True

    # Smart handling per spec key
    if spec_key in ('storage', 'ram'):
        m = re.search(r'(\d+)', sv)
        if m:
            num = m.group(1)
            unit = 'gb' if 'gb' in sv or 'tb' not in sv else 'tb'
            if f"{num}{unit}" in combined_text or f"{num} {unit}" in combined_text or f"{num}gb" in combined_text or f"{num}tb" in combined_text:
                return True

    elif spec_key == 'processor':
        if 'apple' in sv:
            return any(w in combined_text for w in ['apple', 'a14', 'a15', 'a16', 'a17', 'a18', 'bionic', 'm1', 'm2', 'm3', 'chip', 'iphone', 'macbook'])
        elif 'snapdragon' in sv:
            return any(w in combined_text for w in ['snapdragon', 'sd', 'qualcomm'])
        elif 'intel' in sv:
            m = re.search(r'i[3579]', sv)
            target_i = m.group(0) if m else 'intel'
            return target_i in combined_text or 'intel' in combined_text
        elif 'ryzen' in sv:
            m = re.search(r'\d+', sv)
            target_r = m.group(0) if m else '5'
            return f"ryzen {target_r}" in combined_text or 'ryzen' in combined_text
        elif 'mediatek' in sv or 'dimensity' in sv:
            return any(w in combined_text for w in ['mediatek', 'dimensity', 'helio'])
        elif 'exynos' in sv:
            return 'exynos' in combined_text or 'samsung' in combined_text

    elif spec_key in ('type', 'anc', 'connectivity'):
        if 'tws' in sv or 'truly wireless' in sv:
            return any(w in combined_text for w in ['tws', 'wireless', 'earbuds', 'airpods', 'buds'])
        return True

    elif spec_key in ('battery', 'display', 'features', 'warranty', 'tech', 'strap', 'shape', 'color', 'appliance_type', 'star_rating', 'capacity'):
        # For non-critical optional metadata, don't drop items if title omits the string
        return True

    return False


def score_and_rank_products(products: list, filter_params: dict, raw_q: str = '') -> list:
    """
    Score products dynamically based on user selected specifications.
    Uses a weighted Match Score system instead of strict binary elimination.

    Scoring:
    - Product Name match: +40 pts
    - Brand match:        +25 pts
    - Category match:     +20 pts
    - RAM match:          +15 pts
    - Storage match:      +15 pts
    - Processor match:    +15 pts
    - Price Range match:  +15 pts
    - Battery match:      +10 pts
    - Display Size match: +10 pts
    - Rating match:       +10 pts
    - Color match:        +5 pts
    """
    if not products:
        return products

    if not filter_params:
        filter_params = {}

    brand        = (filter_params.get('brand') or '').strip()
    category     = (filter_params.get('category') or '').strip()
    price_min    = filter_params.get('price_min')
    price_max    = filter_params.get('price_max')
    min_rating   = filter_params.get('min_rating')
    min_discount = filter_params.get('min_discount')
    platform     = (filter_params.get('platform') or '').strip().lower()
    spec_filters = filter_params.get('specs', {}) or {}

    # Count total user-selected filter criteria
    selected_criteria = []
    if raw_q and raw_q.strip() and raw_q.strip().lower() not in ('any', 'all', ''):
        selected_criteria.append(('product_name', 'Product Name', raw_q, 40))
    if brand and brand.lower() not in ('any', 'all', 'all brands', ''):
        selected_criteria.append(('brand', 'Brand', brand, 25))
    if category and category.lower() not in ('any', 'all', ''):
        selected_criteria.append(('category', 'Category', category, 20))
    if price_min is not None or price_max is not None:
        p_label = f"₹{price_min or 0}–₹{price_max or '∞'}"
        selected_criteria.append(('price_range', 'Price Range', p_label, 15))
    if min_rating is not None:
        selected_criteria.append(('min_rating', 'Minimum Rating', f"{min_rating}★", 10))

    for skey, sval in spec_filters.items():
        if sval and str(sval).strip().lower() not in ('any', 'all', 'any ram', 'any storage', 'any processor', 'any battery', 'any display size', 'any color', 'any rating', 'any type', 'any feature', 'any connectivity', 'any mic', 'any shape', 'any strap', 'any appliance', 'any star rating', 'any capacity', 'any tech', 'any warranty', ''):
            s_pts = 15 if skey in ('ram', 'storage', 'processor') else (10 if skey in ('battery', 'display', 'type') else 5)
            s_label = skey.replace('_', ' ').title()
            selected_criteria.append((skey, s_label, str(sval), s_pts))

    total_specs_count = len(selected_criteria)

    processed = []
    for item in products:
        title_lower = item.get('title', '').lower()
        item_specs  = item.get('specs', {}) or {}
        item_brand  = str(item.get('brand') or item_specs.get('brand', '') or '')
        pn          = item.get('price_num')

        # Platform filter (Strict hardware filter if requested)
        if platform and platform not in ('any', 'all', ''):
            if item.get('platform', '').lower() != platform:
                continue

        match_score = 0
        matched_specs = []
        missing_specs = []
        matched_count = 0

        for key_type, label, target_val, pts in selected_criteria:
            is_matched = False

            if key_type == 'product_name':
                q_words = [w for w in target_val.lower().split() if len(w) > 2]
                if q_words and any(w in title_lower for w in q_words):
                    is_matched = True
            elif key_type == 'brand':
                if _brand_matches(target_val, title_lower, item_brand):
                    is_matched = True
            elif key_type == 'category':
                cat_words = [w for w in target_val.lower().split() if len(w) > 2]
                if cat_words and (any(w in title_lower for w in cat_words) or target_val.lower() in str(item_specs).lower()):
                    is_matched = True
            elif key_type == 'price_range':
                if pn is not None:
                    p_min_pass = price_min is None or pn >= price_min
                    p_max_pass = price_max is None or pn <= price_max
                    if p_min_pass and p_max_pass:
                        is_matched = True
            elif key_type == 'min_rating':
                ir = _safe_float(item.get('rating'))
                if ir > 0 and ir >= _safe_float(min_rating):
                    is_matched = True
            else:
                if _spec_matches(key_type, target_val, title_lower, item_specs):
                    is_matched = True

            if is_matched:
                match_score += pts
                matched_count += 1
                matched_specs.append(f"{label}: {target_val}")
            else:
                missing_specs.append(f"{label}: {target_val}")

        # Compute percentage & badge
        if total_specs_count > 0:
            match_pct = round((matched_count / total_specs_count) * 100)
            match_badge = f"Matches {matched_count} of {total_specs_count} specs"
        else:
            match_pct = 100
            match_badge = "100% Match"

        base_similarity = _safe_float(item.get('similarity_score'), 80.0)
        final_score = base_similarity + match_score

        item['match_score']           = match_score
        item['final_score']           = final_score
        item['match_count']           = matched_count
        item['total_specs_selected'] = total_specs_count
        item['match_pct']             = match_pct
        item['match_badge']           = match_badge
        item['matched_specs']         = matched_specs
        item['missing_specs']         = missing_specs

        processed.append(item)

    # Sort products by: Match Score (desc), Match Count (desc), Rating (desc), Price (asc)
    processed.sort(
        key=lambda x: (
            x.get('match_score', 0),
            x.get('match_count', 0),
            _safe_float(x.get('rating')),
            -1 * (x.get('price_num') or 9999999)
        ),
        reverse=True
    )

    return processed


def apply_filters(products: list, filter_params: dict) -> list:
    """Filter and score products using score_and_rank_products."""
    return score_and_rank_products(products, filter_params)




def parse_filter_params(request_args: dict) -> dict:
    """
    Parse filter parameters from Flask request.args into a clean filter_params dict.
    Handles price_range "min-max" format, category specifications, and numeric conversions.
    """
    params = {}

    category = request_args.get('category', '').strip()
    if category and category.lower() not in ('any', 'all', ''):
        params['category'] = category

    brand = request_args.get('brand', '').strip()
    if brand and brand.lower() not in ('any', 'all', ''):
        params['brand'] = brand

    price_range = request_args.get('price_range', '').strip()
    if price_range and '-' in price_range:
        parts = price_range.split('-')
        try:
            params['price_min'] = int(parts[0])
            params['price_max'] = int(parts[1])
        except (ValueError, IndexError):
            pass
    else:
        # Also support separate price_min / price_max params
        try:
            if request_args.get('price_min'):
                params['price_min'] = int(request_args.get('price_min'))
            if request_args.get('price_max'):
                params['price_max'] = int(request_args.get('price_max'))
        except (ValueError, TypeError):
            pass

    min_rating = request_args.get('min_rating', '').strip()
    if min_rating:
        try:
            params['min_rating'] = float(min_rating.rstrip('+'))
        except ValueError:
            pass

    min_discount = request_args.get('min_discount', '').strip()
    if min_discount:
        try:
            params['min_discount'] = int(min_discount.rstrip('%+'))
        except ValueError:
            pass

    platform = request_args.get('platform', '').strip()
    if platform and platform.lower() not in ('any', 'all', ''):
        params['platform'] = platform

    # Dynamic specs: any param named spec_<key>=<value> or known category spec keys
    spec_filters = {}
    known_spec_keys = {
        'ram', 'storage', 'processor', 'battery', 'display', 'color', 
        'type', 'anc', 'connectivity', 'mic', 'shape', 'features', 
        'strap', 'appliance_type', 'star_rating', 'capacity', 'tech', 'warranty'
    }
    for key, val in request_args.items():
        if not val or str(val).strip().lower() in ('any', 'all', ''):
            continue
        if key.startswith('spec_'):
            spec_filters[key[5:]] = str(val).strip()
        elif key in known_spec_keys:
            spec_filters[key] = str(val).strip()

    if spec_filters:
        params['specs'] = spec_filters

    return params

