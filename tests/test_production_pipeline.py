"""
tests/test_production_pipeline.py
=================================
Automated test suite verifying the SmartBuy Production-Quality Comparison Pipeline.
Tests:
1. Query understanding & entity parsing (Vivo, iPhone, HP laptop, Grocery, Beauty)
2. Accessory & mismatch hard rejection gates (cases, covers, tempered glass, generation mismatches)
3. Generic brand rejection (e.g. Amazon returning just "vivo")
4. Quantity & unit price normalization (g, kg, ml, L, packs)
5. Suspicious price anomaly rejection (₹186 case vs ₹18,899 phone -> PRICE/IDENTITY UNVERIFIED)
6. Quality scoring & data confidence
7. Best Deal engine (Best Value, not min price)
8. Single Source of Truth end-to-end pipeline
9. Direct product URL search flow
"""

import pytest
from search.query_parser import parse_query_entities
from search.quantity_normalizer import normalize_quantity_and_pack, calculate_standard_unit_price
from search.quality_scorer import compute_quality_and_confidence
from search.product_matcher import evaluate_product_match, check_suspicious_price
from search.pipeline import run_comparison_pipeline
from scrapers.common_schema import validate_and_build_product
from url_detector import detect_search_type, validate_and_detect_url


# ─── 1. Query Entity Parser Tests ─────────────────────────────────────────────

def test_query_parser_vivo():
    q = "vivo t4 5g 8gb 128gb"
    entities = parse_query_entities(q)
    assert entities["brand"].lower() == "vivo"
    assert entities["model"].lower() == "t4"
    assert entities["network"].lower() == "5g"
    assert entities["ram"].lower() == "8gb"
    assert entities["storage"].lower() == "128gb"
    assert entities["category"] in ("smartphones", "phone", "smartphone")
    assert entities["is_accessory"] is False


def test_query_parser_accessory():
    q = "iphone 15 case"
    entities = parse_query_entities(q)
    assert entities["is_accessory"] is True
    assert entities["brand"].lower() == "apple"
    assert "iphone" in entities["model"].lower()


def test_query_parser_grocery_pack():
    q = "chia seeds 500g pack of 2"
    entities = parse_query_entities(q)
    assert entities["category"] in ("grocery", "food")
    assert entities["pack_count"] == 2
    assert "500" in str(entities.get("weight") or "") or "1000" in str(entities.get("weight") or "")


# ─── 2. Quantity & Unit Price Normalization ────────────────────────────────────

def test_quantity_normalization():
    # 500g x 2 should normalize to 1000g / 1 kg
    info = normalize_quantity_and_pack("Organic Raw Chia Seeds 500g (Pack of 2)")
    assert info["pack_count"] == 2
    assert info["quantity_in_grams"] == 1000.0
    assert info["unit"] == "kg"
    assert info["total_quantity"] == "1 kg"

    # Unit price calculation
    unit_p = calculate_standard_unit_price(350, info)
    assert unit_p is not None
    assert "₹35 / 100g" in unit_p or "100g" in unit_p


# ─── 3. Quality & Data Confidence Scorer ──────────────────────────────────────

def test_quality_and_confidence():
    complete_prod = validate_and_build_product({
        "platform": "Amazon",
        "title": "Vivo T4 5G (Starlight Blue, 8GB RAM, 128GB Storage)",
        "price_num": 18899.0,
        "rating": 4.3,
        "review_count": 1240,
        "brand": "Vivo",
        "model": "T4 5G",
        "seller": "Appario Retail",
        "warranty": "1 Year Manufacturer Warranty",
        "availability": "In Stock",
        "product_url": "https://www.amazon.in/dp/B0CX12345",
        "image_url": "https://m.media-amazon.com/images/I/71example.jpg"
    })
    q_score, d_conf = compute_quality_and_confidence(complete_prod)
    assert q_score >= 70.0
    assert d_conf >= 65.0

    sparse_prod = validate_and_build_product({
        "platform": "Meesho",
        "title": "vivo",
        "price_num": 186.0
    })
    q_score_sp, d_conf_sp = compute_quality_and_confidence(sparse_prod)
    assert q_score_sp < 60.0
    assert d_conf_sp < 40.0


# ─── 4. Rejection Gates: Generic Titles, Accessories & Generations ────────────

def test_reject_generic_brand_title():
    target = parse_query_entities("vivo t4 5g")
    generic_item = validate_and_build_product({
        "platform": "Amazon",
        "title": "vivo",
        "price_num": 18999.0
    })
    status, score, breakdown, reasons = evaluate_product_match(target, generic_item)
    assert status == "REJECTED"
    assert any("generic" in r.lower() or "lacks" in r.lower() for r in reasons)


def test_reject_model_generation_mismatch():
    target = parse_query_entities("vivo t4 5g")
    wrong_gen_item = validate_and_build_product({
        "platform": "Flipkart",
        "title": "vivo T5e 5G (Titanium Grey, 128 GB) (8 GB RAM)",
        "price_num": 16999.0
    })
    status, score, breakdown, reasons = evaluate_product_match(target, wrong_gen_item)
    assert status == "REJECTED"
    assert any("generation" in r.lower() or "mismatch" in r.lower() for r in reasons)


def test_reject_phone_accessory_case():
    target = parse_query_entities("vivo t4 5g")
    case_item = validate_and_build_product({
        "platform": "Meesho",
        "title": "Shockproof Soft Silicone Back Cover for Vivo T4 5G",
        "price_num": 186.0
    })
    status, score, breakdown, reasons = evaluate_product_match(target, case_item)
    assert status == "REJECTED"
    assert any("accessory" in r.lower() for r in reasons)


def test_reject_laptop_bag_when_searching_laptop():
    target = parse_query_entities("hp laptop")
    bag_item = validate_and_build_product({
        "platform": "Amazon",
        "title": "HP Lightweight 15.6-inch Laptop Backpack / Bag",
        "price_num": 899.0
    })
    status, score, breakdown, reasons = evaluate_product_match(target, bag_item)
    assert status == "REJECTED"
    assert any("accessory" in r.lower() for r in reasons)


def test_reject_facewash_vs_soap():
    target = parse_query_entities("himalaya face wash")
    soap_item = validate_and_build_product({
        "platform": "Meesho",
        "title": "Himalaya Neem & Turmeric Bathing Soap 125g",
        "price_num": 55.0
    })
    status, score, breakdown, reasons = evaluate_product_match(target, soap_item)
    assert status == "REJECTED"
    assert any("conflict" in r.lower() or "product type" in r.lower() or "soap" in r.lower() for r in reasons)


# ─── 5. Exact & Variant Match Verification ────────────────────────────────────

def test_exact_product_match():
    target = parse_query_entities("vivo t4 5g 8gb 128gb")
    exact_item = validate_and_build_product({
        "platform": "Amazon",
        "title": "Vivo T4 5G (Starlight Blue, 8GB RAM, 128GB Storage)",
        "price_num": 18899.0,
        "brand": "vivo",
        "model": "t4",
        "network": "5g",
        "ram": "8gb",
        "storage": "128gb"
    })
    status, score, breakdown, reasons = evaluate_product_match(target, exact_item)
    assert status == "EXACT_MATCH"
    assert score >= 85.0


def test_variant_product_match():
    target = parse_query_entities("vivo t4 5g 8gb 128gb")
    variant_item = validate_and_build_product({
        "platform": "Flipkart",
        "title": "vivo T4 5G (Starlight Blue, 256 GB) (8 GB RAM)",
        "price_num": 20999.0,
        "brand": "vivo",
        "model": "t4",
        "network": "5g",
        "ram": "8gb",
        "storage": "256gb"
    })
    status, score, breakdown, reasons = evaluate_product_match(target, variant_item)
    assert status == "VARIANT_MATCH"
    assert score >= 75.0


# ─── 6. Suspicious Price Protection Test ──────────────────────────────────────

def test_suspicious_price_detection():
    # If Amazon is ~18k and Flipkart is ~18k, Meesho returning ₹186 is an extreme anomaly
    amazon_p = validate_and_build_product({
        "platform": "Amazon",
        "title": "Vivo T4 5G 8GB 128GB",
        "price_num": 18899.0,
        "match_status": "EXACT_MATCH"
    })
    flipkart_p = validate_and_build_product({
        "platform": "Flipkart",
        "title": "Vivo T4 5G 8GB 128GB",
        "price_num": 18499.0,
        "match_status": "EXACT_MATCH"
    })
    suspicious_meesho = validate_and_build_product({
        "platform": "Meesho",
        "title": "Vivo T4 5G Phone",
        "price_num": 186.0,
        "match_status": "EXACT_MATCH"  # falsely claimed exact match
    })

    all_candidates = [amazon_p, flipkart_p, suspicious_meesho]
    is_susp, reason = check_suspicious_price(suspicious_meesho, all_candidates)
    assert is_susp is True
    assert "Suspicious price" in reason or "PRICE/IDENTITY UNVERIFIED" in reason


# ─── 7. Full Single Source of Truth Pipeline Integration ──────────────────────

def test_full_pipeline_vivo_comparison():
    raw_results = {
        "Amazon": [
            validate_and_build_product({
                "platform": "Amazon",
                "title": "vivo",  # Generic ad - must be rejected
                "price_num": 18999.0
            }),
            validate_and_build_product({
                "platform": "Amazon",
                "title": "Vivo T4 5G (Starlight Blue, 8GB RAM, 128GB Storage)",
                "price_num": 18899.0,
                "rating": 4.3,
                "review_count": 890,
                "availability": "In Stock"
            })
        ],
        "Flipkart": [
            validate_and_build_product({
                "platform": "Flipkart",
                "title": "vivo T5e 5G (128 GB) (8 GB RAM)",  # Wrong generation - must be rejected
                "price_num": 16999.0
            }),
            validate_and_build_product({
                "platform": "Flipkart",
                "title": "vivo T4 5G (Starlight Blue, 128 GB) (8 GB RAM)",
                "price_num": 18499.0,
                "rating": 4.4,
                "review_count": 1420,
                "availability": "In Stock"
            })
        ],
        "Meesho": [
            validate_and_build_product({
                "platform": "Meesho",
                "title": "Vivo T4 5G Back Cover Case",  # Accessory - must be rejected
                "price_num": 186.0
            })
        ]
    }

    platform_status = {
        "Amazon": {"status": "success", "available": True, "count": 2},
        "Flipkart": {"status": "success", "available": True, "count": 2},
        "Meesho": {"status": "success", "available": True, "count": 1}
    }

    result = run_comparison_pipeline("vivo t4 5g 8gb 128gb", raw_results, platform_status)

    # 1. Check validated_products
    val_prods = result["validated_products"]
    titles = [p["title"] for p in val_prods]
    assert "vivo" not in titles
    assert "vivo T5e 5G (128 GB) (8 GB RAM)" not in titles
    assert "Vivo T4 5G Back Cover Case" not in titles
    assert "Vivo T4 5G (Starlight Blue, 8GB RAM, 128GB Storage)" in titles
    assert "vivo T4 5G (Starlight Blue, 128 GB) (8 GB RAM)" in titles

    # 2. Check Top Verified Offers
    top_offers = result["top_verified_offers"]
    assert top_offers["Amazon"]["available"] is True
    assert top_offers["Amazon"]["price_num"] == 18899.0
    assert top_offers["Amazon"]["price_formatted"] is not None

    assert top_offers["Flipkart"]["available"] is True
    assert top_offers["Flipkart"]["price_num"] == 18499.0
    assert top_offers["Flipkart"]["price_formatted"] is not None

    # Meesho accessory must NOT be in top verified offers
    assert top_offers["Meesho"]["available"] is False

    # 3. Check Best Deal
    best_deal = result["best_deal"]
    assert best_deal is not None
    # Must NOT pick Meesho ₹186!
    assert best_deal["platform"] in ("Amazon", "Flipkart")
    assert best_deal["price_num"] in (18499.0, 18899.0)

    # 4. Specifications matrix
    matrix = result["specifications_matrix"]
    assert len(matrix) > 0
    spec_names = [row["specification"] for row in matrix]
    assert "RAM" in spec_names
    assert "Storage" in spec_names
    assert "5G" in spec_names


# ─── 8. Direct Product URL Detection & Routing ────────────────────────────────

def test_url_detector_direct_links():
    amz_url = "https://www.amazon.in/dp/B0CX212R4B"
    d_amz = detect_search_type(amz_url)
    assert d_amz["type"] == "product_url"
    assert d_amz["platform"] == "amazon"

    fk_url = "https://dl.flipkart.com/s/7wE5_yNNNN"
    d_fk = detect_search_type(fk_url)
    assert d_fk["type"] == "product_url"
    assert d_fk["platform"] == "flipkart"

    query_text = "vivo t4 5g 8gb 128gb"
    d_q = detect_search_type(query_text)
    assert d_q["type"] == "product_name"
