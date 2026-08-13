"""
test_strict_exact_matching_all_cases.py
========================================
Test script verifying strict exact matching logic across Fashion, Shoes, Laptops, and Mobiles.
"""

import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from search.identity_matcher import (
    extract_product_identity,
    calculate_identity_match,
    group_exact_and_similar_products
)

def run_all_tests():
    print("=" * 70)
    print("RUNNING STRICT CATEGORY-AWARE EXACT MATCHING SUITE")
    print("=" * 70)

    # ── CASE 1: Men's black Nike running shoes size 9 ──
    q1 = "Mens black Nike running shoes size 9"
    q1_ident = extract_product_identity(q1)

    t1_exact = {"title": "Nike Men's Revolution 6 Black Running Shoes Size 9 UK", "price": "₹3,495", "price_num": 3495}
    t1_wrong_color = {"title": "Nike Men's Revolution 6 Blue Running Shoes Size 9 UK", "price": "₹3,495", "price_num": 3495}
    t1_wrong_size = {"title": "Nike Men's Revolution 6 Black Running Shoes Size 10 UK", "price": "₹3,495", "price_num": 3495}
    t1_wrong_gender = {"title": "Nike Women's Revolution 6 Black Running Shoes Size 9 UK", "price": "₹3,495", "price_num": 3495}
    t1_wrong_brand = {"title": "Adidas Men's Running Shoes Black Size 9", "price": "₹3,495", "price_num": 3495}

    s1, m1, r1 = calculate_identity_match(q1_ident, extract_product_identity(t1_exact))
    print(f"Case 1 (Exact Match): Score={s1}% | Match={m1} | {r1}")
    assert m1 == True, "Case 1 exact match failed!"

    s1b, m1b, r1b = calculate_identity_match(q1_ident, extract_product_identity(t1_wrong_color))
    print(f"Case 1 (Wrong Color): Score={s1b}% | Match={m1b} | {r1b}")
    assert m1b == False, "Case 1 wrong color was not rejected!"

    s1c, m1c, r1c = calculate_identity_match(q1_ident, extract_product_identity(t1_wrong_size))
    print(f"Case 1 (Wrong Size): Score={s1c}% | Match={m1c} | {r1c}")
    assert m1c == False, "Case 1 wrong size was not rejected!"

    s1d, m1d, r1d = calculate_identity_match(q1_ident, extract_product_identity(t1_wrong_gender))
    print(f"Case 1 (Wrong Gender): Score={s1d}% | Match={m1d} | {r1d}")
    assert m1d == False, "Case 1 wrong gender was not rejected!"

    s1e, m1e, r1e = calculate_identity_match(q1_ident, extract_product_identity(t1_wrong_brand))
    print(f"Case 1 (Wrong Brand): Score={s1e}% | Match={m1e} | {r1e}")
    assert m1e == False, "Case 1 wrong brand was not rejected!"

    # ── CASE 2: Women's red cotton kurti ──
    q2 = "Womens red cotton kurti"
    q2_ident = extract_product_identity(q2)

    t2_exact = {"title": "BIBA Women Red Pure Cotton Printed Straight Kurti", "price": "₹1,299", "price_num": 1299}
    t2_wrong_color = {"title": "BIBA Women Blue Pure Cotton Printed Straight Kurti", "price": "₹1,299", "price_num": 1299}
    t2_wrong_mat = {"title": "BIBA Women Red Polyester Kurti", "price": "₹1,299", "price_num": 1299}

    s2, m2, r2 = calculate_identity_match(q2_ident, extract_product_identity(t2_exact))
    print(f"\nCase 2 (Exact Match): Score={s2}% | Match={m2} | {r2}")
    assert m2 == True, "Case 2 exact match failed!"

    s2b, m2b, r2b = calculate_identity_match(q2_ident, extract_product_identity(t2_wrong_color))
    print(f"Case 2 (Wrong Color): Score={s2b}% | Match={m2b} | {r2b}")
    assert m2b == False, "Case 2 wrong color was not rejected!"

    s2c, m2c, r2c = calculate_identity_match(q2_ident, extract_product_identity(t2_wrong_mat))
    print(f"Case 2 (Wrong Material): Score={s2c}% | Match={m2c} | {r2c}")
    assert m2c == False, "Case 2 wrong material was not rejected!"

    # ── CASE 3: Men's Levi's blue slim fit jeans ──
    q3 = "Mens Levis blue slim fit jeans"
    q3_ident = extract_product_identity(q3)

    t3_exact = {"title": "Levi's Men 511 Slim Fit Blue Denim Jeans", "price": "₹2,499", "price_num": 2499}
    t3_wrong_fit = {"title": "Levi's Men 511 Regular Fit Blue Jeans", "price": "₹2,499", "price_num": 2499}

    s3, m3, r3 = calculate_identity_match(q3_ident, extract_product_identity(t3_exact))
    print(f"\nCase 3 (Exact Match): Score={s3}% | Match={m3} | {r3}")
    assert m3 == True, "Case 3 exact match failed!"

    s3b, m3b, r3b = calculate_identity_match(q3_ident, extract_product_identity(t3_wrong_fit))
    print(f"Case 3 (Wrong Fit): Score={s3b}% | Match={m3b} | {r3b}")
    assert m3b == False, "Case 3 wrong fit was not rejected!"

    # ── CASE 4: Black Nike hoodie ──
    q4 = "Black Nike hoodie"
    q4_ident = extract_product_identity(q4)

    t4_exact = {"title": "Nike Men's Sportswear Club Fleece Black Pullover Hoodie", "price": "₹3,995", "price_num": 3995}
    t4_wrong_type = {"title": "Nike Men's Dri-FIT Black Running T-Shirt", "price": "₹1,995", "price_num": 1995}

    s4, m4, r4 = calculate_identity_match(q4_ident, extract_product_identity(t4_exact))
    print(f"\nCase 4 (Exact Match): Score={s4}% | Match={m4} | {r4}")
    assert m4 == True, "Case 4 exact match failed!"

    s4b, m4b, r4b = calculate_identity_match(q4_ident, extract_product_identity(t4_wrong_type))
    print(f"Case 4 (Wrong Product Type): Score={s4b}% | Match={m4b} | {r4b}")
    assert m4b == False, "Case 4 wrong product type was not rejected!"

    # ── CASE 5: Grouping & Fallback Test ("EXACT PRODUCT NOT FOUND") ──
    raw_results = {
        "Amazon": [t1_exact],
        "Flipkart": [t1_exact],
        "Meesho": [t1_wrong_color] # Meesho has wrong color blue -> should display EXACT PRODUCT NOT FOUND!
    }

    grouped = group_exact_and_similar_products(q1, raw_results)
    print("\n" + "="*70)
    print("GROUPED RESULTS FOR EXPLICIT EXACT MATCH TABLE:")
    print("Amazon Match:", bool(grouped['exact_matches']['Amazon']))
    print("Flipkart Match:", bool(grouped['exact_matches']['Flipkart']))
    print("Meesho Match:", bool(grouped['exact_matches']['Meesho']), "(Expected None -> EXACT PRODUCT NOT FOUND)")

    assert grouped['exact_matches']['Amazon'] is not None
    assert grouped['exact_matches']['Flipkart'] is not None
    assert grouped['exact_matches']['Meesho'] is None, "Meesho wrong color was incorrectly included in exact match!"

    print("\n" + "="*70)
    print("🎉 ALL STRICT CATEGORY-AWARE EXACT MATCHING TESTS PASSED 100%!")
    print("="*70)

if __name__ == "__main__":
    run_all_tests()
