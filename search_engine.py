"""
search_engine.py
================
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Core Search Engine Orchestrator:
- Parallel fetching across Amazon, Flipkart, and Meesho via ThreadPoolExecutor
- Per-platform status tracking & failure isolation
- Platform-isolated caching with ?fresh=1 bypass
- Processing pipeline: Relevance filtering, Canonical matching, Specification matrix, Best Deal
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple

# ── Scrapers ──────────────────────────────────────────────────────────────
from scrapers.amazon_scraper import AmazonScraper
from scrapers.flipkart_scraper import FlipkartScraper
from scrapers.meesho_scraper import MeeshoScraper

# ── Processing Package ───────────────────────────────────────────────────
from search.normalizer import normalize_query, detect_query_type
from search.matching import (
    calculate_similarity,
    get_adaptive_threshold,
    deduplicate_products,
    is_relevant,
)
from search.ranking import rank_products, annotate_badges, generate_sort_views
from search.filters import extract_filters_from_results, apply_filters
from search.specs_extractor import extract_specs
from ai_compare import get_ai_comparison, get_best_deals
from cache import get_platform_cached_results, set_platform_cached_results

from scrapers.scraper_logger import log_scraper_event

logger = logging.getLogger("smartbuy.search_engine")
logging.basicConfig(level=logging.INFO)

import os

PLATFORM_TIMEOUTS = {
    "amazon": int(os.getenv("AMAZON_TIMEOUT_SEC", "35")),
    "flipkart": int(os.getenv("FLIPKART_TIMEOUT_SEC", "25")),
    "meesho": int(os.getenv("MEESHO_TIMEOUT_SEC", "35")),
}

_scrapers_instances = {
    "Amazon": AmazonScraper(),
    "Flipkart": FlipkartScraper(),
    "Meesho": MeeshoScraper(),
}


def log_pipeline_diagnostic(
    user_input: str,
    input_type: str,
    detected_platform: Optional[str],
    url_normalization: Optional[str],
    scraper_selected: str,
    platform_status: Dict[str, Any],
    raw_results: Dict[str, Any],
    category: str,
    validated_products: List[Any],
    best_deal: Optional[Dict[str, Any]]
):
    """Logs the standardized SmartBuy verification pipeline trace per Section 22."""
    best_prod_name = best_deal.get('title') or best_deal.get('product_name') if best_deal else "N/A"
    best_q_score = best_deal.get('quality_score') if best_deal else "N/A"

    logger.info("=" * 60)
    logger.info("[SMARTBUY PIPELINE TRACE]")
    logger.info(f"USER INPUT: {user_input}")
    logger.info(f"INPUT TYPE: {input_type}")
    logger.info(f"DETECTED PLATFORM: {detected_platform or 'All Platforms (Product Search)'}")
    logger.info(f"URL NORMALIZATION: {url_normalization or 'N/A'}")
    logger.info(f"SCRAPER SELECTED: {scraper_selected}")
    for p_name, stat in platform_status.items():
        p_items = raw_results.get(p_name, [])
        first_item = p_items[0] if p_items else {}
        first_img = first_item.get('image_url') or first_item.get('image') or 'None'
        first_specs = len(first_item.get('specifications') or {}) if isinstance(first_item, dict) else 0
        p_stat_val = stat.get('status', 'unknown')
        logger.info(f"[{p_name.upper()}] Status: {p_stat_val.upper()} | Items: {len(p_items)} | Raw Title: '{first_item.get('title', 'N/A')[:40]}' | Image: {first_img[:50]}... | Specs: {first_specs}")
        if p_stat_val in ('timeout', 'blocked', 'scraper_error'):
            logger.warning(f"[{p_name.upper()}] Request: FAILED | Reason: {stat.get('error', p_stat_val)} | Final status: {p_stat_val.upper()}")
    logger.info(f"CATEGORY DETECTION: {category}")
    logger.info(f"PRODUCT MATCHING: {len(validated_products)} products validated")
    logger.info(f"COMPARISON: Complete")
    logger.info(f"QUALITY SCORE: {best_q_score} (Best Deal: '{best_prod_name[:40]}')")
    logger.info(f"FRONTEND: READY")
    logger.info("=" * 60)


def fetch_all_products_parallel(query: str, bypass_fresh: bool = False) -> tuple[dict, dict]:
    """
    Fetch products from Amazon, Flipkart, and Meesho in parallel.
    Platform failures are completely isolated — if one fails, others continue.
    Uses platform-isolated caching when bypass_fresh is False.
    """
    logger.info(f"[SEARCH] Starting parallel multi-platform search for '{query}' (fresh={bypass_fresh})...")

    raw_results = {name: [] for name in _scrapers_instances}
    platform_status = {
        name: {
            "platform": name,
            "status": "unavailable",
            "available": False,
            "error": None,
            "count": 0,
            "duration": 0.0,
            "source": "live",
            "retry_available": True
        } for name in _scrapers_instances
    }

    platforms_to_scrape = {}

    # 1. Check Platform-Isolated Cache
    for name in _scrapers_instances:
        if not bypass_fresh:
            cached_entry = get_platform_cached_results(name, query, bypass_fresh=False)
            if cached_entry and cached_entry.get("results"):
                items = cached_entry["results"]
                raw_results[name] = items
                platform_status[name]["platform"] = name
                platform_status[name]["available"] = True
                platform_status[name]["count"] = len(items)
                platform_status[name]["status"] = cached_entry.get("scrape_status", "success")
                platform_status[name]["source"] = "cache"
                platform_status[name]["retry_available"] = False
                logger.info(f"[{name.upper()}] Loaded {len(items)} items from platform cache")
                continue

        platforms_to_scrape[name] = _scrapers_instances[name]

    if not platforms_to_scrape:
        return raw_results, platform_status

    def _execute_scraper(name, scraper_obj, q):
        start = time.time()
        try:
            items, status, err_msg = scraper_obj.search_products(q)
            dur = round(time.time() - start, 2)
            stat_val = status.value if hasattr(status, "value") else str(status)
            return name, items, stat_val, err_msg, "live", dur
        except Exception as err:
            dur = round(time.time() - start, 2)
            logger.exception(f"[{name}] Scraper execution exception: {err}")
            return name, [], "scraper_error", str(err), "live", dur

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_platform = {
            executor.submit(_execute_scraper, name, obj, query): name
            for name, obj in platforms_to_scrape.items()
        }

        for future in as_completed(future_to_platform):
            platform = future_to_platform[future]
            p_timeout = PLATFORM_TIMEOUTS.get(platform.lower(), 35)
            try:
                p_name, items, status_code, err_msg, src, dur = future.result(timeout=p_timeout)
                raw_results[p_name] = items or []
                platform_status[p_name]["platform"] = p_name
                platform_status[p_name]["count"] = len(items or [])
                platform_status[p_name]["available"] = bool(items)
                platform_status[p_name]["status"] = status_code if items else (status_code if status_code != "success" else "no_products_found")
                platform_status[p_name]["error"] = err_msg
                platform_status[p_name]["duration"] = dur
                platform_status[p_name]["source"] = src
                platform_status[p_name]["retry_available"] = not bool(items)

                # Store in isolated platform cache if items were found
                if items:
                    set_platform_cached_results(p_name, query, items, status_code)

                log_scraper_event(p_name, query, status_code, retry=0, products_count=len(items or []), duration=dur)
                logger.info(f"[{p_name.upper()}] source={src} status={status_code} products={len(items or [])} duration={dur}s")
            except TimeoutError:
                logger.error(f"[{platform.upper()}] Scraper timed out after configured limit ({p_timeout}s).")
                raw_results[platform] = []
                platform_status[platform]["platform"] = platform
                platform_status[platform]["status"] = "timeout"
                platform_status[platform]["available"] = False
                platform_status[platform]["error"] = f"Request timed out after {p_timeout}s"
                platform_status[platform]["retry_available"] = True
                log_scraper_event(platform, query, "timeout", retry=0, products_count=0, error=f"{platform} request timed out")
            except Exception as e:
                logger.error(f"[{platform.upper()}] Scraper execution exception: {e}")
                raw_results[platform] = []
                platform_status[platform]["platform"] = platform
                platform_status[platform]["status"] = "scraper_error"
                platform_status[platform]["available"] = False
                platform_status[platform]["error"] = str(e)
                platform_status[platform]["retry_available"] = True
                log_scraper_event(platform, query, "scraper_error", retry=0, products_count=0, error=str(e))

    return raw_results, platform_status


def fetch_single_platform(platform_name: str, query: str, bypass_fresh: bool = True) -> tuple[list, dict]:
    """
    Fetch products for a single platform independently for retry or on-demand refresh.
    Returns: (items_list, platform_status_dict)
    """
    clean_name = None
    for name in _scrapers_instances:
        if name.lower() == platform_name.strip().lower():
            clean_name = name
            break
    if not clean_name:
        return [], {
            "platform": platform_name,
            "status": "error",
            "available": False,
            "count": 0,
            "error": f"Unknown platform '{platform_name}'",
            "retry_available": False
        }

    # Check cache if not bypass_fresh
    if not bypass_fresh:
        cached_entry = get_platform_cached_results(clean_name, query, bypass_fresh=False)
        if cached_entry and cached_entry.get("results"):
            items = cached_entry["results"]
            stat = cached_entry.get("scrape_status", "success")
            return items, {
                "platform": clean_name,
                "status": stat,
                "available": True,
                "count": len(items),
                "error": None,
                "duration": 0.0,
                "source": "cache",
                "retry_available": False
            }

    scraper_obj = _scrapers_instances[clean_name]
    start = time.time()
    try:
        items, status, err_msg = scraper_obj.search_products(query)
        dur = round(time.time() - start, 2)
        stat_val = status.value if hasattr(status, "value") else str(status)
        final_stat = stat_val if items else (stat_val if stat_val != "success" else "no_products_found")
        if items:
            set_platform_cached_results(clean_name, query, items, stat_val)
        return items or [], {
            "platform": clean_name,
            "status": final_stat,
            "available": bool(items),
            "count": len(items or []),
            "error": err_msg,
            "duration": dur,
            "source": "live",
            "retry_available": not bool(items)
        }
    except Exception as err:
        dur = round(time.time() - start, 2)
        logger.exception(f"[{clean_name}] Single platform search exception: {err}")
        return [], {
            "platform": clean_name,
            "status": "scraper_error",
            "available": False,
            "count": 0,
            "error": str(err),
            "duration": dur,
            "source": "live",
            "retry_available": True
        }


def fetch_all_products_with_fallbacks(query_chain: list[str], bypass_fresh: bool = False) -> tuple[dict, dict]:
    """
    Execute scraper search with automatic fallback loop:
    Try query_chain[0] broad query across Amazon, Flipkart, Meesho.
    """
    combined_raw = {"Amazon": [], "Flipkart": [], "Meesho": []}
    combined_status = {
        "Amazon": {"available": False, "error": None, "count": 0, "status": "unavailable"},
        "Flipkart": {"available": False, "error": None, "count": 0, "status": "unavailable"},
        "Meesho": {"available": False, "error": None, "count": 0, "status": "unavailable"},
    }

    if not query_chain:
        query_chain = ['Products']

    for idx, q in enumerate(query_chain):
        logger.info(f"Search Stage {idx+1}/{len(query_chain)} using query: '{q}'")
        raw_res, status = fetch_all_products_parallel(q, bypass_fresh=bypass_fresh)

        total_items = sum(len(items) for items in raw_res.values())

        for platform, items in raw_res.items():
            if items:
                combined_raw[platform].extend(items)
                combined_status[platform]["available"] = True
                combined_status[platform]["count"] = len(combined_raw[platform])
                combined_status[platform]["status"] = status.get(platform, {}).get("status", "success")
            else:
                combined_status[platform]["status"] = status.get(platform, {}).get("status", "unavailable")
                combined_status[platform]["error"] = status.get(platform, {}).get("error")

        if total_items >= 3 or idx == len(query_chain) - 1:
            break

    return combined_raw, combined_status


def process_results(query: str, raw_results: dict,
                    filter_params: Optional[dict] = None,
                    platform_status: Optional[dict] = None) -> dict:
    """
    Full product comparison pipeline:
        raw items → similarity filter → spec extraction → deduplication → match scoring → ranking → badges
    """
    if platform_status is None:
        platform_status = {
            p: {"available": bool(items), "error": None, "count": len(items), "status": "success" if items else "no_products_found"}
            for p, items in raw_results.items()
        }

    from search.category_detector import detect_category
    from search.pipeline import run_comparison_pipeline

    detected_cat = detect_category(query=query)
    logger.info(f"[PIPELINE] Executing Single Source of Truth pipeline for query: '{query}' | Category: '{detected_cat}'")

    pipeline_data = run_comparison_pipeline(
        query=query,
        raw_platform_results=raw_results,
        platform_status=platform_status
    )

    platform_results = pipeline_data["validated_by_platform"]
    all_matched = pipeline_data["validated_products"]

    # Upsert validated products to database
    try:
        from database import upsert_normalized_product
        for it in all_matched:
            upsert_normalized_product(it, query=query)
    except Exception:
        pass

    # Apply Match Scoring & Ranking if filters provided
    if filter_params:
        from search.filters import score_and_rank_products
        for platform in platform_results:
            platform_results[platform] = score_and_rank_products(
                platform_results[platform], filter_params, raw_q=query
            )
        all_matched = score_and_rank_products(all_matched, filter_params, raw_q=query)
    else:
        from search.ranking import rank_products
        for platform in platform_results:
            platform_results[platform] = rank_products(platform_results[platform])
        all_matched = rank_products(all_matched)

    # Badges & Views
    annotate_badges(platform_results)
    from search.ranking import get_summary_badges
    summary_badges = get_summary_badges(all_matched)
    sort_views = generate_sort_views(all_matched)

    all_raw_for_filters = [item for items in raw_results.values() for item in items]
    dynamic_filters = extract_filters_from_results(all_raw_for_filters)

    top_verified_offers = pipeline_data["top_verified_offers"]
    specifications_matrix = pipeline_data["specifications_matrix"]
    quality_comparison_table = pipeline_data.get("quality_comparison_table", [])
    comparison_summary = pipeline_data.get("comparison_summary", {})
    best_deal = pipeline_data["best_deal"]
    overall_best = best_deal
    savings_info = pipeline_data["savings_info"]
    match_pairs = pipeline_data["match_pairs"]
    marketplace_status = pipeline_data.get("marketplace_status", {})

    best_match_per_platform = pipeline_data["best_match_per_platform"]
    best_per_platform = {
        "Amazon": best_match_per_platform.get("Amazon"),
        "Flipkart": best_match_per_platform.get("Flipkart"),
        "Meesho": best_match_per_platform.get("Meesho"),
    }

    ai_summary = get_ai_comparison(query, platform_results)

    platforms_payload = {
        "amazon": {
            "status": platform_status.get("Amazon", {}).get("status", "success"),
            "products": platform_results.get("Amazon", [])
        },
        "flipkart": {
            "status": platform_status.get("Flipkart", {}).get("status", "success"),
            "products": platform_results.get("Flipkart", [])
        },
        "meesho": {
            "status": platform_status.get("Meesho", {}).get("status", "success"),
            "products": platform_results.get("Meesho", [])
        }
    }

    amz_prod = best_match_per_platform.get("Amazon")
    fk_prod = best_match_per_platform.get("Flipkart")
    mee_prod = best_match_per_platform.get("Meesho")

    log_pipeline_diagnostic(
        user_input=query,
        input_type="Product Name",
        detected_platform=None,
        url_normalization=None,
        scraper_selected="Multi-Platform Search (Amazon, Flipkart, Meesho)",
        platform_status=platform_status,
        raw_results=raw_results,
        category=detected_cat,
        validated_products=all_matched,
        best_deal=best_deal
    )

    comparison = {
        "query": query,
        "matched_products": [p for p in best_match_per_platform.values() if p],
        "specifications": specifications_matrix,
        "has_match": pipeline_data["has_cross_platform_match"],
        "best_deal": best_deal,
        "amazon": amz_prod,
        "flipkart": fk_prod,
        "meesho": mee_prod,
        "Amazon": amz_prod,
        "Flipkart": fk_prod,
        "Meesho": mee_prod,
        "specification_table": {
            "has_match": pipeline_data["has_cross_platform_match"],
            "rows": specifications_matrix,
            "columns": ["specification", "amazon", "flipkart", "meesho"]
        },
        "quality_comparison_table": quality_comparison_table,
        "comparison_summary": comparison_summary,
        "match_pairs": match_pairs,
        "products": {
            "amazon": platform_results.get("Amazon", []),
            "flipkart": platform_results.get("Flipkart", []),
            "meesho": platform_results.get("Meesho", [])
        }
    }

    return {
        "query":                 query,
        "platforms":             platforms_payload,
        "comparison":            comparison,
        "platform_results":      platform_results,
        "platform_status":       platform_status,
        "all_results":           all_matched,
        "validated_products":    all_matched,
        "sort_views":            sort_views,
        "summary_badges":        summary_badges,
        "dynamic_filters":       dynamic_filters,
        "best_per_platform":     best_per_platform,
        "overall_best":          overall_best,
        "ai_summary":            ai_summary,
        "top_verified_offers":   top_verified_offers,
        "top_prices_data":       top_verified_offers,
        "top_prices":            top_verified_offers,
        "best_overall_deal":     overall_best,
        "savings_info":          savings_info,
        "comparison_data":       comparison,
        "specification_table":   comparison.get("specification_table", {}),
        "specifications_matrix": specifications_matrix,
        "quality_comparison_table": quality_comparison_table,
        "comparison_summary":    comparison_summary,
        "marketplace_status":    marketplace_status,
        "best_deal":             best_deal,
        "match_pairs":           match_pairs,
        "has_cross_platform_match": pipeline_data.get("has_cross_platform_match", False),
        "detected_category":     detected_cat
    }
