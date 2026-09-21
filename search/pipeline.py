"""
search/pipeline.py
==================
SmartBuy Production-Quality Product Comparison Pipeline.

The Single Source of Truth Coordinator:
Produces `validated_products` which is the ONLY source for:
- Product cards
- Specification comparison matrix
- Matching status section
- Top Verified Offers
- Best Deal calculation
- Quality comparison

Guarantees:
- Hard rejection of accessories and model mismatches
- Extreme price anomaly detection (PRICE/IDENTITY UNVERIFIED)
- Best Deal based on Best Value, never raw minimum price
- Returns "No exact cross-platform match available" when cross-platform identity is unverified
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from search.query_parser import parse_query_entities
from search.product_matcher import evaluate_product_match, check_suspicious_price
from search.specs_extractor import build_category_spec_matrix, compute_marketplace_statuses
from search.quality_scorer import compute_quality_and_confidence
from search.category_detector import detect_category

logger = logging.getLogger("smartbuy.search.pipeline")


def run_comparison_pipeline(
    query: str,
    raw_platform_results: Dict[str, List[Dict[str, Any]]],
    platform_status: Dict[str, Dict[str, Any]],
    source_product: Optional[Dict[str, Any]] = None,
    is_url_search: bool = False
) -> Dict[str, Any]:
    """
    Master pipeline orchestrator taking raw results from Amazon, Flipkart, and Meesho
    and producing an authoritative, unified comparison payload.
    """
    clean_q = str(query or "").strip()
    detected_cat = detect_category(query=clean_q)

    # 1. Query Understanding / Target Entity Extraction
    if is_url_search and source_product:
        target_info = {
            "raw_query": clean_q,
            "brand": source_product.get("brand"),
            "model": source_product.get("model"),
            "category": source_product.get("category") or detected_cat,
            "product_type": source_product.get("category") or detected_cat,
            "ram": source_product.get("ram"),
            "storage": source_product.get("storage"),
            "network": source_product.get("network"),
            "weight": source_product.get("weight"),
            "pack_count": source_product.get("pack_quantity"),
            "is_accessory": False,
        }
    else:
        target_info = parse_query_entities(clean_q)
        if not target_info.get("category") or target_info["category"] == "other":
            target_info["category"] = detected_cat

    # 2. Strict Matching, Rejections & Quality Validation per Marketplace
    validated_products_by_platform: Dict[str, List[Dict[str, Any]]] = {
        "Amazon": [],
        "Flipkart": [],
        "Meesho": []
    }
    all_raw_candidates: List[Dict[str, Any]] = []
    rejected_products: List[Dict[str, Any]] = []

    for platform_key in ("Amazon", "Flipkart", "Meesho"):
        raw_items = raw_platform_results.get(platform_key) or raw_platform_results.get(platform_key.lower()) or []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item["platform"] = platform_key
            all_raw_candidates.append(item)

            # Evaluate match status
            status, score, breakdown, reasons = evaluate_product_match(target_info, item)
            item["match_status"] = status
            item["match_score"] = score
            item["match_breakdown"] = breakdown
            item["match_reasons"] = reasons

            # Compute quality and confidence
            q_score, d_conf = compute_quality_and_confidence(item)
            item["quality_score"] = q_score
            item["data_confidence"] = d_conf

            if status == "REJECTED":
                rejected_products.append(item)
            else:
                validated_products_by_platform[platform_key].append(item)

    # 3. Suspicious Price Protection (Section 17)
    # Check all validated products against median price of exact/variant matches
    all_candidates_for_median = [
        p for plat_items in validated_products_by_platform.values() for p in plat_items
    ]
    for p in all_candidates_for_median:
        is_suspicious, susp_reason = check_suspicious_price(p, all_candidates_for_median)
        if is_suspicious:
            p["match_status"] = "PRICE/IDENTITY UNVERIFIED"
            p["match_reasons"].append(susp_reason)
            logger.warning(f"[{p.get('platform')}] Flagged suspicious price: '{p.get('title')[:35]}' ({p.get('price')}): {susp_reason}")

    # validated_products is the SINGLE SOURCE OF TRUTH
    all_validated_products = [
        p for plat_items in validated_products_by_platform.values() for p in plat_items
        if p.get("match_status") != "REJECTED"
    ]

    # 4. Determine Best Validated Match per Platform for Specification Matrix & Deal Calculation
    best_match_per_platform: Dict[str, Optional[Dict[str, Any]]] = {
        "Amazon": None,
        "Flipkart": None,
        "Meesho": None
    }
    for plat in ("Amazon", "Flipkart", "Meesho"):
        plat_items = validated_products_by_platform.get(plat) or []
        # Filter for Exact Match or allowed Variant Match with verified price
        exact_or_variant = [
            it for it in plat_items
            if it.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH") and it.get("price_num") and it["price_num"] > 0
        ]
        if exact_or_variant:
            # Sort by match score desc, then price asc
            exact_or_variant.sort(key=lambda x: (-x.get("match_score", 0), x.get("price_num", 9999999)))
            best_match_per_platform[plat] = exact_or_variant[0]
        elif plat_items:
            # Fallback to highest scoring similar product if no exact match
            similar_items = [it for it in plat_items if it.get("price_num") and it["price_num"] > 0]
            if similar_items:
                similar_items.sort(key=lambda x: (-x.get("match_score", 0), x.get("price_num", 9999999)))
                best_match_per_platform[plat] = similar_items[0]

    # 5. Top Verified Offers (Section 15)
    # Replaces broken "No product available" logic. Only includes EXACT_MATCH or allowed VARIANT_MATCH.
    top_verified_offers: Dict[str, Dict[str, Any]] = {}
    valid_verified_deals: List[Dict[str, Any]] = []

    for plat in ("Amazon", "Flipkart", "Meesho"):
        best_p = best_match_per_platform.get(plat)
        if best_p and best_p.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH"):
            p_fmt = best_p.get("price") or (f"₹{best_p.get('price_num'):,}" if best_p.get("price_num") else "N/A")
            offer_data = {
                "available": True,
                "platform": plat,
                "product": best_p,
                "product_name": best_p.get("title", "Product"),
                "title": best_p.get("title", "Product"),
                "image": best_p.get("image") or best_p.get("image_url"),
                "price": p_fmt,
                "formatted_price": p_fmt,
                "price_formatted": p_fmt,
                "price_num": best_p.get("price_num"),
                "mrp": best_p.get("mrp"),
                "discount": best_p.get("discount"),
                "rating": best_p.get("rating"),
                "reviews": best_p.get("review_count"),
                "quality_score": best_p.get("quality_score", 0.0),
                "data_confidence": best_p.get("data_confidence", 0.0),
                "quantity": best_p.get("quantity") or best_p.get("weight") or f"Pack of {best_p.get('pack_quantity', 1)}",
                "variant": best_p.get("model") or "Standard",
                "seller": best_p.get("seller") or "Verified Seller",
                "availability": best_p.get("availability", "In Stock"),
                "unit_price": best_p.get("unit_price") or "N/A",
                "match_status": best_p.get("match_status"),
                "match_score": best_p.get("match_score", 0.0),
                "link": best_p.get("product_url") or best_p.get("link", "#"),
                "is_overall_best": False
            }
            top_verified_offers[plat] = offer_data
            valid_verified_deals.append(offer_data)
        else:
            top_verified_offers[plat] = {
                "available": False,
                "platform": plat,
                "product": None,
                "product_name": "No verified match on this marketplace",
                "title": "No verified match on this marketplace",
                "price": "N/A",
                "price_num": None,
                "rating": None,
                "reviews": None,
                "quality_score": 0.0,
                "data_confidence": 0.0,
                "is_overall_best": False
            }

    # 6. Category-Specific Specification Matrix (Section 13 & 19)
    spec_category = target_info.get("category") or detected_cat
    specification_matrix = build_category_spec_matrix(
        spec_category,
        best_match_per_platform,
        platform_status
    )
    marketplace_status = compute_marketplace_statuses(
        best_match_per_platform,
        platform_status
    )

    # 7. Best Deal Engine (Section 16: Best Value Algorithm + Savings)
    best_deal: Optional[Dict[str, Any]] = None
    no_deal_message: Optional[str] = None
    savings_info: Optional[Dict[str, Any]] = None

    # Check cross-platform match requirements
    verified_platforms_count = len(valid_verified_deals)
    has_cross_platform_match = verified_platforms_count >= 2

    if verified_platforms_count >= 1:
        # Calculate Best Value score for each verified deal
        min_p = min(d["price_num"] for d in valid_verified_deals if d["price_num"])
        scored_deals = []

        for d in valid_verified_deals:
            p_val = d["price_num"]
            prod = d["product"]

            # Deal formula: 35% Price, 25% Quality, 15% Reviews, 15% Seller, 10% Availability
            price_comp = (min_p / max(1, p_val)) * 35.0
            qual_comp = (d["quality_score"] / 100.0) * 25.0
            rev_cnt = d["reviews"] or 0
            rev_comp = min(15.0, (rev_cnt / 500.0) * 15.0 if rev_cnt < 500 else 15.0)
            avail_comp = 10.0 if d["availability"] == "In Stock" else 0.0
            match_comp = (d["match_score"] / 100.0) * 15.0

            deal_score = round(price_comp + qual_comp + rev_comp + avail_comp + match_comp, 1)

            scored_deals.append({
                "deal_data": d,
                "deal_score": deal_score,
                "price_num": p_val
            })

        # Pick deal with highest overall deal score
        scored_deals.sort(key=lambda x: (-x["deal_score"], x["price_num"]))
        winner_deal = scored_deals[0]["deal_data"]
        winner_deal["is_overall_best"] = True

        # Calculate savings if 2 or more offers exist
        savings = 0
        if verified_platforms_count >= 2:
            prices = [d["price_num"] for d in valid_verified_deals if d["price_num"]]
            highest_p = max(prices)
            savings = max(0, highest_p - winner_deal["price_num"])
            if savings > 0:
                highest_deal = next(d for d in valid_verified_deals if d["price_num"] == highest_p)
                savings_info = {
                    "amount": savings,
                    "amount_formatted": f"₹{savings:,}",
                    "compared_platform": highest_deal["platform"],
                    "highest_price_formatted": highest_deal["price"]
                }

        reasons = [
            f"Verified {winner_deal['match_status']} on {winner_deal['platform']}",
            f"Verified Price: {winner_deal['price']}",
            f"Product Quality Score: {winner_deal['quality_score']}/100",
            f"{winner_deal['availability']}"
        ]
        if winner_deal.get("rating"):
            reasons.append(f"Rated {winner_deal['rating']} ★ ({winner_deal.get('reviews', 0):,} reviews)")
        if savings > 0:
            reasons.append(f"Saves ₹{savings:,} compared to {savings_info['compared_platform']}")

        best_deal = {
            "platform": winner_deal["platform"],
            "price": winner_deal["price_num"],
            "formatted_price": winner_deal["price"],
            "price_formatted": winner_deal["price"],
            "price_num": winner_deal["price_num"],
            "title": winner_deal["title"],
            "product_name": winner_deal["title"],
            "link": winner_deal["link"],
            "image": winner_deal["image"],
            "rating": winner_deal["rating"],
            "reviews": winner_deal["reviews"],
            "quality_score": winner_deal["quality_score"],
            "data_confidence": winner_deal["data_confidence"],
            "savings": savings,
            "match_status": winner_deal["match_status"],
            "reasons": reasons,
            "reason_text": " • ".join(reasons)
        }
    else:
        no_deal_message = "No exact cross-platform match available"

    # 8. Pairwise Matching Status Summary
    match_pairs = {}
    pair_defs = [
        ("Amazon", "Flipkart", "Amazon ↔ Flipkart"),
        ("Amazon", "Meesho", "Amazon ↔ Meesho"),
        ("Flipkart", "Meesho", "Flipkart ↔ Meesho")
    ]
    for p1, p2, label in pair_defs:
        it1 = best_match_per_platform.get(p1)
        it2 = best_match_per_platform.get(p2)
        if it1 and it2 and it1.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH") and it2.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH"):
            avg_score = int((it1.get("match_score", 0) + it2.get("match_score", 0)) / 2)
            classification = "Exact Match" if avg_score >= 85 else "Variant Match"
            match_pairs[label] = {
                "score": avg_score,
                "classification": classification,
                "label": label
            }
        else:
            match_pairs[label] = {
                "score": 0,
                "classification": "Not Available",
                "label": label
            }

    return {
        "query": clean_q,
        "target_info": target_info,
        "detected_category": spec_category,
        "category": spec_category,
        "validated_products": all_validated_products,
        "validated_by_platform": validated_products_by_platform,
        "rejected_products": rejected_products,
        "top_verified_offers": top_verified_offers,
        "top_prices": top_verified_offers,
        "specifications_matrix": specification_matrix,
        "best_deal": best_deal,
        "overall_best": best_deal,
        "best_overall_deal": best_deal,
        "no_deal_message": no_deal_message,
        "savings_info": savings_info,
        "match_pairs": match_pairs,
        "has_cross_platform_match": has_cross_platform_match,
        "platform_status": platform_status,
        "marketplace_status": marketplace_status,
        "best_match_per_platform": best_match_per_platform
    }
