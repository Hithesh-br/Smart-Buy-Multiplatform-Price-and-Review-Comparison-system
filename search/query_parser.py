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
    'Avogro', 'Nutraj', 'Happilo', 'Farmley', 'Tulsi', 'Carnival', 'Wonderland', 'Solimo', 'Vedaka',
    'GreenFinity', 'Naturoz', 'Bajaj', 'Parachute', 'Dabur', 'Patanjali', 'MONK&METAL', 'Monk & Metal',
    'Reginald Men', 'Reginald',
    'Nike', 'Adidas', 'Puma', 'Reebok', 'Campus', 'Bata', 'Sparx', 'Woodland', 'Red Tape',
    'Skybags', 'American Tourister', 'Safari', 'Wildcraft', 'Lavie', 'Baggit', 'Caprese',
    'Milton', 'Cello', 'Prestige', 'Hawkins', 'Pigeon', 'Philips', 'Havells', 'Crompton'
]

COMMON_COLORS = [
    'Black', 'White', 'Blue', 'Red', 'Green', 'Silver', 'Gold', 'Grey', 'Gray',
    'Pink', 'Purple', 'Yellow', 'Orange', 'Brown', 'Navy', 'Titanium', 'Midnight'
]

COMMON_MATERIALS = [
    'Cotton', 'Leather', 'Denim', 'Silk', 'Polyester', 'Georgette', 'Chiffon',
    'Linen', 'Wool', 'Nylon', 'Stainless Steel', 'Plastic', 'Ceramic', 'Glass', 'Wood'
]


def extract_specific_product_type(text: str, category: str = "") -> str:
    """
    Extracts the granular, specific product type from query or title.
    Examples:
    - 'Avogro Premium Pistachios 500GM' -> 'pistachios'
    - 'Bajaj 100% Pure Coconut Oil 1 litre' -> 'coconut_oil'
    - 'Stainless Steel Water Bottle' -> 'water_bottle'
    - 'Reginald Men Hydrating Face & Beard Wash' -> 'face_wash'
    - 'Royal Oscar Fish Food' -> 'fish_food'
    - 'Avishi Pigerry Pig Health Supplement' -> 'pig_supplement'
    """
    t_low = str(text or "").lower()

    # Animal / Pet Products
    if re.search(r'\b(pigs?\s*supplement|pigerry|swine|pig\s*feed)\b', t_low):
        return "pig_supplement"
    if re.search(r'\b(fish\s*food|fish\s*feed|aquarium\s*food|pellet\s*fish\s*food)\b', t_low):
        return "fish_food"
    if re.search(r'\b(dog\s*food|puppy\s*food)\b', t_low):
        return "dog_food"
    if re.search(r'\b(cat\s*food|kitten\s*food)\b', t_low):
        return "cat_food"
    if re.search(r'\b(animal\s*feed|cattle\s*feed|poultry\s*feed)\b', t_low):
        return "animal_feed"

    # Grocery: Dry fruits, nuts & edible oils
    if re.search(r'\b(pistachio|pistachios|pista)\b', t_low):
        return "pistachios"
    if re.search(r'\b(almond|almonds|badam)\b', t_low):
        return "almonds"
    if re.search(r'\b(cashew|cashews|kaju)\b', t_low):
        return "cashews"
    if re.search(r'\b(walnut|walnuts|akhrot)\b', t_low):
        return "walnuts"
    if re.search(r'\b(raisin|raisins|kishmish)\b', t_low):
        return "raisins"
    if re.search(r'\b(dates|khajoor)\b', t_low):
        return "dates"
    if re.search(r'\b(makhana|fox\s*nuts?)\b', t_low):
        return "makhana"
    if re.search(r'\b(chia\s*seeds?)\b', t_low):
        return "chia_seeds"
    if re.search(r'\b(flax\s*seeds?)\b', t_low):
        return "flax_seeds"
    if re.search(r'\b(coconut\s*oil)\b', t_low):
        return "coconut_oil"
    if re.search(r'\b(mustard\s*oil|sarson\s*tel)\b', t_low):
        return "mustard_oil"
    if re.search(r'\b(olive\s*oil)\b', t_low):
        return "olive_oil"

    # Personal Care & Beauty
    if re.search(r'\b(face\s*(?:and|&)?\s*(?:\w+\s*)?wash|facewash|beard\s*wash|facial\s*cleanser)\b', t_low):
        return "face_wash"
    if re.search(r'\b(soap|soaps|bathing\s*bar)\b', t_low):
        return "soap"
    if re.search(r'\b(shampoo|hair\s*wash)\b', t_low):
        return "shampoo"
    if re.search(r'\b(sunscreen|sunblock)\b', t_low):
        return "sunscreen"
    if re.search(r'\b(face\s*cream|moisturizer|moisturiser|day\s*cream|night\s*cream)\b', t_low):
        return "face_cream"
    if re.search(r'\b(serum|face\s*serum)\b', t_low):
        return "serum"
    if re.search(r'\b(lipstick|lip\s*gloss|lip\s*balm)\b', t_low):
        return "lipstick"
    if re.search(r'\b(foundation|compact|bb\s*cream)\b', t_low):
        return "foundation"

    # Home & Kitchen
    if re.search(r'\b(water\s*bottle|water\s*bottles|steel\s*bottle|flask|thermos|sipper)\b', t_low) or (re.search(r'\bbottles?\b', t_low) and any(w in t_low for w in ('steel', 'water', 'stainless', 'copper', 'insulated', 'vacuum', 'sipper'))):
        return "water_bottle"
    if re.search(r'\b(pressure\s*cooker|cooker)\b', t_low):
        return "pressure_cooker"
    if re.search(r'\b(mixer\s*grinder|mixer|grinder|blender)\b', t_low):
        return "mixer_grinder"
    if re.search(r'\b(electric\s*kettle|kettle)\b', t_low):
        return "electric_kettle"
    if re.search(r'\b(refrigerator|fridge)\b', t_low):
        return "refrigerator"
    if re.search(r'\b(washing\s*machine|washer)\b', t_low):
        return "washing_machine"
    if re.search(r'\b(microwave)\b', t_low):
        return "microwave"

    # Electronics
    if re.search(r'\b(smartwatch|smart\s*watch)\b', t_low):
        return "smartwatch"
    if re.search(r'\b(phone|smartphone|mobile)\b', t_low):
        return "phone"
    if re.search(r'\b(laptop|notebook|macbook)\b', t_low):
        return "laptop"
    if re.search(r'\b(tablet|ipad)\b', t_low):
        return "tablet"
    if re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive)\b', t_low):
        return "pen_drive"
    if re.search(r'\b(earphone|earphones|earbuds|airpods|neckband|tws)\b', t_low):
        return "earphones"
    if re.search(r'\b(headphone|headphones|headset)\b', t_low):
        return "headphones"
    if re.search(r'\b(charger|adapter|power\s*adapter)\b', t_low):
        return "charger"
    if re.search(r'\b(tv|television)\b', t_low):
        return "television"

    # Footwear & Clothing
    if re.search(r'\b(shoe|shoes|sneaker|sneakers|boots?|loafers?|running\s*shoes)\b', t_low):
        return "shoes"
    if re.search(r'\b(slipper|slippers|flip\s*flop|chappals?|slides?)\b', t_low):
        return "slippers"
    if re.search(r'\b(shirt|shirts|tshirt|t-shirt)\b', t_low):
        return "shirt"
    if re.search(r'\b(saree|sari)\b', t_low):
        return "saree"

    return category or "other"


NON_BRAND_TERMS = {
    # Demographics & Genders
    'men', 'man', 'mens', "men's", 'women', 'woman', 'womens', "women's",
    'kids', 'kid', "kids'", 'boy', 'boys', "boys'", 'girl', 'girls', "girls'",
    'baby', 'babies', 'infant', 'infants', 'adult', 'adults', 'unisex', 'male', 'female',
    'ladies', 'lady', 'gent', 'gents',
    # Apparel & Footwear items
    'jeans', 'shirt', 'shirts', 'tshirt', 't-shirt', 'tee', 'tees', 'top', 'tops',
    'dress', 'dresses', 'saree', 'sari', 'kurta', 'kurtas', 'kurti', 'kurtis',
    'pant', 'pants', 'trousers', 'trouser', 'jacket', 'jackets', 'hoodie', 'hoodies',
    'sweater', 'sweaters', 'shoes', 'shoe', 'sneakers', 'sneaker', 'sandals', 'sandal',
    'slippers', 'slipper', 'boots', 'boot', 'loafers', 'flats', 'heels', 'shorts',
    'leggings', 'trackpants', 'joggers', 'socks', 'innerwear', 'briefs', 'bra',
    # Fabrics & Materials
    'cotton', 'denim', 'linen', 'silk', 'wool', 'leather', 'nylon', 'polyester',
    'fleece', 'chiffon', 'georgette', 'khadi', 'velvet', 'satin', 'stretchable', 'stretch',
    'stainless', 'steel', 'plastic', 'glass', 'ceramic', 'copper', 'metal', 'wood', 'wooden',
    # Styles, Cuts & Fits
    'baggy', 'slim', 'skinny', 'loose', 'relaxed', 'straight', 'flared', 'regular',
    'oversized', 'casual', 'formal', 'party', 'ethnic', 'western', 'printed', 'plain',
    'solid', 'striped', 'checked', 'cargo', 'high', 'mid', 'low', 'waist', 'rise',
    # Common Product Types & Tech
    'smartwatch', 'smart', 'watch', 'phone', 'smartphone', 'mobile', 'laptop', 'tablet',
    'pen', 'drive', 'pendrive', 'face', 'wash', 'facewash', 'soap', 'shampoo', 'cream',
    'moisturizer', 'moisturiser', 'sunscreen', 'serum', 'lotion', 'bottle', 'flask',
    'cooker', 'kettle', 'mixer', 'grinder', 'blender', 'oil', 'earphones', 'earbuds',
    'headphones', 'neckband', 'speaker', 'speakers', 'charger', 'adapter', 'cable',
    'case', 'cover', 'guard', 'protector', 'seeds', 'nuts', 'dry', 'fruit', 'fruits',
    'pack', 'combo', 'set', 'pure', 'organic', 'natural', 'fresh', 'premium', 'best',
    'buy', 'online', 'new', 'original', 'cheap', 'top', 'good', 'color', 'size'
}


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

    # 1. Detect Category & Specific Product Type
    category = detect_category(query=clean_q)
    entities["category"] = category
    entities["product_type"] = extract_specific_product_type(clean_q, category)

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

    # If brand not in KNOWN_BRANDS, dynamically extract leading brand token if not a generic term
    if not entities["brand"]:
        tokens = clean_q.split()
        if tokens:
            t0 = tokens[0]
            t0_low = t0.lower()
            if t0_low not in NON_BRAND_TERMS and len(t0) > 1 and t0[0].isupper():
                if len(tokens) >= 2 and tokens[1].lower() in ('men', 'metal', 'naturals', 'organics', 'foods', 'pure', 'gold') and f"{t0_low} {tokens[1].lower()}" not in NON_BRAND_TERMS:
                    entities["brand"] = f"{tokens[0]} {tokens[1]}"
                else:
                    entities["brand"] = t0

    # Safety check: if brand somehow ended up as a non-brand term, reset to None
    if entities["brand"] and str(entities["brand"]).strip().lower() in NON_BRAND_TERMS:
        entities["brand"] = None

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
