"""
tests/test_category_specs_quality_matching.py
=============================================
Comprehensive test suite validating:
1. Strict Product Matching (accessory rejection, variant detection, pack differences)
2. Category Detection across all 8 categories
3. Category-wise Specification Extraction & Normalization
4. Specification-Grounded Quality Scoring (no fake baseline points, no invented AnTuTu)
5. Quality First, Price Second Ranking Logic
6. Missing Data and Platform Fallback Handling ("Matching product not found on this platform.")
"""

import unittest
from search.product_matcher import (
    validate_product_for_comparison,
    classify_product_relationship,
    is_accessory_conflict,
    get_match_status_label,
    MATCH_EXACT,
    MATCH_VARIANT,
    MATCH_SIMILAR,
    MATCH_REJECT_ACCESSORY,
    MATCH_DIFFERENT
)
from search.specs_extractor import (
    detect_category,
    extract_field_value,
    get_fields_for_category,
    normalize_product_specifications,
    normalize_unit_value,
    build_dynamic_specifications
)
from search.quality_scorer import (
    calculate_specification_quality,
    get_detailed_quality_report,
    calculate_value_for_money_index
)
from search.ranking import rank_products


class TestStrictProductMatching(unittest.TestCase):
    """Test Section 2: Correct Product Matching & Accessory Rejection."""

    def test_mobile_vs_camera_lens_protector_rejection(self):
        """A Vivo X300 FE mobile must not be matched with a camera lens protector."""
        target = {
            "title": "Vivo X300 FE 5G (8GB RAM, 128GB Storage)",
            "brand": "Vivo",
            "category": "mobile",
            "ram": "8 GB",
            "storage": "128 GB"
        }
        candidate = {
            "title": "Tempered Glass Camera Lens Protector for Vivo X300 FE",
            "brand": "Generic",
            "category": "mobile"
        }
        is_valid, label, reason = validate_product_for_comparison(target, candidate)
        self.assertFalse(is_valid, "Lens protector should be rejected when searching for mobile phone")
        self.assertIn("Different Product", label)

    def test_mobile_vs_back_cover_rejection(self):
        """A phone must not match a phone case/cover."""
        self.assertTrue(is_accessory_conflict("Samsung Galaxy S24 Ultra", "Samsung Galaxy S24 Ultra Back Cover Silicon Case"))

    def test_laptop_vs_laptop_bag_rejection(self):
        """A laptop must not be matched with a laptop bag."""
        target = {
            "title": "Lenovo IdeaPad Slim 3 Intel Core i5 12th Gen 15.6 inch Laptop",
            "brand": "Lenovo",
            "category": "laptop"
        }
        candidate = {
            "title": "Lenovo 15.6 inch Laptop Shoulder Bag Backpack",
            "brand": "Lenovo",
            "category": "bags"
        }
        is_valid, label, reason = validate_product_for_comparison(target, candidate)
        self.assertFalse(is_valid, "Laptop bag should be rejected when searching for laptop")
        self.assertIn("Different Product", label)

    def test_mobile_storage_variant_detection(self):
        """A 128 GB mobile must not be treated as identical to a 256 GB version."""
        target = {
            "title": "OnePlus 12R (16GB RAM, 256GB Storage) Cool Blue",
            "brand": "OnePlus",
            "category": "mobile",
            "ram": "16 GB",
            "storage": "256 GB"
        }
        candidate = {
            "title": "OnePlus 12R (8GB RAM, 128GB Storage) Cool Blue",
            "brand": "OnePlus",
            "category": "mobile",
            "ram": "8 GB",
            "storage": "128 GB"
        }
        status, score, breakdown, reasons = classify_product_relationship(target, candidate)
        self.assertEqual(status, MATCH_VARIANT)
        label = get_match_status_label(status)
        self.assertIn(label, ("Partial Match", "Same Product – Different Variant"))

    def test_laptop_ram_variant_detection(self):
        """A 4 GB RAM laptop must not be treated as identical to an 8 GB RAM version."""
        target = {
            "title": "HP 15s AMD Ryzen 3 8GB RAM 512GB SSD Laptop",
            "brand": "HP",
            "category": "laptop",
            "ram": "8 GB"
        }
        candidate = {
            "title": "HP 15s AMD Ryzen 3 4GB RAM 512GB SSD Laptop",
            "brand": "HP",
            "category": "laptop",
            "ram": "4 GB"
        }
        status, score, breakdown, reasons = classify_product_relationship(target, candidate)
        self.assertEqual(status, MATCH_VARIANT)
        self.assertIn(get_match_status_label(status), ("Partial Match", "Same Product – Different Variant"))

    def test_facewash_single_vs_combo_pack(self):
        """A single facewash must not be matched with a combo pack without variant identification."""
        target = {
            "title": "Himalaya Purifying Neem Face Wash 150ml",
            "brand": "Himalaya",
            "category": "beauty",
            "pack_quantity": 1
        }
        candidate = {
            "title": "Himalaya Purifying Neem Face Wash 150ml (Pack of 3 Combo)",
            "brand": "Himalaya",
            "category": "beauty",
            "pack_quantity": 3
        }
        status, score, breakdown, reasons = classify_product_relationship(target, candidate)
        self.assertEqual(status, MATCH_VARIANT)
        self.assertIn(get_match_status_label(status), ("Partial Match", "Same Product – Different Variant"))


class TestCategoryDetectionAndExtraction(unittest.TestCase):
    """Test Section 3: 8 Category Detection & Dynamic Specification Extraction."""

    def test_category_detection_all_8_categories(self):
        categories_to_test = [
            ("Samsung Galaxy S24 Ultra 5G AI Smartphone", ("phone", "smartphone", "mobile")),
            ("ASUS ROG Zephyrus G14 Gaming Laptop AMD Ryzen 9", ("laptop",)),
            ("Levi's Men Slim Fit Cotton Casual Shirt", ("clothing", "fashion")),
            ("Skybags Brat Black Casual Backpack 30L Waterproof", ("bags",)),
            ("Tata Sampann Unpolished Toor Dal 1kg", ("grocery", "food")),
            ("Mamaearth Vitamin C Daily Glow Face Serum 30ml", ("beauty", "skincare")),
            ("LG 7 Kg 5 Star Inverter Fully Automatic Washing Machine", ("appliances", "appliance", "home_appliance", "washing_machine")),
            ("Titan Neo Analog Black Dial Men Watch", ("other", "watch", "watches")),
        ]
        for title, expected_cats in categories_to_test:
            detected = detect_category(title=title)
            self.assertIn(detected, expected_cats, f"Failed detecting {expected_cats} for {title}")

    def test_no_fabricated_antutu_score(self):
        """Do not generate an AnTuTu score when it is not available. Must return None / Not Available."""
        product = {
            "title": "Redmi Note 13 5G (Prism Gold, 8GB RAM, 256GB Storage)",
            "brand": "Redmi",
            "specs": {"ram": "8 GB", "storage": "256 GB"}
        }
        val = extract_field_value(product, "AnTuTu Benchmark Score", "mobile")
        self.assertIsNone(val, "AnTuTu score must not be fabricated when missing from listing")

    def test_specification_normalization_units(self):
        """Test unit normalization (GB, kg, g, ml, cm)."""
        val, num, unit = normalize_unit_value("8GB", "ram")
        self.assertEqual(val, "8 GB")
        self.assertEqual(num, 8.0)
        self.assertEqual(unit, "GB")

        val, num, unit = normalize_unit_value("1000 g", "weight")
        self.assertEqual(num, 1.0)
        self.assertEqual(unit, "kg")

        val, num, unit = normalize_unit_value("500ml", "net_quantity")
        self.assertEqual(num, 500.0)
        self.assertEqual(unit, "ml")

    def test_structured_specification_records(self):
        """Test Section 5: Normalizing specs into structured records."""
        product = {
            "title": "Acer Aspire 5 Intel Core i5 16GB RAM 512GB SSD",
            "brand": "Acer",
            "specifications": {
                "Installed Memory": "16 GB",
                "Internal Storage": "512 GB SSD"
            }
        }
        records = normalize_product_specifications(product, "laptop")
        self.assertIn("ram", records)
        ram_rec = records["ram"]
        self.assertEqual(ram_rec["original_name"], "Installed Memory")
        self.assertEqual(ram_rec["normalized_name"], "ram")
        self.assertEqual(ram_rec["normalized_value"], 16.0)
        self.assertEqual(ram_rec["unit"], "GB")
        self.assertTrue(ram_rec["verified"])


class TestQualityFirstPriceSecond(unittest.TestCase):
    """Test Section 1 & 6: Quality Scoring & Smart Ranking Priorities."""

    def test_quality_score_insufficient_data(self):
        """When specification data is insufficient, quality score must be None with clear reason."""
        sparse_product = {
            "title": "Unknown Generic Phone",
            "price_num": 4999
        }
        q_score, label, evidence, coverage = calculate_specification_quality(sparse_product, "mobile")
        self.assertIsNone(q_score, "Score must be None when specification evidence is insufficient")
        self.assertEqual(label, "Quality Score: Not Available", "Label must be 'Quality Score: Not Available' per spec Section 10")
        self.assertLess(coverage, 25.0)

    def test_quality_evidence_basis_checklist(self):
        """Quality report must return verified and unavailable specifications checklist."""
        prod = {
            "title": "Samsung Galaxy M34 5G (Prism Blue, 6GB RAM, 128GB Storage)",
            "brand": "Samsung",
            "specs": {
                "ram": "6 GB",
                "storage": "128 GB",
                "processor": "Exynos 1280",
                "battery": "6000 mAh"
            },
            "specifications": {
                "Display": "Super AMOLED 120Hz",
                "Rear Camera": "50MP OIS"
            }
        }
        report = get_detailed_quality_report(prod, "mobile")
        self.assertTrue(report["has_sufficient_data"])
        self.assertIsNotNone(report["quality_score"])
        self.assertGreaterEqual(report["evidence_coverage"], 50.0)

        basis = report["quality_basis"]
        verified_items = [b for b in basis if b.startswith("✓")]
        self.assertTrue(any("RAM" in b for b in verified_items), "RAM should be verified in basis")
        self.assertTrue(any("Storage" in b for b in verified_items), "Storage should be verified in basis")
        self.assertTrue(any("Processor" in b for b in verified_items), "Processor should be verified in basis")

    def test_quality_first_ranking_cheaper_weak_product_loses(self):
        """Priority 1: A cheaper product with weak specifications must NOT outrank a superior product."""
        high_spec_laptop = {
            "title": "Dell Inspiron 15 (Intel i7 13th Gen, 16GB RAM, 1TB SSD, RTX 3050)",
            "brand": "Dell",
            "category": "laptop",
            "match_status": "EXACT_MATCH",
            "has_sufficient_data": True,
            "quality_score": 88.0,
            "evidence_coverage": 85.0,
            "rating": 4.5,
            "reviews": 1200,
            "price_num": 75000,
            "price": "₹75,000",
            "availability": "In Stock"
        }
        cheap_weak_laptop = {
            "title": "Dell Inspiron 15 (Intel Celeron, 4GB RAM, 128GB eMMC)",
            "brand": "Dell",
            "category": "laptop",
            "match_status": "EXACT_MATCH",
            "has_sufficient_data": True,
            "quality_score": 42.0,
            "evidence_coverage": 70.0,
            "rating": 3.8,
            "reviews": 150,
            "price_num": 24000,
            "price": "₹24,000",
            "availability": "In Stock"
        }
        ranked = rank_products([cheap_weak_laptop, high_spec_laptop])
        self.assertEqual(ranked[0]["title"], high_spec_laptop["title"],
                         "High-spec laptop must outrank cheap Celeron laptop despite higher price")
        self.assertIn("Ranked #1", ranked[0]["rank_explanation"])
        self.assertTrue(any(exp in ranked[1]["rank_explanation"] for exp in (
            "Lower price, but fewer verified specifications",
            "Lower specification quality score"
        )))


if __name__ == "__main__":
    unittest.main()
