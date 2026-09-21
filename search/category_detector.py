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
- Cameras & Photography
- Watches & Smartwatches
- Shoes & Footwear
- Clothing, Sarees, Shirts & Fashion
- Bags, Backpacks & Luggage
- Beauty, Skincare, Haircare, Makeup & Cosmetics
- Soaps, Face Wash & Personal Care
- Groceries, Food & Dry Fruits
- Kitchen Utensils & Cookware
- Home Appliances & Furniture
- Toys, Stationery & Office Supplies
- Accessories

No circular dependencies.
"""

import re
from typing import Optional, Any


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

    # Build primary text focusing on title, product_type, and query
    primary_text = f"{t_str} {pt_str} {q_str}".lower()
    full_text = f"{t_str} {pt_str} {mc_str} {attr_text} {desc_str} {q_str}".lower()

    if not full_text.strip():
        return "other"

    # 1. Chargers, Cables & Power Adapters (MUST precede phone detection so 'vivo charger' -> charger)
    if re.search(r'\b(charger|chargers|adapter|adapters|fast\s*charger|charging\s*cable|power\s*adapter|power\s*cable|dock|powerbank|power\s*bank)\b', primary_text):
        return "charger"

    # 2. Personal Care, Bathing & Grooming
    if re.search(r'\b(soap|soaps|bathing\s*bar|body\s*bar|beauty\s*bar|handmade\s*soap|bathing\s*soap)\b', primary_text):
        return "soap"
    if re.search(r'\b(face\s*wash|facewash|facial\s*cleanser|face\s*cleanser|face\s*scrub)\b', primary_text):
        return "face_wash"
    if re.search(r'\b(shampoo|conditioner|hair\s*wash|hair\s*cleanser|hair\s*oil)\b', primary_text):
        return "shampoo"
    if re.search(r'\b(lipstick|lip\s*stick|lip\s*gloss|lip\s*balm|mascara|eyeliner|eye\s*liner|kajal|foundation|compact|blush|nail\s*polish|makeup|hair\s*dryer|dryer|trimmer|shaver|straightener)\b', primary_text):
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
    if re.search(r'\b(tv|tvs|television|televisions|led\s*tv|smart\s*tv|4k\s*tv|oled|qled|bravia|refrigerator|fridge|washing\s*machine|microwave)\b', primary_text):
        return "television"
    if re.search(r'\b(monitor|printer|keyboard|mouse|router|ssd|hard\s*drive|pendrive|electronics)\b', primary_text):
        return "electronics"

    # 5. Bags, Luggage & Backpacks
    if re.search(r'\b(bag|bags|school\s*bag|backpack|backpacks|trolley|luggage|suitcase|duffel|handbag|handbags|purse|wallet|wallets)\b', primary_text):
        return "bags"

    # 6. Fashion, Footwear & Clothing
    if re.search(r'\b(shoe|shoes|sneaker|sneakers|sandal|sandals|slipper|slippers|boots|loafers|footwear|heels|crocs|running\s*shoes)\b', primary_text):
        return "shoes"
    if re.search(r'\b(saree|sarees|sari|saris|kurti|kurtis|kurta|kurtas|lehenga|blouse|anarkali|salwar)\b', primary_text):
        return "clothing"
    if re.search(r'\b(shirt|shirts|tshirt|t-shirt|t\s*shirt|jeans|trouser|trousers|pant|pants|dress|dresses|jacket|jackets|coat|hoodie|hoodies|sweater|sweaters|shorts|skirt|skirts|tracksuit|suit|suits|blazer|blazers|top|tops)\b', primary_text):
        return "clothing"

    # 7. Grocery, Food & Nutrition
    if re.search(r'\b(chia\s*seed|chia\s*seeds|flax\s*seed|flax\s*seeds|pumpkin\s*seed|pumpkin\s*seeds|sunflower\s*seed|sunflower\s*seeds|basil\s*seed|basil\s*seeds|quinoa|rice|flour|atta|oil|ghee|milk|curd|butter|cheese|bread|egg|sugar|salt|tea|coffee|dal|noodle|noodles|biscuit|biscuits|chocolate|chocolates|grocery|dry\s*fruits|almond|almonds|cashew|cashews)\b', primary_text):
        return "grocery"
    if re.search(r'\b(snack|snacks|cereal|cereals|pasta|jam|sauce|honey|spices|masala|food)\b', primary_text):
        return "grocery"

    # 8. Home, Bedding & Furniture
    if re.search(r'\b(bedsheet|bedsheets|bed\s*sheet|bed\s*cover|pillow|pillows|pillowcase|blanket|blankets|quilt|curtain|curtains|mattress|towel|towels|bedding|cushion|cushions)\b', primary_text):
        return "home"

    # 9. Kitchen & Home Appliances
    if re.search(r'\b(cooker|pan|stove|mixer|grinder|kettle|blender|toaster|microwave|oven|utensil|cookware|storage\s*box|container|containers|kitchen)\b', primary_text):
        return "kitchen"
    if re.search(r'\b(refrigerator|fridge|washing\s*machine|air\s*conditioner|ac|cooler|fan|vacuum|geyser|heater|iron)\b', primary_text):
        return "home_appliance"

    # 9. Furniture & Home Decor
    if re.search(r'\b(chair|table|desk|sofa|bed|mattress|wardrobe|bookshelf|cabinet|curtain|bedsheet|pillow|carpet|furniture)\b', primary_text):
        return "furniture"

    # 10. Toys & Stationery
    if re.search(r'\b(toy|toys|game|games|doll|board\s*game|puzzle|lego)\b', primary_text):
        return "toys"
    if re.search(r'\b(pen|pencil|notebook|diary|paper|stapler|eraser|stationery)\b', primary_text):
        return "stationery"

    # Fallback checking full_text if primary text didn't trigger
    if re.search(r'\b(charger|adapter)\b', full_text):
        return "charger"
    if re.search(r'\b(phone|smartphone|mobile)\b', full_text):
        return "phone"
    if re.search(r'\b(laptop|notebook)\b', full_text):
        return "laptop"
    if re.search(r'\b(soap|face\s*wash|shampoo)\b', full_text):
        return "personal_care"
    if re.search(r'\b(shoes?|sneakers?)\b', full_text):
        return "shoes"
    if re.search(r'\b(clothing|shirt|saree|dress)\b', full_text):
        return "clothing"
    if re.search(r'\b(food|grocery)\b', full_text):
        return "grocery"
    if re.search(r'\b(kitchen)\b', full_text):
        return "kitchen"
    if re.search(r'\b(bag|backpack)\b', full_text):
        return "bags"

    return "other"
