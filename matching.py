"""
matching.py
===========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Top-level export for matching and similarity scoring module.
Delegates to search.matching package.
"""

from search.matching import (
    calculate_similarity,
    get_adaptive_threshold,
    deduplicate_products,
    cross_platform_deduplicate,
    is_relevant,
    THRESHOLDS,
)

__all__ = [
    "calculate_similarity",
    "get_adaptive_threshold",
    "deduplicate_products",
    "cross_platform_deduplicate",
    "is_relevant",
    "THRESHOLDS",
]
