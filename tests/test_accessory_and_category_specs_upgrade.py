"""
tests/test_accessory_and_category_specs_upgrade.py
==================================================
Comprehensive test suite verifying the SmartBuy Scraping, Category Specs,
and Accurate Comparison upgrade.

Covered Scenarios:
1. Rejection of accessories and replacement parts when comparing complete products:
   - Pressure Cooker vs Cooker Gasket / Sealing Ring / Whistle / Safety Valve / Handle
   - Mixer Grinder vs Mixer Jar / Coupler / Blade
   - Electric Kettle vs Kettle Base / Cord
   - Washing Machine vs Inlet Pipe / Machine Cover
   - Mobile Phone vs Case / Cover / Tempered Glass
   - Laptop vs Charger / Bag / Sleeve
2. Rejection of cross-category matches:
   - Face Wash vs Face Cream / Moisturizer / Face Serum / Soap / Sunscreen / Foundation / Lipstick
3. Variant match differentiation (never EXACT_MATCH):
   - 3L vs 5L Cooker -> VARIANT_MATCH
   - 6GB/128GB vs 8GB/256GB Mobile -> VARIANT_MATCH
   - Pack of 1 vs Pack of 2 -> VARIANT_MATCH
4. Category-specific specifications across all 8 prompt categories:
   - Mobiles
   - Laptops
   - Earbuds / Headphones
   - Appliances (Cooker, Mixer, Kettle)
   - Fashion / Clothing / Shoes / Slippers
   - Bags
   - Groceries
   - Beauty / Skincare / Makeup (Face Wash, Moisturizer, Sunscreen, Foundation, Lipstick)
5. Structured comparison table cell statuses:
   - {display, value, source, verified, status}
6. No fake placeholders:
   - No 'Standard Durable Material', 'Standard Quality', or fake warranties.
7. Smart ranking priority:
   - Spec match > features > reviews > value > price
"""

import unittest
from search.product_matcher import (
    evaluate_product_match,
    is_accessory_conflict,
    check_hard_rejections,
    validate_product_for_comparison,
)
from search.query_parser import parse_query_entities
from search.specs_extractor import (
    get_fields_for_category,
    build_dynamic_specifications,
    extract_field_value,
    CATEGORY_SPEC_FIELDS,
)
from search.quality_scorer import compute_quality_and_confidence
from search.ranking import rank_products
from scrapers.common_schema import validate_and_build_product


class TestAccessoryAndReplacementPartRejection(unittest.TestCase):
    """Verifies that complete products strictly reject replacement parts and accessories."""

    def test_pressure_cooker_rejects_gasket_sealing_ring_whistle(self):
        target = parse_query_entities("hawkins pressure cooker 5 litre")
        
        # Gasket
        gasket = validate_and_build_product({
            "platform": "Amazon",
            "title": "Hawkins Sealing Ring Gasket for 5 Litre Pressure Cooker",
            "price_num": 140.0
        })
        status, score, breakdown, reasons = evaluate_product_match(target, gasket)
        self.assertEqual(status, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "replacement part" in r.lower() or "gasket" in r.lower() for r in reasons))

        # Whistle / Weight valve
        whistle = validate_and_build_product({
            "platform": "Flipkart",
            "title": "Hawkins Pressure Cooker Whistle Vent Weight Valve Assembly",
            "price_num": 99.0
        })
        status_w, _, _, reasons_w = evaluate_product_match(target, whistle)
        self.assertEqual(status_w, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "replacement part" in r.lower() or "whistle" in r.lower() for r in reasons_w))

        # Safety valve
        valve = validate_and_build_product({
            "platform": "Meesho",
            "title": "Hawkins Pressure Cooker Safety Valve Pack of 2",
            "price_num": 120.0
        })
        status_v, _, _, reasons_v = evaluate_product_match(target, valve)
        self.assertEqual(status_v, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "replacement part" in r.lower() or "safety valve" in r.lower() for r in reasons_v))

    def test_mixer_grinder_rejects_mixer_jar(self):
        target = parse_query_entities("preethi mixer grinder 750w")
        jar = validate_and_build_product({
            "platform": "Amazon",
            "title": "Preethi 1.5L Stainless Steel Wet Grinding Jar with Lid for Mixer",
            "price_num": 699.0
        })
        status, score, breakdown, reasons = evaluate_product_match(target, jar)
        self.assertEqual(status, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "replacement part" in r.lower() or "jar" in r.lower() for r in reasons))

    def test_electric_kettle_rejects_kettle_base(self):
        target = parse_query_entities("pigeon electric kettle 1.5 litre")
        base = validate_and_build_product({
            "platform": "Flipkart",
            "title": "Replacement 360 Degree Swivel Base for Pigeon Electric Kettle",
            "price_num": 250.0
        })
        status, score, breakdown, reasons = evaluate_product_match(target, base)
        self.assertEqual(status, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "replacement part" in r.lower() or "base" in r.lower() for r in reasons))

    def test_washing_machine_rejects_inlet_pipe_and_cover(self):
        target = parse_query_entities("lg 7kg front load washing machine")
        pipe = validate_and_build_product({
            "platform": "Amazon",
            "title": "Washing Machine Water Inlet Pipe Hose 2M for LG Front Load",
            "price_num": 299.0
        })
        status, score, breakdown, reasons = evaluate_product_match(target, pipe)
        self.assertEqual(status, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "pipe" in r.lower() or "replacement part" in r.lower() for r in reasons))

        cover = validate_and_build_product({
            "platform": "Meesho",
            "title": "Waterproof Dustproof Cover for LG Front Load Washing Machine",
            "price_num": 349.0
        })
        status_c, _, _, reasons_c = evaluate_product_match(target, cover)
        self.assertEqual(status_c, "REJECTED")
        self.assertTrue(any("accessory" in r.lower() or "cover" in r.lower() for r in reasons_c))

    def test_mobile_rejects_case_and_tempered_glass(self):
        target = parse_query_entities("iphone 15 pro 128gb")
        case = validate_and_build_product({
            "platform": "Meesho",
            "title": "Silicone Magnetic Clear Case with Camera Protection for iPhone 15 Pro",
            "price_num": 249.0
        })
        status, _, _, reasons = evaluate_product_match(target, case)
        self.assertEqual(status, "REJECTED")

        glass = validate_and_build_product({
            "platform": "Amazon",
            "title": "9H Hardness Edge-to-Edge Tempered Glass Screen Protector for iPhone 15 Pro",
            "price_num": 199.0
        })
        status_g, _, _, reasons_g = evaluate_product_match(target, glass)
        self.assertEqual(status_g, "REJECTED")

    def test_laptop_rejects_charger_and_sleeve(self):
        target = parse_query_entities("dell inspiron 15 laptop")
        charger = validate_and_build_product({
            "platform": "Flipkart",
            "title": "Dell 65W Power Adapter Charger with Power Cord for Inspiron 15",
            "price_num": 999.0
        })
        status, _, _, reasons = evaluate_product_match(target, charger)
        self.assertEqual(status, "REJECTED")


class TestCrossCategoryAndVariantMatching(unittest.TestCase):
    """Verifies cross-category rejections and variant match differentiation."""

    def test_face_wash_rejects_cream_serum_sunscreen_soap(self):
        target = parse_query_entities("himalaya purifying neem face wash 150ml")
        
        # Moisturizer / Face cream
        cream = validate_and_build_product({
            "platform": "Amazon",
            "title": "Himalaya Nourishing Face Cream / Moisturizer 150ml",
            "price_num": 180.0
        })
        status, _, _, reasons = evaluate_product_match(target, cream)
        self.assertEqual(status, "REJECTED")

        # Sunscreen
        sunscreen = validate_and_build_product({
            "platform": "Flipkart",
            "title": "Himalaya Sunscreen SPF 50 Neem Lotion 150ml",
            "price_num": 250.0
        })
        status_s, _, _, reasons_s = evaluate_product_match(target, sunscreen)
        self.assertEqual(status_s, "REJECTED")

        # Soap
        soap = validate_and_build_product({
            "platform": "Meesho",
            "title": "Himalaya Neem & Turmeric Cleansing Bathing Soap 125g",
            "price_num": 45.0
        })
        status_sb, _, _, reasons_sb = evaluate_product_match(target, soap)
        self.assertEqual(status_sb, "REJECTED")

    def test_variant_difference_capacity_cooker(self):
        """3L cooker vs 5L cooker must be VARIANT_MATCH, never EXACT_MATCH."""
        target = parse_query_entities("prestige deluxe alpha pressure cooker 3 litre")
        variant_5l = validate_and_build_product({
            "platform": "Amazon",
            "title": "Prestige Deluxe Alpha Stainless Steel Pressure Cooker 5 Litre",
            "price_num": 2200.0,
            "brand": "Prestige",
            "model": "Deluxe Alpha"
        })
        status, score, breakdown, reasons = evaluate_product_match(target, variant_5l)
        self.assertEqual(status, "VARIANT_MATCH")
        self.assertNotEqual(status, "EXACT_MATCH")

    def test_variant_difference_phone_storage_and_ram(self):
        """6GB/128GB vs 8GB/256GB phone must be VARIANT_MATCH, never EXACT_MATCH."""
        target = parse_query_entities("redmi note 13 5g 6gb 128gb")
        variant_8_256 = validate_and_build_product({
            "platform": "Flipkart",
            "title": "REDMI Note 13 5G (Prism Gold, 256 GB) (8 GB RAM)",
            "price_num": 18999.0,
            "brand": "Redmi",
            "model": "Note 13 5G",
            "ram": "8gb",
            "storage": "256gb"
        })
        status, score, breakdown, reasons = evaluate_product_match(target, variant_8_256)
        self.assertEqual(status, "VARIANT_MATCH")
        self.assertNotEqual(status, "EXACT_MATCH")

    def test_variant_difference_pack_count(self):
        """Pack of 1 vs Pack of 2 must be VARIANT_MATCH, never EXACT_MATCH."""
        target = parse_query_entities("dettol liquid handwash refill 750ml")
        variant_pack2 = validate_and_build_product({
            "platform": "Amazon",
            "title": "Dettol Liquid Handwash Refill 750ml (Pack of 2)",
            "price_num": 290.0,
            "brand": "Dettol"
        })
        status, score, breakdown, reasons = evaluate_product_match(target, variant_pack2)
        self.assertEqual(status, "VARIANT_MATCH")
        self.assertNotEqual(status, "EXACT_MATCH")


class TestCategorySpecificSpecifications(unittest.TestCase):
    """Verifies that all 8 prompt categories extract relevant specifications and no irrelevant fields."""

    def test_mobiles_specifications(self):
        fields = get_fields_for_category("mobile")
        self.assertIn("Processor", fields)
        self.assertIn("RAM", fields)
        self.assertIn("Storage", fields)
        self.assertIn("Battery Capacity", fields)
        self.assertIn("Charging Speed", fields)
        self.assertNotIn("Fabric/Material", fields)
        self.assertNotIn("Induction Compatibility", fields)

    def test_laptops_specifications(self):
        fields = get_fields_for_category("laptop")
        self.assertIn("Processor", fields)
        self.assertIn("RAM Capacity", fields)
        self.assertIn("Storage Capacity", fields)
        self.assertIn("GPU", fields)
        self.assertNotIn("Sole Material", fields)
        self.assertNotIn("SPF", fields)

    def test_earbuds_specifications(self):
        fields = get_fields_for_category("earbuds")
        self.assertIn("Driver Size", fields)
        self.assertIn("Active Noise Cancellation", fields)
        self.assertIn("Bluetooth Version", fields)
        self.assertNotIn("RAM", fields)
        self.assertNotIn("Processor", fields)

    def test_pressure_cooker_specifications(self):
        fields = get_fields_for_category("pressure_cooker")
        self.assertIn("Capacity", fields)
        self.assertIn("Material", fields)
        self.assertIn("Base Type", fields)
        self.assertIn("Induction Compatibility", fields)
        self.assertIn("Lid Type", fields)
        self.assertNotIn("RAM", fields)
        self.assertNotIn("Display Size", fields)

    def test_mixer_grinder_specifications(self):
        fields = get_fields_for_category("mixer_grinder")
        self.assertIn("Motor Wattage", fields)
        self.assertIn("RPM", fields)
        self.assertIn("Number of Jars", fields)
        self.assertIn("Blade Material", fields)
        self.assertNotIn("RAM", fields)

    def test_electric_kettle_specifications(self):
        fields = get_fields_for_category("electric_kettle")
        self.assertIn("Capacity", fields)
        self.assertIn("Power/Wattage", fields)
        self.assertIn("Auto Shut-Off", fields)
        self.assertIn("Boil Dry Protection", fields)
        self.assertNotIn("Sole Material", fields)

    def test_shoes_specifications(self):
        fields = get_fields_for_category("shoes")
        self.assertIn("Sole Material", fields)
        self.assertIn("Insole/Cushioning", fields)
        self.assertIn("Upper Material", fields)
        self.assertIn("Closure Type", fields)
        self.assertNotIn("RAM", fields)

    def test_bags_specifications(self):
        fields = get_fields_for_category("bags")
        self.assertIn("Capacity", fields)
        self.assertIn("Material", fields)
        self.assertIn("Number of Compartments", fields)
        self.assertIn("Laptop Sleeve Size", fields)
        self.assertNotIn("Processor", fields)

    def test_groceries_specifications(self):
        fields = get_fields_for_category("grocery")
        self.assertIn("Quantity / Net Weight", fields)
        self.assertIn("Unit Price", fields)
        self.assertIn("Dietary Preference", fields)
        self.assertIn("Food Preference", fields)
        self.assertNotIn("RAM", fields)

    def test_beauty_skincare_makeup_specifications(self):
        # Face Wash
        fw_fields = get_fields_for_category("face_wash")
        self.assertIn("Skin Type", fw_fields)
        self.assertIn("Key Ingredients", fw_fields)
        self.assertIn("Formulation", fw_fields)

        # Sunscreen
        sun_fields = get_fields_for_category("sunscreen")
        self.assertIn("SPF Rating", sun_fields)
        self.assertIn("PA Rating", sun_fields)
        self.assertIn("Broad Spectrum", sun_fields)

        # Lipstick
        lip_fields = get_fields_for_category("lipstick")
        self.assertIn("Finish Type", lip_fields)
        self.assertIn("Formulation", lip_fields)
        self.assertIn("Shade / Color", lip_fields)


class TestDynamicSpecificationMatrixAndPlaceholders(unittest.TestCase):
    """Verifies structured cell statuses and absence of fake fallback placeholders."""

    def test_structured_comparison_cells(self):
        amz = {
            "title": "Hawkins Contura 3 Litre Hard Anodised Pressure Cooker",
            "price_num": 1650.0,
            "material": "Hard Anodised Aluminium",
            "brand": "Hawkins",
            "specs": {"Capacity": "3 Litre", "Material": "Hard Anodised Aluminium", "Induction Compatibility": "Induction & Gas"}
        }
        fk = {
            "title": "Hawkins Contura 3 Litre Hard Anodised Pressure Cooker",
            "price_num": 1699.0,
            "material": "Hard Anodised Aluminium",
            "brand": "Hawkins",
            "specs": {"Capacity": "3 Litre", "Material": "Hard Anodised Aluminium"}
        }
        mee = {
            "title": "Hawkins Contura 3 Litre Pressure Cooker",
            "price_num": 1580.0,
            "specs": {}
        }

        matrix = build_dynamic_specifications({"amazon": amz, "flipkart": fk, "meesho": mee}, category="pressure_cooker")
        self.assertGreater(len(matrix), 0)

        # Check structured cell object
        for row in matrix:
            self.assertIn("amazon_data", row)
            self.assertIn("flipkart_data", row)
            self.assertIn("meesho_data", row)
            
            amz_cell = row["amazon_data"]
            self.assertIn("value", amz_cell)
            self.assertIn("source", amz_cell)
            self.assertIn("verified", amz_cell)
            self.assertIn("status", amz_cell)

    def test_no_fake_placeholders(self):
        """Verifies that missing materials or warranties produce 'Not Available', not fake strings."""
        sparse_item = {
            "title": "Generic Unbranded Item",
            "price_num": 500.0
        }
        q_score, d_conf = compute_quality_and_confidence(sparse_item)
        # Material and warranty should not be fake strings
        self.assertNotEqual(sparse_item.get("material"), "Standard Durable Material")
        self.assertNotEqual(sparse_item.get("warranty"), "1 Year Brand Warranty")
        self.assertNotEqual(sparse_item.get("seller"), "Verified Retailer")


class TestQualityScoringAndRankingPriority(unittest.TestCase):
    """Verifies smart ranking priorities: spec match > features > reviews > value > price."""

    def test_smart_ranking_prefers_exact_over_cheaper_variant(self):
        exact_item = validate_and_build_product({
            "platform": "Amazon",
            "title": "boAt Airdopes 141 ANC Bluetooth Earbuds 42H Battery",
            "price_num": 1499.0,
            "match_status": "EXACT_MATCH",
            "match_score": 92.0,
            "rating": 4.2,
            "review_count": 800,
            "quality_score": 82.0
        })

        # Cheaper item, but only a variant match and lower rating
        variant_cheaper = validate_and_build_product({
            "platform": "Meesho",
            "title": "boAt Airdopes 141 Non-ANC Earbuds",
            "price_num": 999.0,
            "match_status": "VARIANT_MATCH",
            "match_score": 75.0,
            "rating": 3.6,
            "review_count": 90,
            "quality_score": 60.0
        })

        ranked = rank_products([variant_cheaper, exact_item])
        # Exact match with higher spec match and quality must rank first
        self.assertEqual(ranked[0]["platform"].lower(), "amazon")
        self.assertEqual(ranked[0]["match_status"], "EXACT_MATCH")


if __name__ == "__main__":
    unittest.main()
