"""
search/identity_matcher.py
==========================
Exact Product Identity & Variant-Level Comparison Engine.

Accepts ANY search query and product (Electronics, Groceries, Fashion, Home Appliances, etc.).
Extracts structured product identity attributes:
  - Brand
  - Series / Line
  - Model / SKU
  - Processor & Processor Generation
  - RAM & Storage
  - GPU / Display / Key Specs
  - Fashion & Clothing Attributes: Gender, Color, Size, Product Type, Fit, Fabric/Material
Calculates weighted identity similarity scores and enforces strict variant mismatch guards
(e.g., 8GB vs 16GB, 256GB vs 512GB, 12th gen vs 13th gen, Men vs Women, Black vs Blue, Size 9 vs 10, etc.)
so different variants are NEVER treated as the same exact product.
"""

import re
import logging
from utils import parse_price
from search.normalizer import normalize_title

logger = logging.getLogger("smartbuy.identity_matcher")

# Known Brand Dictionary for fast detection across categories
KNOWN_BRANDS = {
    'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'sony', 'lg',
    'xiaomi', 'redmi', 'poco', 'realme', 'oneplus', 'vivo', 'oppo', 'motorola',
    'nokia', 'whirlpool', 'godrej', 'haier', 'panasonic', 'toshiba', 'philips',
    'boat', 'noise', 'jbl', 'bose', 'amul', 'fortune', 'britannia', 'nestle',
    'puma', 'nike', 'adidas', 'reebok', 'under armour', 'levis', "levi's", 'zara',
    'h&m', 'biba', 'fabindia', 'manyavar', 'peter england', 'allen solly', 'van heusen',
    'us polo', 'sparkx', 'bata', 'woodland', 'campus', 'red tape', 'titan', 'fastrack', 'casio'
}

BRAND_ALIASES = {
    'iphone': 'apple', 'ipad': 'apple', 'macbook': 'apple', 'airpods': 'apple',
    'galaxy': 'samsung', 'thinkpad': 'lenovo', 'ideapad': 'lenovo', 'yoga': 'lenovo', 'loq': 'lenovo',
    'bravia': 'sony', 'victus': 'hp', 'pavilion': 'hp', 'omen': 'hp', 'envy': 'hp',
    'vivobook': 'asus', 'zenbook': 'asus', 'tuf': 'asus', 'rog': 'asus',
    'aspire': 'acer', 'nitro': 'acer', 'predator': 'acer', 'redmi': 'xiaomi', 'poco': 'xiaomi',
    'x300': 'vivo', 'x200': 'vivo', 'x100': 'vivo', 'x90': 'vivo', 'v40': 'vivo', 'v30': 'vivo',
    'v29': 'vivo', 'y200': 'vivo', 't3': 'vivo', 't2': 'vivo', 'iqoo': 'vivo',
    'nord': 'oneplus', 'find': 'oppo', 'reno': 'oppo', 'levis': "levi's"
}

# Controlled Color Normalization Map
COLOR_MAP = {
    'black': 'black', 'jet black': 'black', 'black/black': 'black', 'pitch black': 'black',
    'white': 'white', 'off-white': 'white', 'off white': 'white', 'pure white': 'white',
    'blue': 'blue', 'light blue': 'blue', 'royal blue': 'blue', 'ice blue': 'blue',
    'navy': 'navy', 'navy blue': 'navy',
    'red': 'red', 'crimson': 'red', 'scarlet': 'red',
    'maroon': 'maroon', 'burgundy': 'maroon', 'wine': 'maroon',
    'green': 'green', 'dark green': 'green', 'olive': 'green', 'mint': 'green',
    'yellow': 'yellow', 'mustard': 'yellow',
    'pink': 'pink', 'rose': 'pink', 'baby pink': 'pink',
    'purple': 'purple', 'violet': 'purple', 'lavender': 'purple', 'lilac': 'purple',
    'grey': 'grey', 'gray': 'grey', 'dark grey': 'grey', 'charcoal': 'grey',
    'beige': 'beige', 'cream': 'beige', 'khaki': 'beige'
}

# Known Product Series Patterns
SERIES_PATTERNS = [
    (r'\b(victus)\b', 'victus'),
    (r'\b(pavilion)\b', 'pavilion'),
    (r'\b(omen)\b', 'omen'),
    (r'\b(ideapad)\b', 'ideapad'),
    (r'\b(thinkpad)\b', 'thinkpad'),
    (r'\b(yoga)\b', 'yoga'),
    (r'\b(loq)\b', 'loq'),
    (r'\b(vivobook)\b', 'vivobook'),
    (r'\b(zenbook)\b', 'zenbook'),
    (r'\b(tuf)\b', 'tuf'),
    (r'\b(rog)\b', 'rog'),
    (r'\b(aspire)\b', 'aspire'),
    (r'\b(predator)\b', 'predator'),
    (r'\b(nitro)\b', 'nitro'),
    (r'\b(macbook\s*air)\b', 'macbook air'),
    (r'\b(macbook\s*pro)\b', 'macbook pro'),
    (r'\b(macbook)\b', 'macbook'),
    (r'\b(galaxy)\b', 'galaxy'),
    (r'\b(iphone)\b', 'iphone'),
    (r'\b(redmi\s*note)\b', 'redmi note'),
    (r'\b(nord)\b', 'nord'),
    (r'\b(bravia)\b', 'bravia'),
]

def _clean_str(val: str) -> str:
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val).lower().strip())

# ── ELECTRONICS EXTRACTORS ──
def extract_ram(text: str) -> str:
    """Extract normalized RAM (e.g., '16gb', '8gb'), ignoring GPU VRAM."""
    t = _clean_str(text)
    m_exp = re.search(r'\b(4|6|8|12|16|24|32|64)\s*gb\s*(?:ram|ddr\d?|lpddr\d?|memory)\b', t)
    if m_exp:
        return f"{m_exp.group(1)}gb"
    matches = re.finditer(r'\b(4|6|8|12|16|24|32|64)\s*gb\b', t)
    for m in matches:
        start, end = m.span()
        suffix = t[end:end+15]
        if not re.search(r'^\s*(?:rtx|gtx|vram|graphics|gpu|radeon)', suffix):
            return f"{m.group(1)}gb"
    return ""

def extract_storage(text: str) -> str:
    """Extract normalized Storage (e.g., '512gb', '1tb', '256gb')."""
    t = _clean_str(text)
    m_tb = re.search(r'\b(1|2|4)\s*tb\b(?:\s*(?:ssd|hdd|rom|storage))?', t)
    if m_tb:
        return f"{m_tb.group(1)}tb"
    m_gb = re.search(r'\b(64|128|256|512|1024)\s*gb\b(?:\s*(?:ssd|hdd|rom|storage|internal))?', t)
    if m_gb:
        return f"{m_gb.group(1)}gb"
    return ""

def extract_processor(text: str) -> tuple[str, str]:
    """Extract (processor_model, processor_generation)."""
    t = _clean_str(text)
    proc_model = ""
    gen = ""
    g_m = re.search(r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:gen|generation)\b', t)
    if g_m:
        gen = f"{g_m.group(1)}th gen"
    i_m = re.search(r'\b(intel\s*core\s*i[3579]|core\s*i[3579]|i[3579])(?:\s*-?\s*(\d{4,5}[a-z]*))?\b', t)
    if i_m:
        p_name = i_m.group(1).replace('intel', '').replace('core', '').strip()
        code = i_m.group(2) or ""
        proc_model = f"intel core {p_name} {code}".strip()
    r_m = re.search(r'\b(ryzen\s*[3579])(?:\s*(\d{4}[a-z]*))?\b', t)
    if not proc_model and r_m:
        proc_model = f"amd {r_m.group(1)} {r_m.group(2) or ''}".strip()
    m_m = re.search(r'\b(m[1-4]\s*(?:pro|max|ultra)?|a1[4-8]\s*bionic)\b', t)
    if not proc_model and m_m:
        proc_model = f"apple {m_m.group(1)}"
    s_m = re.search(r'\b(snapdragon\s*\d+[\w]*|dimensity\s*\d+[\w]*)\b', t)
    if not proc_model and s_m:
        proc_model = s_m.group(1)
    return proc_model, gen

def extract_gpu(text: str) -> str:
    t = _clean_str(text)
    m = re.search(r'\b(rtx\s*\d{4}|gtx\s*\d{4}|radeon\s*rx\s*\d{4}|iris\s*xe)\b', t)
    return re.sub(r'\s+', ' ', m.group(1)) if m else ""

def extract_display(text: str) -> str:
    t = _clean_str(text)
    m = re.search(r'\b(\d{1,2}(?:\.\d)?)\s*(?:inch|"|-inch)\b', t)
    if m:
        return f"{m.group(1)} inch"
    if '4k' in t:
        return '4k'
    if 'fhd' in t or '1080p' in t:
        return 'fhd'
    return ""

def extract_model_sku(text: str) -> str:
    t = text.strip()
    m = re.search(r'\b([a-zA-Z]{1,4}\d{1,5}[a-zA-Z]*|\d{1,4}[a-zA-Z]{1,4}\d*)\b', t)
    if m:
        val = m.group(1).lower()
        if val not in ('512gb', '256gb', '128gb', '64gb', '32gb', '1080p', '16gb', '8gb', '4gb', '1tb', '2tb', '4k', '5g', '4g',
                       'i3', 'i5', 'i7', 'i9', 'ryzen',
                       '13th', '12th', '11th', '14th', '10th', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th'):
            return val
    return ""

# ── FASHION & CLOTHING EXTRACTORS ──
def extract_gender(text: str) -> str:
    t = _clean_str(text)
    if re.search(r'\b(women|womens|women\'s|ladies|lady|female|girl|girls)\b', t):
        return 'women'
    if re.search(r'\b(men|mens|men\'s|man|male|boy|boys|gent|gents)\b', t):
        return 'men'
    if 'unisex' in t:
        return 'unisex'
    return ''

def extract_color(text: str) -> str:
    t = _clean_str(text)
    for col_key, normalized_color in COLOR_MAP.items():
        if re.search(r'\b' + re.escape(col_key) + r'\b', t):
            return normalized_color
    return ''

def extract_size(text: str) -> str:
    t = _clean_str(text)
    # Shoe size (size 9, uk 9, us 9)
    m_shoe = re.search(r'\b(?:size|uk|us)\s*[:\-]?\s*(\d{1,2}(?:\.\d)?)\b', t)
    if m_shoe:
        return m_shoe.group(1)
    # Apparel size (xs, s, m, l, xl, xxl, 3xl)
    m_app = re.search(r'\b(xs|s|m|l|xl|xxl|3xl|xxxl)\b', t)
    if m_app:
        return m_app.group(1)
    # Waist size (28, 30, 32, 34, 36, 38, 40)
    m_waist = re.search(r'\b(\d{2})\s*(?:inch|waist)?\b', t)
    if m_waist and int(m_waist.group(1)) in (28, 30, 32, 34, 36, 38, 40):
        return m_waist.group(1)
    return ''

def extract_fashion_type(text: str) -> str:
    t = _clean_str(text)
    if 'running shoes' in t or 'sports shoes' in t or 'running shoe' in t:
        return 'running shoes'
    if 'sneakers' in t or 'sneaker' in t:
        return 'sneakers'
    if 'shoes' in t or 'shoe' in t or 'footwear' in t:
        return 'shoes'
    if 'hoodie' in t or 'hooded' in t:
        return 'hoodie'
    if 'sweatshirt' in t or 'sweater' in t:
        return 'sweatshirt'
    if 'jacket' in t or 'coat' in t:
        return 'jacket'
    if 't-shirt' in t or 'tshirt' in t or 'tee' in t:
        return 't-shirt'
    if 'shirt' in t:
        return 'shirt'
    if 'jeans' in t or 'denim' in t:
        return 'jeans'
    if 'trouser' in t or 'pant' in t or 'chinos' in t:
        return 'trousers'
    if 'kurti' in t:
        return 'kurti'
    if 'kurta' in t:
        return 'kurta'
    if 'saree' in t or 'sari' in t:
        return 'saree'
    if 'dress' in t or 'gown' in t:
        return 'dress'
    if 'tracksuit' in t or 'track pant' in t:
        return 'tracksuit'
    return ''

def extract_fit(text: str) -> str:
    t = _clean_str(text)
    if 'slim fit' in t or 'slim' in t:
        return 'slim fit'
    if 'regular fit' in t or 'regular' in t:
        return 'regular fit'
    if 'oversized' in t:
        return 'oversized'
    if 'relaxed fit' in t or 'relaxed' in t:
        return 'relaxed fit'
    if 'skinny fit' in t or 'skinny' in t:
        return 'skinny fit'
    return ''

def extract_material(text: str) -> str:
    t = _clean_str(text)
    if 'cotton' in t:
        return 'cotton'
    if 'denim' in t:
        return 'denim'
    if 'polyester' in t:
        return 'polyester'
    if 'silk' in t:
        return 'silk'
    if 'linen' in t:
        return 'linen'
    if 'wool' in t:
        return 'wool'
    if 'leather' in t:
        return 'leather'
    return ''

def extract_product_identity(input_val) -> dict:
    """
    Extract a normalized product identity dictionary from a text query or product item.
    """
    if isinstance(input_val, dict):
        title = input_val.get('title', '')
        specs = input_val.get('specs', {})
        specs_str = " ".join(str(v) for v in specs.values()) if isinstance(specs, dict) else str(specs)
        full_text = f"{title} {specs_str}"
    else:
        title = str(input_val or "")
        full_text = title

    norm_t = _clean_str(full_text)

    # Brand
    brand = ""
    tokens = norm_t.split()
    for tok in tokens:
        if tok in BRAND_ALIASES:
            brand = BRAND_ALIASES[tok]
            break
        if tok in KNOWN_BRANDS:
            brand = tok
            break
    if not brand and tokens:
        first_tok = tokens[0]
        if first_tok in BRAND_ALIASES:
            brand = BRAND_ALIASES[first_tok]
        elif first_tok in KNOWN_BRANDS:
            brand = first_tok

    # Series
    series = ""
    for pattern, s_name in SERIES_PATTERNS:
        if re.search(pattern, norm_t):
            series = s_name
            break

    # RAM & Storage & Tech specs
    ram = extract_ram(norm_t)
    storage = extract_storage(norm_t)
    processor, gen = extract_processor(norm_t)
    gpu = extract_gpu(norm_t)
    display = extract_display(norm_t)
    sku = extract_model_sku(title)

    # Fashion specs
    gender = extract_gender(norm_t)
    color = extract_color(norm_t)
    size = extract_size(norm_t)
    product_type = extract_fashion_type(norm_t)
    fit = extract_fit(norm_t)
    material = extract_material(norm_t)

    # Specific Model Name (e.g., "15", "S24", "15 Pro")
    model = ""
    if sku:
        model = sku
    elif series:
        m_s = re.search(re.escape(series) + r'\s*([a-z0-9\+\-]+)', norm_t)
        if m_s:
            model = m_s.group(1)

    if model in ('intel', 'amd', 'core', 'gaming', 'laptop', 'phone', '5g', '4g', 'i3', 'i5', 'i7', 'i9', 'ryzen', 'pro', 'max', 'plus', 'ultra', 'mini', 'th'):
        model = ""

    return {
        "brand": brand,
        "series": series,
        "model": model,
        "processor": processor,
        "generation": gen,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "display": display,
        "sku": sku,
        "gender": gender,
        "color": color,
        "size": size,
        "product_type": product_type,
        "fit": fit,
        "material": material,
        "raw_text": title
    }

def calculate_identity_match(query_ident: dict, prod_ident: dict) -> tuple[float, bool, str]:
    """
    Calculate weighted product identity match score and check for variant contradictions.
    Returns:
        (score_percentage, is_exact_variant, contradiction_reason)
    """
    p_title = prod_ident.get('raw_text', '').lower()

    # 1. HARD CONTRADICTION / MISMATCH CHECKS (STRICT ACCURACY RULE)

    # Brand Mismatch
    q_brand = query_ident.get('brand', '').lower()
    p_brand = prod_ident.get('brand', '').lower()
    p_brand_alias = BRAND_ALIASES.get(p_brand, p_brand)

    if q_brand and p_brand and q_brand != p_brand and p_brand_alias != q_brand:
        competing = {'samsung', 'apple', 'hp', 'dell', 'lenovo', 'sony', 'asus', 'acer', 'oppo', 'vivo', 'xiaomi', 'oneplus', 'realme', 'nike', 'adidas', 'puma', 'reebok', 'levis'}
        q_mod = query_ident.get('model') or query_ident.get('sku')
        p_mod = prod_ident.get('model') or prod_ident.get('sku')
        if q_mod and p_mod and q_mod == p_mod and p_brand not in (competing - {q_brand}):
            pass
        else:
            return 0.0, False, f"Brand mismatch ({q_brand} vs {p_brand})"

    # Series Mismatch
    q_ser = query_ident.get('series')
    p_ser = prod_ident.get('series')
    if q_ser and p_ser and q_ser != p_ser:
        return 0.0, False, f"Series mismatch ({q_ser} vs {p_ser})"
    if q_ser and q_ser not in p_title and p_ser:
        return 0.0, False, f"Series missing in title ({q_ser})"

    # RAM Contradiction
    q_ram = query_ident.get('ram')
    p_ram = prod_ident.get('ram') or extract_ram(p_title)
    if q_ram and p_ram and q_ram != p_ram:
        return 0.0, False, f"RAM variant mismatch ({q_ram} vs {p_ram})"

    # Storage Contradiction
    q_st = query_ident.get('storage')
    p_st = prod_ident.get('storage') or extract_storage(p_title)
    if q_st and p_st and q_st != p_st:
        return 0.0, False, f"Storage variant mismatch ({q_st} vs {p_st})"

    # Processor Contradiction
    q_pr = query_ident.get('processor')
    if q_pr:
        q_i = re.search(r'i[3579]', q_pr)
        p_i = re.search(r'i[3579]', p_title)
        if q_i and p_i and q_i.group() != p_i.group():
            return 0.0, False, f"Processor model mismatch ({q_pr} vs {p_i.group()})"
        if 'ryzen' in q_pr and 'ryzen' not in p_title:
            return 0.0, False, "Processor brand mismatch (AMD Ryzen expected)"
        if 'intel' in q_pr and 'intel' not in p_title and not p_i:
            return 0.0, False, "Processor brand mismatch (Intel expected)"

    # Generation Contradiction
    q_gen = query_ident.get('generation')
    if q_gen:
        g_in_title = re.search(r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:gen|generation)\b', p_title)
        if g_in_title and f"{g_in_title.group(1)}th gen" != q_gen:
            return 0.0, False, f"Generation mismatch ({q_gen} vs {g_in_title.group(1)}th gen)"

    # Model Variant Modifier check
    q_raw = query_ident.get('raw_text', '').lower()
    if 'iphone 15' in q_raw and 'iphone 15 pro' not in q_raw and 'iphone 15 pro' in p_title:
        return 0.0, False, "Model variant mismatch (Base iPhone 15 expected, found Pro)"
    if 'wh-1000xm5' in q_raw and 'wh-1000xm4' in p_title:
        return 0.0, False, "Model generation mismatch (XM5 expected, found XM4)"

    # ── FASHION & CLOTHING MANDATORY GUARDS ──
    # Gender Contradiction
    q_gender = query_ident.get('gender')
    p_gender = prod_ident.get('gender') or extract_gender(p_title)
    if q_gender and p_gender and q_gender != p_gender and p_gender != 'unisex' and q_gender != 'unisex':
        return 0.0, False, f"Gender mismatch ({q_gender} vs {p_gender})"

    # Color Contradiction (e.g. Black vs Blue)
    q_color = query_ident.get('color')
    p_color = prod_ident.get('color') or extract_color(p_title)
    if q_color and p_color and q_color != p_color:
        return 0.0, False, f"Color mismatch ({q_color} vs {p_color})"

    # Size Contradiction (e.g. Size 9 vs 10, M vs L)
    q_size = query_ident.get('size')
    p_size = prod_ident.get('size') or extract_size(p_title)
    if q_size and p_size and q_size != p_size:
        return 0.0, False, f"Size mismatch ({q_size} vs {p_size})"

    # Product Type Contradiction (e.g. Running Shoes vs T-Shirt / Hoodie)
    q_type = query_ident.get('product_type')
    p_type = prod_ident.get('product_type') or extract_fashion_type(p_title)
    if q_type and p_type and q_type != p_type:
        return 0.0, False, f"Product type mismatch ({q_type} vs {p_type})"

    # Fit Contradiction (e.g. Slim Fit vs Regular Fit)
    q_fit = query_ident.get('fit')
    p_fit = prod_ident.get('fit') or extract_fit(p_title)
    if q_fit and p_fit and q_fit != p_fit:
        return 0.0, False, f"Fit mismatch ({q_fit} vs {p_fit})"

    # Material Contradiction (e.g. Cotton vs Polyester)
    q_mat = query_ident.get('material')
    p_mat = prod_ident.get('material') or extract_material(p_title)
    if q_mat and p_mat and q_mat != p_mat:
        return 0.0, False, f"Material mismatch ({q_mat} vs {p_mat})"

    # 2. WEIGHTED IDENTITY SCORE CALCULATION
    total_applicable = 0
    total_earned = 0

    if query_ident.get('sku'):
        total_applicable += 30
        if prod_ident.get('sku') == query_ident['sku']:
            total_earned += 30

    if query_ident.get('brand'):
        total_applicable += 15
        if prod_ident.get('brand') == query_ident['brand']:
            total_earned += 15

    if query_ident.get('series'):
        total_applicable += 15
        if prod_ident.get('series') == query_ident['series']:
            total_earned += 15

    if query_ident.get('processor'):
        total_applicable += 15
        if prod_ident.get('processor') and query_ident['processor'] in prod_ident['processor']:
            total_earned += 15

    if query_ident.get('generation'):
        total_applicable += 10
        if prod_ident.get('generation') == query_ident['generation']:
            total_earned += 10

    if query_ident.get('ram'):
        total_applicable += 10
        if (prod_ident.get('ram') or extract_ram(p_title)) == query_ident['ram']:
            total_earned += 10

    if query_ident.get('storage'):
        total_applicable += 10
        if (prod_ident.get('storage') or extract_storage(p_title)) == query_ident['storage']:
            total_earned += 10

    if query_ident.get('gpu'):
        total_applicable += 5
        if prod_ident.get('gpu') == query_ident['gpu']:
            total_earned += 5

    if query_ident.get('display'):
        total_applicable += 5
        if prod_ident.get('display') == query_ident['display']:
            total_earned += 5

    # Fashion weights
    if query_ident.get('gender'):
        total_applicable += 10
        if (prod_ident.get('gender') or extract_gender(p_title)) == query_ident['gender']:
            total_earned += 10

    if query_ident.get('color'):
        total_applicable += 10
        if (prod_ident.get('color') or extract_color(p_title)) == query_ident['color']:
            total_earned += 10

    if query_ident.get('size'):
        total_applicable += 10
        if (prod_ident.get('size') or extract_size(p_title)) == query_ident['size']:
            total_earned += 10

    if query_ident.get('product_type'):
        total_applicable += 15
        if (prod_ident.get('product_type') or extract_fashion_type(p_title)) == query_ident['product_type']:
            total_earned += 15

    if total_applicable == 0:
        score = 85.0
    else:
        score = round((total_earned / total_applicable) * 100.0, 2)

    # Requirement 7: match_score >= 85.0% for exact match
    is_exact = score >= 85.0
    return score, is_exact, "Matches exact variant criteria" if is_exact else "Score below variant threshold"


ACCESSORY_KEYWORDS = {
    'case', 'cases', 'cover', 'covers', 'protector', 'skin', 'guard', 'cable', 
    'charger', 'strap', 'band', 'glass', 'sleeve', 'backcover', 'back cover',
    'screen guard', 'tempered glass', 'pouch', 'bag', 'backpack', 'laptop bag',
    'socks', 'sock', 'shoe cover', 'shoe covers', 'holster', 'mount', 'holder',
    'skin guard', 'lens protector'
}


def is_exact_product(user_query: str, product) -> bool:
    """
    STRICT EXACT-PRODUCT FILTERING
    
    Verifies that the product matches the user search query on:
    1. Category & Product Type (Hard filter - rejects accessories & product type mismatches)
    2. Brand (Must match when specified)
    3. Model & Series (Must match exact model - rejects model variants like Lite, Pro, Plus, 14 vs 15)
    4. Key Specifications (Network 5G, Storage, RAM, CPU, Generation)
    5. Variant Information (Color, Size, Gender)
    
    Returns True ONLY when all checks pass. Fuzzy score does NOT override hard rejections.
    """
    if not user_query or not product:
        return False

    if isinstance(product, dict):
        p_title = product.get('title', '')
    else:
        p_title = str(product)

    if not p_title or len(p_title.strip()) < 3:
        return False

    q_norm = _clean_str(user_query)
    t_norm = _clean_str(p_title)

    # 1. ACCESSORY HARD FILTER
    # If title is an accessory but user did not explicitly ask for an accessory, REJECT IMMEDIATELY.
    q_has_acc = any(re.search(r'\b' + re.escape(k) + r'\b', q_norm) for k in ACCESSORY_KEYWORDS)
    t_has_acc = any(re.search(r'\b' + re.escape(k) + r'\b', t_norm) for k in ACCESSORY_KEYWORDS)
    if t_has_acc and not q_has_acc:
        return False

    # 2. CATEGORY & PRODUCT TYPE HARD FILTER
    from search.specs_extractor import detect_category
    q_cat = detect_category(q_norm)
    p_cat = detect_category(t_norm)

    if q_cat != "General Products" and p_cat != "General Products":
        if q_cat != p_cat:
            return False

    # Product Type validation (e.g. mobile phone requested vs phone case scraped; running shoes requested vs socks scraped)
    q_ident = extract_product_identity(user_query)
    p_ident = extract_product_identity(product)

    q_type = q_ident.get('product_type')
    p_type = p_ident.get('product_type')
    if q_type and p_type and q_type != p_type:
        return False

    # 3. BRAND HARD FILTER
    q_brand = q_ident.get('brand', '').lower()
    p_brand = p_ident.get('brand', '').lower()

    if q_brand:
        q_brand_alias = str(BRAND_ALIASES.get(q_brand) or q_brand)
        if q_brand not in t_norm and q_brand_alias not in t_norm:
            competing_brands = {
                'samsung', 'apple', 'hp', 'dell', 'lenovo', 'sony', 'asus', 'acer', 
                'oppo', 'vivo', 'xiaomi', 'oneplus', 'realme', 'poco', 'redmi', 'motorola',
                'nike', 'adidas', 'puma', 'reebok', 'levis', 'boat', 'noise', 'jbl'
            }
            if any(re.search(r'\b' + re.escape(b) + r'\b', t_norm) for b in competing_brands if b != q_brand and b != q_brand_alias):
                return False

    # 4. MODEL & SERIES HARD FILTER
    modifiers = ['lite', 'pro', 'plus', 'max', 'ultra', 'mini', 'pro max', 'x']

    q_mod = q_ident.get('model') or extract_model_sku(user_query)

    for mod in modifiers:
        mod_pattern = r'\b' + re.escape(mod) + r'\b'
        q_has_mod = bool(re.search(mod_pattern, q_norm))
        p_has_mod = bool(re.search(mod_pattern, t_norm))
        if p_has_mod and not q_has_mod:
            return False
        if q_has_mod and not p_has_mod:
            return False

    # iPhone numeric model check (iPhone 15 vs iPhone 14 / 13)
    q_iph = re.search(r'\biphone\s*(\d{1,2})\b', q_norm)
    p_iph = re.search(r'\biphone\s*(\d{1,2})\b', t_norm)
    if q_iph and p_iph and q_iph.group(1) != p_iph.group(1):
        return False
    if q_iph and not p_iph and 'iphone' in t_norm:
        return False

    # Series mismatch
    q_ser = q_ident.get('series')
    p_ser = p_ident.get('series')
    if q_ser and p_ser and q_ser != p_ser:
        return False

    # 5. KEY SPECIFICATION HARD FILTERS
    # Network 5G
    if '5g' in q_norm:
        if '5g' not in t_norm:
            return False

    # Storage
    q_st = q_ident.get('storage')
    p_st = p_ident.get('storage') or extract_storage(t_norm)
    if q_st and p_st and q_st != p_st:
        return False
    if q_st and not p_st:
        q_st_space = q_st.replace('gb', ' gb').replace('tb', ' tb')
        if q_st not in t_norm and q_st_space not in t_norm:
            return False

    # RAM
    q_ram = q_ident.get('ram')
    p_ram = p_ident.get('ram') or extract_ram(t_norm)
    if q_ram and p_ram and q_ram != p_ram:
        return False
    if q_ram and not p_ram:
        q_ram_space = q_ram.replace('gb', ' gb')
        if q_ram not in t_norm and q_ram_space not in t_norm:
            return False

    # CPU Processor (i5 vs i7, Ryzen vs Intel)
    q_proc, _ = extract_processor(q_norm)
    if q_proc:
        q_i = re.search(r'\b(i[3579])\b', q_proc)
        p_i = re.search(r'\b(i[3579])\b', t_norm)
        if q_i and p_i and q_i.group(1) != p_i.group(1):
            return False
        if 'ryzen' in q_proc and 'ryzen' not in t_norm:
            return False
        if 'intel' in q_proc and 'intel' not in t_norm and not p_i:
            return False

    # Generation (13th Gen vs 12th Gen)
    q_gen = q_ident.get('generation')
    if q_gen:
        g_in_title = re.search(r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:gen|generation)\b', t_norm)
        if g_in_title and f"{g_in_title.group(1)}th gen" != q_gen:
            return False

    # 6. VARIANT HARD FILTERS (FASHION)
    # Gender
    q_gender = q_ident.get('gender')
    p_gender = p_ident.get('gender') or extract_gender(t_norm)
    if q_gender and p_gender and q_gender != p_gender and p_gender != 'unisex' and q_gender != 'unisex':
        return False

    # Color
    q_color = q_ident.get('color')
    p_color = p_ident.get('color') or extract_color(t_norm)
    if q_color and p_color and q_color != p_color:
        return False

    # Size
    q_size = q_ident.get('size')
    p_size = p_ident.get('size') or extract_size(t_norm)
    if q_size and p_size and q_size != p_size:
        return False

    # Match score verification
    score, is_exact, reason = calculate_identity_match(q_ident, p_ident)
    if not is_exact or score < 80.0:
        return False

    return True


def group_exact_and_similar_products(query: str, raw_platform_results: dict) -> dict:
    """
    Perform exact variant matching and group products into:
    1. Exact Product Match side-by-side comparison row (Amazon, Flipkart, Meesho)
    2. Highlights (Lowest Price, Highest Rating, Most Reviews, Savings Info)
    3. Similar Products section (non-exact variants)
    """
    q_ident = extract_product_identity(query)
    logger.info(f"Query Identity Extracted: {q_ident}")

    exact_matches = {"Amazon": None, "Flipkart": None, "Meesho": None}
    similar_products = []
    best_scores = {"Amazon": -1.0, "Flipkart": -1.0, "Meesho": -1.0}

    for platform, items in raw_platform_results.items():
        if not items or platform not in exact_matches:
            continue

        for item in items:
            item['platform'] = item.get('platform', platform)
            p_ident = extract_product_identity(item)
            score, is_exact, reason = calculate_identity_match(q_ident, p_ident)
            
            exact_valid = is_exact_product(query, item)

            item['identity'] = p_ident
            item['identity_score'] = score
            item['is_exact_match'] = exact_valid
            item['match_reason'] = reason if exact_valid else "Rejected by strict exact-product filter"

            if exact_valid:
                if score > best_scores[platform]:
                    best_scores[platform] = score
                    prev = exact_matches[platform]
                    if prev is not None:
                        prev['is_exact_match'] = False
                        prev['variant_label'] = "Similar Variant – Not Exact Match"
                        similar_products.append(prev)
                    exact_matches[platform] = item
                else:
                    item['variant_label'] = "Similar Variant – Not Exact Match"
                    similar_products.append(item)
            else:
                item['variant_label'] = "Similar Variant – Not Exact Match"
                similar_products.append(item)

    # Build Summary
    parts = []
    if q_ident.get('gender'):
        parts.append(q_ident['gender'].title())
    if q_ident.get('color'):
        parts.append(q_ident['color'].title())
    if q_ident.get('brand'):
        parts.append(q_ident['brand'].title())
    if q_ident.get('series'):
        parts.append(q_ident['series'].title())
    if q_ident.get('model'):
        parts.append(q_ident['model'].upper())
    if q_ident.get('processor'):
        parts.append(q_ident['processor'].title())
    if q_ident.get('generation'):
        parts.append(q_ident['generation'].title())
    if q_ident.get('ram'):
        parts.append(q_ident['ram'].upper())
    if q_ident.get('storage'):
        parts.append(q_ident['storage'].upper())
    if q_ident.get('product_type'):
        parts.append(q_ident['product_type'].title())
    if q_ident.get('size'):
        parts.append(f"Size {q_ident['size'].upper()}")

    summary = " ".join(parts) if parts else query

    valid_exacts = [p for p in exact_matches.values() if p is not None and p.get('price_num')]
    
    best_price_info = None
    highest_rating_info = None
    most_reviews_info = None
    savings_info = None

    if valid_exacts:
        sorted_by_price = sorted(valid_exacts, key=lambda x: x['price_num'])
        lowest_item = sorted_by_price[0]
        highest_item = sorted_by_price[-1]

        best_price_info = {
            "platform": lowest_item['platform'],
            "price": lowest_item['price'],
            "price_num": lowest_item['price_num'],
            "title": lowest_item['title']
        }

        if len(sorted_by_price) > 1:
            savings_val = highest_item['price_num'] - lowest_item['price_num']
            if savings_val > 0:
                savings_info = {
                    "savings_amount": f"₹{savings_val:,}",
                    "compared_to_platform": highest_item['platform'],
                    "compared_to_price": highest_item['price']
                }

        rated_exacts = [p for p in valid_exacts if p.get('rating') and p['rating'] != 'N/A']
        if rated_exacts:
            highest_rating_item = max(rated_exacts, key=lambda x: float(x['rating']))
            highest_rating_info = {
                "platform": highest_rating_item['platform'],
                "rating": highest_rating_item['rating']
            }

        rev_exacts = [p for p in valid_exacts if p.get('reviews') and p['reviews'] != '0']
        if rev_exacts:
            most_reviews_item = max(rev_exacts, key=lambda x: parse_price(x['reviews']) or 0)
            most_reviews_info = {
                "platform": most_reviews_item['platform'],
                "reviews": most_reviews_item['reviews']
            }

    return {
        "query_identity": q_ident,
        "query_summary": summary,
        "exact_matches": exact_matches,
        "best_price_info": best_price_info,
        "highest_rating_info": highest_rating_info,
        "most_reviews_info": most_reviews_info,
        "savings_info": savings_info,
        "similar_products": similar_products
    }
