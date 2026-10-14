"""
scrapers/gececom_scraper.py
===========================
Dedicated GEC ECom Direct Online Marketplace Scraper Adapter.
Integrates GEC ECom as the 4th major e-commerce provider alongside
Amazon India, Flipkart, and Meesho within the SmartBuy platform comparison engine.
"""

import time
import logging
from typing import Optional, Dict, Any, List

from scrapers.base_scraper import BaseScraper
from scrapers.scraper_result import ScrapeStatus
from scrapers.common_schema import validate_and_build_product
from database import get_all_gececom_products, get_gececom_product_by_id, search_gececom_products

logger = logging.getLogger("smartbuy.scrapers.gececom")


class GecEcomScraper(BaseScraper):
    """
    Adapter integrating GEC ECom Direct Storefront into SmartBuy's multi-platform engine.
    """

    def __init__(self):
        super().__init__("gececom")
        self.max_results = 20

    def search_products(self, query: str) -> tuple[list[dict], ScrapeStatus, Optional[str]]:
        start_time = time.time()
        clean_query = (query or "").strip().lower()

        if not clean_query:
            return [], ScrapeStatus.NO_RESULTS, "Empty search query"

        try:
            # 1. Fetch matching items from database
            matched_raw = search_gececom_products(clean_query)

            # If no direct match, check if broad query matches catalog
            if not matched_raw:
                all_prods = get_all_gececom_products()
                q_words = set(clean_query.split())
                for p in all_prods:
                    title_words = set((p.get("product_name") or "").lower().split())
                    if q_words.intersection(title_words) or p.get("category", "").lower() in clean_query:
                        matched_raw.append(p)

            if not matched_raw:
                return [], ScrapeStatus.NO_RESULTS, "No GEC ECom products matching query"

            # 2. Normalize into SmartBuy authoritative 37-field schema
            normalized_items = []
            for item in matched_raw[:self.max_results]:
                p_id = str(item.get("id") or item.get("_id") or "")
                price_val = int(item.get("current_price") or item.get("price") or 0)
                orig_val = int(item.get("original_price") or price_val)

                raw_dict = {
                    "platform": "gececom",
                    "product_id": f"gec_{p_id}",
                    "product_url": f"/gececom#product-{p_id}",
                    "title": item.get("product_name") or "GEC ECom Product",
                    "price_num": price_val,
                    "price": f"₹{price_val:,}",
                    "mrp_num": orig_val,
                    "mrp": f"₹{orig_val:,}",
                    "rating": float(item.get("rating", 4.3)),
                    "review_count": int(item.get("reviews_count", 150)),
                    "image": item.get("product_image") or "",
                    "category": item.get("category") or "mobiles",
                    "seller": "GEC Direct Store",
                    "seller_rating": 4.9,
                    "availability": "In Stock",
                    "condition": "Brand New with Direct Warranty",
                    "source": "live",
                    "verified_live": True,
                    "warranty": "1 Year Official Direct Brand Warranty",
                    "return_policy": "7 Days Easy Replacement & Refund",
                    "specifications": {
                        "Warranty": "1 Year Manufacturer",
                        "Delivery": "Express Free Delivery Across India",
                        "Store": "GEC ECom Verified Direct"
                    }
                }

                prod = validate_and_build_product(raw_dict, platform="gececom")
                prod["platform_display"] = "GEC ECom"
                prod["platform_badge"] = "GEC Direct"
                normalized_items.append(prod)

            return normalized_items, ScrapeStatus.SUCCESS, None

        except Exception as e:
            logger.error(f"[GEC ECOM] Search exception: {e}")
            return [], ScrapeStatus.SCRAPER_ERROR, str(e)

    def get_product_details(self, url: str) -> Optional[dict]:
        try:
            if "#product-" in url:
                pid = url.split("#product-")[-1].strip()
                item = get_gececom_product_by_id(pid)
                if item:
                    return self.search_products(item.get("product_name", ""))[0][0]
        except Exception:
            pass
        return None

    def extract_product_data(self, element) -> Optional[dict]:
        """Extract product data from raw dictionary or element representation."""
        if isinstance(element, dict):
            return element
        return None

