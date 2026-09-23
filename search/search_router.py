"""
search/search_router.py
=======================
SmartBuy Unified Search Router.

Automatically detects search input type:
- "product_name": Runs multi-platform keyword search pipeline across Amazon, Flipkart, Meesho.
- "product_url": Detects source platform, resolves short/share URLs (e.g. Flipkart dl.flipkart.com/s/...),
  extracts canonical product, searches other platforms, and returns 3-way specification comparison.

Provides:
- detect_search_type(query): Returns {"type": "product_name"} or {"type": "product_url", "platform": "..."}
- route_search(query, bypass_fresh, filters): Standardized execution payload for web routes and JSON APIs.
"""

import logging
from typing import Dict, Any, Optional

from url_detector import detect_search_type
from comparison_engine import compare_by_product_url
from search_engine import fetch_all_products_with_fallbacks, process_results

logger = logging.getLogger("smartbuy.search.router")


def route_search(
    query: str,
    bypass_fresh: bool = False,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Unified entry point for SmartBuy search.
    Automatically identifies whether input is a product name or a supported product URL,
    dispatching to the corresponding comparison pipeline.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        return {
            "search_type": "product_name",
            "success": False,
            "error": "Query cannot be empty",
            "products": {"amazon": [], "flipkart": [], "meesho": []},
            "matches": {"amazon": None, "flipkart": None, "meesho": None},
            "comparison": {"specifications": []},
            "best_deal": None
        }

    detection = detect_search_type(clean_query)
    logger.info(f"[SearchRouter] Query: '{clean_query[:80]}' -> Detection: {detection}")

    if detection["type"] == "product_url":
        target_url = detection.get("url") or clean_query
        comp_result = compare_by_product_url(target_url, fresh=bypass_fresh)

        matches = comp_result.get("matches", {})
        matrix = comp_result.get("specifications_matrix", [])
        best_deal = comp_result.get("best_deal")

        products = {
            "amazon": [matches["amazon"]] if matches.get("amazon") else [],
            "flipkart": [matches["flipkart"]] if matches.get("flipkart") else [],
            "meesho": [matches["meesho"]] if matches.get("meesho") else [],
        }

        return {
            "search_type": "product_url",
            "source_platform": comp_result.get("source_platform"),
            "source_platform_name": comp_result.get("source_platform_name"),
            "source_url": comp_result.get("source_url") or target_url,
            "source_product": comp_result.get("source_product"),
            "products": products,
            "matches": matches,
            "comparison": {
                "specifications": matrix,
                "rows": matrix,
                "columns": ["specification", "amazon", "flipkart", "meesho"]
            },
            "best_deal": best_deal,
            "platform_status": comp_result.get("platform_status", {}),
            "similar_products": comp_result.get("similar_products", {}),
            "quality_comparison_table": comp_result.get("quality_comparison_table", []),
            "comparison_summary": comp_result.get("comparison_summary", {}),
            "success": comp_result.get("success", True),
            "error": comp_result.get("error")
        }

    # Product Name text search
    raw_results, platform_status = fetch_all_products_with_fallbacks([clean_query], bypass_fresh=bypass_fresh)
    processed = process_results(clean_query, raw_results, filter_params=filters or {}, platform_status=platform_status)

    comparison_data = processed.get("comparison_data") or {}
    platform_res = processed.get("platform_results") or {}
    matrix = comparison_data.get("specifications") or processed.get("specifications_matrix") or []
    best_deal = processed.get("best_deal") or processed.get("best_overall_deal")

    amz_list = platform_res.get("Amazon") or []
    matched_amazon = comparison_data.get("amazon") or (amz_list[0] if amz_list else None)

    fk_list = platform_res.get("Flipkart") or []
    matched_flipkart = comparison_data.get("flipkart") or (fk_list[0] if fk_list else None)

    msh_list = platform_res.get("Meesho") or []
    matched_meesho = comparison_data.get("meesho") or (msh_list[0] if msh_list else None)

    return {
        "search_type": "product_name",
        "source_platform": None,
        "source_product": None,
        "query": clean_query,
        "products": {
            "amazon": platform_res.get("Amazon") or raw_results.get("Amazon", []),
            "flipkart": platform_res.get("Flipkart") or raw_results.get("Flipkart", []),
            "meesho": platform_res.get("Meesho") or raw_results.get("Meesho", []),
        },
        "matches": {
            "amazon": matched_amazon,
            "flipkart": matched_flipkart,
            "meesho": matched_meesho,
        },
        "comparison": {
            "specifications": matrix,
            "rows": matrix,
            "columns": ["specification", "amazon", "flipkart", "meesho"]
        },
        "best_deal": best_deal,
        "quality_comparison_table": processed.get("quality_comparison_table", comparison_data.get("quality_comparison_table", [])),
        "comparison_summary": processed.get("comparison_summary", comparison_data.get("comparison_summary", {})),
        "platform_status": platform_status,
        "success": True,
        "total_results": processed.get("total", 0)
    }
