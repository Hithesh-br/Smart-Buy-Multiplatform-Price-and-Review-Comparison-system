"""
search/ranking.py
=================
Multi-criteria product ranking and badge annotation.
Provides multiple sort views for the results page.
"""

import re
from typing import Optional, Dict, Any, List


def safe_number(val, default: float = 0.0) -> float:
    """Safely convert any numeric value, string, or None to float without raising errors."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        val_str = str(val).strip()
        if not val_str or val_str.upper() in ('N/A', 'NONE', 'NOT AVAILABLE', 'NULL', ''):
            return default
        clean_str = val_str.replace(',', '')
        m = re.search(r'(\d+(?:\.\d+)?)', clean_str)
        return float(m.group(1)) if m else default
    except (ValueError, TypeError):
        return default


def _parse_price_num(item: dict) -> int | None:
    """Extract numeric price from item dict, falling back to parsing price string."""
    pn = safe_number(item.get('price_num'), default=-1.0)
    if pn > 0:
        return int(pn)
    price_str = str(item.get('price', ''))
    digits = re.sub(r'[^\d]', '', price_str)
    return int(digits) if digits else None


def _parse_rating(item: dict) -> float:
    """Safely extract rating as float."""
    return safe_number(item.get('rating'))


def _parse_discount(item: dict) -> int:
    """Extract discount percentage as int (0 if unavailable)."""
    return int(safe_number(item.get('discount')))


def _parse_review_count(item: dict) -> int:
    """Extract review count as int."""
    return int(safe_number(item.get('reviews')))


def rank_products(products: list, query: str = "") -> list:
    """
    Quality-First Smart Ranking Algorithm:
      Priority 1: Specification-based quality score
      Priority 2: Feature completeness and evidence coverage
      Priority 3: Rating and review evidence (supporting social proof)
      Priority 4: Warranty, seller credibility, and availability
      Priority 5: Price and economic value for money (never beats higher quality)
    """
    if not products:
        return []

    def sort_key(item):
        # 1. Match status priority (Exact/Variant matches beat loose similar matches, rejected at bottom)
        status = str(item.get("match_status", "")).upper()
        if "EXACT" in status:
            m_score = 4
        elif "VARIANT" in status:
            m_score = 3
        elif "SIMILAR" in status:
            m_score = 2
        elif "REJECT" in status:
            m_score = 0
        else:
            m_score = 1

        # 2. Quality Score (Priority 1: Specification-based quality)
        has_suff = item.get("has_sufficient_data")
        raw_q = item.get("quality_score")
        if raw_q is None:
            raw_q = item.get("quality_report", {}).get("raw_quality_score") if isinstance(item.get("quality_report"), dict) else None
        q_val = safe_number(raw_q)
        if has_suff is False or q_val <= 0:
            q_val = -1.0  # Products with insufficient specs cannot outrank verified products

        # 3. Evidence Coverage / Feature Completeness (Priority 2)
        coverage = safe_number(item.get("evidence_coverage") or item.get("data_confidence"))

        # 4. Rating & Reviews (Priority 3: supporting evidence)
        rating = _parse_rating(item)
        reviews = _parse_review_count(item)

        # 5. Availability (Priority 4)
        avail = 1 if "in stock" in str(item.get("availability", "in stock")).lower() else 0

        # 6. Price (Priority 5: lower price is preferred among equivalent quality)
        price = _parse_price_num(item) or 9_999_999

        return (m_score, q_val, coverage, rating, reviews, avail, -price)

    sorted_list = sorted(products, key=sort_key, reverse=True)

    # Attach transparent ranking explanations
    if sorted_list:
        top_prod = sorted_list[0]
        top_q = safe_number(top_prod.get("quality_score"))
        top_cov = safe_number(top_prod.get("evidence_coverage") or top_prod.get("data_confidence"))
        top_p = _parse_price_num(top_prod) or 0

        for idx, item in enumerate(sorted_list):
            item_q = safe_number(item.get("quality_score"))
            item_cov = safe_number(item.get("evidence_coverage") or item.get("data_confidence"))
            item_p = _parse_price_num(item) or 0
            has_suff = item.get("has_sufficient_data", True)

            if idx == 0:
                if has_suff and item_q > 0:
                    item["rank_explanation"] = f"Ranked #1 based on superior verified specifications ({item_q:.0f}/100 quality score, {item_cov:.0f}% evidence coverage)."
                else:
                    item["rank_explanation"] = "Ranked #1 based on verified product match."
            else:
                if not has_suff:
                    item["rank_explanation"] = "Insufficient specification data for confident quality ranking."
                elif item.get("match_status") == "VARIANT_MATCH":
                    item["rank_explanation"] = "Not an identical match: different product variant or configuration."
                elif item_q < top_q and item_p < top_p:
                    item["rank_explanation"] = f"Lower price, but fewer verified specifications ({item_cov:.0f}% coverage vs {top_cov:.0f}%)."
                elif item_q < top_q:
                    item["rank_explanation"] = f"Lower specification quality score ({item_q:.0f}/100 vs {top_q:.0f}/100)."
                elif item.get("rating") and safe_number(item.get("rating")) > safe_number(top_prod.get("rating")) and item_cov < top_cov:
                    item["rank_explanation"] = "Higher rating, but insufficient technical specification data."
                else:
                    item["rank_explanation"] = "Comparable specifications with competitive platform pricing."

    return sorted_list



def sort_by_price(products: list) -> list:
    """Sort products by price ascending (lowest first)."""
    return sorted(products, key=lambda x: (_parse_price_num(x) or 9_999_999,))


def sort_by_rating(products: list) -> list:
    """Sort products by rating descending (best first)."""
    return sorted(products, key=lambda x: -_parse_rating(x))


def sort_by_discount(products: list) -> list:
    """Sort products by discount percentage descending (biggest discount first)."""
    return sorted(products, key=lambda x: -_parse_discount(x))


def sort_by_reviews(products: list) -> list:
    """Sort products by review count descending."""
    return sorted(products, key=lambda x: -_parse_review_count(x))


def get_summary_badges(products: list) -> dict:
    """
    Compute overall highlight summary badges across all platforms:
    Lowest Price, Highest Rating, Most Reviews, Best Discount, Best Value.
    """
    if not products:
        return {}

    valid_price = [i for i in products if _parse_price_num(i) is not None]
    lowest_price_item = min(valid_price, key=lambda x: _parse_price_num(x) or 9_999_999) if valid_price else None
    highest_rating_item = max(products, key=_parse_rating)
    most_reviews_item = max(products, key=_parse_review_count)
    best_discount_item = max(products, key=_parse_discount)

    # Best value heuristic (high rating, decent reviews, reasonable price)
    best_value_item = max(
        products,
        key=lambda x: (_parse_rating(x) * 20) + (min(_parse_review_count(x), 500) / 25) - ((_parse_price_num(x) or 50000) / 2000)
    )

    return {
        "lowest_price":   lowest_price_item,
        "highest_rating": highest_rating_item if _parse_rating(highest_rating_item) > 0 else None,
        "most_reviews":   most_reviews_item if _parse_review_count(most_reviews_item) > 0 else None,
        "best_discount":  best_discount_item if _parse_discount(best_discount_item) > 0 else None,
        "best_value":     best_value_item,
    }


def generate_sort_views(products: list) -> dict:
    """
    Generate pre-computed sort views for the results page.

    Returns:
        dict with keys: best_match, lowest_price, highest_rated, best_discount, most_reviews
    """
    return {
        'best_match':    rank_products(list(products)),
        'lowest_price':  sort_by_price(list(products)),
        'highest_rated': sort_by_rating(list(products)),
        'best_discount': sort_by_discount(list(products)),
        'most_reviews':  sort_by_reviews(list(products)),
    }


def annotate_badges(platform_results: dict) -> None:
    """
    Mutates items in platform_results in-place to add badge flags:
        is_lowest_price : bool
        is_best_rated   : bool
        is_best_discount: bool
    """
    all_items = [item for items in platform_results.values() for item in items]
    if not all_items:
        return

    valid_price = [i for i in all_items if _parse_price_num(i) is not None]
    min_price_item = min(valid_price, key=lambda x: _parse_price_num(x) or 9_999_999) if valid_price else None
    max_rating_item = max(all_items, key=_parse_rating) if all_items else None
    max_disc_item = max(all_items, key=_parse_discount) if all_items else None

    for item in all_items:
        item['is_lowest_price']  = (min_price_item is not None and item is min_price_item)
        item['is_best_rated']    = (max_rating_item is not None and item is max_rating_item
                                    and _parse_rating(item) > 0)
        item['is_best_discount'] = (max_disc_item is not None and item is max_disc_item
                                    and _parse_discount(item) > 0)


def extract_numeric_price(product: Optional[dict]) -> float | None:
    """Safely extract positive numeric price from product dict without throwing errors."""
    if not isinstance(product, dict):
        return None
    val = product.get("price_num")
    if val is not None and isinstance(val, (int, float)) and val > 0:
        return float(val)
    price_str = product.get("price")
    if not price_str or not isinstance(price_str, str):
        return None
    price_clean = price_str.upper().strip()
    if price_clean in ("N/A", "NONE", "", "NULL", "FREE"):
        return None
    digits = re.sub(r'[^\d.]', '', price_str)
    if not digits:
        return None
    try:
        num = float(digits)
        return num if num > 0 else None
    except ValueError:
        return None


def get_top_best_prices_data(platform_results: dict) -> dict:
    """
    Computes top best price per platform (Amazon, Flipkart, Meesho) from actual scraped results.
    Finds the lowest valid price for each platform and calculates overall deal & savings.
    """
    target_platforms = ["Amazon", "Flipkart", "Meesho"]
    top_prices = {}
    valid_platform_deals = []

    for platform in target_platforms:
        products = platform_results.get(platform, [])
        valid_products = []
        if isinstance(products, list):
            for p in products:
                if isinstance(p, dict):
                    p_num = extract_numeric_price(p)
                    if p_num is not None:
                        valid_products.append((p_num, p))

        if valid_products:
            best_p_num, best_product = min(valid_products, key=lambda x: x[0])
            price_fmt = best_product.get("price") or f"₹{int(best_p_num):,}"
            rating_val = best_product.get("rating")
            if rating_val in ("N/A", "", None, 0, "0"):
                rating_val = None
            reviews_val = best_product.get("reviews")
            if reviews_val in ("0", "", None):
                reviews_val = None

            item_data = {
                "available": True,
                "platform": platform,
                "product": best_product,
                "price_num": best_p_num,
                "price_formatted": price_fmt,
                "title": best_product.get("title", "Product"),
                "rating": rating_val,
                "reviews": reviews_val,
                "image": best_product.get("image"),
                "link": best_product.get("link", "#"),
                "is_overall_best": False,
                "is_lowest_price": False,
            }
            top_prices[platform] = item_data
            valid_platform_deals.append(item_data)
        else:
            top_prices[platform] = {
                "available": False,
                "platform": platform,
                "product": None,
                "price_num": None,
                "price_formatted": "N/A",
                "title": "No product available",
                "rating": None,
                "reviews": None,
                "image": None,
                "link": None,
                "is_overall_best": False,
                "is_lowest_price": False,
            }

    best_overall = None
    savings_info = None

    if valid_platform_deals:
        best_overall = min(valid_platform_deals, key=lambda x: x["price_num"])
        
        for platform in target_platforms:
            if top_prices[platform]["available"] and top_prices[platform]["platform"] == best_overall["platform"]:
                top_prices[platform]["is_overall_best"] = True
                top_prices[platform]["is_lowest_price"] = True

        if len(valid_platform_deals) >= 2:
            highest_deal = max(valid_platform_deals, key=lambda x: x["price_num"])
            savings_amount = highest_deal["price_num"] - best_overall["price_num"]
            if savings_amount > 0:
                savings_info = {
                    "amount": savings_amount,
                    "amount_formatted": f"₹{int(savings_amount):,}",
                    "compared_platform": highest_deal["platform"],
                    "highest_price_formatted": highest_deal["price_formatted"],
                }

    return {
        "top_prices": top_prices,
        "best_overall": best_overall,
        "savings_info": savings_info,
    }

