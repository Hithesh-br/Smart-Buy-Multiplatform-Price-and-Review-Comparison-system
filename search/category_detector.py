"""
search/category_detector.py
===========================
Canonical category detection service for SmartBuy.
Supports any arbitrary e-commerce product query across:
- Phones & Tablets
- Laptops & Computers
- Chargers, Cables & Power Adapters
- Earphones, Headphones & Audio
- Televisions & Displays
- Refrigerators, Washing Machines, Air Conditioners
- Kitchen Appliances (Mixer, Microwave, Cooker, Kettle...)
- Cameras & Photography
- Watches & Smartwatches
- Shoes & Footwear
- Clothing, Sarees, Shirts & Fashion
- Bags, Backpacks & Luggage
- Beauty, Skincare, Haircare, Makeup & Cosmetics
- Soaps, Face Wash & Personal Care
- Shampoo & Hair Care
- Groceries, Food & Dry Fruits
- Kitchen Utensils & Cookware
- Home Appliances & Furniture
- Toys, Stationery & Office Supplies
- Accessories

No circular dependencies.
"""

import re
from typing import Optional, Any


def strip_compatibility_clauses(text: str) -> str:
    """
    Strips 'compatible with ...', 'for laptop/mobile/pc/tv...', 'supports ...'
    from title so that secondary/compatibility devices are not misclassified as the parent device.
    """
    if not text:
        return ""
    # Strip after "compatible with ...", "compatibility ...", "suitable for ...", "works with ..."
    cleaned = re.sub(r'\b(?:compatible\s+with|compatibility\s*:?|suitable\s+for|works\s+with|designed\s+for|supports?)\b.*$', '', text, flags=re.IGNORECASE)
    # Strip phrases like "for laptop", "for iphone", "for tv"
    cleaned = re.sub(r'\bfor\s+(?:laptop|laptops|notebook|notebooks|pc|desktop|computer|computers|mobile|mobiles|phone|phones|smartphone|smartphones|iphone|ipad|tablet|tablets|television|televisions|tv|tvs|audio\s*player|gaming\s*console|netbook)\b.*$', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or text


def detect_category(
    query: str = "",
    title: str = "",
    attributes: Optional[dict] = None,
    marketplace_cat: str = "",
    description: str = "",
    product_type: str = ""
) -> str:
    """
    Canonical category detector.
    Accepts either (query, title) or named arguments.
    Priority:
    1. Direct title / query / product_type signal
    2. Marketplace category
    3. Detailed attributes & description

    Returns a lowercase category slug such as:
    'pen_drive', 'phone', 'laptop', 'television', 'refrigerator', 'washing_machine',
    'air_conditioner', 'microwave', 'mixer_grinder', 'kitchen', 'home_appliance',
    'grocery', 'face_wash', 'shampoo', 'beauty', 'skincare', 'makeup',
    'soap', 'clothing', 'shoes', 'bags', 'earphones', 'headphones',
    'earbuds', 'watch', 'charger', 'tablet', 'camera', 'electronics',
    'furniture', 'home', 'toys', 'stationery', 'other'
    """
    # Normalize inputs
    q_str = str(query or "").strip()
    t_str = str(title or "").strip()
    pt_str = str(product_type or "").strip()
    mc_str = str(marketplace_cat or "").strip()
    desc_str = str(description or "").strip()

    attr_text = ""
    if isinstance(attributes, dict):
        attr_text = " ".join(f"{k} {v}" for k, v in attributes.items())

    # Strip compatibility clauses from title and query to avoid misclassifying accessories/peripherals
    cleaned_t = strip_compatibility_clauses(t_str)
    cleaned_q = strip_compatibility_clauses(q_str)

    # Build primary text focusing on cleaned title, product_type, and cleaned query
    primary_text = f"{cleaned_t} {pt_str} {cleaned_q}".lower()
    full_text = f"{t_str} {pt_str} {mc_str} {attr_text} {desc_str} {q_str}".lower()

    # 0. Storage Devices & USB Flash Drives / Pen Drives
    # (MUST precede laptop/computer/stationery detection so 'HP 128GB Pen Drive compatible with laptop' → pen_drive)
    if re.search(r'\b(pen\s*drive|pendrive|pendrives|usb\s*flash\s*drive|flash\s*drive|flash\s*drives|thumb\s*drive|thumb\s*drives|usb\s*drive|usb\s*drives|memory\s*card|memory\s*cards|micro\s*sd|sd\s*card|microsd|external\s*hard\s*drive|external\s*hdd|external\s*ssd|portable\s*ssd|portable\s*hard\s*drive|otg\s*drive|otg\s*pen\s*drive)\b', primary_text) or re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive)\b', f"{t_str} {pt_str} {q_str}".lower()):
        return "pen_drive"

    # 0b. Bags, Backpacks, Sleeves & Luggage
    # (must precede chargers so 'laptop bag with charger pouch' or 'laptop sleeve' → bags)
    if re.search(r'\b(bag|bags|school\s*bag|backpack|backpacks|trolley|luggage|suitcase|duffel|handbag|handbags|purse|wallet|wallets|laptop\s*bag|laptop\s*case|laptop\s*sleeve|tablet\s*sleeve|sleeve\s*case|pouch)\b', primary_text):
        return "bags"

    # 1. Chargers, Cables & Power Adapters
    # (MUST precede phone detection so 'vivo charger' → charger)
    if re.search(r'\b(charger|chargers|adapter|adapters|fast\s*charger|charging\s*cable|power\s*adapter|power\s*cable|dock|powerbank|power\s*bank)\b', primary_text):
        return "charger"

    # 2. Personal Care, Bathing & Grooming
    if re.search(r'\b(soap|soaps|bathing\s*bar|body\s*bar|beauty\s*bar|handmade\s*soap|bathing\s*soap)\b', primary_text):
        return "soap"
    if re.search(r'\b(face\s*wash|facewash|facial\s*cleanser|face\s*cleanser|face\s*scrub)\b', primary_text):
        return "face_wash"
    if re.search(r'\b(shampoo|conditioner|hair\s*wash|hair\s*cleanser|hair\s*oil|hair\s*mask|hair\s*serum|hair\s*care)\b', primary_text):
        return "shampoo"
    if re.search(r'\b(lipstick|lip\s*stick|lip\s*gloss|lip\s*balm|mascara|eyeliner|eye\s*liner|kajal|foundation|compact|blush|nail\s*polish|makeup|eye\s*shadow|eyeshadow|concealer|bb\s*cream|cc\s*cream|face\s*primer|highlighter|contour|bronzer)\b', primary_text):
        return "makeup"
    if re.search(r'\b(hair\s*dryer|dryer|trimmer|shaver|straightener)\b', primary_text):
        return "beauty"
    if re.search(r'\b(sunscreen|sun\s*screen|spf\s*\d+|sun\s*block|moisturizer|serum|creams?|lotion|skincare|cosmetics?|face\s*mask|peel)\b', primary_text):
        return "skincare"
    if re.search(r'\b(perfume|perfumes|deodorant|deodorants|body\s*spray|fragrance|cologne|mist)\b', primary_text):
        return "beauty"

    # 3. Audio & Wearables
    if re.search(r'\b(earphone|earphones|earbuds|airpods|neckband|tws|in-ear|wireless\s*earbuds)\b', primary_text):
        return "earphones"
    if re.search(r'\b(headphone|headphones|headset|over-ear|on-ear)\b', primary_text):
        return "headphones"
    if re.search(r'\b(speaker|speakers|bluetooth\s*speaker|soundbar|sound\s*bar|home\s*theater)\b', primary_text):
        return "electronics"
    if re.search(r'\b(smartwatch|smartwatches|smart\s*watch|apple\s*watch|galaxy\s*watch|fitness\s*band|tracker\s*band)\b', primary_text):
        return "watch"
    if re.search(r'\b(watch|watches|chronograph|analog\s*watch|digital\s*watch)\b', primary_text):
        return "watch"

    # 4. Electronics, Computers & Devices
    if re.search(r'\b(laptop|laptops|macbook|notebook|notebooks|chromebook|thinkpad|ideapad|vivobook|zenbook|tuf|rog|aspire|omen|pavilion|victus)\b', primary_text):
        return "laptop"
    if re.search(r'\b(phone|phones|mobile|mobiles|iphone|galaxy\s*s\d+|smartphone|smartphones|pixel|redmi|realme|oneplus|vivo|oppo|motorola|iqoo)\b', primary_text):
        return "phone"
    if re.search(r'\b(tablet|tablets|ipad|ipads|tab|tabs|kindle)\b', primary_text):
        return "tablet"
    if re.search(r'\b(camera|cameras|dslr|mirrorless|gopro|digicam|webcam|tripod)\b', primary_text):
        return "camera"

    # 5. Televisions (dedicated subcategory)
    if re.search(r'\b(tv|tvs|television|televisions|led\s*tv|smart\s*tv|4k\s*tv|oled|qled|bravia|crystal\s*uhd)\b', primary_text):
        return "television"

    # 6. Major Home Appliances (dedicated subcategories)
    if re.search(r'\b(refrigerator|fridge|double\s*door\s*fridge|single\s*door\s*fridge|frost\s*free\s*fridge)\b', primary_text):
        return "refrigerator"
    if re.search(r'\b(washing\s*machine|washer|front\s*load|top\s*load|semi\s*automatic|fully\s*automatic)\b', primary_text):
        return "washing_machine"
    if re.search(r'\b(air\s*conditioner|split\s*ac|window\s*ac|inverter\s*ac|portable\s*ac)\b', primary_text):
        return "air_conditioner"
    if re.search(r'\b(microwave|microwave\s*oven|convection\s*microwave|solo\s*microwave)\b', primary_text):
        return "microwave"
    if re.search(r'\b(mixer\s*grinder|mixer|grinder|food\s*processor|hand\s*blender|stand\s*mixer)\b', primary_text):
        return "mixer_grinder"
    if re.search(r'\b(vacuum\s*cleaner|vacuum|robot\s*vacuum|geyser|water\s*heater|room\s*heater|cooler|air\s*cooler|ceiling\s*fan|exhaust\s*fan)\b', primary_text):
        return "home_appliance"

    # 7. Kitchen & Cookware & Water Bottles
    if re.search(r'\b(water\s*bottle|water\s*bottles|steel\s*bottle|steel\s*bottles|sipper|sippers|thermos|flask|flasks|insulated\s*bottle|insulated\s*bottles|fridge\s*bottle|fridge\s*bottles|gym\s*bottle|gym\s*bottles)\b', primary_text) or (re.search(r'\bbottles?\b', primary_text) and any(k in primary_text for k in ('water', 'steel', 'stainless', 'copper', 'insulated', 'vacuum', 'sipper', 'flask'))):
        return "water_bottle"
    if re.search(r'\b(cooker|pressure\s*cooker|pan|stove|induction\s*stove|kettle|electric\s*kettle|toaster|oven|utensil|cookware|storage\s*box|container|containers|kitchen)\b', primary_text):
        return "kitchen"

    # 7b. Face Wash, Soaps, Skincare, Haircare & Beauty
    if re.search(r'\b(face\s*(?:and|&)?\s*(?:\w+\s*)?wash|facewash|face\s*cleanser|facial\s*cleanser|cleanser|beard\s*wash|foaming\s*wash)\b', primary_text):
        return "face_wash"
    if re.search(r'\b(soap|soaps|bathing\s*bar|soap\s*bar|body\s*wash|shower\s*gel)\b', primary_text):
        return "soap"
    if re.search(r'\b(shampoo|shampoos|conditioner|hair\s*conditioner|hair\s*oil|hair\s*serum|hair\s*mask)\b', primary_text):
        return "shampoo"
    if re.search(r'\b(sunscreen|sun\s*screen|sunblock|spf\s*\d+|moisturizer|moisturiser|day\s*cream|night\s*cream|face\s*cream|face\s*serum|skin\s*serum|toner|face\s*scrub|scrub|body\s*lotion|lotion|skin\s*care|skincare)\b', primary_text):
        return "skincare"
    if re.search(r'\b(lipstick|lip\s*stick|lip\s*gloss|lip\s*balm|foundation|kajal|mascara|eyeliner|eye\s*liner|compact|blush|concealer|makeup|cosmetic|cosmetics)\b', primary_text):
        return "makeup"

    # 8. Other Electronics
    if re.search(r'\b(monitor|printer|keyboard|mouse|router|ssd|hard\s*drive|pendrive|electronics)\b', primary_text):
        return "electronics"

    # 9. Bags, Luggage & Backpacks (second check, covered abbreviations)
    if re.search(r'\b(bag|bags|school\s*bag|backpack|backpacks|trolley|luggage|suitcase|duffel|handbag|handbags|purse|wallet|wallets)\b', primary_text):
        return "bags"

    # 10. Fashion, Footwear & Clothing
    if re.search(r'\b(shoe|shoes|sneaker|sneakers|sandal|sandals|slipper|slippers|boots|loafers|footwear|heels|crocs|running\s*shoes)\b', primary_text):
        return "shoes"
    if re.search(r'\b(saree|sarees|sari|saris|kurti|kurtis|kurta|kurtas|lehenga|blouse|anarkali|salwar)\b', primary_text):
        return "clothing"
    if re.search(r'\b(shirt|shirts|tshirt|t-shirt|t\s*shirt|jeans|trouser|trousers|pant|pants|dress|dresses|jacket|jackets|coat|hoodie|hoodies|sweater|sweaters|shorts|skirt|skirts|tracksuit|suit|suits|blazer|blazers|top|tops)\b', primary_text):
        return "clothing"

    # 10b. Pet Supplies, Animal Feed & Veterinary Products
    # (MUST precede Grocery so 'pig supplement' or 'fish food' or 'dog food' is NEVER classified as human grocery!)
    if re.search(r'\b(pet\s*food|dog\s*food|cat\s*food|puppy\s*food|kitten\s*food|bird\s*food|bird\s*feed|fish\s*food|fish\s*feed|aquarium\s*food|pellet\s*fish\s*food|pellet\s*feed|pig\s*food|pigs?\s*supplement|swine\s*feed|cattle\s*feed|poultry\s*feed|animal\s*feed|animal\s*supplement|animal\s*health|pigerry|piglet|swine|veterinary|for\s*pigs|for\s*swine|for\s*dogs|for\s*cats|for\s*fish|for\s*birds|for\s*cattle|for\s*pets|pet\s*supplies|aquarium|cat\s*litter|dog\s*collar|dog\s*leash|pet\s*shampoo)\b', primary_text):
        return "pet_supplies"

    # 11. Grocery, Food & Nutrition (Human Consumption)
    if re.search(r'\b(pistachio|pistachios|pista|almond|almonds|badam|cashew|cashews|kaju|walnut|walnuts|akhrot|raisin|raisins|kishmish|dates|khajoor|dry\s*fruits?|nuts?|makhana|fox\s*nuts?|trail\s*mix|chia\s*seed|chia\s*seeds|flax\s*seed|flax\s*seeds|pumpkin\s*seed|pumpkin\s*seeds|sunflower\s*seed|sunflower\s*seeds|basil\s*seed|basil\s*seeds|quinoa|rice|flour|atta|wheat\s*flour|besan|oil|ghee|coconut\s*oil|mustard\s*oil|olive\s*oil|sunflower\s*oil|edible\s*oil|cooking\s*oil|milk|curd|butter|cheese|bread|egg|sugar|salt|tea|coffee|dal|pulses|lentils|noodle|noodles|biscuit|biscuits|chocolate|chocolates|grocery)\b', primary_text):
        return "grocery"
    if re.search(r'\b(snack|snacks|cereal|cereals|pasta|jam|sauce|honey|spices|masala|food|protein\s*powder|whey)\b', primary_text):
        return "grocery"

    # 12. Home, Bedding & Furniture
    if re.search(r'\b(bedsheet|bedsheets|bed\s*sheet|bed\s*cover|pillow|pillows|pillowcase|blanket|blankets|quilt|curtain|curtains|mattress|towel|towels|bedding|cushion|cushions)\b', primary_text):
        return "home"

    # 13. Furniture & Home Decor
    if re.search(r'\b(chair|table|desk|sofa|bed|mattress|wardrobe|bookshelf|cabinet|curtain|bedsheet|pillow|carpet|furniture)\b', primary_text):
        return "furniture"

    # 14. Toys & Stationery (with guard so 'pen drive' is never classified as stationery)
    if re.search(r'\b(toy|toys|game|games|doll|board\s*game|puzzle|lego)\b', primary_text):
        return "toys"
    if re.search(r'\b(ball\s*pen|gel\s*pen|fountain\s*pen|pencil|pencils|notebook|notebooks|diary|paper|stapler|eraser|stationery)\b', primary_text) or (re.search(r'\bpen\b', primary_text) and not re.search(r'\b(pen\s*drive|pendrive)\b', f"{t_str} {q_str}".lower())):
        return "stationery"

    # === Fallback: check full_text if primary text didn't trigger ===
    if re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive)\b', full_text):
        return "pen_drive"

    # === Fallback: check full_text if primary text didn't trigger ===
    if re.search(r'\b(charger|adapter)\b', full_text):
        return "charger"
    if re.search(r'\b(phone|smartphone|mobile)\b', full_text):
        return "phone"
    if re.search(r'\b(laptop|notebook)\b', full_text):
        return "laptop"
    if re.search(r'\b(tv|television)\b', full_text):
        return "television"
    if re.search(r'\b(refrigerator|fridge)\b', full_text):
        return "refrigerator"
    if re.search(r'\b(washing\s*machine)\b', full_text):
        return "washing_machine"
    if re.search(r'\b(microwave)\b', full_text):
        return "microwave"
    if re.search(r'\b(mixer\s*grinder|mixer)\b', full_text):
        return "mixer_grinder"
    if re.search(r'\b(face\s*(?:and|&)?\s*(?:\w+\s*)?wash|facewash|beard\s*wash)\b', full_text):
        return "face_wash"
    if re.search(r'\b(shampoo|conditioner)\b', full_text):
        return "shampoo"
    if re.search(r'\b(makeup|lipstick|foundation)\b', full_text):
        return "makeup"
    if re.search(r'\b(soap|face\s*wash|shampoo)\b', full_text):
        return "soap"
    if re.search(r'\b(shoes?|sneakers?)\b', full_text):
        return "shoes"
    if re.search(r'\b(clothing|shirt|saree|dress)\b', full_text):
        return "clothing"
    if re.search(r'\b(pet\s*food|dog\s*food|cat\s*food|fish\s*food|pig\s*supplement|animal\s*feed|swine|pigerry)\b', full_text):
        return "pet_supplies"
    if re.search(r'\b(food|grocery|dry\s*fruits?|nuts?|pista|almond)\b', full_text):
        return "grocery"
    if re.search(r'\b(water\s*bottle|water\s*bottles|sipper|flask)\b', full_text):
        return "water_bottle"
    if re.search(r'\b(kitchen)\b', full_text):
        return "kitchen"
    if re.search(r'\b(bag|backpack)\b', full_text):
        return "bags"

    return "other"


# Category Families mapping for cross-category compatibility validation
CATEGORY_FAMILIES = {
    # Food & Grocery (Human consumption)
    "grocery": "grocery",
    "dry_fruits": "grocery",
    "nuts": "grocery",
    "cooking_oil": "grocery",
    "food": "grocery",

    # Pet & Animal Products (NEVER compatible with human food/personal care)
    "pet_supplies": "pet",
    "animal_feed": "pet",
    "pet_food": "pet",

    # Personal Care & Beauty
    "face_wash": "personal_care",
    "soap": "personal_care",
    "shampoo": "personal_care",
    "skincare": "personal_care",
    "makeup": "personal_care",
    "beauty": "personal_care",

    # Electronics & Gadgets
    "phone": "electronics",
    "laptop": "electronics",
    "tablet": "electronics",
    "watch": "electronics",
    "television": "electronics",
    "charger": "electronics",
    "earphones": "electronics",
    "headphones": "electronics",
    "pen_drive": "electronics",
    "storage_device": "electronics",
    "electronics": "electronics",
    "camera": "electronics",

    # Home & Kitchen
    "water_bottle": "home_kitchen",
    "kitchen": "home_kitchen",
    "cooker": "home_kitchen",
    "pressure_cooker": "home_kitchen",
    "mixer_grinder": "home_kitchen",
    "electric_kettle": "home_kitchen",
    "refrigerator": "home_kitchen",
    "washing_machine": "home_kitchen",
    "microwave": "home_kitchen",
    "home_appliance": "home_kitchen",
    "furniture": "home_kitchen",
    "home": "home_kitchen",

    # Fashion
    "clothing": "fashion",
    "shoes": "fashion",
    "bags": "fashion",

    # Toys & Stationery
    "toys": "toys",
    "stationery": "stationery",
}


def get_category_family(category: str) -> str:
    """Returns the high-level category family (grocery, pet, personal_care, electronics, home_kitchen, fashion)."""
    c = str(category or "").lower().strip()
    return CATEGORY_FAMILIES.get(c, "other")

