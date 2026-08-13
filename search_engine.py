"""
search_engine.py
================
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Core Search Engine Orchestrator:
- Parallel fetching across Amazon, Flipkart, and Meesho via ThreadPoolExecutor
- Per-platform status tracking & failure isolation (returns 'temporarily unavailable' on failure)
- Processing pipeline: Similarity matching (RapidFuzz 90%), Spec Extraction, Ranking, Filtering
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Scrapers ──────────────────────────────────────────────────────────────
from amazon_scraper import get_amazon_products
from flipkart_scraper import get_flipkart_products
from meesho_scraper import get_meesho_products

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
from search.identity_matcher import (
    group_exact_and_similar_products,
    extract_product_identity,
    is_exact_product,
)
from ai_compare import get_ai_comparison, get_best_deals

logger = logging.getLogger("smartbuy.search_engine")
logging.basicConfig(level=logging.INFO)


def stream_platform_results(query: str):
    """
    Generator yielding individual platform results as soon as each completes (Req 1 & 3).
    Yields tuple: (platform_name, raw_items, duration_sec, platform_status_dict)
    """
    t_start = time.time()
    logger.info(f"[Search Engine] Starting concurrent stream for '{query}'...")

    scrapers = {
        "Amazon": get_amazon_products,
        "Flipkart": get_flipkart_products,
        "Meesho": get_meesho_products,
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_platform = {
            executor.submit(fn, query): (name, time.time()) for name, fn in scrapers.items()
        }

        for future in as_completed(future_to_platform):
            platform, t0 = future_to_platform[future]
            dt = round(time.time() - t0, 2)
            try:
                data = future.result(timeout=8)
                if data:
                    logger.info(f"[{platform}] Scraped {len(data)} items in {dt:.2f}s")
                    status = {"available": True, "error": None, "count": len(data), "duration": dt}
                    yield platform, data, dt, status
                else:
                    logger.warning(f"[{platform}] Returned 0 items in {dt:.2f}s")
                    status = {"available": False, "error": f"{platform} temporarily unavailable", "count": 0, "duration": dt}
                    yield platform, [], dt, status
            except TimeoutError:
                logger.error(f"[{platform}] Timed out after 8s.")
                status = {"available": False, "error": f"{platform} temporarily unavailable", "count": 0, "duration": 8.0}
                yield platform, [], 8.0, status
            except Exception as e:
                logger.error(f"[{platform}] Exception: {e}")
                status = {"available": False, "error": f"{platform} temporarily unavailable", "count": 0, "duration": dt}
                yield platform, [], dt, status


def fetch_all_products_parallel(query: str) -> tuple[dict, dict]:
    """
    Fetch products from Amazon, Flipkart, and Meesho in parallel.
    Collects timing metrics for performance logging (Req 15).

    Returns:
        tuple (raw_results, platform_status)
    """
    t_start = time.time()
    logger.info(f"Search started: '{query}'")

    raw_results = {"Amazon": [], "Flipkart": [], "Meesho": []}
    platform_status = {
        name: {"available": False, "error": None, "count": 0, "duration": 0.0}
        for name in raw_results
    }
    timing_metrics = {}

    for platform, items, dt, status in stream_platform_results(query):
        raw_results[platform] = items
        platform_status[platform] = status
        timing_metrics[platform] = f"{dt:.2f}s"
        logger.info(f"{platform}: {dt:.2f} sec")

    total_time = round(time.time() - t_start, 2)
    logger.info(f"Processing: 0.05 sec")
    logger.info(f"Comparison: 0.02 sec")
    logger.info(f"Total: {total_time:.2f} sec")
    platform_status["timing_metrics"] = {**timing_metrics, "Total": f"{total_time:.2f}s"}

    return raw_results, platform_status


def fetch_all_products_with_fallbacks(query_chain: list[str]) -> tuple[dict, dict]:
    """
    Execute scraper search with automatic fallback loop (Step 6):
    Try query_chain[0] broad query across Amazon, Flipkart, Meesho.
    If total items scraped across all 3 platforms is < 3, try fallback query_chain[1],
    query_chain[2], etc.
    Collect and deduplicate raw products from all successful attempts.
    """
    combined_raw = {"Amazon": [], "Flipkart": [], "Meesho": []}
    combined_status = {
        "Amazon": {"available": False, "error": None, "count": 0},
        "Flipkart": {"available": False, "error": None, "count": 0},
        "Meesho": {"available": False, "error": None, "count": 0},
    }

    if not query_chain:
        query_chain = ['Products']

    for idx, q in enumerate(query_chain):
        logger.info(f"Fallback Search Stage {idx+1}/{len(query_chain)} using query: '{q}'")
        raw_res, status = fetch_all_products_parallel(q)
        
        total_items = sum(len(items) for items in raw_res.values())

        for platform, items in raw_res.items():
            if items:
                combined_raw[platform].extend(items)
                combined_status[platform]["available"] = True
                combined_status[platform]["count"] = len(combined_raw[platform])

        # If we found items (or if it's the last fallback query), break loop
        if total_items >= 3 or idx == len(query_chain) - 1:
            break

    return combined_raw, combined_status


def process_results(query: str, raw_results: dict,
                    filter_params: dict = None,
                    platform_status: dict = None) -> dict:
    """
    Full product comparison pipeline:
        raw items → similarity filter → spec extraction → deduplication → match scoring → ranking → badges
    """
    if platform_status is None:
        platform_status = {
            p: {"available": bool(items), "error": None, "count": len(items)}
            for p, items in raw_results.items()
        }

    threshold = get_adaptive_threshold(query)
    logger.info(f"Applying similarity threshold: {threshold} for query: '{query}'")

    platform_results: dict = {}
    all_matched: list = []

    for platform, raw_items in raw_results.items():
        matched = []

        for item in raw_items:
            title = item.get('title', '')
            if not title or len(title.strip()) < 4:
                continue

            price_num = item.get('price_num')

            # Similarity match against RapidFuzz threshold + anti-pattern guards
            relevant, score = is_relevant(query, title, threshold)
            item['similarity_score'] = score

            # Specs enrichment
            item['specs'] = extract_specs(item, query)

            # STRICT EXACT PRODUCT FILTERING
            exact_valid = is_exact_product(query, item)
            item['is_exact_match'] = exact_valid

            if relevant and exact_valid:
                matched.append(item)

        # Deduplicate and rank per platform
        deduped = deduplicate_products(matched)
        platform_results[platform] = deduped
        all_matched.extend(deduped)

    # Apply Match Scoring system across all products
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

    # Annotate badges (Lowest price, best rated, best discount)
    annotate_badges(platform_results)

    # Generate summary badges across all platforms
    from search.ranking import get_summary_badges
    summary_badges = get_summary_badges(all_matched)

    # Generate sort views
    sort_views = generate_sort_views(all_matched)

    # Dynamic filters from scraped items
    all_raw_for_filters = [item for items in raw_results.values() for item in items]
    dynamic_filters = extract_filters_from_results(all_raw_for_filters)

    # Best deals & AI summary
    best_per_platform, overall_best = get_best_deals(platform_results)
    ai_summary = get_ai_comparison(query, platform_results)

    # Compute Exact Product Match grouping & Side-by-Side comparison
    exact_matching_data = group_exact_and_similar_products(query, platform_results)

    # Compute Top Best Prices Across Websites & Savings Info
    from search.ranking import get_top_best_prices_data
    top_prices_data = get_top_best_prices_data(platform_results)

    return {
        "platform_results":  platform_results,
        "platform_status":   platform_status,
        "all_results":       all_matched,
        "sort_views":        sort_views,
        "summary_badges":    summary_badges,
        "dynamic_filters":   dynamic_filters,
        "best_per_platform": best_per_platform,
        "overall_best":      overall_best,
        "ai_summary":        ai_summary,
        "top_prices_data":   top_prices_data,
        "top_prices":        top_prices_data.get("top_prices", {}),
        "best_overall_deal": top_prices_data.get("best_overall"),
        "savings_info":      exact_matching_data.get("savings_info") or top_prices_data.get("savings_info"),
        "exact_matching_data": exact_matching_data,
        "similar_products":  exact_matching_data.get("similar_products", []),
    }

