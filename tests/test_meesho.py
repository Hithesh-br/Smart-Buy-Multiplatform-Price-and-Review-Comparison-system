"""
tests/test_meesho.py
====================
Health and pipeline verification test for Meesho data pipeline.
Tests:
1. Meesho search URL generation
2. API availability & configuration
3. Playwright launch & Chromium setup
4. Search page loading
5. Product discovery
6. Product extraction
7. Normalization
8. Validation
9. Matching & Variant awareness
10. Specification extraction
"""

import sys
import os
import urllib.parse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
except Exception:
    pass

from services.meesho_api_client import MeeshoAPIClient
from services.meesho_adapter import normalize_meesho_product, extract_title_from_slug
from search.meesho_service import search_meesho
from search.matching_service import is_product_relevant, calculate_product_match_score, extract_normalized_specs
from search.category_detector import detect_category


def run_meesho_health_test(query: str = "hp laptop charger"):
    print("\n" + "=" * 60)
    print(f"MEESHO HEALTH TEST: '{query}'")
    print("=" * 60)

    # 1. Search URL generation
    encoded = urllib.parse.quote(query)
    search_url = f"https://www.meesho.com/search?q={encoded}"
    print(f"[1] Search URL Generated: {search_url}")
    assert search_url.startswith("https://www.meesho.com/search?q=")

    # 2. API Availability Check
    api_client = MeeshoAPIClient()
    api_status = "CONFIGURED" if api_client.is_configured() else "NOT CONFIGURED (Using Playwright Fallback)"
    print(f"[2] API Status: {api_status}")

    # 3. Slug extraction verification
    test_slug_url = "https://www.meesho.com/exetech-65w-laptop-charger-adapter-compatible-forhp-195v-334a-45mm-blue-pin-slim-pin/p/hmsq5h"
    slug_title = extract_title_from_slug(test_slug_url)
    print(f"[3] URL Slug Enrichment Verification: '{slug_title}'")
    assert "HP" in slug_title or "Exetech" in slug_title

    # 4 & 5. Pipeline Search Execution
    print(f"QUERY: {query}")
    print(f"API: {'SUCCESS' if api_client.is_configured() else 'FAILED / NOT CONFIGURED'}")

    products, status, error_msg = search_meesho(query, limit=10)
    print(f"PLAYWRIGHT: {'SUCCESS' if products else 'FAILED'}")
    print(f"PRODUCTS FOUND: {len(products)}")

    # 6 & 7. Normalization & Validation Check
    valid_count = 0
    for p in products:
        # Check canonical schema keys
        if (p.get("platform") == "meesho" and 
            p.get("title") and 
            (p.get("price_num") or 0) > 0 and 
            p.get("url")):
            valid_count += 1

    print(f"VALID PRODUCTS: {valid_count}")

    # 8 & 9. Relevance & Matching Verification
    matched_count = 0
    for p in products:
        rel, score, reason = is_product_relevant(p, query)
        if rel:
            matched_count += 1
            t_str = str(p.get('title') or '')
            print(f"   -> MATCHED: '{t_str[:60]}' | Price: {p.get('price') or p.get('price_str')}")

    print(f"MATCHED PRODUCTS: {matched_count}")

    # 10. Specification Extraction Verification
    if products:
        specs = extract_normalized_specs(products[0])
        print(f"[10] Sample Normalized Specs: {list(specs.keys())[:8]}")
        assert "Product Name" in specs
        assert "Price" in specs
        assert "Buy Link" in specs

    # Test false match prevention (e.g. phone case should NOT match charger)
    case_item = {
        "platform": "meesho",
        "title": "Vivo T4 Lite 5G Back Cover Case",
        "price_num": 199,
        "url": "https://www.meesho.com/test-case/p/123"
    }
    rel, score, reason = is_product_relevant(case_item, "vivo t4 pro charger")
    print(f"\n[Security Check] 'Vivo T4 Lite Case' vs 'vivo t4 pro charger': Relevant={rel} (Reason: {reason})")
    assert not rel, "Phone case must be rejected for charger search!"

    print("\nALL MEESHO HEALTH CHECKS COMPLETED SUCCESSFULLY.\n")


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "hp laptop charger"
    run_meesho_health_test(q)
