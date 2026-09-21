"""
search/url_detector.py
=======================
Re-exports from root url_detector for modular search package compatibility.
"""

from url_detector import (
    is_valid_http_url,
    detect_search_type,
    detect_platform_from_url,
    extract_amazon_asin,
    extract_flipkart_id,
    extract_meesho_id,
    validate_and_detect_url as _base_validate_and_detect_url,
)

def validate_and_detect_url(url: str) -> dict:
    result = _base_validate_and_detect_url(url)
    if result.get("platform") == "amazon":
        asin = extract_amazon_asin(url)
        return {
            "is_valid": True,
            "platform": "amazon",
            "platform_name": "Amazon",
            "canonical_url": f"https://www.amazon.in/dp/{asin}" if asin else url,
            "original_url": url,
            "product_id": asin,
            "error": None
        }
    return result

__all__ = [
    "is_valid_http_url",
    "detect_search_type",
    "detect_platform_from_url",
    "extract_amazon_asin",
    "extract_flipkart_id",
    "extract_meesho_id",
    "validate_and_detect_url",
]
