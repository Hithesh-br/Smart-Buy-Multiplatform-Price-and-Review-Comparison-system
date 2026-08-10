"""
cache.py
========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
In-memory caching module using cachetools.TTLCache (1-hour TTL).
Caches parsed multi-platform search results to make repeated queries instant.
"""

import logging
from cachetools import TTLCache

logger = logging.getLogger("smartbuy.cache")

# 1-Hour TTL Cache with max size of 200 search queries
_SEARCH_CACHE = TTLCache(maxsize=200, ttl=3600)


def get_cached_search(cache_key: str):
    """
    Retrieve cached search data if available and not expired.
    Returns None if cache miss.
    """
    if cache_key in _SEARCH_CACHE:
        logger.info(f"Cache HIT for key: {cache_key[:60]}...")
        return _SEARCH_CACHE[cache_key]
    return None


def set_cached_search(cache_key: str, data: dict):
    """
    Store search result data in the TTL cache.
    """
    if cache_key and data:
        _SEARCH_CACHE[cache_key] = data
        logger.info(f"Cache STORE for key: {cache_key[:60]}...")


def clear_cache():
    """Clear all items from the search cache."""
    _SEARCH_CACHE.clear()
    logger.info("Search cache cleared.")
