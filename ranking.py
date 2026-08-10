"""
ranking.py
==========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Top-level export for ranking, scoring, and badge annotation module.
Delegates to search.ranking package.
"""

from search.ranking import (
    rank_products,
    annotate_badges,
    generate_sort_views,
)

__all__ = [
    "rank_products",
    "annotate_badges",
    "generate_sort_views",
]
