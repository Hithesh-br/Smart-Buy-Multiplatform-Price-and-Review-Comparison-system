"""
filters.py
==========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Top-level export for dynamic filtering module.
Delegates to search.filters package.
"""

from search.filters import (
    extract_filters_from_results,
    apply_filters,
    parse_filter_params,
)

__all__ = [
    "extract_filters_from_results",
    "apply_filters",
    "parse_filter_params",
]
