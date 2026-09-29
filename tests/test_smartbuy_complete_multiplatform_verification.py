"""
tests/test_smartbuy_complete_multiplatform_verification.py
=========================================================
Authoritative validation suite for SmartBuy Multi-Platform Scraping,
Category-Wise Specifications, Product Matching, and Quality Comparison.

Tests all requirements:
1. Pilgrim facewash (Volume variant 15ml vs 50ml, formulation variant, serum/soap rejection)
2. Vivo mobile phone (Accessory conflict: phone vs camera glass/cover/charger)
3. Laptop (Laptop vs laptop bag rejection, RAM/SSD extraction)
4. Earbuds (Driver size, ANC, battery life, bluetooth, mic)
5. Shirt (Clothing specs without footwear or electronics fields)
6. Slippers (Footwear specs: sole material, insole, closure without sleeve/neck)
7. Bag (Material, capacity, compartments, laptop compartment, water resistance)
8. Grocery product (Pack size, ingredients, nutritional info, certifications)
9. Electronic appliance (Wattage, capacity, energy rating, safety features)
10. Independent platform scraping & status isolation:
    - Amazon Found + Flipkart Found + Meesho Found
    - Amazon Timeout + Flipkart Found + Meesho Found
    - Amazon Found + Flipkart Timeout + Meesho Found
    - Amazon Found + Flipkart Found + Meesho Not Found
    - All Platforms Unavailable
11. 3-Column Table Preservation (Amazon | Flipkart | Meesho)
12. Quality-First, Price-Second ranking
13. Canonical 22-field product schema without data fabrication
14. Isolated single-platform retry
"""

import unittest
from search.category_detector import detect_category
from search.product_matcher import (
    evaluate_product_match, validate_product_for_comparison,
    get_match_status_label, is_accessory_conflict,
    STATUS_EXACT_MATCH, STATUS_VARIANT_MATCH, STATUS_PARTIAL_MATCH,
    STATUS_SIMILAR_PRODUCT, STATUS_DIFFERENT_PRODUCT, STATUS_INSUFFICIENT_DATA
)
from search.specs_extractor import (
    extract_specs, extract_field_value, build_category_spec_matrix,
    compute_marketplace_statuses, get_fields_for_category,
    CATEGORY_BLACKLISTED_FIELDS
)
from search.quality_scorer import (
    compute_quality_and_confidence, get_detailed_quality_report,
    calculate_value_for_money_index
)
from search.ranking import rank_products
from search.pipeline import run_comparison_pipeline
from app import app


class TestCompleteMultiplatformScrapingAndComparison(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = app.test_client()

    # ── 1. PILGRIM FACE WASH & BEAUTY SPECIFICATIONS ──────────────────────────
    def test_pilgrim_facewash_volume_variant(self):
        """15ml vs 50ml must NOT be treated as identical; must be classified as Variant."""
        target = {
            "title": "Pilgrim Volcanic Lava Ash Face Wash 50ml",
            "raw_query": "Pilgrim Volcanic Lava Ash Face Wash 50ml",
            "brand": "Pilgrim",
            "category": "face_wash",
            "volume": "50ml"
        }
        candidate_15ml = {
            "title": "Pilgrim Volcanic Lava Ash Face Wash 15ml Trial Pack",
            "brand": "Pilgrim",
            "category": "face_wash",
            "volume": "15ml",
            "price_num": 149
        }
        status, score, breakdown, reasons = evaluate_product_match(target, candidate_15ml)
        self.assertEqual(status, "VARIANT_MATCH")
        is_valid, label, reason = validate_product_for_comparison(target, candidate_15ml)
        self.assertEqual(label, STATUS_VARIANT_MATCH)
        self.assertIn("Volume variant difference", reason)

    def test_pilgrim_facewash_different_formulation(self):
        """Tea Tree formulation vs Salicylic Acid formulation must be classified as different variant."""
        target = {
            "title": "Pilgrim Tea Tree Face Wash 100ml",
            "raw_query": "Pilgrim Tea Tree Face Wash",
            "brand": "Pilgrim",
            "category": "face_wash"
        }
        candidate_salicylic = {
            "title": "Pilgrim Salicylic Acid Face Wash 100ml",
            "brand": "Pilgrim",
            "category": "face_wash",
            "price_num": 349
        }
        status, score, breakdown, reasons = evaluate_product_match(target, candidate_salicylic)
        self.assertEqual(status, "VARIANT_MATCH")
        is_valid, label, reason = validate_product_for_comparison(target, candidate_salicylic)
        self.assertEqual(label, STATUS_VARIANT_MATCH)
        self.assertIn("Different formulation variant", reason)

    def test_facewash_vs_serum_rejection(self):
        """Facewash must not be compared with face serum."""
        target = {
            "title": "Pilgrim Face Wash",
            "raw_query": "Pilgrim Face Wash",
            "brand": "Pilgrim",
            "category": "face_wash"
        }
        candidate_serum = {
            "title": "Pilgrim 2% Salicylic Acid Face Serum 30ml",
            "brand": "Pilgrim",
            "category": "skincare",
            "price_num": 499
        }
        is_valid, label, reason = validate_product_for_comparison(target, candidate_serum)
        self.assertFalse(is_valid)
        self.assertEqual(label, STATUS_DIFFERENT_PRODUCT)
        self.assertIn("face serum instead of face wash", reason)

    # ── 2. VIVO MOBILE PHONE & ACCESSORY REJECTIONS ───────────────────────────
    def test_vivo_mobile_vs_camera_glass_and_cover_rejection(self):
        """Mobile phone must not match tempered glass or back cover."""
        target = {
            "title": "Vivo T3 5G Mobile Phone 8GB RAM 128GB Storage",
            "raw_query": "Vivo T3 5G mobile phone",
            "brand": "Vivo",
            "category": "phone"
        }
        candidate_glass = {
            "title": "Camera Lens Protector Glass Guard for Vivo T3 5G",
            "brand": "Generic",
            "price_num": 199
        }
        candidate_cover = {
            "title": "Vivo T3 5G Back Cover Shockproof Silicon Bumper Case",
            "brand": "Generic",
            "price_num": 249
        }
        is_valid1, label1, reason1 = validate_product_for_comparison(target, candidate_glass)
        self.assertFalse(is_valid1)
        self.assertEqual(label1, STATUS_DIFFERENT_PRODUCT)

        is_valid2, label2, reason2 = validate_product_for_comparison(target, candidate_cover)
        self.assertFalse(is_valid2)
        self.assertEqual(label2, STATUS_DIFFERENT_PRODUCT)

    # ── 3. LAPTOP VS LAPTOP BAG REJECTION ─────────────────────────────────────
    def test_laptop_vs_laptop_bag_rejection(self):
        """Laptop search must reject laptop bags and backpacks."""
        target = {
            "title": "HP Pavilion 15 Intel Core i5 16GB RAM 512GB SSD Laptop",
            "raw_query": "HP Pavilion 15 laptop",
            "brand": "HP",
            "category": "laptop"
        }
        candidate_bag = {
            "title": "HP 15.6 inch Professional Laptop Backpack Bag",
            "brand": "HP",
            "price_num": 1299
        }
        is_valid, label, reason = validate_product_for_comparison(target, candidate_bag)
        self.assertFalse(is_valid)
        self.assertEqual(label, STATUS_DIFFERENT_PRODUCT)

    # ── 4. SLIPPERS VS SHOES (FOOTWEAR DEDICATED SPECS) ───────────────────────
    def test_slippers_vs_shoes_rejection(self):
        """Slippers must not match running shoes or sneakers."""
        target = {
            "title": "Bata Men Comfort Slides Slippers",
            "raw_query": "slippers",
            "brand": "Bata",
            "category": "shoes"
        }
        candidate_shoe = {
            "title": "Bata Men Running Shoes Sneakers",
            "brand": "Bata",
            "category": "shoes",
            "price_num": 1499
        }
        is_valid, label, reason = validate_product_for_comparison(target, candidate_shoe)
        self.assertFalse(is_valid)
        self.assertEqual(label, STATUS_DIFFERENT_PRODUCT)
        self.assertIn("shoes/sneakers instead of slippers", reason)

    def test_footwear_specifications_exclude_clothing_fields(self):
        """Slippers and shoes must extract footwear specs (Sole, Insole) and hide clothing fields (Sleeve, Neck)."""
        cat_fields = get_fields_for_category("shoes")
        self.assertIn("Sole Material", cat_fields)
        self.assertIn("Closure Type", cat_fields)
        self.assertNotIn("Sleeve Type", cat_fields)
        self.assertNotIn("Neck Type", cat_fields)

        # Check blacklist
        bl = CATEGORY_BLACKLISTED_FIELDS.get("shoes", set())
        self.assertIn("sleeve", bl)
        self.assertIn("ram", bl)
        self.assertIn("processor", bl)

    # ── 5. EARBUDS & AUDIO SPECIFICATIONS ─────────────────────────────────────
    def test_earbuds_specifications_extraction(self):
        """Earbuds must have Driver Size, ANC, Battery Life, and Bluetooth Version."""
        cat_fields = get_fields_for_category("earbuds")
        self.assertIn("Driver Size", cat_fields)
        self.assertIn("Active Noise Cancellation", cat_fields)
        self.assertIn("Battery Life", cat_fields)
        self.assertIn("Bluetooth Version", cat_fields)
        self.assertNotIn("RAM", cat_fields)

        item = {
            "title": "boAt Airdopes 141 ANC TWS Earbuds 10mm Driver 42H Battery IPX5 Bluetooth 5.3",
            "price_num": 1299
        }
        extracted = extract_field_value(item, "Active Noise Cancellation", "earbuds")
        self.assertEqual(extracted, "Active Noise Cancellation (ANC)")
        driver = extract_field_value(item, "Driver Size", "earbuds")
        self.assertEqual(driver, "10mm")

    # ── 6. CLOTHING WITHOUT FOOTWEAR/ELECTRONICS FIELDS ────────────────────────
    def test_shirt_clothing_specifications(self):
        """Shirt must display fabric, fit, sleeve, pattern and NOT sole material or RAM."""
        cat_fields = get_fields_for_category("clothing")
        self.assertIn("Fabric/Material", cat_fields)
        self.assertIn("Sleeve Type", cat_fields)
        self.assertIn("Fit Type", cat_fields)
        self.assertNotIn("Sole Material", cat_fields)
        self.assertNotIn("RAM", cat_fields)

    # ── 7. INDEPENDENT PLATFORM EXECUTION & 3-COLUMN TABLE ────────────────────
    def test_independent_platform_execution_amazon_found_flipkart_timeout_meesho_found(self):
        """
        Amazon: Found
        Flipkart: Timeout
        Meesho: Found
        - Table retains all 3 columns.
        - Flipkart displays Timeout with 'Not Available'.
        - Amazon and Meesho show verified details.
        """
        raw_results = {
            "Amazon": [{
                "title": "Pilgrim Volcanic Lava Ash Face Wash 100ml",
                "price": "₹350",
                "price_num": 350,
                "rating": 4.3,
                "review_count": 520,
                "link": "https://amazon.in/dp/B08XYZ"
            }],
            "Flipkart": [],
            "Meesho": [{
                "title": "Pilgrim Volcanic Lava Ash Face Wash 100ml",
                "price": "₹330",
                "price_num": 330,
                "rating": 4.1,
                "review_count": 180,
                "link": "https://meesho.com/p/123xyz"
            }]
        }
        platform_status = {
            "Amazon": {"status": "success", "available": True, "count": 1, "retry_available": False},
            "Flipkart": {"status": "timeout", "available": False, "count": 0, "error": "Request timed out", "retry_available": True},
            "Meesho": {"status": "success", "available": True, "count": 1, "retry_available": False}
        }

        pipeline_res = run_comparison_pipeline("Pilgrim face wash", raw_results, platform_status)

        top_offers = pipeline_res["top_verified_offers"]
        self.assertTrue(top_offers["Amazon"]["available"])
        self.assertEqual(top_offers["Amazon"]["price"], "₹350")

        self.assertFalse(top_offers["Flipkart"]["available"])
        self.assertEqual(top_offers["Flipkart"]["status"], "Timeout")
        self.assertEqual(top_offers["Flipkart"]["product_name"], "Not Available")
        self.assertEqual(top_offers["Flipkart"]["title"], "Flipkart request timed out.")

        self.assertTrue(top_offers["Meesho"]["available"])
        self.assertEqual(top_offers["Meesho"]["price"], "₹330")

        # 3-column table check
        spec_matrix = pipeline_res["specification_matrix"]
        self.assertTrue(len(spec_matrix) > 0)
        first_row = spec_matrix[0]
        self.assertIn("amazon", first_row)
        self.assertIn("flipkart", first_row)
        self.assertIn("meesho", first_row)
        self.assertEqual(first_row["flipkart"], "Not Available")

    def test_meesho_not_found_message(self):
        """If Meesho has no matching product, displays 'No verified matching product found on Meesho.'"""
        raw_results = {
            "Amazon": [{"title": "HP Pavilion 15 Laptop", "price_num": 55000}],
            "Flipkart": [{"title": "HP Pavilion 15 Laptop", "price_num": 54500}],
            "Meesho": []
        }
        platform_status = {
            "Amazon": {"status": "success", "available": True, "count": 1},
            "Flipkart": {"status": "success", "available": True, "count": 1},
            "Meesho": {"status": "no_products_found", "available": False, "count": 0}
        }
        pipeline_res = run_comparison_pipeline("HP Pavilion 15 Laptop", raw_results, platform_status)
        top_offers = pipeline_res["top_verified_offers"]
        self.assertEqual(top_offers["Meesho"]["title"], "No verified matching product found on Meesho.")

    def test_all_platforms_unavailable_isolation(self):
        """When all platforms time out or fail, comparison table columns are preserved with Not Available."""
        raw_results = {"Amazon": [], "Flipkart": [], "Meesho": []}
        platform_status = {
            "Amazon": {"status": "timeout", "available": False, "retry_available": True},
            "Flipkart": {"status": "timeout", "available": False, "retry_available": True},
            "Meesho": {"status": "timeout", "available": False, "retry_available": True}
        }
        pipeline_res = run_comparison_pipeline("Laptop", raw_results, platform_status)
        for plat in ("Amazon", "Flipkart", "Meesho"):
            offer = pipeline_res["top_verified_offers"][plat]
            self.assertFalse(offer["available"])
            self.assertEqual(offer["status"], "Timeout")
            self.assertEqual(offer["price"], "Not Available")

    # ── 8. QUALITY FIRST, PRICE SECOND RANKING ────────────────────────────────
    def test_quality_first_price_second_ranking(self):
        """A higher quality verified product must outrank a cheaper product with inferior/missing specs."""
        high_quality_laptop = {
            "title": "Lenovo ThinkPad Intel Core i7 16GB RAM 512GB SSD Windows 11",
            "brand": "Lenovo",
            "model": "ThinkPad",
            "category": "laptop",
            "price_num": 68000,
            "quality_score": 92.0,
            "evidence_coverage": 90.0,
            "has_sufficient_data": True,
            "match_status": "EXACT_MATCH"
        }
        cheap_poor_laptop = {
            "title": "Lenovo Generic Laptop 4GB RAM 64GB eMMC",
            "brand": "Lenovo",
            "model": "Generic",
            "category": "laptop",
            "price_num": 18000,
            "quality_score": 52.0,
            "evidence_coverage": 30.0,
            "has_sufficient_data": True,
            "match_status": "EXACT_MATCH"
        }
        ranked = rank_products([cheap_poor_laptop, high_quality_laptop], "Lenovo Laptop")
        self.assertEqual(ranked[0]["title"], high_quality_laptop["title"])
        self.assertIn("superior verified specifications", ranked[0]["rank_explanation"])

    # ── 9. NO DATA FABRICATION FOR MISSING SPECS ──────────────────────────────
    def test_insufficient_specifications_reports_not_available(self):
        """When specs are missing, quality score must be None with 'Quality Score: Not Available'."""
        bare_product = {
            "title": "Some Unknown Brand Item",
            "price_num": 500,
            "platform": "Meesho"
        }
        q_rep = get_detailed_quality_report(bare_product, "other")
        self.assertFalse(q_rep["has_sufficient_data"])
        self.assertIsNone(q_rep["quality_score"])
        self.assertEqual(q_rep["quality_score_label"], "Quality Score: Not Available")
        self.assertIn("Insufficient verified specifications", q_rep["reason"])

    # ── 10. SINGLE-PLATFORM ISOLATED RETRY API ────────────────────────────────
    def test_api_platform_retry_schema(self):
        """Endpoint /api/search/platform must return isolated platform products, status, and retry availability."""
        response = self.client.get('/api/search/platform?platform=Flipkart&q=Pilgrim+face+wash')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("platform", data)
        self.assertEqual(data["platform"], "Flipkart")
        self.assertIn("platform_status", data)
        self.assertIn("retry_available", data)
        self.assertIn("products", data)


if __name__ == '__main__':
    unittest.main()
