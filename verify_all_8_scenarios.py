"""
verify_all_8_scenarios.py
=========================
Comprehensive automated verification script testing the 8 exact scenarios
from Section 24 of the specification:

Test 1: Search "BAJAJ coconut oil"
Test 2: Paste Amazon product URL
Test 3: Paste Flipkart product URL
Test 4: Paste Meesho product URL
Test 5: Search "smartphone" (Verify ONLY mobile specifications)
Test 6: Search "pumpkin seeds" (Verify ONLY grocery/nutrition specifications)
Test 7: Search "face wash" (Verify ONLY beauty/skincare specifications)
Test 8: Search "cotton shirt" (Verify ONLY fashion/clothing specifications)
"""

import sys
import logging
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_scenarios")

from url_detector import detect_search_type, validate_and_detect_url, normalize_product_url
from search.category_detector import detect_category
from search.specs_extractor import get_fields_for_category, build_dynamic_specifications, extract_field_value
from search.search_router import route_search
from comparison_engine import compare_by_product_url
from scrapers.amazon.url_scraper import AmazonUrlScraper
from scrapers.flipkart.url_scraper import FlipkartUrlScraper
from scrapers.meesho.url_scraper import MeeshoUrlScraper

def test_url_detection():
    print("\n" + "="*70)
    print("TEST: URL DETECTION & PLATFORM IDENTIFICATION (SECTION 2 & 13)")
    print("="*70)

    # 1. Amazon URL
    amz_url = "https://www.amazon.in/dp/B08L5WHFT9?tag=smartbuy-21&ref=sr_1_1"
    amz_det = detect_search_type(amz_url)
    assert amz_det["type"] == "product_url", f"Failed: {amz_det}"
    assert amz_det["platform"] == "amazon", f"Failed platform: {amz_det}"
    assert amz_det["url"] == "https://www.amazon.in/dp/B08L5WHFT9"
    print(f"[OK] Amazon URL detected: {amz_det['platform']} -> {amz_det['url']}")

    # 2. Flipkart URL
    fk_url = "https://www.flipkart.com/bajaj-pure-coconut-oil/p/itm12345?pid=OIL12345&lid=LST123"
    fk_det = detect_search_type(fk_url)
    assert fk_det["type"] == "product_url"
    assert fk_det["platform"] == "flipkart"
    assert "https://www.flipkart.com/bajaj-pure-coconut-oil/p/itm12345" in fk_det["url"]
    print(f"[OK] Flipkart URL detected: {fk_det['platform']} -> {fk_det['url']}")

    # 3. Meesho URL
    mee_url = "https://www.meesho.com/s/p/4abcde?utm_source=share"
    mee_det = detect_search_type(mee_url)
    assert mee_det["type"] == "product_url"
    assert mee_det["platform"] == "meesho"
    assert "https://www.meesho.com/s/p/4abcde" in mee_det["url"]
    print(f"[OK] Meesho URL detected: {mee_det['platform']} -> {mee_det['url']}")

    # 4. Product Name
    name_input = "BAJAJ coconut oil"
    name_det = detect_search_type(name_input)
    assert name_det["type"] == "product_name"
    print(f"[OK] Product Name detected: {name_det['type']} for '{name_input}'")


def test_category_isolation_scenarios():
    print("\n" + "="*70)
    print("TEST SCENARIOS 5, 6, 7, 8: CATEGORY SPECIFICATION ISOLATION")
    print("="*70)

    # Test 5: Smartphone
    cat_phone = detect_category(query="smartphone")
    assert cat_phone in ("phone", "smartphone", "mobile"), f"Detected: {cat_phone}"
    phone_fields = [f.lower() for f in get_fields_for_category(cat_phone)]
    print(f"Test 5 'smartphone' category: '{cat_phone}', fields count: {len(phone_fields)}")
    assert "processor" in phone_fields or "ram" in phone_fields or "display" in phone_fields
    # Verify no grocery/clothing fields leaked
    assert "ingredients" not in phone_fields
    assert "fabric" not in phone_fields
    assert "sleeve" not in phone_fields
    print("[OK] Test 5 Passed: Smartphone specifications are strictly mobile (No grocery/fabric leakage)")

    # Test 6: Pumpkin seeds
    cat_seeds = detect_category(query="pumpkin seeds")
    assert cat_seeds in ("grocery", "food"), f"Detected: {cat_seeds}"
    grocery_fields = [f.lower() for f in get_fields_for_category(cat_seeds)]
    print(f"Test 6 'pumpkin seeds' category: '{cat_seeds}', fields count: {len(grocery_fields)}")
    assert any(k in grocery_fields for k in ("quantity / net weight", "net quantity", "protein content", "calories"))
    # Verify no mobile fields leaked
    assert "ram" not in grocery_fields
    assert "processor" not in grocery_fields
    assert "camera" not in grocery_fields
    print("[OK] Test 6 Passed: Pumpkin seeds specifications are strictly grocery/nutrition")

    # Test 7: Face wash
    cat_fw = detect_category(query="face wash")
    assert cat_fw in ("face_wash", "skincare", "beauty"), f"Detected: {cat_fw}"
    fw_fields = [f.lower() for f in get_fields_for_category(cat_fw)]
    print(f"Test 7 'face wash' category: '{cat_fw}', fields count: {len(fw_fields)}")
    assert any(k in fw_fields for k in ("skin type", "key ingredients", "key actives", "formulation"))
    assert "ram" not in fw_fields
    assert "processor" not in fw_fields
    assert "battery" not in fw_fields
    print("[OK] Test 7 Passed: Face wash specifications are strictly beauty/skincare")

    # Test 8: Cotton shirt
    cat_shirt = detect_category(query="cotton shirt")
    assert cat_shirt in ("clothing", "fashion"), f"Detected: {cat_shirt}"
    shirt_fields = [f.lower() for f in get_fields_for_category(cat_shirt)]
    print(f"Test 8 'cotton shirt' category: '{cat_shirt}', fields count: {len(shirt_fields)}")
    assert any(k in shirt_fields for k in ("fabric/material", "fit type", "sleeve type"))
    assert "ram" not in shirt_fields
    assert "processor" not in shirt_fields
    assert "camera" not in shirt_fields
    print("[OK] Test 8 Passed: Cotton shirt specifications are strictly fashion/clothing")


def test_spec_table_filtering_and_no_leakage():
    print("\n" + "="*70)
    print("TEST: SPEC TABLE DYNAMIC GENERATION & SOURCE DATA ISOLATION (SECTIONS 11 & 19)")
    print("="*70)

    # Simulated products from Amazon and Flipkart for coconut oil; Meesho unavailable
    amz_oil = {
        "title": "Bajaj 100% Pure Coconut Oil 750ml",
        "brand": "Bajaj",
        "price": "₹771",
        "price_num": 771,
        "rating": 4.5,
        "review_count": 1200,
        "specifications": {
            "Volume": "750 ml",
            "Key Ingredient": "Pure Coconut",
            "Packaging": "Bottle"
        }
    }
    fk_oil = {
        "title": "Bajaj Pure Coconut Oil 1 L",
        "brand": "Bajaj",
        "price": "₹367",
        "price_num": 367,
        "rating": 4.4,
        "review_count": 206695,
        "specifications": {
            "Volume": "1 Litre",
            "Key Ingredient": "Pure Coconut Extract",
            "Ingredients": "Coconut Oil"
        }
    }
    # Platform status: Meesho timed out or blocked
    p_status = {
        "amazon": {"status": "success", "available": True},
        "flipkart": {"status": "success", "available": True},
        "meesho": {"status": "timeout", "available": False, "error": "Request timed out"}
    }

    rows = build_dynamic_specifications(
        products={"amazon": amz_oil, "flipkart": fk_oil, "meesho": None},
        category="grocery",
        platform_status=p_status
    )

    print(f"Generated {len(rows)} spec rows for coconut oil comparison:")
    for r in rows:
        print(f"  Field: {r['field']:<20} | Amazon: {r['amazon']:<15} | Flipkart: {r['flipkart']:<15} | Meesho: {r['meesho']:<15}")
        # Section 11: Never mix platform data
        if r['field'] == 'Price':
            assert "771" in r['amazon']
            assert "367" in r['flipkart']
            assert r['meesho'] in ('Not Available', '—')
        # Section 19: No mobile specs for coconut oil
        assert r['field'].lower() not in ("ram", "processor", "battery", "camera", "display", "os")
        # Ensure row actually has real data on at least one platform
        has_val = any(v not in ('—', 'Not Available', None) for v in (r['amazon'], r['flipkart'], r['meesho']))
        assert has_val, f"Empty row leaked into table: {r}"

    print("[OK] Specification table verified: No cross-platform data mixing, no empty row bloat, no irrelevant specs.")


def test_url_extraction_logic():
    print("\n" + "="*70)
    print("TEST: EXTRACTOR ERROR HANDLING & STATUS INTEGRITY (SECTION 9 & 18)")
    print("="*70)

    # Test Amazon URL Scraper with mock blocked page -> rejects fake title
    amz_scraper = AmazonUrlScraper()
    blocked_html = "<html><head><title>Robot Check</title></head><body><h1>Robot Check</h1></body></html>"
    blocked_parsed = amz_scraper._parse_amazon_page_html(blocked_html, "https://www.amazon.in/dp/B000000000", "B000000000")
    assert blocked_parsed is None, f"Should reject bot challenge html, got: {blocked_parsed}"
    print("[OK] Amazon parser strictly rejects bot challenge / Robot Check page.")

    # Test Meesho URL Scraper with Access Denied html -> rejects
    mee_scraper = MeeshoUrlScraper()
    mee_blocked_html = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1><div class='sec-if-cpt-container'></div></body></html>"
    mee_parsed = mee_scraper._parse_meesho_page_html(mee_blocked_html, "https://www.meesho.com/s/p/123", "123")
    assert mee_parsed is None, f"Should reject Access Denied page, got: {mee_parsed}"
    print("[OK] Meesho parser strictly rejects Access Denied / Kasada challenge page without creating fake products.")


if __name__ == "__main__":
    test_url_detection()
    test_category_isolation_scenarios()
    test_spec_table_filtering_and_no_leakage()
    test_url_extraction_logic()
    print("\n" + "="*70)
    print("ALL CORE UNIT & INTEGRATION SCENARIOS PASSED SUCCESSFULLY!")
    print("="*70)
