"""
tests/test_specifications.py
============================
Unit tests for specification extraction, category-specific matrix building, and missing value handling.
"""

import pytest
from search.matching_service import (
    extract_normalized_specs,
    get_category_spec_keys,
    build_canonical_comparison
)


def test_extract_normalized_specs():
    prod = {
        "title": "Ghar Magic Soap 100g",
        "brand": "Ghar Soaps",
        "price": "₹299",
        "price_num": 299,
        "rating": 4.3,
        "review_count": 1200,
        "weight": "100g",
        "pack_quantity": "1",
        "specifications": {
            "Skin Type": "All Skin Types",
            "Fragrance": "Sandalwood",
            "Ingredients": "Coconut Oil, Sandalwood"
        }
    }
    specs = extract_normalized_specs(prod)
    assert specs["Product Name"] == "Ghar Magic Soap 100g"
    assert specs["Brand"] == "Ghar Soaps"
    assert specs["Price"] == "₹299"
    assert specs["Skin Type"] == "All Skin Types"
    assert specs["Fragrance"] == "Sandalwood"
    assert specs["Weight"] == "100g"


def test_category_spec_keys():
    phone_keys = get_category_spec_keys("phone")
    assert "RAM" in phone_keys
    assert "Storage" in phone_keys
    assert "Processor" in phone_keys

    soap_keys = get_category_spec_keys("soap")
    assert "Weight" in soap_keys
    assert "Fragrance" in soap_keys
    assert "Skin Type" in soap_keys

    charger_keys = get_category_spec_keys("charger")
    assert "Power" in charger_keys
    assert "Fast Charging" in charger_keys


def test_spec_table_status_differentiation():
    # When Amazon and Flipkart match, but Meesho scraper failed (blocked)
    platform_results = {
        "Amazon": [{
            "platform": "amazon",
            "title": "Ghar Magic Soap 100g",
            "brand": "Ghar Soaps",
            "price": "₹299",
            "price_num": 299,
            "weight": "100g",
            "scrape_status": "success",
            "in_stock": True
        }],
        "Flipkart": [{
            "platform": "flipkart",
            "title": "Ghar Magic Soap 100g",
            "brand": "Ghar Soaps",
            "price": "₹280",
            "price_num": 280,
            "weight": "100g",
            "scrape_status": "success",
            "in_stock": True
        }],
        "Meesho": []
    }
    platform_status = {
        "Amazon": {"available": True, "status": "success", "error": None},
        "Flipkart": {"available": True, "status": "success", "error": None},
        "Meesho": {"available": False, "status": "blocked", "error": "Bot access restricted"}
    }

    comp = build_canonical_comparison("ghar soap", platform_results, platform_status)
    matrix = comp["specifications_matrix"]
    assert len(matrix) > 0

    # Section 3 & 8: Never display scraping error messages inside table cells
    meesho_vals = [r["meesho"] for r in matrix]
    assert not any("Scraping unavailable" in str(v) for v in meesho_vals)
    assert not any("temporarily unavailable" in str(v) for v in meesho_vals)
    # Missing cells must display '—'
    assert all(v == "—" for v in meesho_vals)


def test_spec_table_no_match_differentiation():
    # When Amazon and Flipkart match, and Meesho scraper succeeded but returned 0 items
    platform_results = {
        "Amazon": [{
            "platform": "amazon",
            "title": "Ghar Magic Soap 100g",
            "brand": "Ghar Soaps",
            "price": "₹299",
            "price_num": 299,
            "scrape_status": "success"
        }],
        "Flipkart": [{
            "platform": "flipkart",
            "title": "Ghar Magic Soap 100g",
            "brand": "Ghar Soaps",
            "price": "₹280",
            "price_num": 280,
            "scrape_status": "success"
        }],
        "Meesho": []
    }
    platform_status = {
        "Amazon": {"available": True, "status": "success"},
        "Flipkart": {"available": True, "status": "success"},
        "Meesho": {"available": False, "status": "no_results"}
    }

    comp = build_canonical_comparison("ghar soap", platform_results, platform_status)
    matrix = comp["specifications_matrix"]
    meesho_vals = [r["meesho"] for r in matrix]
    # Cells must display '—', never repeating messages across every row
    assert not any("No matching product" in str(v) for v in meesho_vals)
    assert not any("Scraping unavailable" in str(v) for v in meesho_vals)
    assert all(v == "—" for v in meesho_vals)
