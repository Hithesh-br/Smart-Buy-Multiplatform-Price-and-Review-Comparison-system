"""
search/meesho_service.py
========================
Authoritative Meesho Data Pipeline for SmartBuy.
Integrates with the modular scrapers.meesho architecture:
- Method 1: Configured Third-Party / Partner API
- Method 2: Direct HTTP / JSON-LD extraction
- Method 3: Playwright Browser Scraper
- Method 4: Graceful Empty Result (with accurate status classification)

Never uses fake or dummy product data.
Every product adheres to SmartBuy's canonical normalized schema.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from scrapers.meesho.meesho_search import MeeshoSearch
from scrapers.meesho.meesho_normalizer import normalize_meesho_product
from scrapers.meesho.meesho_parser import extract_title_from_slug

logger = logging.getLogger("smartbuy.meesho_service")
_search_instance = MeeshoSearch()


def search_meesho(query: str, limit: int = 12, return_details: bool = False) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    """
    Primary Meesho data access function for SmartBuy search pipeline.
    Returns:
        tuple (products: list[dict], status_code: str, error_message: Optional[str])
    """
    clean_query = query.strip()
    if not clean_query:
        return [], "no_results", "Empty search query"

    logger.info(f"[MEESHO] Starting multi-layer pipeline for query: '{clean_query}' (limit={limit})...")
    items, status_str, err_msg = _search_instance.search(clean_query, limit=limit)

    if items:
        logger.info(f"[MEESHO] Pipeline SUCCESS – retrieved {len(items)} normalized products")
        return items, "success", None

    logger.warning(f"[MEESHO] Pipeline finished with status={status_str}, error={err_msg}")
    return [], status_str, err_msg
