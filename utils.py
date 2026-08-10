"""
utils.py
========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Utility module containing common helper functions:
- Numeric price parsing
- String sanitization & normalization
- Logging setup
- Standard error response formatters
"""

import re
import logging

# Configure logger
logger = logging.getLogger("smartbuy.utils")
logging.basicConfig(level=logging.INFO)


def parse_price(text) -> int | None:
    """
    Extract numeric integer price from a raw string or integer input.
    Examples: '₹1,299' -> 1299, '1299.00' -> 1299
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    
    s = str(text).strip()
    # Remove trailing decimals like .00 or .50
    s = re.sub(r'\.\d{2}$', '', s)
    digits = re.sub(r'[^\d]', '', s)
    return int(digits) if digits else None


def clean_text(text: str) -> str:
    """
    Sanitize text input by removing HTML tags, extra whitespace, and control chars.
    """
    if not text:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]*>', '', str(text))
    # Replace multiple spaces/newlines with single space
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def format_platform_error(platform: str, error_detail: str = "") -> dict:
    """
    Generate a standardized error dictionary for a failed platform scraper.
    """
    msg = f"{platform} temporarily unavailable"
    if error_detail:
        logger.error(f"[{platform}] Error: {error_detail}")
    else:
        logger.error(f"[{platform}] Scraper failed or returned no data.")
        
    return {
        "platform": platform,
        "available": False,
        "error": msg,
        "items": []
    }
