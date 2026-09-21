"""
tests/test_matching.py
======================
Unit tests for canonical product matching score, variant discrimination, and equivalence detection.
"""

import pytest
from search.matching_service import calculate_product_match_score, are_exact_matches


def test_same_product_different_titles():
    item1 = {
        "title": "GHAR SOAP MAGIC SOAP 300G PACK OF 3",
        "brand": "Ghar Soaps",
        "weight": "300g",
        "pack_quantity": "3"
    }
    item2 = {
        "title": "Ghar Magic Soap 100g x 3",
        "brand": "Ghar",
        "weight": "300g",
        "pack_quantity": "3"
    }
    score, classification, breakdown = calculate_product_match_score(item1, item2)
    assert score >= 85
    assert classification in ("Exact Match", "Strong Match")
    assert breakdown["brand"] >= 18
    assert breakdown["pack_quantity"] == 10.0


def test_variant_discrimination_different_weight():
    item1 = {
        "title": "True Elements Raw Chia Seeds 500g",
        "brand": "True Elements",
        "weight": "500g",
        "pack_quantity": "1"
    }
    item2 = {
        "title": "True Elements Raw Chia Seeds 1kg",
        "brand": "True Elements",
        "weight": "1kg",
        "pack_quantity": "1"
    }
    score, classification, breakdown = calculate_product_match_score(item1, item2)
    # Weight conflict -> weight_score == 0 and classified as Variant, NOT Exact Match
    assert breakdown["weight"] == 0.0
    assert classification == "Variant"
    assert not are_exact_matches(item1, item2)


def test_variant_discrimination_different_pack():
    item1 = {
        "title": "Ghar Soaps Sandalwood Magic Soap 100g",
        "brand": "Ghar Soaps",
        "weight": "100g",
        "pack_quantity": "1"
    }
    item2 = {
        "title": "Ghar Soaps Sandalwood Magic Soap 100g (Pack of 3)",
        "brand": "Ghar Soaps",
        "weight": "100g",
        "pack_quantity": "3"
    }
    score, classification, breakdown = calculate_product_match_score(item1, item2)
    assert breakdown["pack_quantity"] == 0.0
    assert classification == "Variant"
    assert not are_exact_matches(item1, item2)


def test_variant_discrimination_different_storage():
    item1 = {
        "title": "Apple iPhone 15 (128 GB) - Black",
        "brand": "Apple",
        "model": "iPhone 15",
    }
    item2 = {
        "title": "Apple iPhone 15 (256 GB) - Black",
        "brand": "Apple",
        "model": "iPhone 15",
    }
    score, classification, breakdown = calculate_product_match_score(item1, item2)
    assert breakdown["variant"] == 0.0
    assert classification == "Variant"
    assert not are_exact_matches(item1, item2)


def test_different_model_conflict():
    item1 = {
        "title": "Vivo T4 Charger 44W Fast Adapter",
        "brand": "Vivo",
        "model": "T4"
    }
    item2 = {
        "title": "Vivo T3 Charger 44W Fast Adapter",
        "brand": "Vivo",
        "model": "T3"
    }
    score, classification, breakdown = calculate_product_match_score(item1, item2)
    # Conflicting models T4 vs T3
    assert breakdown["model"] == 0.0
    assert classification == "Not a Match"
    assert not are_exact_matches(item1, item2)


def test_price_not_used_in_matching():
    # Two identical products with completely different prices must match
    item1 = {
        "title": "Pilgrim Volcanic Lava Face Wash 100ml",
        "brand": "Pilgrim",
        "price_num": 250,
    }
    item2 = {
        "title": "Pilgrim Volcanic Lava Face Wash 100ml",
        "brand": "Pilgrim",
        "price_num": 399,
    }
    score, classification, _ = calculate_product_match_score(item1, item2)
    assert score >= 90
    assert classification == "Exact Match"
