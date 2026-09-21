"""
test_profile_search_activity_pipeline.py
=========================================
Comprehensive verification test for Profile Search Activity Data Pipeline:
- Category Detection (detect_category)
- Accessory Exclusion in Best Deal Calculation (calculate_best_deal)
- History Normalization for Profile (prepare_search_history_for_profile)
- Template Rendering & Search Again URL generation
"""

import sys
import os
import jinja2

sys.path.insert(0, '.')

from search.specs_extractor import detect_category
from ai_compare import calculate_best_deal
from database import prepare_search_history_for_profile

print("==================================================================")
print("TEST 1: CATEGORY DETECTION (detect_category)")
print("==================================================================\n")

test_cases_category = [
    ("vivo t4 5g", "Mobiles"),
    ("HP Victus laptop", "Laptops"),
    ("Philips hair dryer", "Personal Care & Beauty"),
    ("Ghar soap", "Personal Care & Beauty"),
    ("Nike shoes", "Fashion & Footwear"),
    ("headphones", "Audio"),
    ("pressure cooker", "Kitchenware"),
    ("refrigerator", "TVs & Appliances"),
    ("MANKIND Acne Star Face Wash", "Personal Care & Beauty"),
    ("random unknown item", "General")
]

for query, expected_cat in test_cases_category:
    res_cat = detect_category(query)
    print(f"  Query: '{query}' -> Category: '{res_cat}' (Expected: '{expected_cat}')")
    assert res_cat == expected_cat, f"Category mismatch for '{query}': got '{res_cat}', expected '{expected_cat}'"

print("  Result: PASS [OK]\n")


print("==================================================================")
print("TEST 2: PRODUCT MATCHING & ACCESSORY EXCLUSION (calculate_best_deal)")
print("==================================================================\n")

# Example from prompt:
# User searches "vivo t4 5g"
# Amazon: Vivo T4 5G -> ₹17,890
# Flipkart: Vivo T4 5G -> ₹18,999
# Meesho: Vivo T4 5G Back Cover Soft Silicone -> ₹299 (Accessory!)
prods_vivo = {
    "Amazon": [{"title": "Vivo T4 5G 8GB RAM 128GB Storage", "price_num": 17890, "price": "₹17,890"}],
    "Flipkart": [{"title": "Vivo T4 5G (Steel Blue, 128 GB)", "price_num": 18999, "price": "₹18,999"}],
    "Meesho": [{"title": "Vivo T4 5G Back Cover Soft Silicone Case", "price_num": 299, "price": "₹299"}]
}

deal_vivo = calculate_best_deal(prods_vivo, query="vivo t4 5g")
print("Vivo T4 5G Search Results Comparison:")
print(f"  Best Platform: {deal_vivo['best_platform']} (Expected: Amazon)")
print(f"  Best Price:    Rs.{deal_vivo['best_price']} (Expected: 17890)")

assert deal_vivo['best_platform'] == "Amazon", f"Expected Amazon, got {deal_vivo['best_platform']}"
assert deal_vivo['best_price'] == 17890, f"Expected 17890, got {deal_vivo['best_price']}"
print("  Result: PASS [OK]\n")

# Example 2 from prompt:
# User searches "MANKIND Acne Star Face Wash"
# Amazon: ₹110
# Flipkart: ₹95
# Meesho: ₹105
prods_facewash = {
    "Amazon": [{"title": "MANKIND Acne Star Face Wash 100g", "price_num": 110}],
    "Flipkart": [{"title": "MANKIND Acne Star Face Wash 100g", "price_num": 95}],
    "Meesho": [{"title": "MANKIND Acne Star Face Wash 100g", "price_num": 105}]
}
deal_facewash = calculate_best_deal(prods_facewash, query="MANKIND Acne Star Face Wash")
print("Face Wash Search Results Comparison:")
print(f"  Best Platform: {deal_facewash['best_platform']} (Expected: Flipkart)")
print(f"  Best Price:    Rs.{deal_facewash['best_price']} (Expected: 95)")

assert deal_facewash['best_platform'] == "Flipkart", f"Expected Flipkart, got {deal_facewash['best_platform']}"
assert deal_facewash['best_price'] == 95, f"Expected 95, got {deal_facewash['best_price']}"
print("  Result: PASS [OK]\n")


print("==================================================================")
print("TEST 3: BACKEND PROFILE HISTORY PREPARATION (prepare_search_history_for_profile)")
print("==================================================================\n")

raw_history = [
    {
        "_id": "507f1f77bcf86cd799439011",
        "search_query": "vivo t4 5g",
        "category": "",
        "best_platform": "Amazon",
        "best_price": 17890,
        "searched_at": "2026-09-01T15:39:00Z"
    },
    {
        "_id": "507f1f77bcf86cd799439012",
        "search_query": "MANKIND Acne Star Face Wash",
        "category": "General",
        "best_platform": "Flipkart",
        "best_price": "₹95",
        "best_deal": {"platform": "Flipkart", "price": 95, "title": "MANKIND Acne Star Face Wash"},
        "platform_results": {
            "amazon": {"price": 110, "available": True},
            "flipkart": {"price": 95, "available": True},
            "meesho": {"price": 105, "available": True}
        },
        "searched_at": "2026-09-01T15:23:00Z"
    }
]

prepared = prepare_search_history_for_profile(raw_history)
print(f"Prepared History Record 1: {prepared[0]}")
assert prepared[0]['query'] == "vivo t4 5g"
assert prepared[0]['category'] == "Mobiles"
assert prepared[0]['best_platform'] == "Amazon"
assert prepared[0]['best_price'] == 17890
assert prepared[0]['searched_at'] == "2026-09-01 15:39"

print(f"Prepared History Record 2 (Canonical Stored): {prepared[1]}")
assert prepared[1]['query'] == "MANKIND Acne Star Face Wash"
assert prepared[1]['category'] == "Personal Care & Beauty"
assert prepared[1]['best_platform'] == "Flipkart"
assert prepared[1]['best_price'] == 95
assert prepared[1]['searched_at'] == "2026-09-01 15:23"
print("  Result: PASS [OK]\n")


print("==================================================================")
print("TEST 4: JINJA TEMPLATE RENDERING (profile.html)")
print("==================================================================\n")

templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))
tmpl = env.get_template('profile.html')

context = {
    "current_user": {"name": "Demo User", "email": "demo@example.com", "is_admin": False},
    "stats": {
        "name": "Demo User",
        "email": "demo@example.com",
        "total_searches": len(prepared),
        "recent_searches": prepared,
        "selected_products": []
    },
    "selected_product": None,
    "get_flashed_messages": lambda **kwargs: [],
    "url_for": lambda endpoint, **kwargs: f"/{endpoint}?q={kwargs.get('q', '')}"
}

rendered_html = tmpl.render(**context)
assert "vivo t4 5g" in rendered_html
assert "MANKIND Acne Star Face Wash" in rendered_html
assert "Mobiles" in rendered_html
assert "Personal Care &amp; Beauty" in rendered_html or "Personal Care" in rendered_html
assert "Amazon" in rendered_html
assert "Flipkart" in rendered_html
assert "₹17,890" in rendered_html
assert "₹95" in rendered_html
assert "SmartBuy" not in rendered_html or "SmartBuy Profile" in rendered_html  # SmartBuy not in platform badges
print("  profile.html rendered successfully with 100% prepared history data!")
print("  Result: PASS [OK]\n")

print("==================================================================")
print("ALL 4 PIPELINE VERIFICATION TESTS PASSED SUCCESSFULLY!")
print("==================================================================")
