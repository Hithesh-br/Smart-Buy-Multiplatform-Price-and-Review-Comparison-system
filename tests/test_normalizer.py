"""
tests/test_normalizer.py
========================
Unit tests for query and product attribute normalization, unit conversions, and category detection.
"""

import pytest
from search.normalizer import (
    normalize_query,
    normalize_title,
    normalize_brand,
    normalize_model,
    normalize_weight,
    normalize_pack_quantity,
    normalize_price,
    normalize_rating,
    normalize_review_count,
    detect_category,
)


def test_normalize_query():
    assert normalize_query("buy ghar soap online") == "ghar soap"
    assert normalize_query("  vivo t4 charger 44w  ") == "vivo t4 charger 44w"
    assert normalize_query("chia seeds 500g") == "chia seeds 500g"
    assert normalize_query("iphone 15 128 gb") == "iphone 15 128gb"


def test_normalize_title():
    t1 = "Ghar Soaps Magic Soap 300g (Pack of 3)"
    assert "300g" in normalize_title(t1)
    assert "pack of 3" in normalize_title(t1)


def test_normalize_brand():
    assert normalize_brand("ghar soaps") == "Ghar Soaps"
    assert normalize_brand("apple inc") == "Apple"
    assert normalize_brand("SAMSUNG") == "Samsung"
    assert normalize_brand("philgrim") == "Pilgrim"
    assert normalize_brand("Generic") is None
    assert normalize_brand("") is None


def test_normalize_model():
    assert normalize_model("T4") == "T4"
    assert normalize_model("S24 Ultra") == "S24 Ultra"
    assert normalize_model("natural") is None


def test_normalize_weight():
    assert normalize_weight("1000g") == "1kg"
    assert normalize_weight("500 grams") == "500g"
    assert normalize_weight("0.5 kg") == "500g"
    assert normalize_weight("100 ml") == "100ml"
    assert normalize_weight("1 Litre") == "1L"
    assert normalize_weight("no weight here") is None


def test_normalize_pack_quantity():
    assert normalize_pack_quantity("Pack of 3") == "3"
    assert normalize_pack_quantity("Pack-2") == "2"
    assert normalize_pack_quantity("100g x 3") == "3"
    assert normalize_pack_quantity("Single Bar") == "1"


def test_normalize_price():
    assert normalize_price("₹299") == 299
    assert normalize_price("Rs. 1,499.00") == 1499
    assert normalize_price(0) is None
    assert normalize_price("N/A") is None


def test_normalize_rating():
    assert normalize_rating("4.2 out of 5 stars") == 4.2
    assert normalize_rating(4.5) == 4.5
    assert normalize_rating("0.0") is None
    assert normalize_rating("N/A") is None


def test_normalize_review_count():
    assert normalize_review_count("1,450 ratings") == 1450
    assert normalize_review_count(350) == 350
    assert normalize_review_count("0") == 0


def test_detect_category():
    # Category detection across broad domains
    assert detect_category(query="ghar soap") == "soap"
    assert detect_category(title="Pilgrim Volcanic Lava Face Wash") == "face_wash"
    assert detect_category(query="vivo t4 charger") == "charger"
    assert detect_category(title="Apple iPhone 15 128GB") == "phone"
    assert detect_category(title="HP Pavilion Laptop Core i5") == "laptop"
    assert detect_category(title="Raw Chia Seeds 500g") == "grocery"
    assert detect_category(title="boAt Rockerz 450 Bluetooth Headphones") == "headphones"
    assert detect_category(title="Nike Air Jordan Shoes") == "shoes"
    assert detect_category(title="L'Oreal Paris Total Repair Shampoo") == "shampoo"
    assert detect_category(title="Prestige Induction Cooktop Pan") == "kitchen"
