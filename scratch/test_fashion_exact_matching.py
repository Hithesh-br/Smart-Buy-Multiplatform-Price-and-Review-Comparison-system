"""
test_fashion_exact_matching.py
==============================
Test suite for Category-Aware Exact Matching (Fashion, Shoes, Clothing & Electronics).
"""

import sys, os, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Known fashion brands
FASHION_BRANDS = {
    'nike', 'adidas', 'puma', 'reebok', 'under armour', 'levis', "levi's", 'zara',
    'h&m', 'biba', 'fabindia', 'manyavar', 'peter england', 'allen solly', 'van heusen',
    'us polo', 'u.s. polo', 'sparkx', 'bata', 'woodland', 'campus', 'red tape'
}

COLOR_MAP = {
    'black': 'black', 'jet black': 'black', 'black/black': 'black', 'pitch black': 'black',
    'white': 'white', 'off-white': 'white', 'off white': 'white',
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

def extract_gender(text: str) -> str:
    t = text.lower()
    if re.search(r'\b(women|womens|women\'s|ladies|lady|female|girl|girls)\b', t):
        return 'women'
    if re.search(r'\b(men|mens|men\'s|man|male|boy|boys|gent|gents)\b', t):
        return 'men'
    if 'unisex' in t:
        return 'unisex'
    return ''

def extract_color(text: str) -> str:
    t = text.lower()
    for col_key, normalized_color in COLOR_MAP.items():
        if re.search(r'\b' + re.escape(col_key) + r'\b', t):
            return normalized_color
    return ''

def extract_size(text: str) -> str:
    t = text.lower()
    # Shoe size (e.g. size 9, uk 9, us 9, size: 9, size-9)
    m_shoe = re.search(r'\b(?:size|uk|us)\s*[:\-]?\s*(\d{1,2}(?:\.\d)?)\b', t)
    if m_shoe:
        return m_shoe.group(1)
    # Apparel size (xs, s, m, l, xl, xxl, 3xl)
    m_app = re.search(r'\b(xs|s|m|l|xl|xxl|3xl|xxxl)\b', t)
    if m_app:
        return m_app.group(1)
    # Waist size for jeans
    m_waist = re.search(r'\b(\d{2})\s*(?:inch|waist)?\b', t)
    if m_waist and int(m_waist.group(1)) in (28, 30, 32, 34, 36, 38, 40):
        return m_waist.group(1)
    return ''

def extract_fashion_type(text: str) -> str:
    t = text.lower()
    if 'running shoes' in t or 'sports shoes' in t:
        return 'running shoes'
    if 'sneakers' in t:
        return 'sneakers'
    if 'shoes' in t or 'footwear' in t:
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
    t = text.lower()
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
    t = text.lower()
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

def test_fashion():
    print("="*70)
    print("TESTING FASHION & CLOTHING EXACT MATCHING CONSTRAINTS")
    print("="*70)

    # Example 1: Men's black Nike running shoes size 9
    q1 = "Men's black Nike running shoes size 9"
    q1_g = extract_gender(q1)
    q1_c = extract_color(q1)
    q1_s = extract_size(q1)
    q1_t = extract_fashion_type(q1)
    print("Query 1 Extracted:", {"gender": q1_g, "color": q1_c, "size": q1_s, "type": q1_t})
    assert q1_g == 'men'
    assert q1_c == 'black'
    assert q1_s == '9'
    assert q1_t == 'running shoes'

    # Example 2: Women's red cotton kurti
    q2 = "Women's red cotton kurti"
    q2_g = extract_gender(q2)
    q2_c = extract_color(q2)
    q2_m = extract_material(q2)
    q2_t = extract_fashion_type(q2)
    print("\nQuery 2 Extracted:", {"gender": q2_g, "color": q2_c, "material": q2_m, "type": q2_t})
    assert q2_g == 'women'
    assert q2_c == 'red'
    assert q2_m == 'cotton'
    assert q2_t == 'kurti'

    # Example 3: Men's Levi's blue slim fit jeans
    q3 = "Men's Levi's blue slim fit jeans"
    q3_g = extract_gender(q3)
    q3_c = extract_color(q3)
    q3_f = extract_fit(q3)
    q3_t = extract_fashion_type(q3)
    print("\nQuery 3 Extracted:", {"gender": q3_g, "color": q3_c, "fit": q3_f, "type": q3_t})
    assert q3_g == 'men'
    assert q3_c == 'blue'
    assert q3_f == 'slim fit'
    assert q3_t == 'jeans'

    # Example 4: Black Nike hoodie
    q4 = "Black Nike hoodie"
    q4_c = extract_color(q4)
    q4_t = extract_fashion_type(q4)
    print("\nQuery 4 Extracted:", {"color": q4_c, "type": q4_t})
    assert q4_c == 'black'
    assert q4_t == 'hoodie'

    print("\n🎉 ALL FASHION EXTRACTION TEST CASES PASSED 100%!")

if __name__ == "__main__":
    test_fashion()
