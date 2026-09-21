"""
search/quality_scorer.py
========================
SmartBuy Product Quality Score & Data Confidence Engine.

Calculates:
1. product_quality_score (0.0 to 100.0):
   Evaluates product desirability and buyer confidence based on:
   - Rating value with Bayesian damping
   - Review volume and confidence (log-scaled)
   - Seller quality & rating
   - Warranty & return policy
   - Stock availability & condition
   - Specification completeness

2. data_confidence_score (0.0 to 100.0):
   Evaluates data richness and verification completeness:
   - Measures how many of the 37 schema attributes are populated from authentic data
   - Differentiates rich API/detailed scrape vs minimal listing card

Keeps product_quality_score STRICTLY SEPARATE from data_confidence_score.
Missing information does NOT automatically mean quality = 0.
"""

import math
from typing import Dict, Any, Tuple


def compute_quality_and_confidence(product: Dict[str, Any]) -> Tuple[float, float]:
    """
    Computes (quality_score, data_confidence) for a product dictionary.
    Returns scores clamped between 0.0 and 100.0.
    """
    # ── 1. Compute Data Confidence Score ──────────────────────────────────────
    # Measures the completeness and richness of extracted data points
    confidence_points = 0.0
    total_possible_conf = 100.0

    # Critical Identifiers (25 pts)
    if product.get("title") and len(str(product["title"]).strip()) >= 10:
        confidence_points += 10.0
    if product.get("brand"):
        confidence_points += 5.0
    if product.get("model") and product["model"] != "N/A":
        confidence_points += 5.0
    if product.get("product_id"):
        confidence_points += 5.0

    # Pricing & Availability (25 pts)
    if product.get("price_num") and product["price_num"] > 0:
        confidence_points += 15.0
    if product.get("mrp_num"):
        confidence_points += 5.0
    if product.get("availability"):
        confidence_points += 5.0

    # Images & Media (15 pts)
    imgs = product.get("images") or ([product.get("image")] if product.get("image") else [])
    if imgs and len(imgs) > 0:
        confidence_points += 10.0
        if len(imgs) >= 3:
            confidence_points += 5.0

    # Social Proof / Ratings (15 pts)
    if product.get("rating") is not None:
        confidence_points += 8.0
    if product.get("review_count") is not None and product["review_count"] > 0:
        confidence_points += 7.0

    # Specifications & Metadata (20 pts)
    specs = product.get("specifications") or {}
    if isinstance(specs, dict) and len(specs) > 0:
        confidence_points += min(15.0, len(specs) * 2.5)
    if product.get("seller"):
        confidence_points += 2.5
    if product.get("warranty") or product.get("return_policy"):
        confidence_points += 2.5

    data_confidence = round(min(100.0, max(10.0, confidence_points)), 1)

    # ── 2. Compute Product Quality Score ──────────────────────────────────────
    # Evaluates buyer confidence and product offering quality
    quality_points = 0.0

    # Component A: Rating with Bayesian smoothing (35 pts max)
    # Uses prior mean of 3.8 so unrated products get a neutral ~20 pts instead of 0!
    raw_r = product.get("rating")
    raw_rev = product.get("review_count") or 0
    prior_rating = 3.8
    prior_weight = 10.0

    if raw_r is not None and raw_r > 0:
        smoothed_rating = ((raw_r * raw_rev) + (prior_rating * prior_weight)) / (raw_rev + prior_weight)
        quality_points += (smoothed_rating / 5.0) * 35.0
    else:
        # Neutral rating component for unrated items
        quality_points += (prior_rating / 5.0) * 20.0

    # Component B: Review Confidence (log-scaled, 20 pts max)
    if raw_rev > 0:
        # log10(1) = 0, log10(10000) = 4 -> 4 * 5 = 20 pts
        rev_score = min(20.0, math.log10(max(1, raw_rev)) * 5.0)
        quality_points += rev_score
    else:
        quality_points += 5.0  # neutral floor

    # Component C: Availability & Condition (15 pts max)
    avail = str(product.get("availability", "")).lower()
    if "out of stock" in avail:
        quality_points += 0.0
    else:
        quality_points += 15.0

    # Component D: Seller Reputation (15 pts max)
    seller = product.get("seller")
    seller_rating = product.get("seller_rating")
    if seller_rating is not None and seller_rating > 0:
        quality_points += (min(5.0, float(seller_rating)) / 5.0) * 15.0
    elif seller:
        # Verified seller present
        quality_points += 10.0
    else:
        quality_points += 7.0  # neutral

    # Component E: Warranty & Specification Completeness (15 pts max)
    if product.get("warranty") and str(product["warranty"]).lower() not in ("n/a", "none"):
        quality_points += 5.0
    if product.get("return_policy") and str(product["return_policy"]).lower() not in ("n/a", "none"):
        quality_points += 3.0

    spec_count = len(specs) if isinstance(specs, dict) else 0
    if spec_count >= 5:
        quality_points += 7.0
    elif spec_count >= 2:
        quality_points += 4.0
    else:
        quality_points += 2.0

    product_quality_score = round(min(100.0, max(15.0, quality_points)), 1)

    return product_quality_score, data_confidence
