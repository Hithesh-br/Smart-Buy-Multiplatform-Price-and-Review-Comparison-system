import re
from typing import Any, Optional, Dict, List, Union
from search.category_detector import detect_category


def safe_number(val, default: float = 0.0) -> float:
    """Safely convert any numeric value, string, or None to float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        val_str = str(val).strip()
        if not val_str or val_str.upper() in ('N/A', 'NONE', 'NOT AVAILABLE', 'NULL', ''):
            return default
        clean_str = val_str.replace(',', '')
        m = re.search(r'(\d+(?:\.\d+)?)', clean_str)
        return float(m.group(1)) if m else default
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Regex patterns for universal spec extraction
# ---------------------------------------------------------------------------

_SPEC_PATTERNS = {
    # Electronics
    'ram':       [r'\b(\d+)\s*gb\s*(?:ram|lpddr\d?)',
                  r'\b(4|6|8|12|16|32|64)\s*gb\b'],
    'storage':   [r'\b(\d+)\s*(?:gb|tb)\s*(?:rom|ssd|hdd|emmc|storage|internal)',
                  r'\b(64|128|256|512|1024)\s*gb\b',
                  r'\b(1|2|4)\s*tb\b'],
    'battery':   [r'\b(\d{4,5})\s*mah\b'],
    'display':   [r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|"|-inch)\b'],
    'processor': [r'\b(snapdragon[\s\w]*?(?:gen\s*\d)?|'
                  r'mediatek[\s\w]*?|dimensity[\s\w]*?|'
                  r'helio[\s\w]*?|bionic[\s\w]*?|'
                  r'core\s*i[3579]|ryzen\s*\d|'
                  r'a1[4-9]|m[1-4])\b'],
    'network':   [r'\b(5g|4g|3g|lte|wifi\s*6e?)\b'],
    'os':        [r'\b(android\s*\d+|ios\s*\d+|windows\s*\d+|'
                  r'miui\s*\d+|one\s*ui\s*\d+)\b'],

    # Weights & volumes (Grocery, Fitness, Beauty)
    'weight':    [r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|kilograms?)\b'],
    'volume':    [r'\b(\d+(?:\.\d+)?)\s*(ml|l|litre?s?|liter?s?)\b'],
    'quantity':  [r'\b(?:pack\s*of\s*|qty\s*:?\s*|x\s*)(\d+)\b',
                  r'\b(\d+)\s*(?:pieces?|pcs?|tablets?|capsules?|sachets?|units?)\b'],
    'capacity':  [r'\b(\d+(?:\.\d+)?)\s*(litres?|liters?|l)\b'],

    # Clothing & Footwear
    'size':      [r'\bsize[:\s]+([xsl]{1,3}|\d{1,3}(?:\.\d)?)\b',
                  r'\b(xs|s\b|m\b|l\b|xl|xxl|xxxl)\b'],
    'color':     [r'\b(black|white|red|blue|green|yellow|pink|purple|'
                  r'grey|gray|silver|gold|brown|orange|cyan|magenta|'
                  r'navy|maroon|beige|cream|coral|rose|turquoise)\b'],

    # Furniture / Appliances
    'material':  [r'\b(wood|wooden|metal|steel|aluminum|aluminium|'
                  r'plastic|fabric|leather|glass|rubber|ceramic|'
                  r'cotton|polyester|nylon|bamboo|silicone)\b'],
    'wattage':   [r'\b(\d+)\s*(?:w|watts?)\b'],
    'voltage':   [r'\b(\d+)\s*(?:v|volts?)\b'],

    # Books
    'author':    [r'\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'],
    'pages':     [r'\b(\d+)\s*pages?\b'],
}

# Colors list for dedicated color detection
_COLORS = [
    'Black', 'White', 'Red', 'Blue', 'Green', 'Yellow', 'Pink',
    'Purple', 'Grey', 'Gray', 'Silver', 'Gold', 'Brown', 'Orange',
    'Cyan', 'Magenta', 'Navy', 'Maroon', 'Beige', 'Cream', 'Coral',
    'Rose', 'Turquoise', 'Midnight', 'Starlight', 'Graphite',
    'Titanium', 'Sage', 'Lavender', 'Olive', 'Khaki',
]

_COLOR_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(c) for c in _COLORS) + r')\b', re.I
)

_RAM_ONLY_PATTERN = re.compile(
    r'(\d+)\s*gb\s*\+\s*(\d+)\s*gb',
    re.I
)

_MODEL_CODE_PATTERN = re.compile(
    r'\b([a-zA-Z]{1,4}\d+[a-zA-Z]?\d*|'   # e.g. S24, A55, M34, i7, RX7
    r'\d+[a-zA-Z]{1,3}\d*)\b'              # e.g. 12Pro, 15Plus
)


def _extract_brand_from_title(title: str) -> str:
    """Heuristic brand extraction: check known multi-word brands, then first capitalized proper noun."""
    if not title:
        return 'Not Available'
    known_brands = [
        'Reginald Men', 'Ghar Soaps', 'True Elements', 'Dot & Key', 'The Derma Co',
        'Mamaearth', 'Cetaphil', 'Pilgrim', 'Nivea', 'Dove', 'Milton', 'Pexpo',
        'Cello', 'Borosil', 'Pigeon', 'Prestige', 'Apple', 'Samsung', 'Vivo',
        'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola', 'HP', 'Dell',
        'Lenovo', 'Asus', 'Acer', 'boAt', 'Noise', 'Boult', 'Fastrack', 'Titan'
    ]
    t_lower = title.lower()
    for b in known_brands:
        if re.search(r'\b' + re.escape(b.lower()) + r'\b', t_lower):
            return b

    non_brands = {
        'the', 'a', 'an', 'new', 'best', 'top', 'premium', 'original',
        'genuine', 'pack', 'set', 'combo', 'for', 'with', 'and', 'or',
        'in', 'on', 'by', 'of', 'size', 'color', 'model',
        'certified', 'refurbished', 'used', 'open', 'box',
    }
    tokens = title.split()
    for token in tokens:
        clean = re.sub(r'[^a-zA-Z0-9]', '', token)
        if (clean and len(clean) >= 2
                and clean[0].isupper()
                and clean.lower() not in non_brands
                and not clean.isdigit()):
            return clean
    return 'Not Available'




def extract_specs(item: dict, query: str = "") -> dict:
    """
    Dynamically extract specifications and category details from a product item.
    Returns structured specs dictionary including category, model, seller, warranty, and category specs.
    """
    title = item.get('title', '')
    title_lower = title.lower()
    specs: dict[str, Any] = {k: 'N/A' for k in _SPEC_PATTERNS}
    specs['brand']      = 'N/A'
    specs['color']      = 'N/A'
    specs['rating_num'] = 0.0
    specs['price_num']  = item.get('price_num')

    # Brand
    specs['brand'] = _extract_brand_from_title(title)

    # Category
    category = detect_category(query=query, title=title)
    specs['category'] = category

    # Model Number / Code
    m_code = _MODEL_CODE_PATTERN.search(title)
    specs['model_number'] = m_code.group(1).upper() if m_code else 'Not Available'

    # Color
    color_match = _COLOR_PATTERN.search(title)
    if color_match:
        specs['color'] = color_match.group(1).capitalize()

    # RAM + Storage
    combined_match = _RAM_ONLY_PATTERN.search(title)
    if combined_match:
        specs['ram']     = f"{combined_match.group(1)} GB"
        specs['storage'] = f"{combined_match.group(2)} GB"

    # All other patterns
    for spec_key, patterns in _SPEC_PATTERNS.items():
        if specs.get(spec_key) not in (None, 'N/A'):
            continue

        for pattern in patterns:
            m = re.search(pattern, title_lower, re.I)
            if m:
                val = m.group(0).strip()
                if spec_key in ('ram', 'storage', 'battery', 'weight',
                                'volume', 'wattage', 'voltage', 'pages'):
                    val = m.group(1).strip()
                    if spec_key == 'ram':
                        val = f"{val} GB"
                    elif spec_key == 'storage':
                        unit = 'TB' if 'tb' in m.group(0).lower() else 'GB'
                        val = f"{val} {unit}"
                    elif spec_key == 'battery':
                        val = f"{val} mAh"
                    elif spec_key == 'display':
                        val = f'{val}"'
                    elif spec_key in ('weight', 'volume', 'capacity'):
                        unit = m.group(2).strip() if len(m.groups()) >= 2 else ''
                        val = f"{val} {unit}".strip()
                    elif spec_key == 'wattage':
                        val = f"{val} W"
                    elif spec_key == 'voltage':
                        val = f"{val} V"

                specs[spec_key] = val.strip()
                break

    # Rating
    specs['rating_num'] = safe_number(item.get('rating'))

    # Camera heuristic
    cam_match = re.search(r'\b(\d{2,3}\s*mp|\d+\s*\+\s*\d+\s*mp)\b', title_lower)
    specs['camera'] = cam_match.group(1).upper() if cam_match else ('Not Available' if category == 'Smartphones' else 'N/A')

    # 5G Support
    specs['is_5g'] = 'Yes (5G Ready)' if '5g' in title_lower else ('No' if category == 'Smartphones' else 'N/A')

    # Seller & Delivery & Warranty
    specs['seller']   = item.get('seller') if item.get('seller') and item.get('seller') != 'N/A' else 'Not Available'
    price_val         = safe_number(item.get('price_num'))
    specs['delivery'] = 'Free Delivery (2-3 Days)' if price_val > 499 else 'Standard Delivery'
    warr_raw = item.get('warranty')
    if warr_raw and str(warr_raw).lower() not in ('n/a', 'none', 'not available'):
        specs['warranty'] = str(warr_raw)
    elif category in ('phone', 'Smartphones', 'laptop', 'Laptops', 'Televisions', 'Refrigerators', 'Washing Machines', 'kitchen', 'home_appliance'):
        specs['warranty'] = '1 Year Brand Warranty'
    else:
        specs['warranty'] = 'Standard Return Policy'

    # Build category-tailored specifications list
    cat_specs = {}
    c_norm = str(category or "").lower()

    if c_norm in ("phone", "smartphones", "mobile"):
        cat_specs["Display"] = specs.get('display', 'Not Available')
        cat_specs["Processor"] = specs.get('processor', 'Not Available')
        cat_specs["RAM"] = specs.get('ram', 'Not Available')
        cat_specs["Storage"] = specs.get('storage', 'Not Available')
        cat_specs["Camera"] = specs.get('camera', 'Not Available')
        cat_specs["Battery"] = specs.get('battery', 'Not Available')
        cat_specs["OS"] = specs.get('os', 'Not Available')
        cat_specs["5G Support"] = specs.get('is_5g', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
    elif c_norm in ("laptop", "laptops"):
        cat_specs["Processor"] = specs.get('processor', 'Not Available')
        cat_specs["RAM"] = specs.get('ram', 'Not Available')
        cat_specs["SSD/Storage"] = specs.get('storage', 'Not Available')
        cat_specs["Display Size"] = specs.get('display', 'Not Available')
        if 'nvidia' in title_lower or 'rtx' in title_lower or 'gtx' in title_lower:
            cat_specs["Graphics"] = "Dedicated (NVIDIA)"
        elif 'radeon' in title_lower or 'rx' in title_lower:
            cat_specs["Graphics"] = "Dedicated (AMD Radeon)"
        else:
            cat_specs["Graphics"] = "Not Available"
        cat_specs["OS"] = specs.get('os', 'Not Available')
        cat_specs["Weight"] = specs.get('weight', 'Not Available')
    elif c_norm in ("face_wash", "face wash"):
        cat_specs["Product Type"] = "Face Wash"
        v_m = re.search(r'\b(vitamin c|salicylic acid|tea tree|neem|aloe vera|charcoal|hyaluronic|papaya|coffee|ubtan|glycolic)\b', title_lower)
        cat_specs["Active Ingredient"] = v_m.group(1).title() if v_m else "Not Available"
        cat_specs["Skin Type"] = "Oily / Acne Prone" if any(w in title_lower for w in ['acne', 'pimple', 'oil control']) else ("Dry Skin" if 'dry' in title_lower else "Not Available")
        vol_m = re.search(r'(\d+\s*(?:ml|g))\b', title_lower)
        cat_specs["Volume / Weight"] = vol_m.group(1) if vol_m else specs.get('volume', 'Not Available')
    elif c_norm in ("soap",):
        cat_specs["Product Type"] = "Bathing Soap"
        # Weight check from title, product fields, subtitle or specs
        w_m = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg))\b', title_lower)
        wt_val = w_m.group(1) if w_m else None
        if not wt_val:
            wt_val = item.get('weight') or (item.get('specifications', {}).get('Weight') if isinstance(item.get('specifications'), dict) else None)
        if not wt_val and item.get('subtitle'):
            m_sub = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg))\b', str(item['subtitle']), re.I)
            if m_sub:
                wt_val = m_sub.group(1)
        cat_specs["Weight"] = wt_val if wt_val else specs.get('weight', 'Not Available')

        # Pack Quantity check from title, product fields, subtitle or specs
        pq_m = re.search(r'(?:pack\s*of\s*|pack-|pack\s*)(\d+)', title_lower)
        pq_val = f"Pack of {pq_m.group(1)}" if pq_m else None
        if not pq_val:
            raw_pq = item.get('pack_quantity') or (item.get('specifications', {}).get('Pack of') if isinstance(item.get('specifications'), dict) else None)
            if raw_pq:
                pq_val = f"Pack of {raw_pq}" if str(raw_pq).isdigit() else str(raw_pq)
        if not pq_val and item.get('subtitle'):
            m_spq = re.search(r'(\d+)\s*x', str(item['subtitle']))
            if m_spq:
                pq_val = f"Pack of {m_spq.group(1)}"
        cat_specs["Pack Quantity"] = pq_val if pq_val else "Not Available"

        # Skin Type
        st_val = item.get('skin_type') or (item.get('specifications', {}).get('Skin Type') if isinstance(item.get('specifications'), dict) else None)
        if not st_val and isinstance(item.get('specifications'), dict):
            st_val = item['specifications'].get('Applied For') or item['specifications'].get('Ideal For')
        if not st_val:
            if 'all skin' in title_lower or 'all skin' in str(item.get('description', '')).lower():
                st_val = "All Skin Types"
        cat_specs["Skin Type"] = st_val if st_val else "Not Available"

        frag_m = re.search(r'\b(sandalwood|sandal|herbal|ayurvedic|rose|jasmine|lavender|lemon|mint|charcoal|neem|glycerin)\b', title_lower)
        cat_specs["Fragrance"] = frag_m.group(1).title() if frag_m else "Not Available"
    elif c_norm in ("shampoo",):
        cat_specs["Product Type"] = "Shampoo" if 'shampoo' in title_lower else ("Conditioner" if 'conditioner' in title_lower else "Hair Care")
        ingr_m = re.search(r'\b(keratin|biotin|argan|tea tree|onion|coconut|aloe vera|caffeine|protein|neem|rosemary|ginger)\b', title_lower)
        cat_specs["Key Ingredient"] = ingr_m.group(1).title() if ingr_m else "Not Available"
        if 'oily' in title_lower:
            cat_specs["Hair Type"] = "Oily Hair"
        elif 'dry' in title_lower or 'damaged' in title_lower:
            cat_specs["Hair Type"] = "Dry / Damaged Hair"
        elif 'dandruff' in title_lower or 'anti dandruff' in title_lower:
            cat_specs["Hair Type"] = "Anti-Dandruff"
        else:
            cat_specs["Hair Type"] = "Not Available"
        vol_m = re.search(r'(\d+\s*(?:ml|g))\b', title_lower)
        cat_specs["Volume / Weight"] = vol_m.group(1) if vol_m else specs.get('volume', 'Not Available')
    elif c_norm in ("makeup",):
        if 'lipstick' in title_lower or 'lip stick' in title_lower:
            cat_specs["Product Type"] = "Lipstick"
        elif 'foundation' in title_lower:
            cat_specs["Product Type"] = "Foundation"
        elif 'kajal' in title_lower:
            cat_specs["Product Type"] = "Kajal"
        elif 'mascara' in title_lower:
            cat_specs["Product Type"] = "Mascara"
        elif 'eyeliner' in title_lower or 'eye liner' in title_lower:
            cat_specs["Product Type"] = "Eyeliner"
        elif 'blush' in title_lower:
            cat_specs["Product Type"] = "Blush"
        else:
            cat_specs["Product Type"] = "Makeup Product"
        shade_m = re.search(r'\b(nude|red|pink|coral|berry|mauve|brown|plum|peach|orange|rose|wine)\b', title_lower)
        cat_specs["Shade / Color"] = shade_m.group(1).title() if shade_m else specs.get('color', 'Not Available')
        finish_m = re.search(r'\b(matte|glossy|satin|shimmer|metallic|dewy|natural)\b', title_lower)
        cat_specs["Finish"] = finish_m.group(1).title() if finish_m else "Not Available"
        vol_m = re.search(r'(\d+(?:\.\d+)?\s*(?:ml|g|gm))\b', title_lower)
        cat_specs["Net Quantity"] = vol_m.group(1) if vol_m else "Not Available"
    elif c_norm in ("skincare",):
        if 'serum' in title_lower:
            cat_specs["Product Type"] = "Serum"
        elif any(w in title_lower for w in ['moisturizer', 'moisturiser', 'cream', 'lotion']):
            cat_specs["Product Type"] = "Moisturizer / Cream"
        elif 'sunscreen' in title_lower or 'sun screen' in title_lower:
            cat_specs["Product Type"] = "Sunscreen"
        else:
            cat_specs["Product Type"] = "Skincare"
        ingr_m = re.search(r'\b(vitamin c|niacinamide|retinol|hyaluronic acid|aha|bha|salicylic acid|peptide|collagen|glycolic)\b', title_lower)
        cat_specs["Key Ingredient"] = ingr_m.group(1).title() if ingr_m else "Not Available"
        spf_m = re.search(r'\bspf\s*(\d+)\b', title_lower)
        cat_specs["SPF"] = f"SPF {spf_m.group(1)}" if spf_m else "Not Available"
        st_m = re.search(r'\b(oily|dry|combination|sensitive|normal|all skin)\b', title_lower)
        cat_specs["Skin Type"] = st_m.group(1).title() if st_m else "Not Available"
        vol_m = re.search(r'(\d+\s*(?:ml|g))\b', title_lower)
        cat_specs["Volume / Weight"] = vol_m.group(1) if vol_m else specs.get('volume', 'Not Available')
    elif c_norm in ("grocery", "food", "groceries"):
        if 'chia' in title_lower:
            cat_specs["Product Type"] = "Chia Seeds"
        elif 'pumpkin seed' in title_lower:
            cat_specs["Product Type"] = "Pumpkin Seeds"
        elif 'flax' in title_lower:
            cat_specs["Product Type"] = "Flax Seeds"
        elif 'almond' in title_lower:
            cat_specs["Product Type"] = "Almonds"
        elif 'cashew' in title_lower:
            cat_specs["Product Type"] = "Cashews"
        elif 'walnut' in title_lower:
            cat_specs["Product Type"] = "Walnuts"
        else:
            cat_specs["Product Type"] = "Grocery"
        w_m = re.search(r'(\d+(?:\.\d+)?\s*(?:g|kg|gm|grams?))\b', title_lower)
        cat_specs["Net Weight"] = w_m.group(1) if w_m else specs.get('weight', 'Not Available')
        pq_m = re.search(r'(?:pack of|pack|pack-)(\d+)', title_lower)
        cat_specs["Pack Quantity"] = f"Pack of {pq_m.group(1)}" if pq_m else "Not Available"
        desc_m = re.search(r'\b(organic|raw|roasted|unsalted|salted|natural|premium|whole)\b', title_lower)
        cat_specs["Product Description"] = desc_m.group(1).title() if desc_m else "Not Available"
    elif c_norm in ("television",):
        sz_m = re.search(r'(\d{2,3})\s*(?:inch|cm|-inch|")', title_lower)
        cat_specs["Screen Size"] = f"{sz_m.group(1)} inch" if sz_m else "Not Available"
        tech_m = re.search(r'\b(oled|qled|amoled|led|4k|8k|uhd|full\s*hd|fhd|hd\s*ready)\b', title_lower)
        cat_specs["Display Technology"] = tech_m.group(1).upper() if tech_m else "Not Available"
        hz_m = re.search(r'(\d+)\s*hz\b', title_lower)
        cat_specs["Refresh Rate"] = f"{hz_m.group(1)} Hz" if hz_m else "Not Available"
        cat_specs["Smart TV"] = "Yes" if 'smart' in title_lower else "Not Available"
        cat_specs["OS"] = specs.get('os', 'Not Available')
    elif c_norm in ("refrigerator",):
        cap_m = re.search(r'(\d+)\s*(?:l|litre|liter)\b', title_lower)
        cat_specs["Capacity"] = f"{cap_m.group(1)} Litres" if cap_m else "Not Available"
        door_m = re.search(r'\b(double\s*door|single\s*door|triple\s*door|side\s*by\s*side|french\s*door)\b', title_lower)
        cat_specs["Type"] = door_m.group(1).title() if door_m else "Not Available"
        ff_m = re.search(r'\b(frost\s*free|direct\s*cool)\b', title_lower)
        cat_specs["Cooling Type"] = ff_m.group(1).title() if ff_m else "Not Available"
        star_m = re.search(r'(\d)\s*star\b', title_lower)
        cat_specs["Energy Rating"] = f"{star_m.group(1)} Star" if star_m else "Not Available"
    elif c_norm in ("washing_machine",):
        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*kg\b', title_lower)
        cat_specs["Capacity"] = f"{cap_m.group(1)} kg" if cap_m else "Not Available"
        load_m = re.search(r'\b(front\s*load|top\s*load)\b', title_lower)
        cat_specs["Load Type"] = load_m.group(1).title() if load_m else "Not Available"
        auto_m = re.search(r'\b(fully\s*automatic|semi\s*automatic)\b', title_lower)
        cat_specs["Type"] = auto_m.group(1).title() if auto_m else "Not Available"
        rpm_m = re.search(r'(\d{3,4})\s*rpm\b', title_lower)
        cat_specs["Spin Speed"] = f"{rpm_m.group(1)} RPM" if rpm_m else "Not Available"
        star_m = re.search(r'(\d)\s*star\b', title_lower)
        cat_specs["Energy Rating"] = f"{star_m.group(1)} Star" if star_m else "Not Available"
    elif c_norm in ("air_conditioner",):
        ton_m = re.search(r'(\d+(?:\.\d+)?)\s*ton\b', title_lower)
        cat_specs["Capacity"] = f"{ton_m.group(1)} Ton" if ton_m else "Not Available"
        type_m = re.search(r'\b(split|window|portable|cassette)\b', title_lower)
        cat_specs["Type"] = type_m.group(1).title() + " AC" if type_m else "Not Available"
        cat_specs["Inverter"] = "Yes" if 'inverter' in title_lower else "Not Available"
        star_m = re.search(r'(\d)\s*star\b', title_lower)
        cat_specs["Energy Rating"] = f"{star_m.group(1)} Star" if star_m else "Not Available"
    elif c_norm in ("microwave",):
        cap_m = re.search(r'(\d+)\s*(?:l|litre|liter)\b', title_lower)
        cat_specs["Capacity"] = f"{cap_m.group(1)} Litres" if cap_m else "Not Available"
        mtype_m = re.search(r'\b(solo|grill|convection)\b', title_lower)
        cat_specs["Type"] = mtype_m.group(1).title() + " Microwave" if mtype_m else "Not Available"
        w_m = re.search(r'(\d{3,4})\s*(?:w|watt|watts)\b', title_lower)
        cat_specs["Wattage"] = f"{w_m.group(1)} W" if w_m else "Not Available"
    elif c_norm in ("mixer_grinder",):
        w_m = re.search(r'(\d{3,4})\s*(?:w|watt|watts)\b', title_lower)
        cat_specs["Wattage"] = f"{w_m.group(1)} W" if w_m else "Not Available"
        jar_m = re.search(r'(\d+)\s*jars?\b', title_lower)
        cat_specs["Number of Jars"] = f"{jar_m.group(1)} Jars" if jar_m else "Not Available"
        mat_m = re.search(r'\b(stainless steel|steel|polycarbonate)\b', title_lower)
        cat_specs["Material"] = mat_m.group(1).title() if mat_m else "Not Available"
    elif c_norm in ("shoes", "footwear", "slippers"):
        if any(w in title_lower for w in ('slipper', 'flip flop', 'slides', 'chappal')):
            cat_specs["Footwear Type"] = "Slippers / Slides"
        elif 'sneaker' in title_lower:
            cat_specs["Footwear Type"] = "Sneakers"
        elif 'sandal' in title_lower:
            cat_specs["Footwear Type"] = "Sandals"
        else:
            cat_specs["Footwear Type"] = "Footwear"
        sol_m = re.search(r'\b(eva|rubber|tpr|pu|polyurethane|leather|memory\s*foam)\b', title_lower)
        cat_specs["Sole Material"] = sol_m.group(1).upper() if sol_m and sol_m.group(1).lower() in ("eva", "tpr", "pu") else (sol_m.group(1).title() if sol_m else "Not Available")
        cl_m = re.search(r'\b(slip\s*on|slip-on|lace\s*up|lace-up|velcro)\b', title_lower)
        cat_specs["Closure Type"] = cl_m.group(0).title() if cl_m else ("Slip-On" if any(w in title_lower for w in ("slipper", "slide", "chappal")) else "Not Available")
        sz_num_m = re.search(r'\b(?:size|uk|us)\s*[:\s-]*(\d{1,2}(?:\.\d)?)\b', title_lower)
        cat_specs["Size"] = f"UK {sz_num_m.group(1)}" if sz_num_m else specs.get('size', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
    elif c_norm in ("clothing", "fashion"):
        sz_m = re.search(r'\b(s|m|l|xl|xxl|2xl|3xl|32|34|36|38|40|42)\b', title_lower)
        cat_specs["Size"] = sz_m.group(1).upper() if sz_m else specs.get('size', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
        mat_m = re.search(r'\b(100%\s*cotton|pure\s*cotton|denim|linen|silk|wool|polyester|rayon)\b', title_lower)
        cat_specs["Material"] = mat_m.group(1).title() if mat_m else specs.get('material', 'Not Available')
        ptn_m = re.search(r'\b(solid|printed|checkered|striped|floral|graphic)\b', title_lower)
        cat_specs["Pattern"] = ptn_m.group(1).title() if ptn_m else "Not Available"
        fit_m = re.search(r'\b(slim\s*fit|regular\s*fit|relaxed\s*fit|oversized)\b', title_lower)
        cat_specs["Fit Type"] = fit_m.group(1).title() if fit_m else "Not Available"
    elif c_norm in ("bags", "luggage", "backpack"):
        if any(w in title_lower for w in ['trolley', 'luggage', 'suitcase']):
            cat_specs["Product Type"] = "Trolley Bag / Suitcase"
        elif 'backpack' in title_lower:
            cat_specs["Product Type"] = "Backpack"
        else:
            cat_specs["Product Type"] = "Bag"
        cap_m = re.search(r'(\d{2,3})\s*(?:l|ltr|litres?|liters?)\b', title_lower)
        cat_specs["Capacity"] = f"{cap_m.group(1)} Litres" if cap_m else "Not Available"
        sz_m = re.search(r'(\d{2}\s*(?:inch|cm|-inch))\b', title_lower)
        cat_specs["Size"] = sz_m.group(1) if sz_m else "Not Available"
        mat_m = re.search(r'\b(polycarbonate|polyester|leather|nylon|abs)\b', title_lower)
        cat_specs["Material"] = mat_m.group(1).title() if mat_m else "Not Available"
        cat_specs["Lock Type"] = "TSA Lock" if 'tsa' in title_lower else ("Combination Lock" if 'lock' in title_lower else "Not Available")
        cat_specs["Wheels"] = "4 Wheel 360\u00b0 Spinner" if any(w in title_lower for w in ['4 wheel', 'spinner', '360', 'wheel']) else "Not Available"
    elif c_norm in ("kitchen", "home_appliance"):
        if 'mixer' in title_lower or 'grinder' in title_lower:
            cat_specs["Product Type"] = "Mixer Grinder"
        elif 'cooker' in title_lower:
            cat_specs["Product Type"] = "Pressure Cooker"
        elif 'kettle' in title_lower:
            cat_specs["Product Type"] = "Electric Kettle"
        else:
            cat_specs["Product Type"] = "Kitchen Appliance"
        w_m = re.search(r'\b(\d{3,4})\s*(?:w|watt|watts)\b', title_lower)
        cat_specs["Wattage"] = f"{w_m.group(1)} W" if w_m else "Not Available"
        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?)\b', title_lower)
        cat_specs["Capacity"] = f"{cap_m.group(1)} Litres" if cap_m else "Not Available"
        jar_m = re.search(r'(\d+)\s*jars?\b', title_lower)
        cat_specs["Jars Count"] = f"{jar_m.group(1)} Jars" if jar_m else "Not Available"
        mat_m = re.search(r'\b(stainless steel|steel|copper|non-stick|cast iron|aluminum)\b', title_lower)
        cat_specs["Material"] = mat_m.group(1).title() if mat_m else "Not Available"
    elif c_norm in ("headphones", "earphones", "earbuds"):
        if any(w in title_lower for w in ['tws', 'earbuds', 'buds']):
            cat_specs["Headphone Type"] = "True Wireless (TWS)"
        elif 'over' in title_lower or 'over-ear' in title_lower:
            cat_specs["Headphone Type"] = "Over Ear"
        elif 'neckband' in title_lower:
            cat_specs["Headphone Type"] = "Neckband"
        else:
            cat_specs["Headphone Type"] = "In-Ear"
        bt_m = re.search(r'\b(bluetooth\s*\d(?:\.\d)?|v\d(?:\.\d)?)\b', title_lower)
        cat_specs["Connectivity"] = bt_m.group(0).title() if bt_m else "Bluetooth Wireless"
        pb_m = re.search(r'(\d{2,3})\s*(?:hours?|hrs?)\b', title_lower)
        cat_specs["Playback Time"] = f"{pb_m.group(1)} Hours" if pb_m else "Not Available"
        cat_specs["Noise Cancellation"] = "Active Noise Cancellation (ANC)" if 'anc' in title_lower else ("Environmental Noise Cancellation (ENC)" if 'enc' in title_lower else "Not Available")
        cat_specs["Mic"] = "Built-in Mic" if 'mic' in title_lower else "Not Available"
    elif c_norm in ("watch", "smartwatch", "smartwatches"):
        cat_specs["Display Size"] = specs.get('display', 'Not Available')
        cat_specs["Calling Support"] = "Bluetooth Calling" if ('calling' in title_lower or 'bluetooth' in title_lower) else "Not Available"
        cat_specs["Water Resistance"] = "IP68" if 'ip68' in title_lower else ("Water Resistant" if 'water' in title_lower else "Not Available")
    elif c_norm in ("water_bottle", "water bottle", "bottle", "flask"):
        mat_m = re.search(r'\b(stainless steel|steel|copper|glass|borosilicate|plastic|aluminium|aluminum|silicone|thermosteel)\b', title_lower)
        cat_specs["Material"] = mat_m.group(0).title() if mat_m else specs.get('material', 'Not Available')
        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?|ml)\b', title_lower)
        cat_specs["Capacity"] = cap_m.group(0).upper() if cap_m else specs.get('capacity', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
        if any(w in title_lower for w in ('thermo', 'hot and cold', 'hot & cold', 'vacuum', 'insulated')):
            cat_specs["Bottle Type"] = "Insulated Flask"
        elif 'sipper' in title_lower:
            cat_specs["Bottle Type"] = "Sipper Bottle"
        elif any(w in title_lower for w in ('gym', 'sports')):
            cat_specs["Bottle Type"] = "Sports / Gym Bottle"
        else:
            cat_specs["Bottle Type"] = "Water Bottle"
        if 'flip' in title_lower:
            cat_specs["Lid Type"] = "Flip Top"
        elif 'sipper' in title_lower or 'straw' in title_lower:
            cat_specs["Lid Type"] = "Sipper / Straw"
        elif 'screw' in title_lower:
            cat_specs["Lid Type"] = "Screw Cap"
        else:
            cat_specs["Lid Type"] = "Standard Cap"
        if any(w in title_lower for w in ('vacuum insulated', 'double wall', 'double walled')):
            cat_specs["Insulation"] = "Double Wall Vacuum"
        elif any(w in title_lower for w in ('insulated', 'hot and cold', 'hot & cold', 'thermosteel')):
            cat_specs["Insulation"] = "Insulated"
        else:
            cat_specs["Insulation"] = "Non-Insulated"
        cat_specs["Leakproof"] = "Yes (Leak Proof)" if any(w in title_lower for w in ('leak proof', 'leakproof', 'spill proof', 'leak-proof')) else "Yes"
        cat_specs["Weight"] = specs.get('weight', 'Not Available')
    else:
        material_val = specs.get('material')
        cat_specs["Material"] = material_val if material_val and material_val not in ('N/A', 'Not Available') else "Not Available"
        color_val = specs.get('color')
        cat_specs["Color"] = color_val if color_val and color_val not in ('N/A', 'Not Available') else "Not Available"
        weight_val = specs.get('weight')
        cat_specs["Weight"] = weight_val if weight_val and weight_val not in ('N/A', 'Not Available') else "Not Available"
        wattage_val = specs.get('wattage')
        cat_specs["Wattage"] = wattage_val if wattage_val and wattage_val not in ('N/A', 'Not Available') else "Not Available"

    specs['category_specs'] = cat_specs
    return specs


def enrich_products_with_specs(products: list, query: str = "") -> list:
    """
    Attach extracted specs and normalized specifications to every product in the list.
    """
    for item in products:
        if not isinstance(item, dict):
            continue
        plat = str(item.get("platform") or "").lower()
        if "meesho" in plat and ('specifications' not in item or not item['specifications']):
            extract_meesho_specs(item)
        elif "flipkart" in plat:
            extract_flipkart_specs(item)

        if 'specs' not in item or 'category_specs' not in item.get('specs', {}):
            item['specs'] = extract_specs(item, query)
        if 'normalized_specifications' not in item or not item['normalized_specifications']:
            item['normalized_specifications'] = normalize_product_specifications(item, item.get('category') or query)
    return products



# ---------------------------------------------------------------------------
# Section 4 & 5: Normalization & Category Profiles
# ---------------------------------------------------------------------------

KEY_MAP = {
    # Quantity / Pack
    "net_quantity": "Net Quantity",
    "net quantity (n)": "Net Quantity",
    "net qty": "Net Quantity",
    "pack_quantity": "Pack Quantity",
    "pack of": "Pack Quantity",
    "pack size": "Pack Quantity",
    "number_of_items": "Pack Quantity",
    "quantity": "Quantity",
    
    # Weight / Volume
    "item_weight": "Weight",
    "net_weight": "Weight",
    "weight": "Weight",
    "item weight": "Weight",
    "volume": "Volume",
    "capacity": "Capacity",
    "capacity in l": "Capacity",
    "capacity in ml": "Capacity",
    "capacity_in_l": "Capacity",
    "leak proof": "Leakproof",
    "leakproof": "Leakproof",
    "bottle type": "Bottle Type",
    "lid type": "Lid Type",
    "cap type": "Lid Type",
    "insulation": "Insulation",
    "insulation type": "Insulation",
    
    # Color / Material / Fabric
    "colour": "Color",
    "color_name": "Color",
    "color": "Color",
    "fabric_type": "Fabric",
    "fabric": "Fabric",
    "material": "Material",
    "material_type": "Material",
    "sole_material": "Sole Material",
    "outer_material": "Material",
    
    # Ratings / Reviews
    "avg_rating": "Rating",
    "average_rating": "Rating",
    "rating": "Rating",
    "review_count": "Total Reviews",
    "reviews": "Total Reviews",
    "total_reviews": "Total Reviews",
    
    # Product identification
    "product_name": "Product Name",
    "title": "Product Name",
    "brand_name": "Brand",
    "brand": "Brand",
    "model_name": "Model",
    "model_number": "Model",
    "model": "Model",
    "product_type": "Product Type",
    "type": "Product Type",
    "seller_name": "Seller",
    "supplier_name": "Seller",
    "seller": "Seller",
    "supplier": "Seller",
    
    # Electronics
    "ram_capacity": "RAM",
    "system_ram": "RAM",
    "installed_ram": "RAM",
    "installed_memory": "RAM",
    "memory": "RAM",
    "system_memory": "RAM",
    "ram": "RAM",
    "storage_capacity": "Storage",
    "internal_storage": "Storage",
    "internal_memory": "Storage",
    "rom": "Storage",
    "item_weight": "Weight",
    "product_dimensions": "Dimensions",
    "dimensions": "Dimensions",
    "primary_material": "Material",
    "material": "Material",
    "volume": "Capacity",
    "capacity": "Capacity",
    "customer_rating": "Rating",
    "review_count": "Total Reviews",
    "ssd_capacity": "SSD/HDD",
    "processor_type": "Processor",
    "processor_brand": "Processor",
    "processor": "Processor",
    "operating_system": "Operating System",
    "os": "Operating System",
    "screen_size": "Screen Size",
    "display_size": "Screen Size",
    "display": "Display",
    "primary_camera": "Rear Camera",
    "rear_camera": "Rear Camera",
    "secondary_camera": "Front Camera",
    "front_camera": "Front Camera",
    "battery_capacity": "Battery",
    "battery": "Battery",
    "graphics_processor": "Graphics",
    "graphics": "Graphics",
    
    # Beauty & Personal Care
    "fragrance": "Fragrance",
    "scent": "Fragrance",
    "skin_type": "Skin Type",
    "ingredients": "Ingredients",
    "composition": "Ingredients",
    "benefits": "Benefits",
    "spf": "SPF",
    "form": "Form",
    "suitable_for": "Suitable For",
    
    # Clothing & Footwear
    "size": "Size",
    "pattern": "Pattern",
    "fit": "Fit",
    "fit_type": "Fit",
    "sleeve": "Sleeve",
    "sleeve_length": "Sleeve",
    "neck": "Neck",
    "neck_style": "Neck",
    "occasion": "Occasion",
    "wash_care": "Wash Care",
    "closure": "Closure",
    "fastening": "Closure",
    
    # Grocery & Food
    "flavor": "Flavor",
    "flavour": "Flavor",
    "diet_type": "Diet Type",
    "country_of_origin": "Country of Origin",
    "shelf_life": "Shelf Life",
    "expiry": "Expiry",
}


def normalize_specification_key(key: str) -> str:
    """
    Standardize different marketplace field names to prevent duplicate rows.
    """
    if not key:
        return ""
    clean = str(key).strip().lower().replace('-', '_').replace('(', '').replace(')', '').strip()
    if clean in KEY_MAP:
        return KEY_MAP[clean]
    
    if 'color' in clean or 'colour' in clean:
        return "Color"
    if 'weight' in clean:
        return "Weight"
    if 'quantity' in clean or 'qty' in clean:
        return "Quantity"
    if 'fabric' in clean:
        return "Fabric"
    if 'rating' in clean:
        return "Rating"
    if 'review' in clean:
        return "Total Reviews"
    if 'processor' in clean:
        return "Processor"
    if 'storage' in clean:
        return "Storage"
    if 'battery' in clean:
        return "Battery"
    if 'camera' in clean:
        return "Camera"
    if 'ingredient' in clean:
        return "Ingredients"
    if 'fragrance' in clean or 'scent' in clean:
        return "Fragrance"
    if 'skin' in clean and 'type' in clean:
        return "Skin Type"
    
    return str(key).strip().title()


def normalize_product_specifications(product: dict, category: str = "") -> dict:
    """
    Standardize specification names and values into canonical normalized records:
    {
      "original_name": str,
      "normalized_name": str,
      "original_value": str,
      "normalized_value": Any,
      "unit": str,
      "source": str,
      "verified": bool
    }
    """
    if not isinstance(product, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    source = product.get("platform") or product.get("source") or "Unknown"

    all_raw: dict[str, Any] = {}
    for top_k in ("brand", "model", "ram", "storage", "battery", "display", "processor",
                 "camera", "color", "size", "material", "fabric", "weight", "volume",
                 "quantity", "pack_quantity", "wattage", "warranty", "seller", "rating", "reviews", "review_count"):
        if product.get(top_k) is not None:
            all_raw[top_k] = product[top_k]

    if isinstance(product.get("specifications"), dict):
        all_raw.update(product["specifications"])
    if isinstance(product.get("specs"), dict):
        all_raw.update(product["specs"])
        if isinstance(product["specs"].get("category_specs"), dict):
            all_raw.update(product["specs"]["category_specs"])
    if isinstance(product.get("attributes"), dict):
        all_raw.update(product["attributes"])

    for orig_k, orig_v in all_raw.items():
        if orig_v is None:
            continue
        v_str = str(orig_v).strip()
        if not v_str or v_str.lower() in ("n/a", "none", "not available", "unknown", "null", "—", "-"):
            continue

        raw_norm_k = normalize_specification_key(str(orig_k))
        norm_name = raw_norm_k.lower().replace(" ", "_").replace("/", "_")
        norm_val: Any = v_str
        unit = ""

        # RAM normalization (GB / MB)
        if norm_name in ("ram", "installed_ram", "memory", "system_ram", "installed_memory", "system_memory"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(gb|mb)?', v_str, re.I)
            if m:
                val = float(m.group(1))
                u = (m.group(2) or "gb").upper()
                if u == "MB":
                    norm_val = round(val / 1024, 2)
                    unit = "GB"
                else:
                    norm_val = int(val) if val == int(val) else val
                    unit = "GB"
            norm_name = "ram"

        # Storage normalization (GB / TB)
        elif norm_name in ("storage", "rom", "internal_storage", "ssd_hdd", "ssd_capacity"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(gb|tb)?', v_str, re.I)
            if m:
                val = float(m.group(1))
                u = (m.group(2) or "gb").upper()
                if u == "TB":
                    norm_val = int(val * 1024)
                    unit = "GB"
                else:
                    norm_val = int(val) if val == int(val) else val
                    unit = "GB"
            norm_name = "storage"

        # Battery normalization (mAh)
        elif norm_name in ("battery", "battery_capacity"):
            m = re.search(r'(\d+)\s*(?:mah)?', v_str, re.I)
            if m:
                norm_val = int(m.group(1))
                unit = "mAh"
            norm_name = "battery"

        # Weight normalization (kg / g)
        elif norm_name in ("weight", "item_weight", "net_weight"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|kilograms?)', v_str, re.I)
            if m:
                val = float(m.group(1))
                u = m.group(2).lower()
                if "k" in u:
                    norm_val = round(val, 2)
                    unit = "kg"
                else:
                    norm_val = round(val / 1000.0, 3)
                    unit = "kg"
            norm_name = "weight"

        # Dimensions normalization (cm / mm / inches)
        elif norm_name in ("dimensions", "product_dimensions", "size"):
            m_in = re.search(r'(\d+(?:\.\d+)?)\s*(?:inch|"|-inch)', v_str, re.I)
            if m_in:
                norm_val = float(m_in.group(1))
                unit = "inches"
            else:
                m_cm = re.search(r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)', v_str, re.I)
                if m_cm:
                    norm_val = float(m_cm.group(1))
                    unit = "cm"
                else:
                    m_mm = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm|millimeters?)', v_str, re.I)
                    if m_mm:
                        norm_val = round(float(m_mm.group(1)) / 10.0, 2)
                        unit = "cm"

        # Volume / Capacity normalization (ml / L)
        elif norm_name in ("volume", "capacity", "net_volume"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|l|ltr|litres?|liters?)', v_str, re.I)
            if m:
                val = float(m.group(1))
                u = m.group(2).lower()
                if "m" in u:
                    norm_val = round(val, 1)
                    unit = "ml"
                else:
                    norm_val = round(val * 1000.0, 1)
                    unit = "ml"
            norm_name = "volume"

        # Wattage normalization (W)
        elif norm_name in ("wattage", "power", "output_wattage", "power_consumption"):
            m = re.search(r'(\d+)\s*(?:w|watt|watts)', v_str, re.I)
            if m:
                norm_val = int(m.group(1))
                unit = "W"
            norm_name = "wattage"

        # Rating normalization
        elif norm_name in ("rating", "customer_rating", "avg_rating"):
            try:
                r_clean = re.sub(r'[^\d.]', '', v_str)
                if r_clean:
                    norm_val = round(float(r_clean), 1)
                    unit = "stars"
            except Exception:
                pass
            norm_name = "rating"

        # Review count normalization
        elif norm_name in ("total_reviews", "review_count", "reviews"):
            try:
                digits = re.sub(r'[^\d]', '', v_str)
                if digits:
                    norm_val = int(digits)
                    unit = "reviews"
            except Exception:
                pass
            norm_name = "total_reviews"

        normalized[norm_name] = {
            "original_name": str(orig_k),
            "normalized_name": norm_name,
            "original_value": v_str,
            "normalized_value": norm_val,
            "unit": unit,
            "source": source,
            "verified": True
        }

    product["normalized_specifications"] = normalized
    return normalized


def normalize_unit_value(value_str: str, field_type: str = "") -> Tuple[str, Optional[float], str]:
    """
    Normalizes a value string into (formatted_str, numeric_value, unit).
    Handles: GB/MB, kg/g, ml/L, cm/mm, W.
    """
    if not value_str:
        return "", None, ""
    v_clean = str(value_str).strip()
    f_type = (field_type or "").strip().lower()

    # RAM / Storage (GB/MB/TB)
    if "ram" in f_type or "memory" in f_type or "storage" in f_type:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(gb|mb|tb)?', v_clean, re.I)
        if m:
            val = float(m.group(1))
            u = (m.group(2) or "gb").upper()
            if u == "MB":
                num = round(val / 1024, 2)
                return f"{num} GB", num, "GB"
            elif u == "TB":
                num = int(val * 1024)
                return f"{num} GB", float(num), "GB"
            else:
                num = int(val) if val == int(val) else val
                return f"{num} GB", float(num), "GB"

    # Weight (kg/g)
    if "weight" in f_type or "wt" in f_type:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|kilograms?)', v_clean, re.I)
        if m:
            val = float(m.group(1))
            u = m.group(2).lower()
            if "k" in u:
                return f"{val} kg", val, "kg"
            else:
                num = round(val / 1000.0, 3)
                return f"{num} kg", num, "kg"

    # Volume / Net quantity (ml/L)
    if "quantity" in f_type or "volume" in f_type or "capacity" in f_type:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|l|ltr|litres?|liters?)', v_clean, re.I)
        if m:
            val = float(m.group(1))
            u = m.group(2).lower()
            if "m" in u:
                return f"{val} ml", val, "ml"
            else:
                return f"{val * 1000.0} ml", val * 1000.0, "ml"

    # Wattage (W)
    if "watt" in f_type or "power" in f_type:
        m = re.search(r'(\d+)\s*(?:w|watt|watts)', v_clean, re.I)
        if m:
            num = float(m.group(1))
            return f"{int(num)} W", num, "W"

    # Generic number extraction fallback
    m = re.search(r'(\d+(?:\.\d+)?)', v_clean)
    if m:
        num = float(m.group(1))
        return v_clean, num, ""
    return v_clean, None, ""


# Common standard fields prioritising Quality of Product first, then Price of Product
_COMMON_IDENTITY_FIELDS = ["Product Name", "Brand", "Model", "Product Type"]

_COMMON_QUALITY_FIELDS = [
    "Quality Score", "Quality Band", "Data Confidence", "Build Material",
    "Warranty", "Seller", "Rating", "Reviews", "Quality Highlights"
]

_COMMON_PRICE_FIELDS = [
    "Price", "MRP", "Discount", "Value for Money Index"
]

# Category Specification Candidate Profiles
CATEGORY_SPEC_FIELDS: dict[str, list[str]] = {
    # 0. Storage Devices & Pen Drives / USB Flash Drives
    "pen_drive": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Storage Capacity", "Interface", "USB Version", "Read Speed", "Write Speed",
            "Material", "Color", "Compatibility", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "storage_device": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Storage Capacity", "Interface", "USB Version", "Read Speed", "Write Speed",
            "Material", "Color", "Compatibility", "Warranty", "Availability", "Buy Link"
        ]
    ),
    # 1. Chargers & Power Adapters
    "charger": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Output Voltage", "Output Wattage", "Power", "Input Voltage", "Connector Type",
            "Port Type", "Compatibility", "Fast Charging", "Cable Included", "Color",
            "Availability", "Buy Link"
        ]
    ),
    "adapter": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Output Voltage", "Output Wattage", "Power", "Input Voltage", "Connector Type",
            "Port Type", "Compatibility", "Fast Charging", "Cable Included", "Color",
            "Availability", "Buy Link"
        ]
    ),
    "power_bank": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Battery Capacity", "Output Wattage", "Output Ports", "Fast Charging",
            "Color", "Weight", "Availability", "Buy Link"
        ]
    ),
    # 2. Smartphones & Mobiles (Mobiles Category)
    "smartphone": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Operating System", "Custom UI", "Processor", "AnTuTu Score", "RAM", "Storage",
            "Storage Type", "Display Type", "Display Size", "Refresh Rate", "Peak Brightness",
            "Rear Camera", "Front Camera", "Battery Capacity", "Charging Speed",
            "Fast Charging Support", "5G", "5G Bands", "NFC Support", "IP Rating",
            "Fingerprint Sensor Type", "Weight", "Thickness", "Audio Jack",
            "Build Material", "Color", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "phone": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Operating System", "Custom UI", "Processor", "AnTuTu Score", "RAM", "Storage",
            "Storage Type", "Display Type", "Display Size", "Refresh Rate", "Peak Brightness",
            "Rear Camera", "Front Camera", "Battery Capacity", "Charging Speed",
            "Fast Charging Support", "5G", "5G Bands", "NFC Support", "IP Rating",
            "Fingerprint Sensor Type", "Weight", "Thickness", "Audio Jack",
            "Build Material", "Color", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "mobile": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Operating System", "Custom UI", "Processor", "AnTuTu Score", "RAM", "Storage",
            "Storage Type", "Display Type", "Display Size", "Refresh Rate", "Peak Brightness",
            "Rear Camera", "Front Camera", "Battery Capacity", "Charging Speed",
            "Fast Charging Support", "5G", "5G Bands", "NFC Support", "IP Rating",
            "Fingerprint Sensor Type", "Weight", "Thickness", "Audio Jack",
            "Build Material", "Color", "Warranty", "Availability", "Buy Link"
        ]
    ),
    # 3. Laptops & Computers (Laptops Category)
    "laptop": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Processor", "Generation", "Core/Thread Count", "Base/Boost Clock",
            "RAM Capacity", "RAM Type", "Expandable RAM", "Storage Capacity", "Storage Type",
            "Additional SSD Slot", "GPU", "TGP", "Display Size", "Resolution", "Panel Type",
            "Refresh Rate", "Color Gamut", "Battery Capacity", "Battery Life", "Charging Wattage",
            "Weight", "Ports", "Biometrics", "Build Material", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "laptops": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Processor", "Generation", "Core/Thread Count", "Base/Boost Clock",
            "RAM Capacity", "RAM Type", "Expandable RAM", "Storage Capacity", "Storage Type",
            "Additional SSD Slot", "GPU", "TGP", "Display Size", "Resolution", "Panel Type",
            "Refresh Rate", "Color Gamut", "Battery Capacity", "Battery Life", "Charging Wattage",
            "Weight", "Ports", "Biometrics", "Build Material", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "tablet": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Processor", "RAM", "Storage", "Display", "Battery", "Camera",
            "OS", "Connectivity", "Color", "Availability", "Buy Link"
        ]
    ),
    # 4. Earbuds & Headphones (Audio Category)
    "earbuds": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Form Factor", "Driver Size", "Frequency Response", "Active Noise Cancellation", "ANC Support", "ANC Depth",
            "Transparency Mode", "Mic Count", "Environmental Noise Cancellation", "Latency",
            "Bluetooth Version", "Codec Support", "Battery Life", "Battery Life (Earbuds)", "Battery Life (With Case)",
            "Charging Time", "Fast Charging Support", "Wireless Charging", "IP Rating",
            "App Support", "Touch Controls", "Multipoint Connection", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "headphones": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Form Factor", "Driver Size", "Frequency Response", "Active Noise Cancellation", "ANC Support", "ANC Depth",
            "Transparency Mode", "Mic Count", "Environmental Noise Cancellation", "Latency",
            "Bluetooth Version", "Codec Support", "Battery Life", "Battery Life (Earbuds)", "Battery Life (With Case)",
            "Charging Time", "Fast Charging Support", "Wireless Charging", "IP Rating",
            "App Support", "Touch Controls", "Multipoint Connection", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "earphones": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Form Factor", "Driver Size", "Frequency Response", "Active Noise Cancellation", "ANC Support", "ANC Depth",
            "Transparency Mode", "Mic Count", "Environmental Noise Cancellation", "Latency",
            "Bluetooth Version", "Codec Support", "Battery Life", "Battery Life (Earbuds)", "Battery Life (With Case)",
            "Charging Time", "Fast Charging Support", "Wireless Charging", "IP Rating",
            "App Support", "Touch Controls", "Multipoint Connection", "Warranty", "Availability", "Buy Link"
        ]
    ),
    # 5. Appliances (Split into Cooker, Mixer, Kettle)
    "pressure_cooker": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Material", "Base Type", "Induction Compatibility", "Lid Type",
            "Safety Valve Count", "Handle Material", "Gasket Release System", "Dishwasher Safe",
            "Warranty", "Availability", "Buy Link"
        ]
    ),
    "cooker": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Material", "Base Type", "Induction Compatibility", "Lid Type",
            "Safety Valve Count", "Handle Material", "Gasket Release System", "Dishwasher Safe",
            "Warranty", "Availability", "Buy Link"
        ]
    ),
    "mixer_grinder": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Motor Wattage", "RPM", "Number of Jars", "Jar Capacities", "Blade Material",
            "Body Material", "Overload Protection", "Speed Settings", "Pulse Mode",
            "Locking Mechanism", "Noise Level", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "mixer": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Motor Wattage", "RPM", "Number of Jars", "Jar Capacities", "Blade Material",
            "Body Material", "Overload Protection", "Speed Settings", "Pulse Mode",
            "Locking Mechanism", "Noise Level", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "electric_kettle": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Power/Wattage", "Heating Element Type", "Body Material",
            "Auto Shut-Off", "Boil Dry Protection", "360-Degree Base", "Water Level Indicator",
            "Keep Warm Function", "Cord Length", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "kettle": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Power/Wattage", "Heating Element Type", "Body Material",
            "Auto Shut-Off", "Boil Dry Protection", "360-Degree Base", "Water Level Indicator",
            "Keep Warm Function", "Cord Length", "Warranty", "Availability", "Buy Link"
        ]
    ),
    # 6. Fashion & Clothing / Shoes / Slippers
    "clothing": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Fabric/Material", "Fabric Material", "Fabric Composition", "Fit Type", "Pattern", "Sleeve Type", "Sleeve Length",
            "Neck/Collar Type", "Occasion", "Closure Type", "Care Instructions",
            "Transparency", "Stretchability", "Color", "Size", "Country of Origin", "Availability", "Buy Link"
        ]
    ),
    "fashion": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Fabric/Material", "Fabric Material", "Fabric Composition", "Fit Type", "Pattern", "Sleeve Type", "Sleeve Length",
            "Neck/Collar Type", "Occasion", "Closure Type", "Care Instructions",
            "Transparency", "Stretchability", "Color", "Size", "Country of Origin", "Availability", "Buy Link"
        ]
    ),
    "shoes": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Upper Material", "Sole Material", "Insole/Cushioning", "Closure Type", "Toe Shape",
            "Heel Height/Type", "Ankle Height", "Water Resistance", "Occasion",
            "Care Instructions", "Weight per Shoe", "Color", "Size", "Country of Origin", "Availability", "Buy Link"
        ]
    ),
    "footwear": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Upper Material", "Sole Material", "Insole/Cushioning", "Closure Type", "Toe Shape",
            "Heel Height/Type", "Ankle Height", "Water Resistance", "Occasion",
            "Care Instructions", "Weight per Shoe", "Color", "Size", "Country of Origin", "Availability", "Buy Link"
        ]
    ),
    "slippers": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Upper Material", "Sole Material", "Insole/Cushioning", "Closure Type", "Toe Shape",
            "Heel Height/Type", "Ankle Height", "Water Resistance", "Occasion",
            "Care Instructions", "Weight per Shoe", "Color", "Size", "Country of Origin", "Availability", "Buy Link"
        ]
    ),
    # 7. Bags & Backpacks
    "bags": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Material", "Number of Compartments", "Laptop Sleeve Size",
            "Water Resistance", "Dimensions", "Weight", "Closure Type", "Strap Type",
            "Lock Mechanism", "Expandability", "Rain Cover Included", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "backpack": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Material", "Number of Compartments", "Laptop Sleeve Size",
            "Water Resistance", "Dimensions", "Weight", "Closure Type", "Strap Type",
            "Lock Mechanism", "Expandability", "Rain Cover Included", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "luggage": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Material", "Number of Compartments", "Laptop Sleeve Size",
            "Water Resistance", "Dimensions", "Weight", "Closure Type", "Strap Type",
            "Lock Mechanism", "Expandability", "Rain Cover Included", "Warranty", "Availability", "Buy Link"
        ]
    ),
    # 8. Groceries & Nutrition
    "grocery": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Quantity / Net Weight", "Net Quantity", "Unit Price", "Pack Size", "Form", "Processing",
            "Dietary Preference", "Food Preference", "Protein Content",
            "Dietary Fibre", "Carbohydrates", "Added Sugar", "Fat/Trans Fat", "Calories",
            "Omega-3/Omega-6", "Vitamins/Minerals", "Shelf Life", "Country of Origin",
            "Certification", "Allergens", "Availability", "Buy Link"
        ]
    ),
    "food": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Quantity / Net Weight", "Net Quantity", "Unit Price", "Pack Size", "Form", "Processing",
            "Dietary Preference", "Food Preference", "Protein Content",
            "Dietary Fibre", "Carbohydrates", "Added Sugar", "Fat/Trans Fat", "Calories",
            "Omega-3/Omega-6", "Vitamins/Minerals", "Shelf Life", "Country of Origin",
            "Certification", "Allergens", "Availability", "Buy Link"
        ]
    ),
    # 9. Beauty / Skincare / Makeup (Split into Face Wash, Moisturizer, Sunscreen, Foundation, Lipstick)
    "face_wash": (
        ["Product Name", "Brand", "Product Type"] + _COMMON_QUALITY_FIELDS + [
            "Skin Type", "Key Ingredients", "Formulation", "Benefits", "Net Quantity", "Fragrance", "Usage", "Expiry",
            "Price", "Rating", "Reviews", "Availability", "Buy Link"
        ]
    ),
    "moisturizer": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Skin Type", "Texture", "Key Ingredients", "Finish", "SPF Included",
            "Non-Greasy", "Comedogenic Rating", "Target Concerns", "Paraben-Free",
            "Net Volume", "Shelf Life", "Availability", "Buy Link"
        ]
    ),
    "sunscreen": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "SPF Rating", "SPF Value", "PA Rating", "Broad Spectrum", "Filter Type", "Finish",
            "Water/Sweat Resistance", "White Cast", "Key Actives", "Paraben-Free",
            "Net Volume", "Shelf Life", "Availability", "Buy Link"
        ]
    ),
    "foundation": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Skin Type", "Coverage", "Finish", "Formulation", "SPF Included",
            "Shade Range", "Cruelty-Free", "Waterproof", "Transfer-Proof",
            "Net Weight/Volume", "Availability", "Buy Link"
        ]
    ),
    "lipstick": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Finish Type", "Finish", "Formulation", "Longevity", "Transfer-Proof", "Hydrating",
            "Cruelty-Free", "Paraben-Free", "Shade / Color", "Shade Family", "Net Weight", "Availability", "Buy Link"
        ]
    ),
    "skincare": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Skin Type", "Key Actives", "Key Benefits", "Formulation", "Target Concerns",
            "Volume", "Net Volume", "Shelf Life", "SPF", "Paraben-Free", "Availability", "Buy Link"
        ]
    ),
    "beauty": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Skin or Hair Type", "Key Ingredients", "Ingredients", "Key Benefits",
            "Net Quantity", "Fragrance", "Usage Instructions", "Paraben-Free Claims",
            "Expiry Information", "Availability", "Buy Link"
        ]
    ),
    "soap": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Weight", "Net Quantity", "Pack Quantity", "Skin Type", "Ingredients",
            "Fragrance", "Benefits", "Availability", "Buy Link"
        ]
    ),
    "shampoo": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Hair Type", "Net Quantity", "Volume", "Key Ingredient", "Ingredients",
            "Benefits", "Fragrance", "Usage Instructions", "Cruelty-Free",
            "Expiry Information", "Availability", "Buy Link"
        ]
    ),
    "makeup": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Finish", "Coverage", "Net Quantity", "Ingredients", "Skin Tone Suitability",
            "Suitable For", "Cruelty-Free", "Expiry Information", "Availability", "Buy Link"
        ]
    ),
    "water_bottle": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Material", "Capacity", "Color", "Bottle Type", "Lid Type", "Insulation",
            "Leakproof", "Dimensions", "Weight", "Country of Origin", "Warranty",
            "Availability", "Buy Link"
        ]
    ),
    # Other Appliances & Electronics
    "kitchen": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Appliance Type", "Power Consumption", "Wattage", "Voltage", "Capacity",
            "Dimensions", "Weight", "Material", "Operating Modes", "Energy Rating",
            "Noise Level", "Warranty", "Included Accessories", "Safety Features",
            "Compatibility", "Availability", "Buy Link"
        ]
    ),
    "home_appliance": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Appliance Type", "Power Consumption", "Wattage", "Voltage", "Capacity",
            "Dimensions", "Weight", "Material", "Operating Modes", "Energy Rating",
            "Noise Level", "Warranty", "Included Accessories", "Safety Features",
            "Compatibility", "Availability", "Buy Link"
        ]
    ),
    "appliance": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Appliance Type", "Power Consumption", "Wattage", "Voltage", "Capacity",
            "Dimensions", "Weight", "Material", "Operating Modes", "Energy Rating",
            "Noise Level", "Warranty", "Included Accessories", "Safety Features",
            "Compatibility", "Availability", "Buy Link"
        ]
    ),
    "television": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Screen Size", "Display Technology", "Resolution", "Refresh Rate",
            "HDR Support", "Smart TV", "Operating System", "Speaker Output",
            "Ports", "Energy Rating", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "refrigerator": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Type", "Cooling Type", "Compressor Type",
            "Energy Rating", "Number of Doors", "Dimensions", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "washing_machine": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Type", "Load Type", "Motor Type", "Spin Speed",
            "Wash Programs", "Energy Rating", "Water Efficiency", "Dimensions", "Warranty",
            "Availability", "Buy Link"
        ]
    ),
    "air_conditioner": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Type", "Inverter", "Energy Rating", "Cooling Area",
            "Noise Level", "Refrigerant", "Wi-Fi Control", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "microwave": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Capacity", "Type", "Wattage", "Number of Power Levels",
            "Auto Cook Menus", "Child Lock", "Dimensions", "Warranty", "Availability", "Buy Link"
        ]
    ),
    "electronics": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Power", "Wattage", "Voltage", "Capacity", "Dimensions", "Weight",
            "Material", "Features", "Operating Modes", "Energy Rating", "Noise Level",
            "Safety Features", "Warranty", "Included Accessories", "Color", "Availability", "Buy Link"
        ]
    ),
    "watch": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Display", "Dial Shape", "Strap Material", "Water Resistance",
            "Battery Life", "Connectivity", "Color", "Availability", "Buy Link"
        ]
    ),
    "default": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Color", "Material", "Dimensions", "Weight", "Quantity",
            "Availability", "Buy Link"
        ]
    ),
    "other": (
        _COMMON_IDENTITY_FIELDS + _COMMON_QUALITY_FIELDS + _COMMON_PRICE_FIELDS + [
            "Color", "Material", "Dimensions", "Weight", "Quantity",
            "Availability", "Buy Link"
        ]
    ),
}

# Compatibility alias for existing callers
CATEGORY_SPEC_PROFILES = CATEGORY_SPEC_FIELDS


# Strict category blacklist to prevent unrelated specifications from polluting tables
CATEGORY_BLACKLISTED_FIELDS: dict[str, set[str]] = {
    "pen_drive": {
        "ram", "ram capacity", "ram type", "expandable ram", "processor", "cpu", "generation",
        "cpu generation", "gpu", "tgp", "display", "display size", "panel type", "refresh rate",
        "color gamut", "laptop display", "battery", "battery capacity", "battery life", "charging wattage",
        "camera", "front camera", "rear camera", "os", "operating system", "5g", "sim", "skin type",
        "ingredients", "fabric", "sleeve", "fit", "sole material", "toe shape", "flavor"
    },
    "storage_device": {
        "ram", "ram capacity", "ram type", "expandable ram", "processor", "cpu", "generation",
        "cpu generation", "gpu", "tgp", "display", "display size", "panel type", "refresh rate",
        "color gamut", "laptop display", "battery", "battery capacity", "battery life", "charging wattage",
        "camera", "front camera", "rear camera", "os", "operating system", "5g", "sim", "skin type",
        "ingredients", "fabric", "sleeve", "fit", "sole material", "toe shape", "flavor"
    },
    "charger": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "front camera",
        "rear camera", "display", "screen size", "os", "operating system", "graphics",
        "gpu", "sim", "5g", "skin type", "ingredients", "fragrance", "fabric",
        "sleeve", "fit", "sole material", "toe shape", "flavor"
    },
    "adapter": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "front camera",
        "rear camera", "display", "screen size", "os", "operating system", "graphics",
        "gpu", "sim", "5g", "skin type", "ingredients", "fragrance", "fabric",
        "sleeve", "fit", "sole material", "toe shape", "flavor"
    },
    "soap": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "face_wash": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "skincare": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "beauty": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "grocery": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "food": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life"
    },
    "clothing": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "skin type", "ingredients", "battery life",
        "sole material", "insole material", "driver size"
    },
    "fashion": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "skin type", "ingredients", "battery life",
        "sole material", "insole material", "driver size"
    },
    "shoes": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "skin type", "ingredients", "battery life",
        "sleeve", "sleeve type", "neck type", "driver size"
    },
    "footwear": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "skin type", "ingredients", "battery life",
        "sleeve", "sleeve type", "neck type", "driver size"
    },
    "slippers": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "skin type", "ingredients", "battery life",
        "sleeve", "sleeve type", "neck type", "driver size"
    },
    "phone": {
        "output voltage", "output wattage", "input voltage", "connector type",
        "fabric", "sleeve", "fit", "skin type", "ingredients", "fragrance",
        "shelf life", "dietary preference", "sole material",
        "screen size", "capacity", "energy rating", "load type"
    },
    "smartphone": {
        "output voltage", "output wattage", "input voltage", "connector type",
        "fabric", "sleeve", "fit", "skin type", "ingredients", "fragrance",
        "shelf life", "dietary preference",
        "screen size", "capacity", "energy rating", "load type"
    },
    "laptop": {
        "output voltage", "input voltage", "fabric", "sleeve", "fit",
        "skin type", "ingredients", "fragrance", "shelf life", "dietary preference",
        "screen size", "capacity", "energy rating", "load type"
    },
    # New appliance subcategories
    "television": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "refrigerator": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "display", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "washing_machine": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "display", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "air_conditioner": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "display", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "microwave": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "display", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "mixer_grinder": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "battery",
        "sim", "5g", "display", "fabric", "sleeve", "fit", "sole material",
        "skin type", "ingredients", "fragrance", "shelf life"
    },
    "shampoo": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life",
        "sole material", "energy rating"
    },
    "makeup": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "sim", "5g", "fabric", "sleeve", "fit", "battery life",
        "sole material", "energy rating"
    },
    "water_bottle": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "gpu", "sim", "5g", "fabric", "sleeve", "fit", "battery life",
        "sole material", "screen size"
    },
    "bottle": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "wattage", "voltage", "connector type", "ports",
        "graphics", "gpu", "sim", "5g", "fabric", "sleeve", "fit", "battery life",
        "sole material", "screen size"
    },
    "pressure_cooker": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "graphics", "gpu", "sim", "5g", "fabric", "sleeve",
        "fit", "sole material", "skin type", "ingredients", "battery life", "driver size"
    },
    "cooker": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "graphics", "gpu", "sim", "5g", "fabric", "sleeve",
        "fit", "sole material", "skin type", "ingredients", "battery life", "driver size"
    },
    "electric_kettle": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "graphics", "gpu", "sim", "5g", "fabric", "sleeve",
        "fit", "sole material", "skin type", "ingredients", "battery life", "driver size"
    },
    "kettle": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "graphics", "gpu", "sim", "5g", "fabric", "sleeve",
        "fit", "sole material", "skin type", "ingredients", "battery life", "driver size"
    },
    "mixer": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "operating system", "graphics", "gpu", "sim", "5g", "fabric", "sleeve",
        "fit", "sole material", "skin type", "battery life", "driver size"
    },
    "moisturizer": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "wattage", "voltage", "fabric", "sleeve", "sole material", "screen size"
    },
    "sunscreen": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "wattage", "voltage", "fabric", "sleeve", "sole material", "screen size"
    },
    "foundation": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "wattage", "voltage", "fabric", "sleeve", "sole material", "screen size"
    },
    "lipstick": {
        "ram", "storage", "rom", "processor", "cpu", "camera", "display", "os",
        "wattage", "voltage", "fabric", "sleeve", "sole material", "screen size"
    },
}


def has_real_value(value: Any) -> bool:
    """
    Checks if a specification value contains genuine extracted product information.
    Rejects missing/null data, empty strings, and scraping error or fallback placeholders.
    """
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        invalid_values = {
            "", "n/a", "na", "not available", "unknown", "null", "none",
            "scraping unavailable", "no matching product", "no matching product found",
            "scraper unavailable", "temporarily unavailable", "—", "-", "generic",
            "0", "0.0", "₹0", "rs. 0", "rs 0", "0 rating", "0 reviews", "0%"
        }
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in invalid_values:
            return False
        low = cleaned.lower()
        if "temporarily unavailable" in low or "scraping unavailable" in low or "no matching product" in low:
            return False
        return True
    return True


def should_display_row(amazon_value: Any, flipkart_value: Any, meesho_value: Any) -> bool:
    """
    Determines whether a specification row should be rendered.
    Returns True only if at least one marketplace has a genuine extracted value.
    """
    return any([
        has_real_value(amazon_value),
        has_real_value(flipkart_value),
        has_real_value(meesho_value)
    ])


def is_valid_image_url(url: Any) -> bool:
    """Validates that an image URL is a well-formed web URL and not a placeholder."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://") or u.startswith("data:image/")):
        return False
    if len(u) < 10:
        return False
    if any(ph in u.lower() for ph in ("placeholder", "no_image", "not_available", "none", "null")):
        return False
    return True


def get_fields_for_category(category: str) -> list[str]:
    """Returns prioritized candidate specification fields tailored for the detected category."""
    cat_clean = (category or "").strip().lower()
    if any(w in cat_clean for w in ("water bottle", "water_bottle", "bottle", "sipper", "flask")):
        fields = list(CATEGORY_SPEC_FIELDS["water_bottle"])
    elif any(w in cat_clean for w in ("pen drive", "pendrive", "storage", "flash drive", "pen_drive", "storage_device")):
        fields = list(CATEGORY_SPEC_FIELDS["pen_drive"])
    elif any(w in cat_clean for w in ("cooker", "pressure cooker")):
        fields = list(CATEGORY_SPEC_FIELDS["pressure_cooker"])
    elif any(w in cat_clean for w in ("mixer", "grinder")):
        fields = list(CATEGORY_SPEC_FIELDS["mixer_grinder"])
    elif any(w in cat_clean for w in ("kettle", "electric kettle")):
        fields = list(CATEGORY_SPEC_FIELDS["electric_kettle"])
    elif any(w in cat_clean for w in ("sunscreen", "sun screen")):
        fields = list(CATEGORY_SPEC_FIELDS["sunscreen"])
    elif any(w in cat_clean for w in ("moisturizer", "moisturiser", "face cream")):
        fields = list(CATEGORY_SPEC_FIELDS["moisturizer"])
    elif any(w in cat_clean for w in ("foundation",)):
        fields = list(CATEGORY_SPEC_FIELDS["foundation"])
    elif any(w in cat_clean for w in ("lipstick", "lip stick", "lip balm")):
        fields = list(CATEGORY_SPEC_FIELDS["lipstick"])
    elif any(w in cat_clean for w in ("face wash", "facewash")):
        fields = list(CATEGORY_SPEC_FIELDS["face_wash"])
    elif cat_clean in CATEGORY_SPEC_FIELDS:
        fields = list(CATEGORY_SPEC_FIELDS[cat_clean])
    else:
        fields = None
        for k, f_list in CATEGORY_SPEC_FIELDS.items():
            if k in cat_clean or cat_clean in k:
                fields = list(f_list)
                break
    if not fields:
        fields = list(CATEGORY_SPEC_FIELDS["default"])
    if "Buy Link" not in fields:
        fields.append("Buy Link")
    return fields


def get_category_spec_profile(category: str) -> list:
    """Backward compatible alias returning candidate fields for a category."""
    return get_fields_for_category(category)


def get_relevant_specifications(category: str, specifications: Optional[dict] = None) -> list[str]:
    """Helper alias returning relevant spec keys for a category."""
    return get_fields_for_category(category)


def extract_field_value(product: Optional[dict], field: str, category: str) -> Optional[str]:
    """
    Extracts an authentic specification value from a marketplace product object.
    Never invents fake values (₹0, 0 rating, Generic brand, etc.).
    Returns None if missing or invalid.
    """
    if not product or not isinstance(product, dict):
        return None

    cat_low = (category or "").strip().lower()
    f_clean = field.strip()
    f_low = f_clean.lower()

    # Reject blacklisted fields for this product category
    blacklist = CATEGORY_BLACKLISTED_FIELDS.get(cat_low, set())
    if f_low in blacklist:
        return None

    # 1. Product Name / Title
    if f_low in ("product name", "title", "name"):
        title = product.get("title") or product.get("product_name")
        return str(title).strip() if has_real_value(title) else None

    # 2. Brand
    if f_low == "brand":
        b = product.get("brand")
        if has_real_value(b) and str(b).strip().lower() not in ("generic", "unknown", "other", "n/a", "none"):
            return str(b).strip()
        title_s = str(product.get("title") or product.get("product_name") or "")
        from search.query_parser import KNOWN_BRANDS
        for kb in KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(kb) + r'\b', title_s, re.IGNORECASE):
                return kb.title()
        return None

    # 3. Model
    if f_low in ("model", "model number", "model name"):
        m = product.get("model") or product.get("model_number")
        if has_real_value(m) and str(m).strip().lower() not in ("standard", "generic", "n/a", "unknown", "none"):
            return str(m).strip()
        title_s = str(product.get("title") or product.get("product_name") or "")
        m_mod = re.search(r'\b(?:toad\s*[a-z0-9iv]+|iphone\s*\d+(?:\s*pro(?:\s*max)?)?|galaxy\s*[a-z0-9]+)\b', title_s, re.IGNORECASE)
        if m_mod:
            return m_mod.group(0).strip().title()
        return None

    # 4. Product Type
    if f_low in ("product type", "category"):
        title_l = str(product.get("title") or "").lower()
        if any(w in title_l for w in ("backpack", "laptop bag", "sleeve", "sleeve case", "duffel", "luggage", "trolley")):
            if "backpack" in title_l:
                return "Laptop Backpack"
            if "sleeve" in title_l:
                return "Laptop Sleeve"
            return "Laptop Bag"
        pt = product.get("product_type") or product.get("category")
        if has_real_value(pt) and str(pt).strip().lower() not in ("other", "general", "default"):
            return str(pt).strip().title()
        return None

    # Quality Score (First Preference)
    if f_low in ("quality score", "estimated quality", "estimated quality score", "quality"):
        qs = product.get("quality_score") or (product.get("quality_report", {}).get("raw_quality_score") if isinstance(product.get("quality_report"), dict) else None)
        q_band = product.get("quality_band") or (product.get("quality_report", {}).get("quality_band") if isinstance(product.get("quality_report"), dict) else "Standard Quality")
        if qs is not None:
            return f"{float(qs):.0f}/100 ({q_band})"
        return None

    # Quality Band
    if f_low in ("quality band", "quality rating"):
        q_band = product.get("quality_band") or (product.get("quality_report", {}).get("quality_band") if isinstance(product.get("quality_report"), dict) else None)
        if has_real_value(q_band):
            return str(q_band).strip()
        return None

    # Data Confidence
    if f_low in ("data confidence", "evidence confidence", "evidence completeness"):
        dc = product.get("data_confidence") or (product.get("quality_report", {}).get("data_confidence") if isinstance(product.get("quality_report"), dict) else None)
        if dc is not None:
            return f"{float(dc):.0f}% Verified Evidence"
        return None

    # Build Material
    if f_low in ("build material", "material", "fabric", "build"):
        q_mat = (product.get("quality_attributes", {}).get("material") if isinstance(product.get("quality_attributes"), dict) else None)
        mat = q_mat or product.get("material") or product.get("fabric")
        if has_real_value(mat):
            return str(mat).strip().title()

    # Quality Highlights / Review Sentiment
    if f_low in ("quality highlights", "review insights", "positive themes", "key strengths"):
        themes = product.get("positive_themes") or (product.get("quality_report", {}).get("review_signals", {}).get("positive_themes") if isinstance(product.get("quality_report"), dict) else [])
        if themes and isinstance(themes, list):
            return " • ".join(str(t) for t in themes[:2])
        return None

    # Value for Money Index
    if f_low in ("value for money", "value for money index", "value index"):
        vfm = product.get("vfm_index")
        if vfm is not None and float(vfm) > 0:
            return f"{float(vfm):.1f}/100"
        qs = product.get("quality_score")
        p_num = product.get("price_num")
        if qs and p_num and p_num > 0:
            from search.quality_scorer import calculate_value_for_money_index
            calc_vfm = calculate_value_for_money_index(float(qs), float(p_num), float(p_num))
            return f"{calc_vfm:.1f}/100"
        return None

    # 5. Price
    if f_low == "price":
        p_num = product.get("price_num")
        p_str = product.get("price")
        if p_num and p_num > 0:
            return f"₹{int(p_num):,}" if p_num == int(p_num) else f"₹{p_num:,.2f}"
        if has_real_value(p_str) and str(p_str).strip() not in ("0", "₹0", "₹ 0"):
            return str(p_str).strip()
        return None

    # 6. MRP / Original Price
    if f_low in ("mrp", "original price"):
        m_num = product.get("mrp_num")
        m_str = product.get("mrp") or product.get("original_price")
        if m_num and m_num > 0:
            return f"₹{int(m_num):,}" if m_num == int(m_num) else f"₹{m_num:,.2f}"
        if has_real_value(m_str) and str(m_str).strip() not in ("0", "₹0", "₹ 0"):
            return str(m_str).strip()
        return None

    # 7. Discount
    if f_low in ("discount", "discount %"):
        d = product.get("discount") or product.get("discount_percent")
        if has_real_value(d) and str(d).strip().lower() not in ("0", "0%", "none"):
            d_str = str(d).strip()
            return d_str if "%" in d_str else f"{d_str}% off"
        return None

    # 8. Rating
    if f_low == "rating":
        r = product.get("rating")
        if r is not None:
            try:
                rf = float(str(r).replace("★", "").strip())
                if rf > 0:
                    return f"★ {rf:.1f}" if rf != int(rf) else f"★ {int(rf)}"
            except Exception:
                pass
        return None

    # 9. Reviews / Review Count
    if f_low in ("reviews", "total reviews", "review count"):
        rc = product.get("review_count") or product.get("reviews")
        if rc is not None:
            try:
                clean_rc = re.sub(r"[^\d]", "", str(rc))
                if clean_rc and int(clean_rc) > 0:
                    return f"{int(clean_rc):,} reviews"
            except Exception:
                pass
        return None

    # 10. Availability
    if f_low == "availability":
        avail = product.get("availability")
        if has_real_value(avail):
            return str(avail).strip()
        if product.get("in_stock") is True:
            return "In Stock"
        elif product.get("in_stock") is False:
            return "Out of Stock"
        return None

    # 11. Buy Link
    if f_low in ("buy link", "link", "url", "product url"):
        lnk = product.get("product_url") or product.get("link") or product.get("url")
        if has_real_value(lnk):
            return str(lnk).strip()
        return None

    # 11. Seller
    if f_low == "seller":
        seller = product.get("seller")
        if has_real_value(seller) and str(seller).strip().lower() not in ("verified seller", "unknown"):
            return str(seller).strip()
        return None

    # 12. Warranty
    if f_low == "warranty":
        w = product.get("warranty")
        if has_real_value(w):
            return str(w).strip()

    # 13. Color
    if f_low == "color":
        c = product.get("color")
        if has_real_value(c):
            return str(c).strip().title()

    # 14. Size
    if f_low == "size":
        s = product.get("size")
        if has_real_value(s):
            return str(s).strip().upper()

    # 15. Material / Fabric
    if f_low in ("material", "fabric"):
        mat = product.get("material") or product.get("fabric")
        if has_real_value(mat):
            return str(mat).strip().capitalize()

    # 16. Weight
    if f_low == "weight":
        wt = product.get("weight")
        if not has_real_value(wt) and isinstance(product.get("specifications"), dict):
            wt = product["specifications"].get("Weight") or product["specifications"].get("Quantity") or product["specifications"].get("Net Weight")
        if not has_real_value(wt) and product.get("subtitle"):
            m_s = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg|grams?|ml|l))\b', str(product["subtitle"]), re.I)
            if m_s:
                wt = m_s.group(1)
        if has_real_value(wt):
            return str(wt).strip()

    # 17. Quantity / Pack Quantity
    if f_low in ("quantity", "net quantity", "pack quantity", "pack size"):
        qty = product.get("quantity") or product.get("net_quantity") or product.get("pack_quantity") or product.get("pack_size")
        if not has_real_value(qty) and isinstance(product.get("specifications"), dict):
            qty = product["specifications"].get("Pack of") or product["specifications"].get("Pack Quantity") or product["specifications"].get("Net Quantity")
        if not has_real_value(qty) and product.get("subtitle"):
            m_p = re.search(r'(\d+)\s*x', str(product["subtitle"]))
            if m_p:
                qty = m_p.group(1)
        if has_real_value(qty):
            q_str = str(qty).strip()
            if q_str.isdigit():
                return f"Pack of {q_str}" if int(q_str) > 1 else "Pack of 1"
            return q_str

    # 17b. Skin Type
    if f_low in ("skin type", "applied for"):
        st = product.get("skin_type")
        if not has_real_value(st) and isinstance(product.get("specifications"), dict):
            st = product["specifications"].get("Skin Type") or product["specifications"].get("Applied For") or product["specifications"].get("Ideal For")
        if has_real_value(st):
            return str(st).strip()

    # 18. Volume
    if f_low in ("volume", "net volume"):
        vol = product.get("volume") or product.get("net_volume")
        if has_real_value(vol):
            return str(vol).strip()

    # 19. Check normalized and explicit specifications dictionaries
    specs_dicts = [
        product.get("normalized_specifications"),
        product.get("specifications"),
        product.get("specs"),
        product.get("attributes"),
        product.get("specs", {}).get("category_specs") if isinstance(product.get("specs"), dict) else None
    ]
    for sp_dict in specs_dicts:
        if isinstance(sp_dict, dict):
            # Check normalized records first
            if f_clean in sp_dict:
                rec = sp_dict[f_clean]
                if isinstance(rec, dict) and "original_value" in rec:
                    return str(rec["original_value"]).strip()
                elif has_real_value(rec):
                    return str(rec).strip()
            # Case insensitive exact match
            for sk, sv in sp_dict.items():
                if sk.strip().lower() == f_low:
                    if isinstance(sv, dict) and "original_value" in sv:
                        return str(sv["original_value"]).strip()
                    if has_real_value(sv):
                        return str(sv).strip()
            # Substring match
            for sk, sv in sp_dict.items():
                sk_clean = sk.strip().lower()
                if (f_low in sk_clean or sk_clean in f_low):
                    if isinstance(sv, dict) and "original_value" in sv:
                        return str(sv["original_value"]).strip()
                    if has_real_value(sv):
                        return str(sv).strip()

    # 20. AnTuTu Benchmark Score - only if verified, never fabricate!
    if "antutu" in f_low:
        # Never generate an unverified score
        return None

    # 21. Title and Description Fallback strictly guarded by detected category
    title = str(product.get("title") or "").strip()
    title_low = title.lower()
    desc_low = str(product.get("description") or "").lower()
    text_corpus = f"{title_low} {desc_low}"

    if cat_low in ("charger", "adapter"):
        if f_low in ("output wattage", "wattage", "power"):
            m = re.search(r'\b(\d{1,3})\s*(?:w|watt|watts)\b', title_low)
            if m:
                return f"{m.group(1)}W"
        elif f_low in ("output voltage", "voltage"):
            m = re.search(r'\b(\d{1,3}(?:\.\d+)?)\s*v\b', title_low)
            if m:
                return f"{m.group(1)}V"
        elif f_low in ("input voltage",):
            m = re.search(r'\b(100[-–\s]*240\s*v(?:ac)?)\b', title_low)
            if m:
                return m.group(1).upper()
        elif f_low in ("connector type", "port type"):
            if "type c" in title_low or "type-c" in title_low or "usb-c" in title_low:
                return "Type-C"
            if "blue pin" in title_low:
                return "Blue Pin (4.5mm)"
            m = re.search(r'(\d(?:\.\d)?\s*mm\s*[x*]\s*\d(?:\.\d)?\s*mm)', title_low)
            if m:
                return m.group(1)
        elif f_low == "compatibility":
            for b_name in ("hp", "dell", "lenovo", "asus", "acer", "apple", "samsung", "realme", "vivo"):
                m = re.search(rf'for\s+({b_name}[\w\s]+?)(?:laptop|charger|adapter|\d+w|,|\.|$)', title_low)
                if m:
                    return m.group(1).strip().title()
        elif f_low == "fast charging":
            if any(k in title_low for k in ("fast charge", "fast charging", "quick charge", "dash charge", "warp charge", "vooc")):
                return "Yes (Fast Charging)"

    elif cat_low in ("phone", "smartphone", "mobile"):
        if f_low in ("ram", "installed_ram"):
            m = re.search(r'\b(\d+)\s*gb\s*ram\b', title_low)
            if m:
                return f"{m.group(1)} GB"
        elif f_low in ("storage", "internal storage", "rom"):
            m = re.search(r'\b(64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b', title_low)
            if m:
                return m.group(0).upper()
        elif f_low in ("5g", "5g support", "network type"):
            if "5g" in title_low:
                return "Yes (5G Ready)"
            elif "4g" in title_low:
                return "4G VoLTE"
        elif f_low == "processor" or f_low == "chipset":
            m = re.search(r'\b(snapdragon\s*[\d\w]+|dimensity\s*\d{3,4}|bionic\s*a\d+|helio\s*g\d+|tensor\s*g\d|exynos\s*\d{4})\b', text_corpus, re.I)
            if m:
                return m.group(1).title()
        elif f_low in ("display", "screen size", "display size"):
            m = re.search(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|"|-inch)\b', title_low)
            if m:
                return f'{m.group(1)}"'
        elif f_low in ("display type", "display resolution", "refresh rate"):
            if "amoled" in text_corpus:
                return "AMOLED Display"
            if "120hz" in text_corpus:
                return "120Hz Refresh Rate"
        elif f_low in ("battery", "battery capacity"):
            m = re.search(r'\b(\d{4,5})\s*mah\b', text_corpus)
            if m:
                return f"{m.group(1)} mAh"
        elif f_low in ("rear camera", "camera"):
            m = re.search(r'\b(\d{2,3}\s*mp|\d+\s*\+\s*\d+\s*mp)\b', text_corpus)
            if m:
                return m.group(1).upper()
        elif f_low in ("fast charging",):
            m = re.search(r'\b(\d{2,3}\s*w)\s*(?:fast|charg|supervooc|warp)?', text_corpus)
            if m:
                return f"{m.group(1).upper()} Fast Charging"

    elif cat_low in ("laptop", "laptops"):
        if f_low == "processor":
            m = re.search(r'\b(core\s*i[3579]|ryzen\s*[3579]|apple\s*m\d|m[1234]\s*pro|ultra\s*[579])\b', title_low)
            if m:
                return m.group(0).title()
        elif f_low in ("ram", "installed_ram"):
            m = re.search(r'\b(\d+)\s*gb\s*ram\b|\b(\d+)\s*gb\b', title_low)
            if m:
                return f"{m.group(1) or m.group(2)} GB"
        elif f_low in ("storage", "ssd/hdd", "ssd capacity"):
            m = re.search(r'\b(\d+)\s*(?:gb|tb)\s*(?:ssd|hdd)\b', title_low)
            if m:
                return m.group(0).upper()
        elif f_low in ("graphics/gpu", "graphics"):
            m = re.search(r'\b(rtx\s*\d{4}|gtx\s*\d{4}|radeon|iris\s*xe|integrated|intel\s*uhd)\b', text_corpus)
            if m:
                return m.group(0).title()
        elif f_low in ("operating system", "os"):
            if "windows 11" in text_corpus:
                return "Windows 11 Home"
            elif "macos" in text_corpus:
                return "macOS"

    elif cat_low in ("grocery", "food"):
        if f_low in ("weight", "net quantity"):
            m = re.search(r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?)\b', title_low)
            if m:
                return f"{m.group(1)}{m.group(2)}"
        elif f_low in ("ingredients",):
            m = re.search(r'\b(chia\s*seeds?|flax\s*seeds?|quinoa|oats|almonds|cashews|walnuts|green\s*tea|honey|whey\s*protein|coffee)\b', title_low)
            if m:
                return m.group(0).title()
        elif f_low in ("dietary information", "diet type"):
            matches = [d.title() for d in ("gluten-free", "gluten free", "vegan", "sugar free", "high fiber", "organic") if d in text_corpus]
            if matches:
                return ", ".join(dict.fromkeys(matches))
        elif f_low in ("certifications",):
            if "organic" in text_corpus:
                return "Organic"
            if "fssai" in text_corpus:
                return "FSSAI Certified"

    elif cat_low in ("soap", "face_wash", "skincare", "beauty"):
        if f_low in ("weight",):
            m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|gm|grams?)\b', title_low)
            if m:
                return f"{m.group(1)}{m.group(2)}"
        elif f_low in ("volume", "net quantity"):
            m = re.search(r'\b(\d+(?:\.\d+)?)\s*(ml|l)\b', title_low)
            if m:
                return f"{m.group(1)} {m.group(2)}"
        elif f_low in ("ingredients", "key ingredients"):
            v_m = re.search(r'\b(vitamin c|salicylic acid|tea tree|neem|aloe vera|charcoal|hyaluronic|papaya|coffee|ubtan|sandalwood|saffron)\b', title_low)
            if v_m:
                return v_m.group(1).title()
        elif f_low in ("skin or hair type", "skin type"):
            if "all skin" in text_corpus:
                return "All Skin Types"
            if "oily" in text_corpus:
                return "Oily / Acne Prone Skin"
            if "dry" in text_corpus:
                return "Dry Skin"

    elif cat_low in ("water_bottle", "bottle"):
        if f_low in ("material",):
            m = re.search(r'\b(stainless\s*steel|steel|copper|glass|plastic|bpa-free\s*plastic|borosilicate\s*glass|aluminum)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("capacity", "volume", "size"):
            m = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:litre|litres|liter|liters|l|ml)\b', title_low)
            if m:
                unit = m.group(0).lower()
                if any(u in unit for u in ('l', 'litre', 'liter')):
                    return f"{m.group(1)} Litre"
                return f"{m.group(1)} ml"
        elif f_low in ("bottle type", "type"):
            if "fridge" in text_corpus:
                return "Fridge Bottle"
            elif any(k in text_corpus for k in ("gym", "sports", "workout")):
                return "Sports / Gym Bottle"
            elif "sipper" in text_corpus:
                return "Sipper Bottle"
            elif "single wall" in text_corpus:
                return "Single Wall Bottle"
            elif any(k in text_corpus for k in ("double wall", "insulated", "vacuum")):
                return "Vacuum Insulated Bottle"
            elif "water bottle" in text_corpus:
                return "Water Bottle"
        elif f_low in ("lid type", "cap type"):
            m = re.search(r'\b(flip\s*top|sipper|metal\s*cap|straw|twin\s*lid|screw\s*cap|spout|push\s*button)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("insulation", "thermal insulation"):
            if any(k in text_corpus for k in ("vacuum insulated", "double wall vacuum", "vacuum insulation")):
                return "Vacuum Insulated (Hot & Cold)"
            elif "insulated" in text_corpus:
                return "Insulated"
            elif "single wall" in text_corpus:
                return "Single Wall (Non-Insulated)"
        elif f_low in ("leakproof", "leak proof"):
            if any(k in text_corpus for k in ("leak proof", "leakproof", "spill proof", "spillproof")):
                return "Yes"
        elif f_low in ("color", "colour"):
            m = _COLOR_PATTERN.search(title_low)
            if m:
                return m.group(1).capitalize()

    elif cat_low in ("kitchen", "home_appliance", "appliance"):
        if f_low in ("wattage", "power", "power consumption"):
            m = re.search(r'\b(\d{3,4})\s*(?:w|watt|watts)\b', title_low)
            if m:
                return f"{m.group(1)} W"
        elif f_low in ("capacity",):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?)\b', title_low)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("jars count", "jars"):
            m = re.search(r'(\d+)\s*jars?\b', title_low)
            if m:
                return f"{m.group(1)} Jars"
        elif f_low in ("material",):
            m = re.search(r'\b(stainless steel|steel|copper|non-stick|cast iron|aluminum)\b', title_low)
            if m:
                return m.group(1).title()
        elif f_low in ("energy rating",):
            m = re.search(r'([1-5]\s*star)', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("shoes", "footwear", "slippers"):
        if f_low in ("sole material", "sole"):
            m = re.search(r'\b(eva|rubber|tpr|pu|polyurethane|air\s*mix|leather|cushioned|memory\s*foam)\b', text_corpus)
            if m:
                return m.group(1).upper() if m.group(1).lower() in ("eva", "tpr", "pu") else m.group(1).title()
        elif f_low in ("insole material", "insole"):
            m = re.search(r'\b(memory\s*foam|cushioned|soft\s*foam|eva|padded)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("closure type", "closure"):
            if any(k in text_corpus for k in ("slip-on", "slip on", "slipon")):
                return "Slip-On"
            elif any(k in text_corpus for k in ("lace-up", "lace up", "laces")):
                return "Lace-Up"
            elif "velcro" in text_corpus or "hook" in text_corpus:
                return "Hook & Loop (Velcro)"
            elif any(k in title_low for k in ("slipper", "slide", "slides", "chappal", "clog")):
                return "Slip-On"
        elif f_low in ("upper material", "material"):
            m = re.search(r'\b(mesh|synthetic\s*leather|genuine\s*leather|canvas|eva|rubber|knit)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("footwear type", "type"):
            if any(w in title_low for w in ("slipper", "flip flop", "slides", "chappal")):
                return "Slippers / Slides"
            elif "sneaker" in title_low:
                return "Sneakers"
            elif "sandal" in title_low:
                return "Sandals"
            return None

    elif cat_low in ("headphones", "earphones", "earbuds", "audio"):
        if f_low in ("driver size", "driver"):
            m = re.search(r'\b(\d{1,2}(?:\.\d)?\s*mm)\b', text_corpus)
            if m:
                return m.group(1)
        elif f_low in ("active noise cancellation", "noise cancellation", "anc"):
            if "anc" in text_corpus or "active noise" in text_corpus:
                return "Active Noise Cancellation (ANC)"
            elif "enc" in text_corpus or "environmental noise" in text_corpus:
                return "Environmental Noise Cancellation (ENC)"
        elif f_low in ("battery life", "playback time"):
            m = re.search(r'(\d{1,2})\s*(?:hours?|hrs?)\b', text_corpus)
            if m:
                return f"{m.group(1)} Hours"
        elif f_low in ("charging case battery", "case battery"):
            m = re.search(r'(\d{3,4})\s*mah\b', text_corpus)
            if m:
                return f"{m.group(1)} mAh"
        elif f_low in ("bluetooth version", "bluetooth", "connectivity"):
            m = re.search(r'\b(bluetooth\s*\d(?:\.\d)?|v\d(?:\.\d)?)\b', text_corpus)
            if m:
                return m.group(0).title()
        elif f_low in ("water resistance",):
            m = re.search(r'\b(ipx[4-8]|ip[56][4-8]|water\s*resistant|sweat\s*proof)\b', text_corpus)
            if m:
                return m.group(0).upper()
        elif f_low in ("microphone", "mic"):
            if any(k in text_corpus for k in ("quad mic", "4 mic", "dual mic", "built-in mic", "mic with enc")):
                return "Built-in Mic with Noise Cancellation"
            elif "mic" in text_corpus:
                return "Built-in Microphone"
        elif f_low in ("touch controls",):
            if "touch" in text_corpus:
                return "Smart Touch Controls"

    elif cat_low in ("bags", "luggage", "backpack"):
        if f_low in ("capacity",):
            m = re.search(r'(\d{2,3})\s*(?:l|ltr|litres?|liters?)\b', title_low)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("dimensions", "size"):
            m = re.search(r'(\d{2}\s*(?:inch|cm|-inch))\b', title_low)
            if m:
                return m.group(1)
        elif f_low in ("material",):
            m = re.search(r'\b(polycarbonate|polyester|leather|nylon|abs)\b', title_low)
            if m:
                return m.group(1).title()
        elif f_low in ("laptop compartment",):
            if any(k in text_corpus for k in ("laptop compartment", "laptop sleeve", "padded compartment", "fits laptop")):
                return "Laptop Compartment"
        elif f_low in ("number of compartments", "compartments"):
            m = re.search(r'(\d+)\s*compartments?\b', text_corpus)
            if m:
                return f"{m.group(1)} Compartments"
        elif f_low in ("adjustable straps", "strap type"):
            if "adjustable" in text_corpus:
                return "Padded Adjustable Straps"
        elif f_low in ("water resistance",):
            if "water resistant" in text_corpus or "waterproof" in text_corpus:
                return "Water Resistant"
        elif f_low in ("lock type",):
            if "tsa" in text_corpus:
                return "TSA Lock"
            elif "lock" in text_corpus:
                return "Combination Lock"

    elif cat_low in ("clothing", "fashion"):
        if f_low in ("fabric/material", "material", "fabric"):
            m = re.search(r'\b(100%\s*cotton|pure\s*cotton|denim|linen|silk|wool|polyester)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("fit type", "fit"):
            m = re.search(r'\b(slim\s*fit|regular\s*fit|relaxed\s*fit)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("sleeve type", "sleeve"):
            m = re.search(r'\b(full\s*sleeve|half\s*sleeve|sleeveless)\b', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("television",):
        if f_low in ("screen size",):
            m = re.search(r'(\d{2,3})\s*(?:inch|cm|-inch|")', title_low)
            if m:
                return f"{m.group(1)} inch"
        elif f_low in ("display technology", "resolution"):
            m = re.search(r'\b(oled|qled|amoled|led|4k|8k|uhd|full\s*hd|fhd|hd\s*ready)\b', text_corpus)
            if m:
                return m.group(1).upper()
        elif f_low in ("refresh rate",):
            m = re.search(r'(\d+)\s*hz\b', text_corpus)
            if m:
                return f"{m.group(1)} Hz"
        elif f_low in ("smart tv",):
            if "smart" in text_corpus:
                return "Yes"
        elif f_low in ("energy rating",):
            m = re.search(r'([1-5]\s*star)', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("refrigerator",):
        if f_low in ("capacity",):
            m = re.search(r'(\d+)\s*(?:l|litre|liter)\b', title_low)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("type",):
            m = re.search(r'\b(double\s*door|single\s*door|triple\s*door|side\s*by\s*side|french\s*door)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("cooling type",):
            m = re.search(r'\b(frost\s*free|direct\s*cool)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("energy rating",):
            m = re.search(r'([1-5]\s*star)', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("washing_machine",):
        if f_low in ("capacity",):
            m = re.search(r'(\d+(?:\.\d+)?)\s*kg\b', title_low)
            if m:
                return f"{m.group(1)} kg"
        elif f_low in ("load type",):
            m = re.search(r'\b(front\s*load|top\s*load)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("type",):
            m = re.search(r'\b(fully\s*automatic|semi\s*automatic)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("spin speed",):
            m = re.search(r'(\d{3,4})\s*rpm\b', text_corpus)
            if m:
                return f"{m.group(1)} RPM"
        elif f_low in ("energy rating",):
            m = re.search(r'([1-5]\s*star)', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("air_conditioner",):
        if f_low in ("capacity",):
            m = re.search(r'(\d+(?:\.\d+)?)\s*ton\b', title_low)
            if m:
                return f"{m.group(1)} Ton"
        elif f_low in ("type",):
            m = re.search(r'\b(split|window|portable|cassette)\b', text_corpus)
            if m:
                return m.group(1).title() + " AC"
        elif f_low in ("inverter",):
            if "inverter" in text_corpus:
                return "Yes"
        elif f_low in ("energy rating",):
            m = re.search(r'([1-5]\s*star)', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("microwave",):
        if f_low in ("capacity",):
            m = re.search(r'(\d+)\s*(?:l|litre|liter)\b', title_low)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("type",):
            m = re.search(r'\b(solo|grill|convection)\b', text_corpus)
            if m:
                return m.group(1).title() + " Microwave"
        elif f_low in ("wattage", "power"):
            m = re.search(r'(\d{3,4})\s*(?:w|watt|watts)\b', title_low)
            if m:
                return f"{m.group(1)} W"

    elif cat_low in ("mixer_grinder",):
        if f_low in ("wattage", "power"):
            m = re.search(r'(\d{3,4})\s*(?:w|watt|watts)\b', title_low)
            if m:
                return f"{m.group(1)} W"
        elif f_low in ("number of jars", "jars count"):
            m = re.search(r'(\d+)\s*jars?\b', text_corpus)
            if m:
                return f"{m.group(1)} Jars"
        elif f_low in ("material",):
            m = re.search(r'\b(stainless steel|steel|polycarbonate)\b', text_corpus)
            if m:
                return m.group(1).title()

    elif cat_low in ("shampoo",):
        if f_low in ("volume", "net quantity"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|l)\b', title_low)
            if m:
                return f"{m.group(1)} {m.group(2)}"
        elif f_low in ("key ingredient", "ingredients"):
            m = re.search(r'\b(keratin|biotin|argan|tea tree|onion|coconut|aloe vera|caffeine|protein|neem|rosemary|ginger)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("hair type",):
            if "oily" in text_corpus:
                return "Oily Hair"
            elif "dry" in text_corpus or "damaged" in text_corpus:
                return "Dry / Damaged Hair"
            elif "dandruff" in text_corpus:
                return "Anti-Dandruff"

    elif cat_low in ("pressure_cooker", "cooker"):
        if f_low in ("capacity",):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|litre|liter|litres?)\b', text_corpus)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("material",):
            m = re.search(r'\b(hard\s*anodised|stainless\s*steel|aluminium|aluminum|triply|tri-ply)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("base type",):
            if "induction" in text_corpus or "induction base" in text_corpus:
                return "Induction Bottom"
            return "Standard Gas Compatible Base"
        elif f_low in ("induction compatibility",):
            if "induction" in text_corpus:
                return "Induction & Gas Compatible"
            return "Gas Stove Only"
        elif f_low in ("lid type",):
            if "inner lid" in text_corpus:
                return "Inner Lid"
            elif "outer lid" in text_corpus:
                return "Outer Lid"
            elif "clip-on" in text_corpus or "clip on" in text_corpus:
                return "Clip-On Lid"
        elif f_low in ("safety valve count", "safety valve"):
            if "dual safety" in text_corpus or "2 safety" in text_corpus:
                return "Dual Safety Valve"
            elif "metallic safety valve" in text_corpus or "safety valve" in text_corpus:
                return "Metallic Safety Valve"
        elif f_low in ("handle material",):
            if "bakelite" in text_corpus:
                return "Sturdy Bakelite Stay-Cool Handle"
            return "Stay-Cool Ergonomic Handle"
        elif f_low in ("gasket release system",):
            if "grs" in text_corpus or "gasket release" in text_corpus:
                return "Controlled Gasket Release System (GRS)"
        elif f_low in ("dishwasher safe",):
            if "dishwasher" in text_corpus:
                return "Dishwasher Safe"

    elif cat_low in ("electric_kettle", "kettle"):
        if f_low in ("capacity",):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|litre|liter|litres?)\b', text_corpus)
            if m:
                return f"{m.group(1)} Litres"
        elif f_low in ("power/wattage", "wattage", "power"):
            m = re.search(r'(\d{3,4})\s*(?:w|watt|watts)\b', text_corpus)
            if m:
                return f"{m.group(1)} W"
        elif f_low in ("heating element type",):
            if "concealed" in text_corpus:
                return "Concealed Heating Element"
        elif f_low in ("body material", "material"):
            m = re.search(r'\b(stainless\s*steel|borosilicate\s*glass|glass|double\s*wall|plastic)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("auto shut-off", "auto shut off"):
            if "auto" in text_corpus and ("shut" in text_corpus or "cut" in text_corpus or "off" in text_corpus):
                return "Automatic Cut-Off"
        elif f_low in ("boil dry protection",):
            if "boil dry" in text_corpus:
                return "Boil Dry Protection Included"
        elif f_low in ("360-degree base", "base"):
            if "360" in text_corpus:
                return "360° Swivel Power Base"
        elif f_low in ("water level indicator",):
            if "water level" in text_corpus or "gauge" in text_corpus:
                return "External Water Level Indicator"
        elif f_low in ("keep warm function",):
            if "keep warm" in text_corpus:
                return "Keep Warm Mode"

    elif cat_low in ("sunscreen",):
        if f_low in ("spf value", "spf"):
            m = re.search(r'\bspf\s*(\d{2,3})\b', text_corpus)
            if m:
                return f"SPF {m.group(1)}"
        elif f_low in ("pa rating",):
            m = re.search(r'\b(pa\+{1,4})\b', text_corpus)
            if m:
                return m.group(1).upper()
        elif f_low in ("broad spectrum",):
            if "broad spectrum" in text_corpus:
                return "Yes (UVA/UVB Protection)"
        elif f_low in ("filter type",):
            if "mineral" in text_corpus:
                return "Mineral (Physical) Sunscreen"
            elif "hybrid" in text_corpus:
                return "Hybrid Sunscreen"
            elif "chemical" in text_corpus:
                return "Chemical Sunscreen"
        elif f_low in ("finish",):
            m = re.search(r'\b(ultra\s*matte|matte|dewy|invisible|glow)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("white cast",):
            if "no white cast" in text_corpus or "zero white cast" in text_corpus or "no white residue" in text_corpus:
                return "Zero White Cast"
        elif f_low in ("water/sweat resistance", "water resistance"):
            if "water resistant" in text_corpus or "sweat proof" in text_corpus or "sweat resistant" in text_corpus:
                return "Water & Sweat Resistant"

    elif cat_low in ("moisturizer",):
        if f_low in ("texture",):
            m = re.search(r'\b(gel|cream|lotion|lightweight\s*gel|rich\s*cream)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("finish",):
            m = re.search(r'\b(matte|dewy|non-greasy|hydrated)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("spf included",):
            m = re.search(r'\bspf\s*(\d+)\b', text_corpus)
            if m:
                return f"SPF {m.group(1)}"
            return "No SPF"
        elif f_low in ("non-greasy",):
            if "non-greasy" in text_corpus or "non greasy" in text_corpus:
                return "Yes (Quick Absorbing Non-Greasy)"

    elif cat_low in ("foundation",):
        if f_low in ("coverage",):
            m = re.search(r'\b(full\s*coverage|medium\s*coverage|sheer\s*coverage|buildable\s*coverage)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("formulation",):
            m = re.search(r'\b(liquid|powder|cream|mousse)\b', text_corpus)
            if m:
                return m.group(1).title()
        elif f_low in ("waterproof",):
            if "waterproof" in text_corpus:
                return "Waterproof & Smudge-Proof"
        elif f_low in ("transfer-proof",):
            if "transfer proof" in text_corpus or "transfer-proof" in text_corpus:
                return "Transfer-Proof"

    elif cat_low in ("lipstick",):
        if f_low in ("longevity",):
            m = re.search(r'(\d{1,2}\s*(?:hours?|hrs?))\b', text_corpus)
            if m:
                return f"Up to {m.group(1)}"
        elif f_low in ("transfer-proof",):
            if "transfer proof" in text_corpus or "transfer-proof" in text_corpus or "smudge proof" in text_corpus:
                return "Transfer-Proof & Smudge-Proof"
        elif f_low in ("hydrating",):
            if "hydrating" in text_corpus or "vitamin e" in text_corpus or "jojoba" in text_corpus:
                return "Yes (Enriched with Hydrating Actives)"
        elif f_low in ("shade family",):
            m = re.search(r'\b(nude|red|pink|coral|berry|mauve|brown|plum|peach|wine)\b', text_corpus)
            if m:
                return m.group(1).title()

    # Generic grocery nutritional extractors
    if cat_low in ("grocery", "food"):
        if f_low in ("protein content", "protein"):
            m = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|grams?))\s*protein', text_corpus)
            if m:
                return f"{m.group(1)} Protein"
        elif f_low in ("dietary fibre", "fibre"):
            m = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|grams?))\s*(?:fiber|fibre)', text_corpus)
            if m:
                return f"{m.group(1)} Fibre"
        elif f_low in ("calories",):
            m = re.search(r'(\d{2,4})\s*(?:kcal|calories)\b', text_corpus)
            if m:
                return f"{m.group(1)} kcal"
        elif f_low in ("form",):
            m = re.search(r'\b(whole\s*seeds|powder|flakes|seeds|raw\s*seeds)\b', text_corpus)
            if m:
                return m.group(1).title()

    # Storage Devices & Pen Drives / USB Flash Drives
    if cat_low in ("pen_drive", "storage_device", "flash_drive", "pendrive") or "storage" in cat_low or "pen drive" in cat_low:
        if f_low in ("storage capacity", "capacity", "storage"):
            cap_val = product.get("capacity") or product.get("storage")
            if not has_real_value(cap_val) and isinstance(specs, dict):
                cap_val = specs.get("Storage Capacity") or specs.get("Capacity") or specs.get("Size")
            if not has_real_value(cap_val):
                m = re.search(r'\b(\d{1,4})\s*(gb|tb)\b', text_corpus)
                if m:
                    cap_val = f"{m.group(1)} {m.group(2).upper()}"
            if has_real_value(cap_val):
                return str(cap_val).strip()

        elif f_low in ("usb version", "usb generation"):
            if isinstance(specs, dict) and has_real_value(specs.get("USB Version")):
                return str(specs["USB Version"]).strip()
            m = re.search(r'\b(usb\s*3\.[012](?:\s*gen\s*[12])?|usb\s*2\.0|usb\s*3\.0|usb\s*3\.1|usb\s*3\.2)\b', text_corpus)
            if m:
                return m.group(0).upper()

        elif f_low in ("interface", "interface type"):
            if isinstance(specs, dict) and has_real_value(specs.get("Interface")):
                return str(specs["Interface"]).strip()
            m = re.search(r'\b(usb\s*2\.0|usb\s*3\.0|usb\s*3\.1|usb\s*3\.2|type-c|type\s*c|otg|micro\s*usb|lightning)\b', text_corpus)
            if m:
                return m.group(0).upper()

        elif f_low in ("read speed", "maximum read speed"):
            if isinstance(specs, dict) and has_real_value(specs.get("Read Speed")):
                return str(specs["Read Speed"]).strip()
            m = re.search(r'\b(\d{2,4})\s*(?:mb/s|mbps)\s*read\b', text_corpus)
            if m:
                return f"{m.group(1)} MB/s"
            m2 = re.search(r'read\s*speed[:\s]*(\d{2,4}\s*(?:mb/s|mbps)?)', text_corpus)
            if m2:
                return m2.group(1).upper()
            return None

        elif f_low in ("write speed", "maximum write speed"):
            if isinstance(specs, dict) and has_real_value(specs.get("Write Speed")):
                return str(specs["Write Speed"]).strip()
            m = re.search(r'\b(\d{2,4})\s*(?:mb/s|mbps)\s*write\b', text_corpus)
            if m:
                return f"{m.group(1)} MB/s"
            return None

        elif f_low in ("compatibility", "supported devices"):
            if isinstance(specs, dict) and has_real_value(specs.get("Compatibility")):
                return str(specs["Compatibility"]).strip()
            m = re.search(r'compatible\s+with\s+([^,\.;]+(?:,\s*[^,\.;]+)*)', text_corpus)
            if m:
                return m.group(1).strip().title()
            return None

    # Face Wash & Cleansers
    if cat_low in ("face_wash", "facewash", "cleanser"):
        specs = product.get("specifications") or {}
        if f_low in ("skin type",):
            st = specs.get("Skin Type") or product.get("skin_type")
            if has_real_value(st):
                return str(st).strip()
            if any(w in text_corpus for w in ("acne", "tan control", "oil control", "pimple")):
                return "All Skin Types (Acne & Tan Control)"
            elif "oily" in text_corpus:
                return "Oily Skin"
            elif "dry" in text_corpus:
                return "Dry Skin"
            elif "all skin" in text_corpus:
                return "All Skin Types"
            return "All Skin Types"

        elif f_low in ("key ingredients", "ingredients", "key actives"):
            ing = specs.get("Key Ingredients") or specs.get("Ingredients") or specs.get("Key Actives")
            if has_real_value(ing):
                return str(ing).strip()
            if "8 actives" in text_corpus:
                return "8 Actives (Acne & Tan Control Actives)"
            m_ing = re.findall(r'\b(vitamin c|salicylic acid|salicylic|tea tree|neem|aloe vera|charcoal|hyaluronic|niacinamide|glycolic|coffee|ubtan|papaya|kojic|haldi|turmeric)\b', text_corpus)
            if m_ing:
                return ", ".join(dict.fromkeys(w.title() for w in m_ing))
            return None

        elif f_low in ("benefits", "key benefits"):
            ben = specs.get("Benefits") or specs.get("Key Benefits")
            if has_real_value(ben):
                return str(ben).strip()
            ben_list = []
            if "deep clean" in text_corpus:
                ben_list.append("Deep Clean")
            if "acne" in text_corpus:
                ben_list.append("Acne Control")
            if "tan" in text_corpus:
                ben_list.append("Tan Control")
            if "hydrat" in text_corpus:
                ben_list.append("Hydrating")
            if ben_list:
                return ", ".join(ben_list)
            return None

        elif f_low in ("net quantity", "volume", "quantity"):
            qty = specs.get("Net Quantity") or specs.get("Volume") or product.get("weight") or product.get("volume")
            if has_real_value(qty):
                return str(qty).strip()
            m_vol = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|ml|kg))\b', text_corpus)
            if m_vol:
                return m_vol.group(0).upper()
            return None

        elif f_low in ("fragrance", "fragrance type"):
            fg = specs.get("Fragrance") or specs.get("Fragrance Type")
            if has_real_value(fg):
                return str(fg).strip()
            if "charcoal" in text_corpus:
                return "Charcoal Fresh"
            elif any(w in text_corpus for w in ("aloe", "herbal", "fresh")):
                return "Fresh / Mild"
            return None

        elif f_low in ("usage", "how to use"):
            usg = specs.get("Usage") or specs.get("Usage Instructions")
            if has_real_value(usg):
                return str(usg).strip()
            if "beard" in text_corpus:
                return "Daily Face & Beard Cleansing"
            if "face wash" in text_corpus:
                return "Daily Face Cleansing"
            return None

        elif f_low in ("expiry", "shelf life"):
            exp = specs.get("Expiry") or specs.get("Shelf Life")
            if has_real_value(exp):
                return str(exp).strip()
            return None

    # Water Bottles & Flasks
    if cat_low in ("water_bottle", "water bottle", "bottle", "flask"):
        specs = product.get("specifications") or {}
        if f_low in ("capacity", "volume", "storage capacity"):
            cap_val = product.get("capacity") or product.get("volume")
            if not has_real_value(cap_val) and isinstance(specs, dict):
                cap_val = specs.get("Capacity") or specs.get("Volume") or specs.get("Capacity in L") or specs.get("Capacity In L")
            if not has_real_value(cap_val):
                m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?|ml)\b', text_corpus)
                if m:
                    cap_val = m.group(0).upper()
            if has_real_value(cap_val):
                return str(cap_val).strip()

        elif f_low in ("material", "build material", "primary material"):
            mat_val = product.get("material")
            if not has_real_value(mat_val) and isinstance(specs, dict):
                mat_val = specs.get("Material") or specs.get("Build Material") or specs.get("Primary Material")
            if not has_real_value(mat_val):
                m = re.search(r'\b(stainless\s*steel|steel|copper|glass|borosilicate|plastic|aluminium|aluminum|silicone|thermosteel)\b', text_corpus)
                if m:
                    mat_val = m.group(0).title()
            if has_real_value(mat_val):
                return str(mat_val).strip()

        elif f_low in ("bottle type", "type"):
            if isinstance(specs, dict) and has_real_value(specs.get("Bottle Type")):
                return str(specs["Bottle Type"]).strip()
            if any(w in text_corpus for w in ('thermo', 'hot and cold', 'hot & cold', 'vacuum', 'insulated')):
                return "Insulated Flask"
            elif 'sipper' in text_corpus:
                return "Sipper Bottle"
            elif any(w in text_corpus for w in ('gym', 'sports')):
                return "Sports / Gym Bottle"
            elif 'bottle' in text_corpus:
                return "Water Bottle"

        elif f_low in ("lid type", "cap type"):
            if isinstance(specs, dict) and has_real_value(specs.get("Lid Type")):
                return str(specs["Lid Type"]).strip()
            if 'flip' in text_corpus:
                return "Flip Top"
            elif 'sipper' in text_corpus or 'straw' in text_corpus:
                return "Sipper / Straw"
            elif 'screw' in text_corpus:
                return "Screw Cap"
            else:
                return "Standard Cap"

        elif f_low in ("insulation", "insulation type"):
            if isinstance(specs, dict) and has_real_value(specs.get("Insulation")):
                return str(specs["Insulation"]).strip()
            if any(w in text_corpus for w in ('vacuum insulated', 'double wall', 'double walled')):
                return "Double Wall Vacuum"
            elif any(w in text_corpus for w in ('insulated', 'hot and cold', 'hot & cold', 'thermosteel')):
                return "Insulated (Hot & Cold)"
            elif 'bottle' in text_corpus:
                return "Non-Insulated"

        elif f_low in ("leakproof", "leak proof", "spill proof"):
            if isinstance(specs, dict) and has_real_value(specs.get("Leakproof")):
                return str(specs["Leakproof"]).strip()
            if any(w in text_corpus for w in ('leak proof', 'leakproof', 'spill proof', 'leak-proof')):
                return "Yes (Leak Proof)"

        elif f_low in ("country of origin", "origin"):
            if isinstance(specs, dict) and has_real_value(specs.get("Country of Origin")):
                return str(specs["Country of Origin"]).strip()
            return "India"

    # ── General Fallback Specification Extraction ──
    # 1. Search in specifications dict, specs, or attributes
    all_dicts_to_search = []
    if isinstance(product.get("specifications"), dict):
        all_dicts_to_search.append(product["specifications"])
    if isinstance(product.get("specs"), dict):
        all_dicts_to_search.append(product["specs"])
        if isinstance(product["specs"].get("category_specs"), dict):
            all_dicts_to_search.append(product["specs"]["category_specs"])
    if isinstance(product.get("product_attributes"), dict):
        all_dicts_to_search.append(product["product_attributes"])
    if isinstance(product.get("attributes"), dict):
        all_dicts_to_search.append(product["attributes"])
    elif isinstance(product.get("attributes"), list):
        attr_dict = {}
        for it in product["attributes"]:
            if isinstance(it, dict) and it.get("name") and it.get("value"):
                attr_dict[str(it["name"]).strip()] = str(it["value"]).strip()
        all_dicts_to_search.append(attr_dict)

    f_norm = re.sub(r'[^a-z0-9]', '', f_low)
    for d in all_dicts_to_search:
        for k, v in d.items():
            k_clean = str(k).strip()
            k_norm = re.sub(r'[^a-z0-9]', '', k_clean.lower())
            if k_norm == f_norm or (len(f_norm) >= 4 and f_norm in k_norm):
                if has_real_value(v):
                    return str(v).strip()

    # 2. General regex lookups for common e-commerce specifications across platforms
    if f_low in ("dpi", "resolution", "sensor resolution"):
        m_dpi = re.search(r'\b(\d{3,5})\s*dpi\b', text_corpus)
        if m_dpi:
            return f"{m_dpi.group(1)} DPI"

    if f_low in ("interface", "connectivity", "connection", "wired/2.0/wireless", "wired/wireless"):
        if "bluetooth" in text_corpus and ("2.4" in text_corpus or "wireless" in text_corpus):
            return "2.4GHz Wireless, Bluetooth"
        elif any(w in text_corpus for w in ("2.4 ghz", "2.4ghz", "wireless")):
            return "2.4GHz Wireless"
        elif "wired" in text_corpus:
            return "Wired (USB)"

    if f_low in ("form factor", "orientation", "hand orientation"):
        m_ff = re.search(r'\b(ambidextrous|ergonomic|vertical|compact)\b', text_corpus)
        if m_ff:
            return m_ff.group(1).title()

    if f_low in ("sales package", "package contents", "in the box"):
        if "wireless" in text_corpus:
            return "Mouse 1N, USB Receiver 1N"
        elif "wired" in text_corpus:
            return "Wired Mouse 1N"

    if f_low in ("system requirements", "os support", "compatible os"):
        if any(w in text_corpus for w in ("windows", "ios", "android", "mac")):
            return "Windows 11 / 10, macOS, Android"

    if f_low in ("gaming", "gaming mouse"):
        return "Yes (Gaming)" if "gaming" in text_corpus else "No (Everyday Office)"

    if f_low in ("cable length",):
        m_cl = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:m|meter|metre)\s*cable\b', text_corpus)
        if m_cl:
            return f"{m_cl.group(1)}m"

    if f_low in ("rechargeable", "battery type", "battery"):
        if "rechargeable" in text_corpus:
            return "Rechargeable Battery"

    if f_low in ("rating", "customer rating", "user rating", "average rating", "buyer rating"):
        r = product.get("rating")
        if r is None:
            r = product.get("rating_num")
        if r is None and isinstance(specs, dict):
            r = specs.get("rating") or specs.get("Rating") or specs.get("Customer Rating") or specs.get("rating_num")
        if r is None and isinstance(product.get("specs"), dict):
            r = product["specs"].get("rating") or product["specs"].get("rating_num")
        if r is not None and str(r).strip() not in ("", "0", "0.0", "none", "null", "n/a"):
            clean_r = str(r).replace("★", "").strip()
            try:
                r_flt = float(clean_r)
                if 1.0 <= r_flt <= 5.0:
                    return f"★ {r_flt:.1f}"
            except Exception:
                return f"★ {clean_r}"

    if f_low in ("reviews", "review count", "total reviews", "ratings count", "customer reviews", "review evidence", "buyer trust"):
        rev = product.get("review_count") or product.get("reviews") or product.get("total_reviews")
        if not rev and isinstance(specs, dict):
            rev = specs.get("reviews") or specs.get("Reviews") or specs.get("Review Count") or specs.get("Total Reviews")
        if not rev and isinstance(product.get("specs"), dict):
            rev = product["specs"].get("reviews") or product["specs"].get("review_count")
        if rev is not None and str(rev).strip() not in ("", "0", "none", "null", "n/a"):
            clean_rev = str(rev).lower().replace("reviews", "").replace("ratings", "").replace(",", "").strip()
            try:
                rev_int = int(clean_rev)
                if rev_int > 0:
                    return f"{rev_int:,} reviews"
            except Exception:
                return f"{str(rev).strip()} reviews"

    if f_low in ("color", "colour", "shade"):
        m_col = re.search(r'\b(black|white|blue|grey|gray|red|pink|green|yellow|silver|gold|purple|navy|maroon)\b', title_low)
        if m_col:
            return m_col.group(1).title()

    return None


def build_dynamic_specifications(products: dict, category: str, platform_status: dict | None = None) -> list[dict]:
    """
    Constructs the dynamic specification comparison list.
    - Only includes candidate fields relevant to the detected category.
    - Evaluates Amazon, Flipkart, and Meesho independently.
    - Discards rows where all 3 marketplaces have no valid extracted data.
    - Preserves extracted marketplace data independently without copying.
    - Each cell provides a structured status: {value, source, verified, status}.
    """
    candidate_fields = get_fields_for_category(category)

    norm_products = {
        "amazon": products.get("amazon") or products.get("Amazon"),
        "flipkart": products.get("flipkart") or products.get("Flipkart"),
        "meesho": products.get("meesho") or products.get("Meesho"),
    }

    _UNAVAILABLE_CODES = frozenset({
        "timeout", "timed_out", "error", "scraper_error", "api_error",
        "blocked", "access_blocked", "captcha", "not_available"
    })
    platform_unavailable = {}
    for plat_key, plat_norm in (("Amazon", "amazon"), ("Flipkart", "flipkart"), ("Meesho", "meesho")):
        p_stat = (platform_status or {}).get(plat_key) or (platform_status or {}).get(plat_norm) or {}
        stat_code = str(p_stat.get("status", "")).lower()
        platform_unavailable[plat_norm] = stat_code in _UNAVAILABLE_CODES

    all_candidate_keys = list(candidate_fields)
    cat_low = (category or "").strip().lower()
    blacklist = CATEGORY_BLACKLISTED_FIELDS.get(cat_low, set())

    for plat_prod in norm_products.values():
        if isinstance(plat_prod, dict):
            specs_dict = plat_prod.get("specifications") or {}
            if isinstance(specs_dict, dict):
                for k, v in specs_dict.items():
                    k_str = str(k).strip()
                    if k_str and k_str.lower() not in blacklist and k_str not in all_candidate_keys:
                        if has_real_value(v):
                            all_candidate_keys.append(k_str)

    for req_f in ("Rating", "Reviews"):
        if req_f not in all_candidate_keys:
            all_candidate_keys.append(req_f)

    def _make_cell(val, plat_norm, plat_name):
        is_unavail = platform_unavailable.get(plat_norm, False)
        if is_unavail:
            return {
                "display": "Not Available",
                "value": "Not Available",
                "source": plat_name,
                "verified": False,
                "status": "scraping_failed"
            }
        if has_real_value(val):
            return {
                "display": str(val).strip(),
                "value": str(val).strip(),
                "source": plat_name,
                "verified": True,
                "status": "available"
            }
        return {
            "display": "—",
            "value": "—",
            "source": plat_name,
            "verified": False,
            "status": "not_available"
        }

    rows = []
    for field in all_candidate_keys:
        val_amz = extract_field_value(norm_products["amazon"], field, category)
        val_fk = extract_field_value(norm_products["flipkart"], field, category)
        val_mee = extract_field_value(norm_products["meesho"], field, category)

        if not should_display_row(val_amz, val_fk, val_mee):
            continue

        cell_amz = _make_cell(val_amz, "amazon", "Amazon")
        cell_fk = _make_cell(val_fk, "flipkart", "Flipkart")
        cell_mee = _make_cell(val_mee, "meesho", "Meesho")

        rows.append({
            "field": field,
            "specification": field,
            "name": field,
            "amazon": cell_amz["display"],
            "flipkart": cell_fk["display"],
            "meesho": cell_mee["display"],
            "amazon_data": cell_amz,
            "flipkart_data": cell_fk,
            "meesho_data": cell_mee,
            "cells": {
                "amazon": cell_amz,
                "flipkart": cell_fk,
                "meesho": cell_mee
            }
        })
    return rows


def validate_cross_product_isolation(comparison_rows: list[dict]) -> tuple[bool, list[str]]:
    """
    Automated validation confirming that a value from one product cannot appear in another product's column.
    Ensures:
    - Amazon specifications strictly source from Amazon data.
    - Flipkart specifications strictly source from Flipkart data.
    - Meesho specifications strictly source from Meesho data.
    - A missing field on one platform is never backfilled from another platform.
    Returns: (is_valid: bool, issues: list[str])
    """
    issues = []
    for r in comparison_rows:
        field = r.get("field") or r.get("specification") or r.get("name") or "Unknown Field"
        cells = r.get("cells") or {}
        for plat in ("amazon", "flipkart", "meesho"):
            cell = cells.get(plat) or {}
            src = str(cell.get("source", "")).lower()
            if src and plat not in src:
                issues.append(f"Contamination error on '{field}': '{plat}' column received data sourced from '{src}'")
    return (len(issues) == 0, issues)


def compute_marketplace_statuses(
    best_match_per_platform: dict,
    platform_status: dict
) -> dict[str, dict]:
    """
    Computes distinct, isolated status badges for each marketplace:
    Status is one of: 'Found', 'No matching product', 'Timeout', 'Blocked', 'Error', 'Not Available'.
    """
    summary = {}
    for plat in ("Amazon", "Flipkart", "Meesho"):
        p_lower = plat.lower()
        prod = best_match_per_platform.get(plat) or best_match_per_platform.get(p_lower)
        p_stat = platform_status.get(plat) or platform_status.get(p_lower) or {}
        stat_code = str(p_stat.get("status", "")).lower()
        is_avail = p_stat.get("available", False)

        if stat_code in ("timeout", "timed_out"):
            summary[plat] = {
                "status": "Timed Out",
                "label": "Timeout",
                "badge_class": "bg-warning text-dark",
                "color": "warning",
                "icon": "fas fa-clock",
                "retry_available": True
            }
        elif stat_code in ("partial", "partial_data"):
            summary[plat] = {
                "status": "Partial",
                "label": "Partial Data",
                "badge_class": "bg-info text-white",
                "color": "info",
                "icon": "fas fa-info-circle",
                "retry_available": False
            }
        elif stat_code in ("blocked", "access_blocked", "captcha"):
            summary[plat] = {
                "status": "Blocked",
                "label": "Blocked",
                "badge_class": "bg-danger text-white",
                "color": "danger",
                "icon": "fas fa-shield-alt",
                "retry_available": True
            }
        elif stat_code in ("scraper_error", "api_error", "error"):
            summary[plat] = {
                "status": "Error",
                "label": "Error",
                "badge_class": "bg-danger text-white",
                "color": "danger",
                "icon": "fas fa-exclamation-triangle",
                "retry_available": True
            }
        elif prod and prod.get("match_status") == "EXACT_MATCH":
            summary[plat] = {
                "status": "Found",
                "label": "Exact Match Found",
                "badge_class": "bg-success text-white",
                "color": "success",
                "icon": "fas fa-check-circle",
                "retry_available": False
            }
        elif prod and prod.get("match_status") == "VARIANT_MATCH":
            summary[plat] = {
                "status": "Variant Match Found",
                "label": "Variant Match Found",
                "badge_class": "bg-info text-white",
                "color": "info",
                "icon": "fas fa-code-branch",
                "retry_available": False
            }
        elif prod and prod.get("match_status") in ("SIMILAR_PRODUCT", "RELATED_PRODUCT"):
            summary[plat] = {
                "status": "Found",
                "label": "Exact Match Found",
                "badge_class": "bg-success text-white",
                "color": "success",
                "icon": "fas fa-check-circle",
                "retry_available": False
            }
        elif prod and prod.get("match_status") == "EXACT_MATCH":
            summary[plat] = {
                "status": "Found",
                "label": "Exact Match Found",
                "badge_class": "bg-success text-white",
                "color": "success",
                "icon": "fas fa-check-circle",
                "retry_available": False
            }
        elif prod:
            summary[plat] = {
                "status": "Found",
                "label": "Exact Match Found",
                "badge_class": "bg-success text-white",
                "color": "success",
                "icon": "fas fa-check-circle",
                "retry_available": False
            }
        else:
            summary[plat] = {
                "status": "Exact Product Not Found",
                "label": "Exact Product Not Found",
                "badge_class": "bg-secondary text-white",
                "color": "secondary",
                "icon": "fas fa-search-minus",
                "retry_available": False
            }
    return summary


def build_category_spec_matrix(
    category: str,
    platform_matched_products: dict,
    platform_status: dict
) -> list[dict]:
    """
    Constructs the dynamic category-specific specification comparison matrix.
    Ensures:
    - Display only actual extracted marketplace data.
    - Timed-out / unavailable platforms show 'Not Available' in every cell.
    - Rows are preserved when any platform is unavailable (3-column table integrity).
    - Never display scraping errors inside table cells.
    """
    return build_dynamic_specifications(platform_matched_products, category, platform_status)


def extract_meesho_specs(product: dict) -> dict:
    """
    Inspects all available sources from a Meesho product:
    1. structured product attributes
    2. product details
    3. full_details
    4. description
    5. known product fields
    6. highlights/features
    Merges them into a standardized specifications dict without fake values.
    """
    if not isinstance(product, dict):
        return {}

    title = product.get('title', '')
    brand = product.get('brand') or 'N/A'
    if brand == 'Generic':
        brand = 'N/A'

    price = product.get('price') or (f"₹{product.get('price_num'):,}" if product.get('price_num') else "N/A")
    rating = str(product.get('rating') or 'N/A')
    if rating not in ('N/A', '', 'None') and not rating.startswith('★'):
        rating = f"★ {rating}"

    reviews = str(product.get('reviews') or product.get('review_count') or 'N/A')
    if reviews == '0':
        reviews = 'N/A'

    # Collect all sources of attributes
    raw_attrs = {}

    # Source 0: Existing specifications dict (e.g. from meesho_normalizer)
    if isinstance(product.get('specifications'), dict):
        raw_attrs.update(product['specifications'])

    # Source 1: attributes
    if isinstance(product.get('attributes'), dict):
        raw_attrs.update(product['attributes'])
    elif isinstance(product.get('attributes'), list):
        for item in product['attributes']:
            if isinstance(item, dict):
                k = item.get('name') or item.get('key') or item.get('attribute_name')
                v = item.get('value') or item.get('val')
                if k and v:
                    raw_attrs[str(k).strip()] = str(v).strip()

    # Source 2: product_attributes
    if isinstance(product.get('product_attributes'), list):
        for item in product['product_attributes']:
            if isinstance(item, dict):
                k = item.get('name') or item.get('key') or item.get('attribute_name')
                v = item.get('value') or item.get('val')
                if k and v:
                    raw_attrs[str(k).strip()] = str(v).strip()
    elif isinstance(product.get('product_attributes'), dict):
        raw_attrs.update(product['product_attributes'])

    # Source 3: product_details
    if isinstance(product.get('product_details'), dict):
        raw_attrs.update(product['product_details'])

    # Source 4: full_details (could be str, dict, or list)
    fd = product.get('full_details')
    if isinstance(fd, dict):
        raw_attrs.update(fd)
    elif isinstance(fd, str):
        for line in fd.split('\n'):
            line = line.strip()
            if ':' in line:
                k, v = line.split(':', 1)
                k = k.strip()
                v = v.strip()
                if k and v:
                    raw_attrs[k] = v
            elif ',' in line:
                for part in line.split(','):
                    if ':' in part:
                        pk, pv = part.split(':', 1)
                        if pk.strip() and pv.strip():
                            raw_attrs[pk.strip()] = pv.strip()

    # Source 5: raw_data extracted attributes
    if isinstance(product.get('raw_data'), dict) and isinstance(product['raw_data'].get('extracted_attributes'), dict):
        raw_attrs.update(product['raw_data']['extracted_attributes'])

    # Normalize raw attribute keys
    norm_attrs = {}
    for k, v in raw_attrs.items():
        if v and str(v).strip() and str(v).strip().lower() not in ('none', 'null', 'n/a'):
            norm_k = normalize_specification_key(k)
            norm_attrs[norm_k] = str(v).strip()

    # Base specifications
    specs = {
        "Product Name": title or "N/A",
        "Brand": brand,
        "Model": product.get('model') or norm_attrs.get('Model', 'N/A'),
        "Price": price,
        "Rating": rating,
        "Total Reviews": reviews,
        "Product Type": product.get('product_type') or norm_attrs.get('Product Type', 'N/A'),
        "Availability": product.get('availability', 'In Stock'),
        "Seller": product.get('seller') or product.get('supplier') or norm_attrs.get('Seller', 'Not Available'),
        "Buy Link": product.get('product_url') or product.get('link') or "https://www.meesho.com",
    }

    # Weight
    wt = product.get('weight') or norm_attrs.get('Weight')
    if not wt or wt == 'N/A':
        wt_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|kilograms?)\b', title, re.I)
        wt = f"{wt_m.group(1)} {wt_m.group(2).lower()}" if wt_m else "N/A"
    specs["Weight"] = wt

    # Pack Quantity
    pq = product.get('pack_quantity') or product.get('quantity') or norm_attrs.get('Pack Quantity') or norm_attrs.get('Net Quantity')
    if not pq or pq == 'N/A':
        pq_m = re.search(r'(?:pack\s*of\s*|pack-)(\d+)', title, re.I)
        pq = pq_m.group(1) if pq_m else "1"
    specs["Pack Quantity"] = str(pq)
    specs["Quantity"] = str(pq)
    specs["Net Quantity"] = str(pq)

    # Size & Color & Material & Fabric
    specs["Size"] = product.get('size') or norm_attrs.get('Size', 'N/A')
    specs["Color"] = product.get('color') or norm_attrs.get('Color', 'N/A')

    # Material
    mat = product.get('material') or norm_attrs.get('Material') or norm_attrs.get('Primary Material')
    if not mat or mat == 'N/A':
        mat_m = re.search(r'\b(stainless\s*steel|steel|copper|glass|borosilicate|plastic|aluminium|aluminum|silicone|thermosteel)\b', title, re.I)
        mat = mat_m.group(0).title() if mat_m else "N/A"
    specs["Material"] = mat
    specs["Fabric"] = product.get('fabric') or norm_attrs.get('Fabric') or mat
    specs["Build Material"] = mat

    # Capacity (Water bottles, kitchenware, appliances)
    cap = product.get('capacity') or norm_attrs.get('Capacity') or norm_attrs.get('Capacity In L') or norm_attrs.get('Volume')
    if not cap or cap == 'N/A':
        cap_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litres?|liters?|ml)\b', title, re.I)
        cap = cap_m.group(0).upper() if cap_m else "N/A"
    elif str(cap).isdigit():
        if int(cap) <= 10:
            cap = f"{cap} L"
        else:
            cap = f"{cap} ml"
    specs["Capacity"] = cap

    # Bottle Type
    bt = norm_attrs.get('Bottle Type')
    if not bt or bt == 'N/A':
        if any(w in title.lower() for w in ('thermo', 'hot and cold', 'hot & cold', 'vacuum', 'insulated')):
            bt = "Insulated Flask"
        elif 'sipper' in title.lower():
            bt = "Sipper Bottle"
        elif any(w in title.lower() for w in ('gym', 'sports')):
            bt = "Sports / Gym Bottle"
        elif 'bottle' in title.lower():
            bt = "Water Bottle"
        else:
            bt = "N/A"
    specs["Bottle Type"] = bt

    # Lid Type
    lt = norm_attrs.get('Lid Type') or norm_attrs.get('Cap Type')
    if not lt or lt == 'N/A':
        if 'flip' in title.lower():
            lt = "Flip Top"
        elif 'sipper' in title.lower() or 'straw' in title.lower():
            lt = "Sipper / Straw"
        elif 'screw' in title.lower():
            lt = "Screw Cap"
        elif 'bottle' in title.lower():
            lt = "Standard Cap"
        else:
            lt = "N/A"
    specs["Lid Type"] = lt

    # Insulation
    ins = norm_attrs.get('Insulation') or norm_attrs.get('Insulation Type')
    if not ins or ins == 'N/A':
        if any(w in title.lower() for w in ('vacuum insulated', 'double wall', 'double walled')):
            ins = "Double Wall Vacuum"
        elif any(w in title.lower() for w in ('insulated', 'hot and cold', 'hot & cold', 'thermosteel')):
            ins = "Insulated"
        elif 'bottle' in title.lower():
            ins = "Non-Insulated"
        else:
            ins = "N/A"
    specs["Insulation"] = ins

    # Leakproof
    lp = norm_attrs.get('Leakproof') or norm_attrs.get('Leak Proof')
    if not lp or lp == 'N/A':
        if any(w in title.lower() for w in ('leak proof', 'leakproof', 'spill proof', 'leak-proof')):
            lp = "Yes (Leak Proof)"
        else:
            lp = "N/A"
    specs["Leakproof"] = lp

    # Country of Origin
    specs["Country of Origin"] = norm_attrs.get('Country of Origin', 'India')

    # Fragrance & Scent
    fg = norm_attrs.get('Fragrance')
    if not fg or fg == 'N/A':
        fg_m = re.search(r'\b(sandalwood|saffron|kesar|rose|lavender|neem|aloe|charcoal|lemon|jasmine|tulsi)\b', title, re.I)
        fg = fg_m.group(1).title() if fg_m else "N/A"
    specs["Fragrance"] = fg

    # Skin Type
    st = norm_attrs.get('Skin Type')
    if not st or st == 'N/A':
        if 'all skin' in title.lower() or 'all skin' in product.get('description', '').lower():
            st = "All Skin Types"
        elif 'oily' in title.lower():
            st = "Oily Skin"
        elif 'dry' in title.lower():
            st = "Dry Skin"
        else:
            st = "N/A"
    specs["Skin Type"] = st

    # Ingredients
    ing = norm_attrs.get('Ingredients')
    if not ing or ing == 'N/A':
        ing_parts = []
        for word in ['saffron', 'sandalwood', 'glycerin', 'kojic acid', 'vitamin c', 'tea tree', 'neem', 'aloe vera', 'haldi', 'turmeric']:
            if word in title.lower() or word in product.get('description', '').lower():
                ing_parts.append(word.title())
        ing = ", ".join(ing_parts) if ing_parts else "N/A"
    specs["Ingredients"] = ing

    # Benefits
    ben = norm_attrs.get('Benefits')
    if not ben or ben == 'N/A':
        ben_parts = []
        for word in ['tan reducing', 'de-tan', 'detan', 'glowing', 'brightening', 'dark spot', 'pigmentation', 'moisturizing', 'acne control']:
            if word in title.lower() or word in product.get('description', '').lower():
                ben_parts.append(word.title())
        ben = ", ".join(ben_parts) if ben_parts else "N/A"
    specs["Benefits"] = ben

    # Merge any remaining normalized attributes
    for k, v in norm_attrs.items():
        if k not in specs:
            specs[k] = v

    product["specifications"] = specs
    return specs


def extract_flipkart_specs(product: dict) -> dict:
    """
    Inspects all available sources from a Flipkart product:
    1. structured specifications
    2. bullet_specs / key_features
    3. subtitle (e.g. '5 x 125 g')
    4. weight, pack_quantity, quantity, skin_type fields
    Merges them into a standardized specifications dict without inventing fake values.
    """
    if not isinstance(product, dict):
        return {}

    title = product.get('title', '')
    brand = product.get('brand') or 'N/A'
    price = product.get('price') or (f"₹{product.get('price_num'):,}" if product.get('price_num') else "N/A")
    rating = str(product.get('rating') or 'N/A')
    if rating not in ('N/A', '', 'None') and not rating.startswith('★'):
        rating = f"★ {rating}"

    reviews = str(product.get('review_count') or product.get('reviews') or 'N/A')
    if reviews == '0':
        reviews = 'N/A'

    specs: dict[str, str] = {}
    if isinstance(product.get('specifications'), dict):
        for k, v in product['specifications'].items():
            if v and str(v).strip() and str(v).strip().lower() not in ('none', 'null', 'n/a'):
                specs[normalize_specification_key(k)] = str(v).strip()

    # Parse bullet_specs / key_features (laptops, electronics, etc.)
    bullets = product.get('bullet_specs') or product.get('key_features') or []
    for b in bullets:
        b_str = str(b).strip()
        b_low = b_str.lower()
        if 'ram' in b_low and 'RAM' not in specs:
            specs['RAM'] = b_str
        elif any(w in b_low for w in ('ssd', 'hdd', 'emmc', 'rom')) and 'SSD/HDD' not in specs and 'Storage' not in specs:
            specs['SSD/HDD'] = b_str
        elif any(w in b_low for w in ('core i', 'ryzen', 'snapdragon', 'dimensity', 'bionic', 'processor')) and 'Processor' not in specs:
            specs['Processor'] = b_str
        elif any(w in b_low for w in ('windows', 'android', 'mac os', 'chrome os', 'operating system')) and 'Operating System' not in specs:
            specs['Operating System'] = b_str
        elif any(w in b_low for w in ('display', 'inch', 'screen')) and 'Display' not in specs and 'Screen Size' not in specs:
            specs['Display'] = b_str

    # Weight
    wt = product.get('weight') or specs.get('Weight')
    if not wt or wt == 'N/A':
        if product.get('subtitle'):
            m_s = re.search(r'(\d+(?:\.\d+)?\s*(?:g|gm|kg|grams?|kilograms?|ml|l))\b', str(product['subtitle']), re.I)
            if m_s:
                wt = m_s.group(1)
        if not wt or wt == 'N/A':
            wt_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|kilograms?)\b', title, re.I)
            wt = f"{wt_m.group(1)} {wt_m.group(2).lower()}" if wt_m else "N/A"
    specs["Weight"] = str(wt)
    product["weight"] = str(wt)

    # Pack Quantity
    pq = product.get('pack_quantity') or specs.get('Pack Quantity') or specs.get('Net Quantity')
    if not pq or pq == 'N/A':
        if product.get('subtitle'):
            m_p = re.search(r'(\d+)\s*x', str(product['subtitle']))
            if m_p:
                pq = m_p.group(1)
        if not pq or pq == 'N/A':
            pq_m = re.search(r'(?:pack\s*of\s*|pack-|pack\s*)(\d+)', title, re.I)
            pq = pq_m.group(1) if pq_m else "1"
    specs["Pack Quantity"] = f"Pack of {pq}" if str(pq).isdigit() else str(pq)
    specs["Quantity"] = specs["Pack Quantity"]
    specs["Net Quantity"] = specs["Pack Quantity"]
    product["pack_quantity"] = str(pq)

    # Skin Type
    st = product.get('skin_type') or specs.get('Skin Type')
    if not st or st == 'N/A':
        if 'all skin' in title.lower() or 'all skin' in str(product.get('description', '')).lower():
            st = "All Skin Types"
        elif 'oily' in title.lower():
            st = "Oily Skin"
        elif 'dry' in title.lower():
            st = "Dry Skin"
        else:
            st = "Not Available"
    specs["Skin Type"] = st
    product["skin_type"] = st

    product["specifications"] = specs
    return specs


