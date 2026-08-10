"""
search/matching.py
==================
Adaptive similarity scoring using RapidFuzz.
Supports ANY product type — no hardcoded brand/model guards.

Algorithm:
    1. Normalize query and title
    2. Detect query type to pick threshold
    3. Compute weighted score from multiple RapidFuzz metrics
    4. Return score 0.0 – 100.0
"""

import re
from rapidfuzz import fuzz
from search.normalizer import (
    normalize_title,
    normalize_query,
    strip_marketing_words,
    detect_query_type,
    _UNIT_PATTERNS,
    _MODEL_CODE_PATTERN,
)

ACCESSORY_KEYWORDS = {'case', 'cover', 'protector', 'skin', 'guard', 'cable', 
                      'charger', 'strap', 'band', 'glass', 'sleeve', 'backcover'}


# ---------------------------------------------------------------------------
# Threshold Configuration
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "generic":     10,
    "category":    20,
    "specific":    30,
    "brand_model": 40,
}


def get_adaptive_threshold(query: str) -> float:
    """Return the appropriate similarity threshold for the given query."""
    query_type = detect_query_type(query)
    return THRESHOLDS.get(query_type, 20)


# ---------------------------------------------------------------------------
# Core Similarity Computation
# ---------------------------------------------------------------------------

def calculate_similarity(query: str, title: str) -> float:
    """
    Calculate product similarity score.
    Supports ANY product type and prevents false rejections of valid e-commerce search results.
    """
    if not query or not title:
        return 0.0

    norm_q = normalize_query(query)
    norm_t = normalize_title(title)

    if not norm_q or not norm_t:
        return 0.0

    q_tokens = set(norm_q.split())
    t_tokens = set(norm_t.split())

    # 1. Anti-Pattern: Accessory rejection
    # If title is an accessory but query didn't ask for one, reject instantly
    q_has_acc = any(k in q_tokens for k in ACCESSORY_KEYWORDS)
    t_has_acc = any(k in t_tokens for k in ACCESSORY_KEYWORDS)
    if t_has_acc and not q_has_acc:
        return 0.0

    # 2. Generic / Category Query Check
    # If the user query is generic (e.g. 'mobile', 'laptop', 'shoes', 'shirt', 'headphones'),
    # any non-accessory item returned by e-commerce search is relevant.
    query_type = detect_query_type(query)
    if query_type in ("generic", "category"):
        # Check token intersection or partial match
        if q_tokens.intersection(t_tokens) or any(qt in norm_t for qt in q_tokens if len(qt) > 2):
            return 100.0
        return 80.0

    # 3. Model & Token Scoring
    clean_t = strip_marketing_words(norm_t)
    if not clean_t:
        clean_t = norm_t

    # 4. RapidFuzz Scoring
    # Use token_set_ratio as primary indicator (checks if query words exist in title)
    tset = fuzz.token_set_ratio(norm_q, clean_t)
    partial = fuzz.partial_ratio(norm_q, clean_t)

    # If any core brand token (e.g. apple, samsung, dell, sony, lg, hp) matches, ensure base score is good
    brand_keywords = {'apple', 'samsung', 'xiaomi', 'redmi', 'poco', 'realme', 'oneplus', 
                      'vivo', 'oppo', 'motorola', 'dell', 'hp', 'lenovo', 'asus', 'acer', 
                      'sony', 'lg', 'jbl', 'boat', 'noise', 'bose', 'iphone', 'galaxy'}
    q_brands = q_tokens.intersection(brand_keywords)
    t_brands = t_tokens.intersection(brand_keywords)
    if q_brands and (q_brands.intersection(t_brands) or any(qb in norm_t for qb in q_brands)):
        tset = max(tset, 75.0)

    score = max(tset, partial)
    return round(float(score), 2)


def is_relevant(query: str, title: str, threshold: float = None) -> tuple[bool, float]:
    """
    Determine if a product is relevant to the query.
    """
    if threshold is None:
        threshold = get_adaptive_threshold(query)

    score = calculate_similarity(query, title)
    return (score >= threshold, score)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_products(products: list) -> list:
    """
    Remove duplicate products by (normalized_title, platform) key.
    Keeps the first occurrence (highest ranked by caller).
    """
    seen = set()
    unique = []
    for item in products:
        norm_t = normalize_title(item.get('title', ''))
        plat   = item.get('platform', '')
        key    = (norm_t, plat)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def cross_platform_deduplicate(products: list, similarity_threshold: float = 90.0) -> list:
    """
    Remove cross-platform duplicates where the same physical product appears
    on multiple platforms with slightly different titles.
    Keeps lowest-priced version when duplicates are found.

    Only applied to the 'all results' combined view, not per-platform views.
    """
    if not products:
        return products

    result = []
    for item in products:
        norm_t = normalize_title(item.get('title', ''))
        is_dup = False
        for existing in result:
            existing_norm = normalize_title(existing.get('title', ''))
            if fuzz.token_set_ratio(norm_t, existing_norm) >= similarity_threshold:
                # Keep the one with the lower price
                item_price   = item.get('price_num') or float('inf')
                exist_price  = existing.get('price_num') or float('inf')
                if item_price < exist_price:
                    result.remove(existing)
                    result.append(item)
                is_dup = True
                break
        if not is_dup:
            result.append(item)
    return result
