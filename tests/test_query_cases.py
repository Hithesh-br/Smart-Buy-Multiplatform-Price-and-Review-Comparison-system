"""
tests/test_query_cases.py
=========================
Verifies category detection and relevance/variant-aware matching across
the 15 canonical test queries requested by user:
- iphone 15
- vivo t4 pro charger
- hp laptop charger
- wireless earbuds
- men shirt
- women saree
- school bag
- face wash
- lipstick
- shampoo
- running shoes
- chocolate
- rice 5kg
- coffee
- kitchen storage box
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
except Exception:
    pass

from search.category_detector import detect_category
from search.matching_service import is_product_relevant, calculate_product_match_score

TEST_CASES = [
    ("iphone 15", "phone", "Apple iPhone 15 128GB Black", "Apple iPhone 14 128GB"),
    ("vivo t4 pro charger", "charger", "Vivo 44W Fast Charger Adapter for Vivo T4 Pro", "Vivo T4 Lite 5G Back Cover Case"),
    ("hp laptop charger", "charger", "HP 65W Blue Pin Laptop Charger Adapter", "HP Pavilion 15 Gaming Laptop"),
    ("wireless earbuds", "earphones", "boAt Airdopes 141 Bluetooth Wireless Earbuds", "boAt Wired In-Ear Earphones"),
    ("men shirt", "clothing", "Allen Solly Men Regular Fit Cotton Formal Shirt", "Women Floral Print Kurti"),
    ("women saree", "clothing", "Georgette Printed Saree with Blouse Piece", "Men Slim Fit Denim Jeans"),
    ("school bag", "bags", "Skybags 32L Waterproof School Backpack Bag", "Leather Wallet for Men"),
    ("face wash", "face_wash", "Pilgrim Volcanic Lava Ash Face Wash 100ml", "Dettol Bathing Soap Bar"),
    ("lipstick", "beauty", "Maybelline New York Matte Liquid Lipstick", "Dove Shampoo 650ml"),
    ("shampoo", "shampoo", "L'Oreal Paris Total Repair 5 Shampoo 650ml", "Nivea Body Lotion 400ml"),
    ("running shoes", "shoes", "Nike Air Zoom Running Shoes for Men", "Cotton Crew Socks Pack of 3"),
    ("chocolate", "grocery", "Cadbury Dairy Milk Silk Chocolate Bar 150g", "Tata Salt 1kg Pack"),
    ("rice 5kg", "grocery", "India Gate Basmati Rice Rozzana 5kg Bag", "Aashirvaad Atta 10kg"),
    ("coffee", "grocery", "Nescafe Classic Instant Coffee Powder 100g Jar", "Taj Mahal Tea 500g"),
    ("kitchen storage box", "kitchen", "Milton Airtight Modular Kitchen Storage Container Box Set", "Plastic Bathroom Bucket"),
    ("pilgrim face wash", "face_wash", "Pilgrim Volcanic Lava Ash Face Wash with Yugdugu 100ml", "Dettol Bathing Soap Bar"),
    ("vivo charger", "charger", "Vivo 44W Fast Charging Adapter", "Vivo Phone Back Cover Case"),
    ("nike shoes", "shoes", "Nike Revolution 6 Running Shoes for Men", "Leather Formal Belt"),
    ("handbag", "bags", "Lavie Women Betula Medium Tote Handbag", "Stainless Steel Water Bottle"),
    ("bluetooth speaker", "electronics", "boAt Stone 180 5W Portable Bluetooth Speaker", "Wired Desktop Keyboard"),
    ("iphone charger", "charger", "Apple 20W USB-C Power Adapter for iPhone", "iPhone Silicone Back Case"),
    ("rice", "grocery", "Daawat Rozana Gold Basmati Rice 5kg", "Tata Salt 1kg Pack"),
    ("bedsheet", "home", "Story@Home 100% Cotton Double Bedsheet with 2 Pillow Covers", "Ceiling Fan 1200mm"),
]


def run_tests():
    print("=" * 65)
    print(f"RUNNING {len(TEST_CASES)} UNIVERSAL CATEGORY & MATCHING VERIFICATION TESTS")
    print("=" * 65)

    passed = 0
    for query, expected_cat, valid_title, invalid_title in TEST_CASES:
        detected_cat = detect_category(query)
        cat_ok = (detected_cat == expected_cat) or (expected_cat == "grocery" and detected_cat in ("grocery", "food"))

        # Valid item should be relevant
        valid_item = {"title": valid_title, "price_num": 499}
        is_rel_val, score_val, reason_val = is_product_relevant(valid_item, query)

        # Invalid/conflicting item should NOT be accepted as exact relevant match
        invalid_item = {"title": invalid_title, "price_num": 299}
        is_rel_inval, score_inval, reason_inval = is_product_relevant(invalid_item, query)

        status_flag = "PASS" if (cat_ok and is_rel_val and not is_rel_inval) else "CHECK"
        if status_flag == "PASS":
            passed += 1

        print(f"[{status_flag}] Query: '{query}'")
        print(f"       Category: Detected='{detected_cat}' (Expected='{expected_cat}')")
        print(f"       Valid item '{valid_title[:35]}...': Relevant={is_rel_val} ({reason_val})")
        print(f"       Conflicting item '{invalid_title[:35]}...': Relevant={is_rel_inval} ({reason_inval})")
        print("-" * 65)

    print(f"\nRESULTS: {passed}/{len(TEST_CASES)} test cases completely verified.\n")
    assert passed == len(TEST_CASES), f"Expected {len(TEST_CASES)} passed, got {passed}"


def test_query_cases():
    run_tests()


if __name__ == "__main__":
    run_tests()


if __name__ == "__main__":
    run_tests()
