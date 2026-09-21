"""
search/query_parser.py
======================
Query Understanding & Entity Extraction Engine for SmartBuy.

Parses unstructured product search queries into strongly typed entity attributes:
brand, model, network (5G/4G), RAM, storage, processor, color, size, weight, volume,
quantity, pack_count, gender, material, category, subcategory.

Enforces deep semantic extraction so downstream matching and filtering
never compare accessories to core devices, or cross different product models.
"""

import re
from typing import Dict, Any, Optional

from search.category_detector import detect_category

KNOWN_BRANDS = [
    'Apple', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Realme', 'Xiaomi', 'Redmi', 'Motorola',
    'Google', 'iQOO', 'Poco', 'Nothing', 'Infinix', 'Tecno', 'Honor', 'Sony', 'LG',
    'HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Apple', 'MacBook', 'Microsoft',
    'boAt', 'Noise', 'Boult', 'Fire-Boltt', 'Fastrack', 'Titan', 'JBL', 'Zebronics', 'Portronics',
    'Pilgrim', 'Ghar', 'Ghar Soaps', 'Mamaearth', 'Dot & Key', 'The Derma Co', 'Cetaphil', 'Neutrogena',
    'Himalaya', 'Nivea', 'Dove', 'L\'Oreal', 'Biotique', 'Plum', 'Garnier', 'Head & Shoulders',
    'True Elements', 'Nutty Gritties', 'Neuherbs', 'Sorich Organics', 'Saffola', 'Tata', 'Fortune',
    'Aashirvaad', 'Daawat', 'India Gate', 'Catch', 'Everest', 'MDH', 'Cadbury', 'Nestle', 'Nescafe',
    'Nike', 'Adidas', 'Puma', 'Reebok', 'Campus', 'Bata', 'Sparx', 'Woodland', 'Red Tape',
    'Skybags', 'American Tourister', 'Safari', 'Wildcraft', 'Lavie', 'Baggit', 'Caprese',
    'Milton', 'Cello', 'Prestige', 'Hawkins', 'Pigeon', 'Bajaj', 'Philips', 'Havells', 'Crompton'
]

COMMON_COLORS = [
    'Black', 'White', 'Blue', 'Red', 'Green', 'Silver', 'Gold', 'Grey', 'Gray',
    'Pink', 'Purple', 'Yellow', 'Orange', 'Brown', 'Navy', 'Titanium', 'Midnight'
]

COMMON_MATERIALS = [
    'Cotton', 'Leather', 'Denim', 'Silk', 'Polyester', 'Georgette', 'Chiffon',
    'Linen', 'Wool', 'Nylon', 'Stainless Steel', 'Plastic', 'Ceramic', 'Glass', 'Wood'
]


def parse_query_entities(query: str) -> Dict[str, Any]:
    """
    Parses product-name query into complete structured entities.
    Example: "Vivo T4 5G 8GB 128GB" ->
    {
        "raw_query": "Vivo T4 5G 8GB 128GB",
        "brand": "Vivo",
        "model": "T4",
        "network": "5G",
        "ram": "8GB",
        "storage": "128GB",
        "category": "smartphone",
        "subcategory": "phone",
        ...
    }
    """
    clean_q = str(query or "").strip()
    q_lower = clean_q.lower()

    entities: Dict[str, Any] = {
        "raw_query": clean_q,
        "brand": None,
        "model": None,
        "product_type": None,
        "category": "other",
        "subcategory": None,
        "network": None,
        "ram": None,
        "storage": None,
        "processor": None,
        "color": None,
        "size": None,
        "weight": None,
        "volume": None,
        "quantity": None,
        "pack_count": None,
        "gender": None,
        "material": None,
        "is_accessory": False,
        "accessory_type": None,
    }

    if not clean_q:
        return entities

    # 1. Detect Category
    category = detect_category(query=clean_q)
    entities["category"] = category
    entities["product_type"] = category

    # Check if query is explicitly asking for an accessory
    acc_match = re.search(r'\b(case|cases|cover|covers|backcover|tempered\s*glass|screen\s*guard|strap|skin|pouch|sleeve|bag|holder)\b', q_lower)
    if acc_match:
        entities["is_accessory"] = True
        entities["accessory_type"] = acc_match.group(1).lower()

    # 2. Extract Brand
    if re.search(r'\b(iphone|ipad|macbook|airpods)\b', q_lower):
        entities["brand"] = "Apple"
    else:
        for b in KNOWN_BRANDS:
            pattern = r'\b' + re.escape(b.lower()) + r'\b'
            if re.search(pattern, q_lower):
                entities["brand"] = b
                break

    # 3. Extract Network (5G / 4G)
    if re.search(r'\b5g\b', q_lower):
        entities["network"] = "5G"
    elif re.search(r'\b4g\b', q_lower):
        entities["network"] = "4G"

    # 4. Extract RAM
    ram_m = re.search(r'\b(2|3|4|6|8|12|16|32|64)\s*gb\s*(?:ram|lpddr\d?)?\b', q_lower)
    if ram_m:
        entities["ram"] = f"{ram_m.group(1)}GB"

    # 5. Extract Storage
    storage_m = re.search(r'\b(32|64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b', q_lower)
    if storage_m:
        val = storage_m.group(0).upper().replace(" ", "")
        # If storage matches RAM token, prioritize larger one or disambiguate
        if entities["ram"] and val == entities["ram"]:
            # Check if there is a second GB token
            all_gbs = re.findall(r'\b(\d+)\s*gb\b', q_lower)
            if len(all_gbs) >= 2:
                entities["ram"] = f"{all_gbs[0]}GB"
                entities["storage"] = f"{all_gbs[1]}GB"
            elif int(storage_m.group(1) or 0) >= 64:
                entities["storage"] = val
                entities["ram"] = None
        else:
            entities["storage"] = val

    # 6. Extract Processor
    proc_m = re.search(r'\b(i[3579]-?\d{4,5}[a-z]?|core\s*i[3579]|ryzen\s*[3579]\s*\d{4}[a-z]?|snapdragon\s*\d+[a-z\s]*(?:gen\s*\d)?|dimensity\s*\d+[a-z]?|apple\s*m[1234](?:\s*pro|\s*max)?|bionic\s*a\d+)\b', q_lower)
    if proc_m:
        entities["processor"] = proc_m.group(1).title()

    # 7. Extract Model
    if entities["brand"] == "Vivo":
        # Vivo models e.g. T4, T4 Pro, T4 Lite, T3, T3x, V40, V30, Y200, X100
        m = re.search(r'\b(t\d(?:\s*pro|\s*lite|\s*x)?|v\d{2}(?:\s*pro)?|y\d{2,3}[a-z]?|x\d{2,3}(?:\s*pro)?)\b', q_lower)
        if m:
            entities["model"] = m.group(1).upper()
    elif entities["brand"] == "Apple":
        m = re.search(r'\b(iphone\s*(?:1[1-6]|se|x|xs|xr)(?:\s*(?:pro\s*max|pro|plus|mini))?|macbook\s*(?:air|pro)|ipad(?:\s*air|\s*pro)?)\b', q_lower)
        if m:
            entities["model"] = m.group(1).title()
    elif entities["brand"] == "Samsung":
        m = re.search(r'\b(galaxy\s*[asmf]\d{1,2}(?:\s*5g)?|galaxy\s*s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|galaxy\s*z\s*(?:fold|flip)\s*\d?)\b', q_lower)
        if m:
            entities["model"] = m.group(1).title()
    elif entities["brand"] == "HP":
        m = re.search(r'\b(pavilion\s*\d{2}?|victus\s*\d{2}?|omen\s*\d{2}?|envy\s*\d{2}?|spectre\s*\d{2}?|14s|15s|probook|elitebook)\b', q_lower)
        if m:
            entities["model"] = m.group(1).title()

    if not entities["model"]:
        # General model pattern for other electronics
        gen_m = re.search(r'\b([a-z]\d{1,3}(?:\s*pro|\s*plus|\s*ultra|\s*lite)?)\b', q_lower)
        if gen_m and gen_m.group(1) not in ('5g', '4g', '8gb', '128gb', '256gb', '64gb'):
            entities["model"] = gen_m.group(1).upper()

    # 8. Extract Weight / Volume (Exclude 5G/4G network tokens)
    wt_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?)\b', q_lower)
    if wt_m and wt_m.group(0).lower() not in ('5g', '4g', '3g', '2g'):
        entities["weight"] = f"{wt_m.group(1)}{wt_m.group(2)}"
        entities["unit"] = wt_m.group(2)
        entities["quantity"] = f"{wt_m.group(1)} {wt_m.group(2)}"

    vol_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(ml|l|litres?|liters?)\b', q_lower)
    if vol_m:
        entities["volume"] = f"{vol_m.group(1)}{vol_m.group(2)}"
        entities["unit"] = vol_m.group(2)
        entities["quantity"] = f"{vol_m.group(1)} {vol_m.group(2)}"

    # 9. Extract Pack Count
    pack_m = re.search(r'\b(?:pack\s*of\s*(\d+)|(\d+)\s*pack)\b', q_lower)
    if pack_m:
        entities["pack_count"] = int(pack_m.group(1) or pack_m.group(2))

    # 10. Extract Color
    for col in COMMON_COLORS:
        if re.search(r'\b' + re.escape(col.lower()) + r'\b', q_lower):
            entities["color"] = col
            break

    # 11. Extract Size (clothing / footwear)
    size_m = re.search(r'\bsize\s*[:\-]?\s*([a-z0-9]+)\b|\b(uk|us|ind)\s*(\d{1,2})\b|\b(xs|s|m|l|xl|xxl|3xl)\b', q_lower)
    if size_m:
        entities["size"] = (size_m.group(1) or (f"{size_m.group(2).upper()} {size_m.group(3)}" if size_m.group(2) else None) or size_m.group(4) or "").upper()

    # 12. Extract Material
    for mat in COMMON_MATERIALS:
        if re.search(r'\b' + re.escape(mat.lower()) + r'\b', q_lower):
            entities["material"] = mat
            break

    # 13. Extract Gender
    if re.search(r'\b(men|man|mens|boy|boys)\b', q_lower):
        entities["gender"] = "Men"
    elif re.search(r'\b(women|woman|womens|girl|girls|lady|ladies)\b', q_lower):
        entities["gender"] = "Women"

    return entities
