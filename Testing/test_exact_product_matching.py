"""
test_exact_product_matching.py
==============================
Verification test script for Exact Product / Model-Level Identity Matching Engine.
"""

import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from search.identity_matcher import (
    extract_product_identity,
    calculate_identity_match,
    group_exact_and_similar_products
)

def run_tests():
    print("=" * 70)
    print("STARTING EXACT PRODUCT IDENTITY MATCHING VERIFICATION")
    print("=" * 70)

    # 1. Query Identity Extraction Test
    q1 = "HP Victus Intel Core 13th Gen"
    ident1 = extract_product_identity(q1)
    print(f"Query 1: '{q1}'")
    print("Extracted Identity:", ident1)
    assert ident1['brand'] == 'hp'
    assert ident1['series'] == 'victus'
    assert ident1['generation'] == '13th gen'
    print("✔ Query 1 identity extraction PASS\n")

    q2 = "HP Victus 15 Intel Core i5 13th Gen 16GB RAM 512GB SSD"
    ident2 = extract_product_identity(q2)
    print(f"Query 2: '{q2}'")
    print("Extracted Identity:", ident2)
    assert ident2['brand'] == 'hp'
    assert ident2['series'] == 'victus'
    assert ident2['model'] == '15'
    assert ident2['processor'] == 'intel core i5'
    assert ident2['ram'] == '16gb'
    assert ident2['storage'] == '512gb'
    print("✔ Query 2 identity extraction PASS\n")

    # 2. Hard Variant Mismatch Guard Tests (CRITICAL ACCURACY RULE)
    # A: Exact Match
    item_exact = {
        "title": "HP Victus 15 Gaming Laptop Intel Core i5 13th Gen (16GB RAM/512GB SSD/RTX 4050)",
        "price": "₹72,999",
        "price_num": 72999
    }
    ident_exact = extract_product_identity(item_exact)
    score_exact, is_match_exact, reason_exact = calculate_identity_match(ident2, ident_exact)
    print("Test Exact Match Candidate:")
    print(f"  Score: {score_exact}% | Is Match: {is_match_exact} | Reason: {reason_exact}")
    assert is_match_exact == True, "Exact candidate failed match!"
    print("✔ Exact Variant match PASS\n")

    # B: RAM Mismatch (8GB vs 16GB)
    item_ram_mismatch = {
        "title": "HP Victus 15 Gaming Laptop Intel Core i5 13th Gen (8GB RAM/512GB SSD/RTX 4050)",
        "price": "₹64,999",
        "price_num": 64999
    }
    ident_ram_mismatch = extract_product_identity(item_ram_mismatch)
    score_ram, is_match_ram, reason_ram = calculate_identity_match(ident2, ident_ram_mismatch)
    print("Test RAM Variant Mismatch Candidate (8GB vs 16GB):")
    print(f"  Score: {score_ram}% | Is Match: {is_match_ram} | Reason: {reason_ram}")
    assert is_match_ram == False, "RAM mismatch candidate incorrectly matched!"
    assert "RAM variant mismatch" in reason_ram
    print("✔ RAM Mismatch Guard PASS\n")

    # C: Storage Mismatch (1TB vs 512GB)
    item_st_mismatch = {
        "title": "HP Victus 15 Gaming Laptop Intel Core i5 13th Gen (16GB RAM/1TB SSD/RTX 4050)",
        "price": "₹78,999",
        "price_num": 78999
    }
    ident_st_mismatch = extract_product_identity(item_st_mismatch)
    score_st, is_match_st, reason_st = calculate_identity_match(ident2, ident_st_mismatch)
    print("Test Storage Variant Mismatch Candidate (1TB vs 512GB):")
    print(f"  Score: {score_st}% | Is Match: {is_match_st} | Reason: {reason_st}")
    assert is_match_st == False, "Storage mismatch candidate incorrectly matched!"
    assert "Storage variant mismatch" in reason_st
    print("✔ Storage Mismatch Guard PASS\n")

    # 3. Grouping & Highlights Test
    raw_results = {
        "Amazon": [item_exact],
        "Flipkart": [
            {
                "title": "HP Victus Intel Core i5 13th Gen - (16 GB/512 GB SSD/Windows 11 Home/6 GB Graphics/NVIDIA GeForce RTX 4050)",
                "price": "₹70,499",
                "price_num": 70499,
                "rating": "4.4",
                "reviews": "1,800"
            }
        ],
        "Meesho": [item_ram_mismatch] # 8GB variant -> should NOT be put in exact match group for Meesho!
    }

    grouped = group_exact_and_similar_products(q2, raw_results)
    print("Grouped Comparison Results:")
    print("  Query Summary:", grouped['query_summary'])
    print("  Amazon Exact Match:", bool(grouped['exact_matches']['Amazon']))
    print("  Flipkart Exact Match:", bool(grouped['exact_matches']['Flipkart']))
    print("  Meesho Exact Match:", bool(grouped['exact_matches']['Meesho']), "(Expected None due to 8GB vs 16GB mismatch)")

    assert grouped['exact_matches']['Amazon'] is not None
    assert grouped['exact_matches']['Flipkart'] is not None
    assert grouped['exact_matches']['Meesho'] is None, "Meesho 8GB variant wrongly grouped into 16GB exact match!"

    print("  Best Price Info:", grouped['best_price_info'])
    print("  Savings Info:", grouped['savings_info'])
    print("  Similar Products Count:", len(grouped['similar_products']))
    assert len(grouped['similar_products']) >= 1

    print("\n" + "=" * 70)
    print("🎉 ALL EXACT PRODUCT IDENTITY MATCHING TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
