"""
SmartBuy Search Package
=======================
Modular search engine for universal product discovery across
Amazon, Flipkart, and Meesho.
"""

from search.normalizer import (
    detect_category,
    normalize_query,
    normalize_title,
    normalize_brand,
    normalize_model,
    normalize_weight,
    normalize_pack_quantity,
    normalize_price,
    normalize_rating,
    normalize_review_count,
)

__all__ = [
    "detect_category",
    "normalize_query",
    "normalize_title",
    "normalize_brand",
    "normalize_model",
    "normalize_weight",
    "normalize_pack_quantity",
    "normalize_price",
    "normalize_rating",
    "normalize_review_count",
]
