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
from search.category_detector import detect_category, get_category_family
from search.query_parser import extract_specific_product_type, KNOWN_BRANDS

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
    model = re.sub(r'[\u200b-\u200f\ufeff]', '', str(model)).strip()
    if '/' in model or len(model) > 25 or model.lower() in ('standard', 'n/a', 'none', 'general'):
        model = ''

    title = product.get('title') or product.get('product_name') or ''
    category = (product.get('category') or product.get('product_type') or detect_category(title=title)).lower()
    variant = product.get('variant') or {}

    if not model and category in ('phone', 'mobile', 'smartphone', 'tablet', 'laptop', 'computer'):
        m_phone = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|galaxy\s*[a-z]\d{1,2}(?:\s*5g|\s*4g)?|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|pixel\s*\d[a-z]?|t\d(?:\s*5g|\s*pro|\s*lite)?|nord(?:\s*ce)?\s*\d[a-z]?)\b', title, re.I)
        if m_phone:
            model = m_phone.group(0).strip()

    parts = []
    if brand:
        parts.append(brand)

    # 0. Pen Drive / USB Flash Drive / Storage Device
    cat_norm = category.replace(" ", "_")
    if cat_norm in ('pen_drive', 'storage_device', 'flash_drive', 'pendrive') or 'storage' in category or 'pen_drive' in cat_norm or 'pen' in category or 'flash' in category:
        if not model:
            # Extract model codes like v222w, cz50, etc.
            m_code = re.search(r'\b([a-z]\d{2,4}[a-z]?|[a-z]{2,4}\d{2,4}[a-z]?)\b', title, re.I)
            if m_code:
                model = m_code.group(1).lower()
        if model:
            parts.append(model)
        cap = variant.get('storage') or variant.get('capacity') or product.get('storage') or product.get('capacity')
        if not cap:
            m_cap = re.search(r'\b(\d{1,4})\s*(gb|tb)\b', title, re.I)
            if m_cap:
                cap = f"{m_cap.group(1)}{m_cap.group(2).upper()}"
        if cap:
            parts.append(str(cap).replace(" ", ""))
        parts.append("pen drive")

    # 1. Phone / Tablet
    elif category in ('phone', 'mobile', 'smartphone', 'tablet'):
        if not model:
            # Extract basic phone tokens
            m = re.search(r'\b(t\d+[a-z]?(?:\s*5g|\s*lite|\s*pro)?|v\d+[a-z]?(?:\s*5g|\s*pro)?|y\d+[a-z]?(?:\s*5g)?|galaxy\s*[a-z0-9]+|iphone\s*\d+[a-z\s]*|pixel\s*\d[a-z]?|nord\s*[a-z0-9\s]+|narzo\s*[a-z0-9\s]+|redmi\s*[a-z0-9\s]+)\b', title, re.I)
            if m:
                model = m.group(1).strip()
        if model:
            parts.append(model)
        storage = variant.get('storage') or product.get('storage')
        if not storage:
            m_st = re.search(r'\b(\d{2,4})\s*(gb|tb)\b', title, re.I)
            if m_st:
                storage = f"{m_st.group(1)}{m_st.group(2).upper()}"
        if storage:
            parts.append(str(storage).replace(" ", "").upper())

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

    # 4. Beauty / Skincare / Soap / Face wash
    elif category in ('soap', 'face_wash', 'beauty', 'skincare', 'shampoo'):
        t_low = title.lower()
        if 'face wash' in t_low or 'facewash' in t_low:
            if 'acne star' in t_low or 'acnestar' in t_low:
                parts.append("Acne Star Facewash")
                if 'anti pigm' in t_low or 'anti pigmentation' in t_low:
                    parts.append("Anti Pigmentation")
                if 'oil control' in t_low:
                    parts.append("Oil Control")
            elif 'hydrat' in t_low and 'beard' in t_low:
                parts.append("Hydrating Face & Beard Wash")
            elif 'zit blocker' in t_low:
                parts.append("Zit Blocker Face Wash")
            else:
                parts.append("Face Wash")
        elif 'soap' in t_low:
            parts.append("Soap")
        elif 'shampoo' in t_low:
            parts.append("Shampoo")
        elif 'moisturizer' in t_low or 'cream' in t_low:
            parts.append("Moisturizer")
        elif model:
            parts.append(model)

        # Check for pack count (e.g. Pack-2, Pack of 2)
        m_pk = re.search(r'\b(?:pack[\s-]*(?:of[\s-]*)?|pack-)(\d+)\b', t_low)
        if m_pk:
            parts.append(f"Pack {m_pk.group(1)}")

        weight = product.get('weight') or variant.get('weight')
        if weight and weight not in ('Not Available', 'N/A'):
            parts.append(weight)

    # 4b. Grocery / Food / Dry Fruits / Cooking Oil
    elif category in ('grocery', 'food', 'dry_fruits', 'cooking_oil') or 'grocery' in category:
        t_low = title.lower()
        ptype = extract_specific_product_type(title, category)
        if ptype and ptype != 'other':
            parts.append(ptype.replace('_', ' ').title())
        elif model:
            parts.append(model)

        # Variant keywords like roasted, salted, cold pressed, virgin
        if 'roasted' in t_low and 'salted' in t_low:
            parts.append("Roasted & Salted")
        elif 'cold pressed' in t_low:
            parts.append("Cold Pressed")

        weight = product.get('weight') or variant.get('weight')
        if not weight:
            m_wt = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg|l|ltr|litre|ml))\b', t_low)
            if m_wt:
                weight = m_wt.group(0)
        if weight and weight not in ('Not Available', 'N/A'):
            parts.append(weight)

    # 5. Fashion / Shoes / Bags / Clothing
    elif category in ('fashion', 'shoes', 'footwear', 'bags', 'clothing'):
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

    # 6. Water Bottles & Flasks
    elif cat_norm in ('water_bottle', 'bottle', 'flask') or 'bottle' in category or 'flask' in category:
        t_low = title.lower()
        if model:
            parts.append(model)
        m_mat = re.search(r'\b(stainless\s*steel|copper|glass|borosilicate|plastic|steel)\b', t_low)
        if m_mat:
            parts.append(m_mat.group(0).title())
        elif product.get('material'):
            parts.append(str(product['material']).title())
        parts.append("Water Bottle")
        m_cap = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?|ml)\b', t_low)
        if m_cap:
            parts.append(m_cap.group(0).upper())
        elif product.get('capacity'):
            parts.append(str(product['capacity']).upper())

    # Fallback to concise title tokens
    if len(parts) < 2 or (len(parts) == 1 and not model):
        clean = strip_marketing_words(title)
        clean = re.sub(r'\(.*?\)', '', clean)
        clean = re.sub(r'[\(\[\{][^\)\]\}]*$', '', clean)
        clean = re.sub(r'[,/|\-]+', ' ', clean).strip()
        tokens = [t for t in clean.split() if len(t) > 1 and not re.match(r'^(with|for|and|the|best|new|original)$', t, re.I)]
        query_str = " ".join(tokens[:5])
        return query_str.strip() or title[:50]

    raw_query = " ".join(parts).strip()
    raw_query = re.sub(r'\(.*?\)', '', raw_query)
    raw_query = re.sub(r'[\(\[\{][^\)\]\}]*$', '', raw_query)
    raw_query = re.sub(r'[,/|\-]+', ' ', raw_query).strip()
    raw_query = re.sub(r'\s+', ' ', raw_query).strip()
    return raw_query


def generate_search_query_cascade(product: Dict[str, Any]) -> List[str]:
    """
    Generates an intelligent multi-query fallback cascade for cross-platform search.
    Example for HP v222w 128GB Pen Drive:
    1. HP v222w 128GB pen drive
    2. HP v222w 128 GB USB flash drive
    3. HP v222w 128GB
    4. HP v222w pen drive
    5. HP 128GB v222w
    """
    brand = product.get('brand') or ''
    if brand.lower() in ('generic', 'other', 'unknown', 'none'):
        brand = ''

    model = product.get('model') or ''
    model = re.sub(r'[\u200b-\u200f\ufeff]', '', str(model)).strip()
    if '/' in model or len(model) > 25 or model.lower() in ('standard', 'n/a', 'none', 'general'):
        model = ''

    title = product.get('title') or product.get('product_name') or ''
    category = (product.get('category') or product.get('product_type') or detect_category(title=title)).lower()
    variant = product.get('variant') or {}

    if not model and category in ('phone', 'mobile', 'smartphone', 'tablet', 'laptop', 'computer'):
        m_phone = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|galaxy\s*[a-z]\d{1,2}(?:\s*5g|\s*4g)?|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|pixel\s*\d[a-z]?|t\d(?:\s*5g|\s*pro|\s*lite)?|nord(?:\s*ce)?\s*\d[a-z]?)\b', title, re.I)
        if m_phone:
            model = m_phone.group(0).strip()

    queries: List[str] = []

    # Pen Drive / Storage Device cascade
    cat_norm = category.replace(" ", "_")
    if cat_norm in ('pen_drive', 'storage_device', 'flash_drive', 'pendrive') or 'storage' in category or 'pen_drive' in cat_norm or 'pen' in category or 'flash' in category:
        if not model:
            m_code = re.search(r'\b([a-z]\d{2,4}[a-z]?|[a-z]{2,4}\d{2,4}[a-z]?)\b', title, re.I)
            if m_code:
                model = m_code.group(1).lower()

        cap = variant.get('storage') or variant.get('capacity') or product.get('storage') or product.get('capacity')
        if not cap:
            m_cap = re.search(r'\b(\d{1,4})\s*(gb|tb)\b', title, re.I)
            if m_cap:
                cap = f"{m_cap.group(1)}{m_cap.group(2).upper()}"

        b_str = brand.strip()
        m_str = model.strip()
        c_str = str(cap).replace(" ", "").upper() if cap else ""

        if b_str and m_str and c_str:
            queries.append(f"{b_str} {m_str} {c_str} pen drive")
            queries.append(f"{b_str} {m_str} {c_str} USB flash drive")
            queries.append(f"{b_str} {m_str} {c_str}")
            queries.append(f"{b_str} {m_str} pen drive")
            queries.append(f"{b_str} {c_str} {m_str}")
        elif b_str and m_str:
            queries.append(f"{b_str} {m_str} pen drive")
            queries.append(f"{b_str} {m_str} USB flash drive")
            queries.append(f"{b_str} {m_str}")
        elif b_str and c_str:
            queries.append(f"{b_str} {c_str} pen drive")
            queries.append(f"{b_str} {c_str} USB flash drive")
        else:
            queries.append(generate_search_query_from_product(product))

    # Water Bottle / Flask cascade
    elif cat_norm in ('water_bottle', 'bottle', 'flask') or 'bottle' in category or 'flask' in category:
        t_low = title.lower()
        m_mat = re.search(r'\b(stainless\s*steel|copper|glass|plastic|steel)\b', t_low)
        mat = m_mat.group(0).title() if m_mat else (str(product.get('material', '')).title() if product.get('material') else "")
        m_cap = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?|ml)\b', t_low)
        cap = m_cap.group(0).upper() if m_cap else (str(product.get('capacity', '')).upper() if product.get('capacity') else "")

        b_str = brand.strip()
        m_str = model.strip()

        if b_str and m_str and cap:
            queries.append(f"{b_str} {m_str} {cap}")
            queries.append(f"{b_str} {mat} water bottle {cap}".strip())
            queries.append(f"{b_str} water bottle {cap}".strip())
        elif b_str and mat and cap:
            queries.append(f"{b_str} {mat} water bottle {cap}")
            queries.append(f"{b_str} water bottle {cap}")
            queries.append(f"{mat} water bottle {cap}")
        elif b_str and cap:
            queries.append(f"{b_str} water bottle {cap}")
            queries.append(f"{b_str} water bottle")
        elif b_str and mat:
            queries.append(f"{b_str} {mat} water bottle")
            queries.append(f"{b_str} water bottle")
        elif mat and cap:
            queries.append(f"{mat} water bottle {cap}")
            queries.append(f"{mat} water bottle")
        else:
            queries.append(generate_search_query_from_product(product))

    # Face Wash / Cleanser cascade
    elif cat_norm in ('face_wash', 'facewash') or 'face_wash' in category or 'face wash' in category or 'facewash' in category:
        t_low = title.lower()
        b_str = brand.strip()
        m_str = model.strip()
        wt = product.get('weight') or variant.get('weight')
        if not wt or str(wt) in ('Not Available', 'N/A'):
            m_wt = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|ml))\b', t_low)
            wt = m_wt.group(0) if m_wt else ""
        wt_str = str(wt).strip() if wt else ""

        # Extract pack count if present
        m_pk = re.search(r'\b(?:pack[\s-]*(?:of[\s-]*)?|pack-)(\d+)\b', t_low)
        pk_num = m_pk.group(1) if m_pk else ""
        pk_suffix = f" Pack {pk_num}" if pk_num else ""
        pk_of_suffix = f" Pack of {pk_num}" if pk_num else ""

        if b_str:
            if 'acne star' in t_low or 'acnestar' in t_low:
                if pk_num:
                    queries.append(f"{b_str} Acne Star Facewash Anti Pigmentation Acne Clear Oil Control{pk_suffix}".strip())
                    queries.append(f"{b_str} Acne Star Face Wash{pk_suffix}".strip())
                    queries.append(f"{b_str} Acne Star Face Wash{pk_of_suffix}".strip())
                    queries.append(f"{b_str} Face Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Acne Star Facewash Anti Pigmentation")
                queries.append(f"{b_str} Acne Star Face Wash")
                queries.append(f"{b_str} Face Wash")
            elif 'hydrat' in t_low and 'beard' in t_low:
                queries.append(f"{b_str} Hydrating Face & Beard Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Hydrating Face Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Face Beard Wash")
                if 'acne' in t_low or 'tan' in t_low:
                    queries.append(f"{b_str} Acne Tan Control Face Wash")
                if wt_str:
                    queries.append(f"{b_str} {wt_str} Face Wash")
                queries.append(f"{b_str} Face Wash")
            elif 'acne' in t_low or 'tan' in t_low:
                queries.append(f"{b_str} Acne Tan Control Face Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Face Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Face Wash")
            elif m_str:
                queries.append(f"{b_str} {m_str} Face Wash{pk_suffix}".strip())
                queries.append(f"{b_str} Face Wash")
            else:
                queries.append(f"{b_str} Face Wash{pk_suffix}".strip())
                if wt_str:
                    queries.append(f"{b_str} {wt_str} Face Wash")
                queries.append(f"{b_str} Face Wash")
        else:
            queries.append(generate_search_query_from_product(product))

    # Grocery / Dry Fruits / Cooking Oil cascade
    elif cat_norm in ('grocery', 'food', 'dry_fruits', 'cooking_oil') or 'grocery' in category:
        t_low = title.lower()
        b_str = brand.strip()
        ptype = extract_specific_product_type(title, category)
        ptype_clean = ptype.replace('_', ' ').title() if ptype and ptype != 'other' else ""
        wt = product.get('weight') or variant.get('weight')
        if not wt or str(wt) in ('Not Available', 'N/A'):
            m_wt = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg|l|ltr|litre|ml))\b', t_low)
            wt = m_wt.group(0) if m_wt else ""
        wt_str = str(wt).strip() if wt else ""

        if b_str and ptype_clean and wt_str:
            queries.append(f"{b_str} Premium {ptype_clean} {wt_str}")
            queries.append(f"{b_str} {ptype_clean} {wt_str}")
            if 'roasted' in t_low and 'salted' in t_low:
                queries.append(f"{b_str} Roasted & Salted {ptype_clean} {wt_str}")
            queries.append(f"{b_str} {ptype_clean}")
        elif b_str and ptype_clean:
            queries.append(f"{b_str} {ptype_clean}")
        elif b_str and wt_str:
            queries.append(f"{b_str} {wt_str}")
        else:
            queries.append(generate_search_query_from_product(product))

    # Phone / Tablet cascade
    elif category in ('phone', 'mobile', 'smartphone', 'tablet'):
        b_str = brand.strip()
        m_str = model.strip()
        if not m_str:
            m_phone = re.search(r'\b(t\d+[a-z]?(?:\s*5g|\s*lite|\s*pro)?|v\d+[a-z]?(?:\s*5g|\s*pro)?|y\d+[a-z]?(?:\s*5g)?|galaxy\s*[a-z0-9]+|iphone\s*\d+[a-z\s]*|pixel\s*\d[a-z]?|nord\s*[a-z0-9\s]+|narzo\s*[a-z0-9\s]+|redmi\s*[a-z0-9\s]+)\b', title, re.I)
            if m_phone:
                m_str = m_phone.group(0).strip()

        cap = variant.get('storage') or product.get('storage')
        if not cap:
            m_cap = re.search(r'\b(\d{2,4})\s*(gb)\b', title, re.I)
            if m_cap:
                cap = f"{m_cap.group(1)}{m_cap.group(2).upper()}"

        if b_str and m_str and cap:
            queries.append(f"{b_str} {m_str} {cap}")
            queries.append(f"{m_str} {cap}")
            queries.append(f"{b_str} {m_str}")
            queries.append(f"{m_str}")
        elif b_str and m_str:
            queries.append(f"{b_str} {m_str}")
            queries.append(f"{m_str}")
        else:
            base_q = generate_search_query_from_product(product)
            queries.append(base_q)
            words = base_q.split()
            if len(words) > 3:
                queries.append(" ".join(words[:3]))

    # Clothing / Fashion cascade
    elif cat_norm in ('fashion', 'clothing', 'shoes', 'footwear', 'bags') or category in ('fashion', 'clothing'):
        clean_title = strip_marketing_words(title)
        clean_title = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]?', '', clean_title)
        clean_title = re.sub(r'[,/|\-]+', ' ', clean_title).strip()
        tokens = [t for t in clean_title.split() if len(t) > 1 and not re.match(r'^(with|for|and|the|best|new|original)$', t, re.I)]
        b_str = brand.strip() if brand and brand.lower() not in ('generic', 'women', 'men', 'kids', 'other') else ''
        if b_str and len(tokens) >= 2:
            queries.append(f"{b_str} {' '.join(tokens[:4])}".strip())
        if len(tokens) >= 3:
            queries.append(" ".join(tokens[:4]))
            queries.append(" ".join(tokens[:3]))
        if len(tokens) >= 2:
            queries.append(" ".join(tokens[:2]))
        queries.append(generate_search_query_from_product(product))

    else:
        # Standard cascade
        base_q = generate_search_query_from_product(product)
        queries.append(base_q)
        if brand and model:
            queries.append(f"{brand} {model}")

    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        cleaned = q.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique_queries.append(cleaned)

    return unique_queries or [generate_search_query_from_product(product)]


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

    cat_can = (canonical.get('category') or canonical.get('product_type') or detect_category(title=t_can)).lower()
    cat_cand = (candidate.get('category') or candidate.get('product_type') or detect_category(title=t_cand)).lower()

    cat_can_norm = cat_can.lower().replace(" ", "_")

    # Hard rejection: Animal / Pet Product vs Human Product
    fam_can = get_category_family(cat_can)
    fam_cand = get_category_family(cat_cand)
    is_pet_target = fam_can == "pet" or cat_can == "pet_supplies"
    has_cand_animal = bool(re.search(r'\b(pigs?|pigerry|swine|piglets?|boar|sow|fish\s*food|fish\s*feed|aquarium|pellet\s*fish|goldfish|royal\s*oscar|dog\s*food|cat\s*food|puppy|kitten|bird\s*food|animal\s*feed|cattle\s*feed|poultry\s*feed|veterinary|livestock|aquatic\s*feed)\b', t_cand.lower()))
    if not is_pet_target and has_cand_animal:
        return 0.0, "Not a Match", {"rejection": 0.0, "reason": "Animal/Pet product conflict"}

    # Hard rejection: Incompatible Category Families
    if fam_can != "other" and fam_cand != "other" and fam_can != fam_cand:
        return 0.0, "Not a Match", {"rejection": 0.0, "reason": "Category family conflict"}

    # Hard rejection: Specific Product Type Incompatibility
    type_can = canonical.get('product_type') or extract_specific_product_type(t_can, cat_can)
    type_cand = candidate.get('product_type') or extract_specific_product_type(t_cand, cat_cand)
    if type_can and type_can != "other":
        if type_cand and type_cand != "other" and type_cand != type_can:
            return 0.0, "Not a Match", {"rejection": 0.0, "reason": "Product type mismatch"}

    # Hard rejection: Brand Conflict
    b_can_norm = normalize_brand(canonical.get('brand'))
    b_cand_norm = normalize_brand(candidate.get('brand'))
    if b_can_norm and b_can_norm.lower() not in ('generic', 'none', 'unknown', ''):
        if b_cand_norm and b_cand_norm.lower() not in ('generic', 'none', 'unknown', ''):
            if b_can_norm.lower() != b_cand_norm.lower() and b_can_norm.lower() not in b_cand_norm.lower() and b_cand_norm.lower() not in b_can_norm.lower():
                return 0.0, "Not a Match", {"brand": 0.0, "rejection": 0.0, "reason": "Brand conflict"}
        elif not re.search(r'\b' + re.escape(b_can_norm.lower()) + r'\b', t_cand.lower()):
            m_can_chk = (canonical.get('model') or '').strip()
            if not m_can_chk or m_can_chk.lower() not in t_cand.lower():
                return 0.0, "Not a Match", {"brand": 0.0, "rejection": 0.0, "reason": "Brand missing from candidate"}

    # Hard rejection of unrelated accessories/devices when comparing storage devices
    if any(k in cat_can_norm for k in ('pen_drive', 'storage', 'flash_drive')) or 'pen drive' in t_can.lower():
        if re.search(r'\b(printer|printers|cable|cables|hdmi|vga|aux|displayport|laptop|desktop|monitor|camera)\b', t_cand.lower()) and not re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive|thumb\s*drive|usb\s*drive)\b', t_cand.lower()):
            return 0.0, "Not a Match", {"brand": 0.0, "category": 0.0, "rejection": 0.0}

    # Hard rejection of unrelated accessories when comparing water bottles
    if any(k in cat_can_norm for k in ('water_bottle', 'bottle', 'flask')) or 'water bottle' in t_can.lower():
        if re.search(r'\b(brush|cleaner|pouch|sleeve|cover|holder|stand|strap|stickers?)\b', t_cand.lower()):
            if not re.search(r'\b(brush|cleaner|pouch|sleeve|cover|holder|stand|strap|stickers?)\b', t_can.lower()):
                return 0.0, "Not a Match", {"brand": 0.0, "category": 0.0, "rejection": 0.0}

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

    # Check bottle material (e.g. Stainless Steel vs Plastic)
    if any(k in cat_can_norm for k in ('water_bottle', 'bottle', 'flask')) or 'water bottle' in t_can.lower():
        is_metal_can = any(w in t_can.lower() for w in ('stainless steel', 'steel', 'copper', 'thermosteel')) or any(w in str(canonical.get('material', '')).lower() for w in ('stainless steel', 'steel', 'copper', 'thermosteel'))
        is_plastic_cand = 'plastic' in t_cand.lower() or 'plastic' in str(candidate.get('material', '')).lower()
        if is_metal_can and is_plastic_cand:
            has_variant_conflict = True

    variant_score = 0.0 if has_variant_conflict else 15.0
    breakdown['variant'] = variant_score

    # 5. Weight / Capacity Score (10 pts)
    w_can = normalize_weight(canonical.get('weight') or v_can.get('weight') or t_can)
    w_cand = normalize_weight(candidate.get('weight') or v_cand.get('weight') or t_cand)
    is_weight_sensitive = cat_can in ('soap', 'face_wash', 'grocery', 'food', 'beauty', 'skincare', 'shampoo', 'water_bottle', 'bottle')
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
        return 0.0, "Not a Match", breakdown

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
