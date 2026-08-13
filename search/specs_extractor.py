import re


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
    """Heuristic brand extraction: the first capitalized proper noun."""
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


def detect_category(title: str, query: str = "") -> str:
    """Detect product category for dynamic table specs."""
    text = f"{title} {query}".lower()
    if any(w in text for w in ['phone', 'mobile', 'iphone', 'galaxy', 'smartphone', 'pixel', 'redmi', 'realme', 'oneplus', 'vivo', 'oppo']):
        return "Smartphones"
    if any(w in text for w in ['laptop', 'macbook', 'notebook', 'chromebook', 'thinkpad', 'ideapad', 'vivobook', 'zenbook', 'tuf', 'rog', 'aspire']):
        return "Laptops"
    if any(w in text for w in ['tv', 'television', 'led tv', 'smart tv', '4k tv', 'oled', 'qled', 'bravia']):
        return "Televisions"
    if any(w in text for w in ['refrigerator', 'fridge', 'freezer']):
        return "Refrigerators"
    if any(w in text for w in ['washing machine', 'washer', 'dryer']):
        return "Washing Machines"
    if any(w in text for w in ['rice', 'flour', 'atta', 'oil', 'ghee', 'milk', 'curd', 'butter', 'cheese', 'bread', 'egg', 'sugar', 'salt', 'tea', 'coffee', 'dal', 'noodle', 'biscuit', 'chocolate', 'grocery']):
        return "Groceries"
    if any(w in text for w in ['soap', 'shampoo', 'face wash', 'cream', 'lotion', 'toothpaste', 'lipstick', 'makeup', 'kajal', 'serum', 'perfume', 'deodorant', 'sunscreen', 'balm']):
        return "Beauty & Personal Care"
    if any(w in text for w in ['cooker', 'pan', 'tawa', 'stove', 'mixer', 'knife', 'bottle', 'lunch box', 'kettle', 'chimney', 'cutlery', 'pot']):
        return "Kitchen Products"
    if any(w in text for w in ['cloth', 'clothes', 'clothing', 'fashion', 'apparel', 'shirt', 'tshirt', 't-shirt', 'jeans', 'trouser', 'pant', 'dress', 'jacket', 'coat', 'hoodie', 'sweater', 'saree', 'kurti', 'kurta', 'lehenga', 'top', 'blouse', 'shorts', 'skirt', 'tracksuit', 'suit', 'blazer', 'shoes', 'sneakers']):
        return "Clothing & Fashion"
    if any(w in text for w in ['chair', 'table', 'sofa', 'bed', 'desk', 'wardrobe', 'bookshelf', 'recliner', 'furniture']):
        return "Furniture"
    return "General Products"


def extract_specs(item: dict, query: str = "") -> dict:
    """
    Dynamically extract specifications and category details from a product item.
    Returns structured specs dictionary including category, model, seller, warranty, and category specs.
    """
    title = item.get('title', '')
    title_lower = title.lower()
    specs = {k: 'N/A' for k in _SPEC_PATTERNS}
    specs['brand']      = 'N/A'
    specs['color']      = 'N/A'
    specs['rating_num'] = 0.0
    specs['price_num']  = item.get('price_num')

    # Brand
    specs['brand'] = _extract_brand_from_title(title)

    # Category
    category = detect_category(title, query)
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
    specs['warranty'] = '1 Year Brand Warranty' if category in ('Smartphones', 'Laptops', 'Televisions', 'Refrigerators', 'Washing Machines') else 'Not Available'

    # Build category-tailored specifications list
    cat_specs = {}
    if category == "Smartphones":
        cat_specs["Display"] = specs.get('display', 'Not Available')
        cat_specs["Processor"] = specs.get('processor', 'Not Available')
        cat_specs["RAM"] = specs.get('ram', 'Not Available')
        cat_specs["Storage"] = specs.get('storage', 'Not Available')
        cat_specs["Camera"] = specs.get('camera', 'Not Available')
        cat_specs["Battery"] = specs.get('battery', 'Not Available')
        cat_specs["OS"] = specs.get('os', 'Android/iOS')
        cat_specs["5G Support"] = specs.get('is_5g', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
    elif category == "Laptops":
        cat_specs["Processor"] = specs.get('processor', 'Not Available')
        cat_specs["RAM"] = specs.get('ram', 'Not Available')
        cat_specs["SSD/Storage"] = specs.get('storage', 'Not Available')
        cat_specs["Display Size"] = specs.get('display', 'Not Available')
        cat_specs["Graphics"] = "Integrated / Dedicated" if 'nvidia' in title_lower or 'rtx' in title_lower else "Integrated Graphics"
        cat_specs["OS"] = specs.get('os', 'Windows 11 Home')
        cat_specs["Weight"] = specs.get('weight', 'Not Available')
    elif category == "Televisions":
        cat_specs["Screen Size"] = specs.get('display', 'Not Available')
        cat_specs["Resolution"] = "4K Ultra HD" if '4k' in title_lower else ("Full HD" if 'fhd' in title_lower else "HD Ready")
        cat_specs["Display Type"] = "OLED" if 'oled' in title_lower else ("QLED" if 'qled' in title_lower else "LED")
        cat_specs["Smart TV"] = "Yes (Android/Google TV)" if 'smart' in title_lower or 'android' in title_lower else "Yes"
        cat_specs["HDMI Ports"] = "2 - 3 Ports"
    elif category == "Refrigerators":
        cat_specs["Capacity"] = specs.get('capacity', 'Not Available')
        cat_specs["Star Rating"] = "3 Star / 4 Star" if '3 star' in title_lower or '4 star' in title_lower else "3 Star Energy Rated"
        cat_specs["Cooling Tech"] = "Frost Free / Direct Cool"
        cat_specs["Compressor"] = "Inverter Compressor"
    elif category == "Washing Machines":
        cat_specs["Capacity"] = specs.get('capacity', specs.get('weight', 'Not Available'))
        cat_specs["Type"] = "Front Load" if 'front' in title_lower else "Top Load Fully Automatic"
        cat_specs["Spin Speed"] = "700 - 1200 RPM"
        cat_specs["Energy Rating"] = "5 Star Rated"
    elif category == "Groceries":
        cat_specs["Brand"] = specs.get('brand', 'Not Available')
        cat_specs["Weight / Volume"] = specs.get('weight', specs.get('volume', 'Not Available'))
        cat_specs["Quantity"] = specs.get('quantity', '1 Pack')
        cat_specs["Pack Size"] = specs.get('quantity', 'Standard Pack')
        cat_specs["Expiry Date"] = "6-12 Months Best Before"
    elif category == "Beauty & Personal Care":
        cat_specs["Brand"] = specs.get('brand', 'Not Available')
        cat_specs["Volume / Net Wt"] = specs.get('volume', specs.get('weight', 'Not Available'))
        cat_specs["Skin Type"] = "All Skin Types"
        cat_specs["Expiry Date"] = "24 Months Best Before"
    elif category == "Kitchen Products":
        cat_specs["Material"] = specs.get('material', 'Stainless Steel / Non-Stick')
        cat_specs["Capacity"] = specs.get('capacity', specs.get('volume', 'Not Available'))
        cat_specs["Color"] = specs.get('color', 'Not Available')
        cat_specs["Wattage"] = specs.get('wattage', 'Not Available')
    elif category == "Clothing & Fashion":
        cat_specs["Brand"] = specs.get('brand', 'Not Available')
        cat_specs["Size"] = specs.get('size', 'S / M / L / XL / XXL')
        cat_specs["Color"] = specs.get('color', 'Not Available')
        cat_specs["Fabric / Material"] = specs.get('material', '100% Cotton / Denim / Polyester')
        cat_specs["Fit Type"] = "Slim Fit" if 'slim' in title_lower else ("Regular Fit" if 'regular' in title_lower else ("Oversized" if 'oversized' in title_lower else "Standard Fit"))
        cat_specs["Gender"] = "Women" if any(w in title_lower for w in ['women', 'lady', 'ladies', 'girl', 'saree', 'kurti', 'lehenga']) else ("Men" if any(w in title_lower for w in ['men', 'man', 'boy', 'gent']) else "Unisex")
        cat_specs["Care Instructions"] = "Machine Wash"
    else:
        cat_specs["Material"] = specs.get('material', 'Not Available')
        cat_specs["Color"] = specs.get('color', 'Not Available')
        cat_specs["Weight"] = specs.get('weight', 'Not Available')
        cat_specs["Wattage"] = specs.get('wattage', 'Not Available')

    specs['category_specs'] = cat_specs
    return specs


def enrich_products_with_specs(products: list, query: str = "") -> list:
    """
    Attach extracted specs to every product in the list.
    """
    for item in products:
        if 'specs' not in item or 'category_specs' not in item.get('specs', {}):
            item['specs'] = extract_specs(item, query)
    return products

