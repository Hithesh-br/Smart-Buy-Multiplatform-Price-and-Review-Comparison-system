"""
tests/test_best_deal.py
=======================
Unit tests for verified Best Deal algorithm, unit price normalization, and transparent reason breakdown.
"""

import pytest
from search.matching_service import compute_best_deal


def test_best_deal_exact_variant():
    canonical = {
        "title": "Pilgrim Volcanic Lava Face Wash 100ml",
        "brand": "Pilgrim",
        "weight": "100ml",
    }
    candidates = [
        {
            "platform": "amazon",
            "title": "Pilgrim Volcanic Lava Face Wash 100ml",
            "brand": "Pilgrim",
            "price_num": 350,
            "in_stock": True,
            "rating": 4.3,
            "review_count": 800,
            "scrape_status": "success",
            "weight": "100ml",
        },
        {
            "platform": "flipkart",
            "title": "Pilgrim Volcanic Lava Face Wash 100ml",
            "brand": "Pilgrim",
            "price_num": 299,
            "in_stock": True,
            "rating": 4.4,
            "review_count": 1200,
            "scrape_status": "success",
            "weight": "100ml",
        },
    ]

    deal = compute_best_deal(candidates, canonical, category="face_wash")
    assert deal is not None
    assert deal["platform"] == "Flipkart"
    assert deal["price"] == 299
    assert deal["savings"] == 51
    assert any("Lowest verified" in r for r in deal["reasons"])
    assert any("variant verified" in r for r in deal["reasons"])


def test_best_deal_safety_rejects_out_of_stock():
    canonical = {
        "title": "Vivo T4 Charger 44W",
        "brand": "Vivo",
        "model": "T4"
    }
    candidates = [
        {
            "platform": "amazon",
            "title": "Vivo T4 Charger 44W Adapter",
            "brand": "Vivo",
            "price_num": 499,
            "in_stock": False,  # Out of stock
            "scrape_status": "success"
        },
        {
            "platform": "flipkart",
            "title": "Vivo T4 Charger 44W Adapter",
            "brand": "Vivo",
            "price_num": 599,
            "in_stock": True,   # In stock
            "scrape_status": "success"
        }
    ]
    deal = compute_best_deal(candidates, canonical, category="charger")
    assert deal is not None
    # Must pick Flipkart because Amazon is Out of Stock!
    assert deal["platform"] == "Flipkart"


def test_best_deal_safety_rejects_scraper_error():
    canonical = {
        "title": "Raw Chia Seeds 500g",
        "brand": "True Elements"
    }
    candidates = [
        {
            "platform": "meesho",
            "title": "Raw Chia Seeds 500g",
            "price_num": 99,
            "in_stock": True,
            "scrape_status": "error"  # Stale / error result
        },
        {
            "platform": "amazon",
            "title": "Raw Chia Seeds 500g",
            "price_num": 240,
            "in_stock": True,
            "scrape_status": "success"
        }
    ]
    deal = compute_best_deal(candidates, canonical, category="grocery")
    assert deal is not None
    assert deal["platform"] == "Amazon"
