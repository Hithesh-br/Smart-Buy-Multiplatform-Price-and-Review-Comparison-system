"""
product_matcher.py
==================
SmartBuy Weighted Product Matching Engine.

Implements strict, multi-signal weighted product comparison:
1. Exact model number (25%)
2. Brand identity (20%)
3. Product type / Category (10%)
4. Variant (RAM / Storage / Wattage / Size) (15%)
5. Weight / Capacity (10%)
6. Pack Quantity (5%)
7. Color (5%)
8. Key specifications overlap (5%)
9. Product name token similarity (5%)

Strictly discriminates:
- EXACT MATCH: All important attributes agree (score >= 88)
- VARIANT MATCH: Same product model/brand, but differs in storage, color, size, pack, or weight (score >= 75)
- SIMILAR PRODUCT: Same brand/category, different model/spec (score 55-74)
- NOT A MATCH: Below threshold (< 55) or conflicting models/brands
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional, List
from rapidfuzz import fuzz

from search.normalizer import (
    normalize_brand,
    normalize_model,
    normalize_title,
    normalize_weight,
    normalize_pack_quantity,
    strip_marketing_words,
)
from search.category_detector import detect_category

logger = logging.getLogger("smartbuy.product_matcher")


def generate_search_query_from_product(product: Dict[str, Any]) -> str:
    """
    Builds a concise, highly effective search query from a canonical product
    to search for the identical item on other platforms.
    Avoids bloated titles that cause marketplace search engines to return 0 results.
    """
    brand = product.get('brand') or ''
    if brand.lower() in ('generic', 'other', 'unknown', 'none'):
        brand = ''

    model = product.get('model') or ''
    if model.lower() in ('standard', 'n/a', 'none', 'general'):
        model = ''

    title = product.get('title') or product.get('product_name') or ''
    category = (product.get('category') or product.get('product_type') or detect_category(title=title)).lower()
    variant = product.get('variant') or {}

    parts = []
    if brand:
        parts.append(brand)

    # 1. Phone / Tablet
    if category in ('phone', 'mobile', 'smartphone', 'tablet'):
        if model:
            parts.append(model)
        storage = variant.get('storage')
        if storage:
            parts.append(storage)
        if not model:
            # Extract basic phone tokens
            m = re.search(r'\b(galaxy\s*[a-z0-9]+|iphone\s*\d+[a-z\s]*|pixel\s*\d[a-z]?|nord\s*[a-z0-9\s]+)\b', title, re.I)
            if m:
                parts.append(m.group(1).title())

    # 2. Laptop
    elif category in ('laptop', 'computer'):
        if model:
            parts.append(model)
        proc = variant.get('processor') or ''
        m_proc = re.search(r'\b(i[3579]|ryzen\s*[3579]|m[1234])\b', title, re.I)
        if m_proc:
            parts.append(m_proc.group(1).upper())

    # 3. Charger / Adapter
    elif category in ('charger', 'adapter', 'power_bank'):
        power = variant.get('power')
        if not power:
            m_pow = re.search(r'\b(\d+w)\b', title, re.I)
            if m_pow:
                power = m_pow.group(1).upper()
        if power:
            parts.append(power)
        parts.append("Charger")

    # 4. Beauty / Skincare / Grocery / Soap / Face wash
    elif category in ('soap', 'face_wash', 'beauty', 'skincare', 'grocery', 'food', 'shampoo'):
        # Check specific product noun
        t_low = title.lower()
        if 'face wash' in t_low or 'facewash' in t_low:
            parts.append("Face Wash")
        elif 'soap' in t_low:
            parts.append("Soap")
        elif 'shampoo' in t_low:
            parts.append("Shampoo")
        elif 'moisturizer' in t_low or 'cream' in t_low:
            parts.append("Moisturizer")
        elif model:
            parts.append(model)

        weight = product.get('weight') or variant.get('weight')
        if weight and weight not in ('Not Available', 'N/A'):
            parts.append(weight)

    # 5. Fashion / Shoes / Bags
    elif category in ('fashion', 'shoes', 'footwear', 'bags'):
        if model:
            parts.append(model)
        t_low = title.lower()
        for noun in ['shoes', 'sneakers', 'sandals', 'shirt', 't-shirt', 'jeans', 'kurta', 'backpack', 'handbag']:
            if noun in t_low:
                parts.append(noun.title())
                break
        size = product.get('size') or variant.get('size')
        if size and len(str(size)) <= 6:
            parts.append(f"Size {size}")

    # Fallback to concise title tokens
    if len(parts) < 2 or (len(parts) == 1 and not model):
        clean = strip_marketing_words(title)
        tokens = [t for t in clean.split() if len(t) > 1 and not re.match(r'^(with|for|and|the|best|new|original)$', t, re.I)]
        query_str = " ".join(tokens[:5])
        return query_str.strip() or title[:50]

    return " ".join(parts).strip()


def compute_weighted_match_score(
    canonical: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[float, str, Dict[str, float]]:
    """
    Computes strict multi-signal weighted match score between canonical product and candidate.
    Returns: (score [0-100], match_class, breakdown_dict)
    """
    breakdown: Dict[str, float] = {}

    t_can = strip_marketing_words(normalize_title(canonical.get('title') or canonical.get('product_name') or ''))
    t_cand = strip_marketing_words(normalize_title(candidate.get('title') or candidate.get('product_name') or ''))

    # 1. Brand Score (20 pts)
    b_can = normalize_brand(canonical.get('brand'))
    b_cand = normalize_brand(candidate.get('brand'))
    if b_can and b_cand:
        if b_can.lower() == b_cand.lower():
            brand_score = 20.0
        elif b_can.lower() in b_cand.lower() or b_cand.lower() in b_can.lower():
            brand_score = 17.0
        else:
            # Conflicting brands -> 0 pts
            brand_score = 0.0
    elif b_can or b_cand:
        brand_score = 10.0
    else:
        brand_score = 15.0
    breakdown['brand'] = brand_score

    # 2. Model Score (25 pts)
    m_can = (canonical.get('model') or '').strip()
    m_cand = (candidate.get('model') or '').strip()
    if m_can and m_can.lower() not in ('standard', 'n/a', 'none', 'general') and \
       m_cand and m_cand.lower() not in ('standard', 'n/a', 'none', 'general'):
        if m_can.lower() == m_cand.lower():
            model_score = 25.0
        else:
            # Check if one is a clean substring of another
            if m_can.lower() in m_cand.lower() or m_cand.lower() in m_can.lower():
                model_score = 18.0
            else:
                model_score = 0.0  # Conflicting models
    elif not m_can or m_can.lower() in ('standard', 'n/a', 'none', 'general'):
        # Category without explicit model (e.g. food/shampoo)
        model_score = 20.0
    else:
        # Check if candidate title explicitly contains the canonical model
        if m_can.lower() in t_cand.lower():
            model_score = 20.0
        else:
            model_score = 5.0
    breakdown['model'] = model_score

    # 3. Product Type / Category Score (10 pts)
    cat_can = (canonical.get('category') or canonical.get('product_type') or 'other').lower()
    cat_cand = (candidate.get('category') or candidate.get('product_type') or 'other').lower()
    if cat_can == cat_cand and cat_can != 'other':
        cat_score = 10.0
    elif cat_can == 'other' or cat_cand == 'other':
        cat_score = 6.0
    else:
        cat_score = 0.0
    breakdown['category'] = cat_score

    # 4. Variant Score (RAM / Storage / Wattage) (15 pts)
    v_can = canonical.get('variant') or {}
    v_cand = candidate.get('variant') or {}
    has_variant_conflict = False

    # Check power/wattage (e.g. 44W vs 18W)
    p_can = v_can.get('power') or re.search(r'\b(\d+w)\b', t_can, re.I)
    p_cand = v_cand.get('power') or re.search(r'\b(\d+w)\b', t_cand, re.I)
    p_can_val = p_can.group(1).upper() if hasattr(p_can, 'group') else (str(p_can).upper() if p_can else None)
    p_cand_val = p_cand.group(1).upper() if hasattr(p_cand, 'group') else (str(p_cand).upper() if p_cand else None)
    if p_can_val and p_cand_val and p_can_val != p_cand_val:
        has_variant_conflict = True

    # Check storage (128GB vs 256GB)
    st_can = v_can.get('storage')
    st_cand = v_cand.get('storage')
    if st_can and st_cand and st_can.lower() != st_cand.lower():
        has_variant_conflict = True

    # Check RAM (8GB vs 12GB)
    ram_can = v_can.get('ram')
    ram_cand = v_cand.get('ram')
    if ram_can and ram_cand and ram_can.lower() != ram_cand.lower():
        has_variant_conflict = True

    # Check 5G vs 4G
    is_5g_can = "5g" in t_can.lower()
    is_5g_cand = "5g" in t_cand.lower()
    is_4g_can = "4g" in t_can.lower()
    is_4g_cand = "4g" in t_cand.lower()
    if (is_5g_can and is_4g_cand and not is_5g_cand) or (is_4g_can and is_5g_cand and not is_5g_can):
        has_variant_conflict = True

    variant_score = 0.0 if has_variant_conflict else 15.0
    breakdown['variant'] = variant_score

    # 5. Weight / Capacity Score (10 pts)
    w_can = normalize_weight(canonical.get('weight') or v_can.get('weight') or t_can)
    w_cand = normalize_weight(candidate.get('weight') or v_cand.get('weight') or t_cand)
    is_weight_sensitive = cat_can in ('soap', 'face_wash', 'grocery', 'food', 'beauty', 'skincare', 'shampoo')
    has_weight_conflict = False
    if w_can and w_cand:
        if w_can == w_cand:
            weight_score = 10.0
        else:
            weight_score = 0.0
            has_weight_conflict = True
    elif not is_weight_sensitive:
        weight_score = 10.0
    else:
        weight_score = 5.0
    breakdown['weight'] = weight_score

    # 6. Pack Quantity Score (5 pts)
    pq_can = str(canonical.get('pack_quantity') or v_can.get('pack_quantity') or normalize_pack_quantity(t_can) or '1')
    pq_cand = str(candidate.get('pack_quantity') or v_cand.get('pack_quantity') or normalize_pack_quantity(t_cand) or '1')
    has_pack_conflict = False
    if pq_can != pq_cand:
        pack_score = 0.0
        has_pack_conflict = True
    else:
        pack_score = 5.0
    breakdown['pack_quantity'] = pack_score

    # 7. Color Score (5 pts)
    c_can = (canonical.get('color') or v_can.get('color') or '').lower()
    c_cand = (candidate.get('color') or v_cand.get('color') or '').lower()
    has_color_conflict = False
    if c_can and c_cand:
        if c_can == c_cand:
            color_score = 5.0
        else:
            color_score = 1.0
            has_color_conflict = True
    else:
        color_score = 4.0
    breakdown['color'] = color_score

    # 8. Specifications Overlap (5 pts)
    specs_can = canonical.get('specifications') or {}
    specs_cand = candidate.get('specifications') or {}
    matching_specs = 0
    total_checked = 0
    for k, v in specs_can.items():
        if k in specs_cand:
            total_checked += 1
            if str(v).strip().lower() == str(specs_cand[k]).strip().lower():
                matching_specs += 1
    if total_checked > 0:
        specs_score = round((matching_specs / total_checked) * 5.0, 1)
    else:
        specs_score = 4.0
    breakdown['specifications'] = specs_score

    # 9. Cleaned Title Token Similarity (5 pts)
    title_ratio = fuzz.token_set_ratio(t_can, t_cand) / 100.0
    title_score = round(title_ratio * 5.0, 1)
    breakdown['title_similarity'] = title_score

    total_score = round(sum(breakdown.values()), 1)
    total_score = max(0.0, min(100.0, total_score))

    # Immediate disqualification on hard brand mismatch
    if breakdown['brand'] == 0.0 and b_can and b_cand:
        total_score = min(total_score, 40.0)
        return total_score, "Not a Match", breakdown

    # Immediate disqualification on hard model mismatch
    if breakdown['model'] == 0.0 and m_can and m_cand:
        total_score = min(total_score, 45.0)
        return total_score, "Not a Match", breakdown

    # Classification
    is_variant = has_variant_conflict or has_weight_conflict or has_pack_conflict or has_color_conflict

    if total_score >= 88 and not is_variant:
        classification = "Exact Match"
    elif total_score >= 70 or (total_score >= 60 and is_variant):
        classification = "Variant" if is_variant else "Strong Match"
    elif total_score >= 50:
        classification = "Similar Product"
    else:
        classification = "Not a Match"

    return total_score, classification, breakdown


def match_canonical_against_platform_results(
    canonical: Dict[str, Any],
    candidate_products: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Takes candidate products from another platform and finds:
    - Best exact/strong match (if any)
    - List of similar products (if no exact match, or as supplementary items)
    """
    scored = []
    for cand in candidate_products:
        score, cl, breakdown = compute_weighted_match_score(canonical, cand)
        cand_copy = dict(cand)
        cand_copy['match_score'] = score
        cand_copy['match_type'] = cl
        cand_copy['match_breakdown'] = breakdown
        scored.append(cand_copy)

    # Sort descending by match score
    scored.sort(key=lambda x: x['match_score'], reverse=True)

    exact_matches = [p for p in scored if p['match_type'] in ('Exact Match', 'Variant', 'Strong Match') and p['match_score'] >= 70]
    similar_products = [p for p in scored if p['match_type'] == 'Similar Product' or (p['match_score'] >= 50 and p not in exact_matches)]

    best_match = exact_matches[0] if exact_matches else None

    return {
        "best_match": best_match,
        "exact_matches": exact_matches,
        "similar_products": similar_products[:5],
        "has_exact_match": best_match is not None and best_match['match_type'] == 'Exact Match',
        "has_variant_match": best_match is not None and best_match['match_type'] == 'Variant',
    }
