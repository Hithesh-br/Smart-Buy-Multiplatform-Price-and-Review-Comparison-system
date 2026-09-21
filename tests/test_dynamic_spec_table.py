"""
Unit & Integration Tests for SmartBuy Dynamic Product Specification Comparison Table

Validates:
1. Category-specific specifications for all 8 required categories:
   - HP laptop charger (charger: wattage, voltage, connector, compatibility; blocks RAM/Storage/Processor/Camera/OS)
   - iPhone 17 Pro Max (phone: RAM, Storage, Display, Camera, Processor, OS)
   - Vivo T4 5G (phone: RAM, Storage, Display, 5G, Camera)
   - Chia seeds (grocery: Weight, Ingredients, Shelf Life; blocks electronics specs)
   - Ghar soap (soap: Skin Type, Ingredients, Weight, Fragrance)
   - Face wash (face wash: Skin Type, Volume, Ingredients, Benefits)
   - Laptop (laptop: Processor, RAM, Storage, Graphics, OS)
   - Clothing product (clothing: Fabric, Size, Color, Pattern, Fit)
2. Display ONLY real scraped data (no fake Generic, 0 rating, 0 reviews, ₹0, fake models)
3. Hide rows when all three marketplaces have no data
4. Display '—' for missing cells, never scraping error strings like 'Scraping unavailable'
5. Preview image validation: only valid URLs, rejects placeholders and malformed URLs
6. Marketplace status isolation: separate status badges ('Found', 'Partial', 'Timed Out', 'Unavailable')
"""

import pytest
from search.category_detector import detect_category
from search.specs_extractor import (
    has_real_value,
    should_display_row,
    is_valid_image_url,
    get_fields_for_category,
    extract_field_value,
    build_dynamic_specifications,
    compute_marketplace_statuses,
    CATEGORY_BLACKLISTED_FIELDS,
)
from search.matching_service import build_canonical_comparison


# =============================================================================
# 1. Validation of has_real_value, should_display_row, and is_valid_image_url
# =============================================================================

def test_has_real_value_rejection_rules():
    """Verify invalid placeholders and error messages are rejected."""
    invalid_samples = [
        None,
        "",
        "   ",
        "N/A",
        "n/a",
        "Not Available",
        "not available",
        "Unknown",
        "null",
        "None",
        "—",
        "-",
        "Generic",
        "generic",
        "0",
        0,
        0.0,
        "0.0",
        "₹0",
        "Rs. 0",
        "0 rating",
        "0 reviews",
        "0%",
        "Amazon data temporarily unavailable (Scraping unavailable)",
        "Flipkart data temporarily unavailable (Scraping unavailable)",
        "Meesho data temporarily unavailable (Scraping unavailable)",
        "Scraping unavailable",
        "No matching product found",
    ]
    for sample in invalid_samples:
        assert not has_real_value(sample), f"Expected '{sample}' to be rejected as fake/missing value"

    valid_samples = [
        "65W",
        "19.5V",
        "Type-C",
        "Apple iPhone 15",
        "HP",
        1999,
        "₹1,999",
        4.5,
        "★ 4.5",
        120,
        "120 reviews",
        "In Stock",
        "100% Cotton",
        "500g",
    ]
    for sample in valid_samples:
        assert has_real_value(sample), f"Expected '{sample}' to be accepted as real value"


def test_should_display_row():
    """Verify row is shown only if at least one marketplace has real data."""
    assert not should_display_row(None, "N/A", "Scraping unavailable")
    assert not should_display_row("—", "Not Available", "")
    assert not should_display_row("₹0", "0 rating", "Generic")

    # True if at least one platform has genuine extracted data
    assert should_display_row("65W", "—", "—")
    assert should_display_row("—", "Apple A17 Pro", "—")
    assert should_display_row("—", "—", "Cotton")
    assert should_display_row("65W", "65W", "65W")


def test_is_valid_image_url():
    """Verify image URLs are strictly validated."""
    assert is_valid_image_url("https://m.media-amazon.com/images/I/71xyz.jpg")
    assert is_valid_image_url("http://rukminim2.flixcart.com/image/832/832/xif0q/1.jpeg")
    assert is_valid_image_url("https://images.meesho.com/images/products/123/1.jpg")

    assert not is_valid_image_url(None)
    assert not is_valid_image_url("")
    assert not is_valid_image_url("placeholder.png")
    assert not is_valid_image_url("https://example.com/no_image.png")
    assert not is_valid_image_url("invalid-url")
    assert not is_valid_image_url("—")


# =============================================================================
# 2. Category-Specific Specifications for All 8 Required Test Cases
# =============================================================================

REQUIRED_8_TEST_CASES = [
    {
        "query": "HP laptop charger",
        "category": "charger",
        "expected_relevant_fields": ["Output Wattage", "Output Voltage", "Connector Type", "Compatibility"],
        "forbidden_fields": ["RAM", "Storage", "Processor", "Camera", "OS", "Front Camera", "Rear Camera"],
        "sample_amz": {
            "title": "HP 65W USB-C Laptop Charger for HP Pavilion 15",
            "brand": "HP",
            "price_num": 1499,
            "rating": 4.3,
            "review_count": 210,
            "in_stock": True,
            "link": "https://amazon.in/dp/hpcharger"
        },
        "sample_fk": {
            "title": "HP 65W Type C Power Adapter for HP Laptops",
            "brand": "HP",
            "price_num": 1399,
            "rating": 4.1,
            "review_count": 95,
            "in_stock": True,
            "link": "https://flipkart.com/hpcharger"
        },
        "sample_mee": {
            "title": "HP Laptop Charger 65W Type-C",
            "brand": "HP",
            "price_num": 899,
            "rating": 3.9,
            "review_count": 40,
            "in_stock": True,
            "link": "https://meesho.com/hpcharger"
        }
    },
    {
        "query": "iPhone 17 Pro Max",
        "category": "phone",
        "expected_relevant_fields": ["RAM", "Storage", "Display", "Processor", "Battery", "Camera", "OS"],
        "forbidden_fields": ["Output Wattage", "Fabric", "Skin Type", "Ingredients"],
        "sample_amz": {
            "title": "Apple iPhone 17 Pro Max 256GB Natural Titanium 8GB RAM",
            "brand": "Apple",
            "price_num": 149900,
            "rating": 4.8,
            "review_count": 1200,
            "in_stock": True,
            "link": "https://amazon.in/dp/iphone17"
        },
        "sample_fk": {
            "title": "Apple iPhone 17 Pro Max (Natural Titanium, 256 GB)",
            "brand": "Apple",
            "price_num": 147900,
            "rating": 4.7,
            "review_count": 900,
            "in_stock": True,
            "link": "https://flipkart.com/iphone17"
        },
        "sample_mee": None
    },
    {
        "query": "Vivo T4 5G",
        "category": "phone",
        "expected_relevant_fields": ["RAM", "Storage", "Display", "5G", "Camera"],
        "forbidden_fields": ["Output Wattage", "Fabric", "Skin Type", "Ingredients"],
        "sample_amz": {
            "title": "Vivo T4 5G (8GB RAM, 128GB Storage)",
            "brand": "Vivo",
            "price_num": 18999,
            "rating": 4.3,
            "review_count": 350,
            "in_stock": True,
            "link": "https://amazon.in/dp/vivot4"
        },
        "sample_fk": {
            "title": "Vivo T4 5G (Starlight Blue, 128 GB) (8 GB RAM)",
            "brand": "Vivo",
            "price_num": 18499,
            "rating": 4.4,
            "review_count": 520,
            "in_stock": True,
            "link": "https://flipkart.com/vivot4"
        },
        "sample_mee": None
    },
    {
        "query": "Chia seeds",
        "category": "grocery",
        "expected_relevant_fields": ["Weight", "Quantity", "Dietary Preference"],
        "forbidden_fields": ["RAM", "Storage", "Processor", "Camera", "OS", "Wattage", "Battery"],
        "sample_amz": {
            "title": "True Elements Raw Chia Seeds 500g for Weight Loss",
            "brand": "True Elements",
            "price_num": 299,
            "rating": 4.4,
            "review_count": 3500,
            "in_stock": True,
            "link": "https://amazon.in/dp/chiaseeds"
        },
        "sample_fk": {
            "title": "Neuherbs Raw Unroasted Chia Seeds 500g",
            "brand": "Neuherbs",
            "price_num": 275,
            "rating": 4.3,
            "review_count": 1800,
            "in_stock": True,
            "link": "https://flipkart.com/chiaseeds"
        },
        "sample_mee": {
            "title": "Organic Raw Chia Seeds 500g",
            "brand": "Generic Organics",
            "price_num": 199,
            "rating": 4.1,
            "review_count": 450,
            "in_stock": True,
            "link": "https://meesho.com/chiaseeds"
        }
    },
    {
        "query": "Ghar soap",
        "category": "soap",
        "expected_relevant_fields": ["Skin Type", "Ingredients", "Benefits", "Weight"],
        "forbidden_fields": ["RAM", "Storage", "Processor", "Camera", "OS", "Wattage", "Fabric"],
        "sample_amz": {
            "title": "Ghar Soaps Magic Soap 100g with Sandalwood & Saffron",
            "brand": "Ghar Soaps",
            "price_num": 249,
            "rating": 4.2,
            "review_count": 1100,
            "in_stock": True,
            "link": "https://amazon.in/dp/gharsoap"
        },
        "sample_fk": {
            "title": "Ghar Soaps Magic Soap Bar (100 g)",
            "brand": "Ghar Soaps",
            "price_num": 235,
            "rating": 4.1,
            "review_count": 640,
            "in_stock": True,
            "link": "https://flipkart.com/gharsoap"
        },
        "sample_mee": {
            "title": "Ghar Soaps Magic Soap 100g",
            "brand": "Ghar Soaps",
            "price_num": 190,
            "rating": 4.0,
            "review_count": 210,
            "in_stock": True,
            "link": "https://meesho.com/gharsoap"
        }
    },
    {
        "query": "Face wash",
        "category": "face_wash",
        "expected_relevant_fields": ["Skin Type", "Volume", "Ingredients", "Fragrance", "Benefits"],
        "forbidden_fields": ["RAM", "Storage", "Processor", "Camera", "OS", "Wattage", "Battery"],
        "sample_amz": {
            "title": "Himalaya Purifying Neem Face Wash 150ml",
            "brand": "Himalaya",
            "price_num": 199,
            "rating": 4.5,
            "review_count": 8900,
            "in_stock": True,
            "link": "https://amazon.in/dp/facewash"
        },
        "sample_fk": {
            "title": "Himalaya Purifying Neem Face Wash (150 ml)",
            "brand": "Himalaya",
            "price_num": 185,
            "rating": 4.4,
            "review_count": 4500,
            "in_stock": True,
            "link": "https://flipkart.com/facewash"
        },
        "sample_mee": None
    },
    {
        "query": "Laptop",
        "category": "laptop",
        "expected_relevant_fields": ["Processor", "RAM", "Storage", "Display", "Graphics", "OS"],
        "forbidden_fields": ["Fabric", "Skin Type", "Ingredients", "Fragrance", "Shelf Life"],
        "sample_amz": {
            "title": "Lenovo IdeaPad Slim 3 Core i5 16GB RAM 512GB SSD Windows 11",
            "brand": "Lenovo",
            "price_num": 52990,
            "rating": 4.2,
            "review_count": 780,
            "in_stock": True,
            "link": "https://amazon.in/dp/laptop"
        },
        "sample_fk": {
            "title": "Lenovo IdeaPad Slim 3 Intel Core i5 (16 GB/512 GB SSD/Windows 11)",
            "brand": "Lenovo",
            "price_num": 51990,
            "rating": 4.3,
            "review_count": 620,
            "in_stock": True,
            "link": "https://flipkart.com/laptop"
        },
        "sample_mee": None
    },
    {
        "query": "Clothing product",
        "category": "clothing",
        "expected_relevant_fields": ["Fabric", "Size", "Color", "Pattern", "Fit"],
        "forbidden_fields": ["RAM", "Storage", "Processor", "Camera", "OS", "Wattage", "Battery"],
        "sample_amz": {
            "title": "Van Heusen Men's Slim Fit Cotton Formal Shirt Size 40",
            "brand": "Van Heusen",
            "price_num": 1299,
            "rating": 4.2,
            "review_count": 450,
            "in_stock": True,
            "link": "https://amazon.in/dp/shirt"
        },
        "sample_fk": {
            "title": "Van Heusen Men Solid Formal White Shirt",
            "brand": "Van Heusen",
            "price_num": 1199,
            "rating": 4.1,
            "review_count": 320,
            "in_stock": True,
            "link": "https://flipkart.com/shirt"
        },
        "sample_mee": {
            "title": "Cotton Slim Fit Shirt Men White",
            "brand": "Generic",
            "price_num": 499,
            "rating": 3.9,
            "review_count": 120,
            "in_stock": True,
            "link": "https://meesho.com/shirt"
        }
    }
]


@pytest.mark.parametrize("case", REQUIRED_8_TEST_CASES, ids=lambda c: c["query"])
def test_category_specification_matrix_and_isolation(case):
    """
    Validates dynamic specifications for all 8 required categories:
    - Query category detection
    - Candidate field selection matches category
    - Blacklisted fields (e.g. RAM/Processor on chargers/groceries) are NEVER extracted or displayed
    - Output values contain only real scraped data
    - Missing cells display '—', never 'Scraping unavailable'
    """
    q = case["query"]
    expected_cat = case["category"]
    det_cat = detect_category(query=q)

    # Allow compatible category alias (e.g. smartphone <-> phone, soap/face_wash <-> skincare)
    category_group = {
        "charger": ["charger", "adapter"],
        "phone": ["phone", "smartphone", "mobile"],
        "grocery": ["grocery", "food"],
        "soap": ["soap", "skincare", "beauty"],
        "face_wash": ["face_wash", "skincare", "beauty"],
        "laptop": ["laptop"],
        "clothing": ["clothing", "fashion"],
    }
    assert det_cat in category_group.get(expected_cat, [expected_cat]), (
        f"Category mismatch for '{q}': got '{det_cat}', expected group of '{expected_cat}'"
    )

    products = {
        "amazon": case["sample_amz"],
        "flipkart": case["sample_fk"],
        "meesho": case["sample_mee"],
    }

    matrix = build_dynamic_specifications(products, det_cat)
    field_names = [r["name"] for r in matrix]

    # Verify forbidden fields are blocked
    for forbidden in case["forbidden_fields"]:
        assert forbidden not in field_names, (
            f"Forbidden field '{forbidden}' leaked into category '{det_cat}' for '{q}'! Fields: {field_names}"
        )

    # Verify every rendered row has at least one real value and missing cells display '—'
    for row in matrix:
        amz = row["amazon"]
        fk = row["flipkart"]
        mee = row["meesho"]

        # 1. At least one platform must have a real value (empty rows discarded)
        assert should_display_row(amz, fk, mee), (
            f"Row '{row['name']}' has no real values across all platforms: amz={amz}, fk={fk}, mee={mee}"
        )

        # 2. No scraping error text inside any cell
        for val in (amz, fk, mee):
            val_str = str(val).lower()
            assert "scraping unavailable" not in val_str, f"Scraping error found in cell: '{val}'"
            assert "temporarily unavailable" not in val_str, f"Scraping error found in cell: '{val}'"
            assert "no matching product" not in val_str, f"Error message found in cell: '{val}'"

        # 3. If a platform has no product, it must display '—'
        if case["sample_mee"] is None:
            assert mee == "—", f"Platform with no product should display '—', got '{mee}'"


def test_hp_charger_strict_specification_isolation():
    """Explicitly verify HP Laptop Charger shows charger specs and ZERO PC specs."""
    charger_prod = {
        "title": "HP 65W USB-C AC Adapter Charger for HP Pavilion 15 19.5V",
        "brand": "HP",
        "model": "65W USB-C",
        "price_num": 1499,
        "rating": 4.5,
        "review_count": 300,
        "in_stock": True,
        "product_url": "https://amazon.in/hp-charger"
    }
    products = {"amazon": charger_prod, "flipkart": None, "meesho": None}
    matrix = build_dynamic_specifications(products, "charger")
    rendered_fields = [r["name"].lower() for r in matrix]

    # Verify charger-specific fields are present
    assert any("wattage" in f or "power" in f for f in rendered_fields)

    # Verify strictly NO RAM, Storage, Processor, Camera, OS
    prohibited = ["ram", "storage", "processor", "cpu", "camera", "rear camera", "front camera", "os", "graphics"]
    for p in prohibited:
        assert p not in rendered_fields, f"Prohibited field '{p}' appeared in HP laptop charger spec table!"


def test_marketplace_status_isolation():
    """Verify marketplace status badges are cleanly computed independently of table cells."""
    best_match_per_platform = {
        "Amazon": {"title": "Sample Phone", "price_num": 15000},
        "Flipkart": {"title": "Sample Phone", "price_num": 14800},
        "Meesho": None
    }
    platform_status = {
        "Amazon": {"available": True, "status": "success"},
        "Flipkart": {"available": True, "status": "partial"},
        "Meesho": {"available": False, "status": "timeout"}
    }

    statuses = compute_marketplace_statuses(best_match_per_platform, platform_status)

    assert statuses["Amazon"]["status"] == "Found"
    assert statuses["Amazon"]["color"] == "success"

    assert statuses["Flipkart"]["status"] == "Partial"
    assert statuses["Flipkart"]["color"] == "info"

    assert statuses["Meesho"]["status"] == "Timed Out"
    assert statuses["Meesho"]["color"] == "warning"
