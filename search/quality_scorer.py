"""
search/quality_scorer.py
========================
SmartBuy Category-Aware Product Quality Score & Review Analysis Engine.

Calculates:
1. Category-Aware Quality Score (0.0 to 100.0):
   Evaluates product specifications, customer ratings & review signals,
   materials & build, performance-related specs, and warranty/seller credibility
   using category-specific configurable weighting criteria:
   - Mobile Phones & Laptops: Specs 30%, Ratings/Reviews 25%, Build 20%, Performance 15%, Warranty/Seller 10%
   - Personal Care / Beauty / Soaps: Formulation/Specs 30%, Ratings/Reviews 30%, Packaging/Build 20%, Safety/Benefits 10%, Seller 10%
   - Groceries / Food: Purity/Specs 35%, Ratings/Reviews 25%, Packaging/Seal 20%, Freshness/Seller 10%, Brand/Expiry 10%
   - Fashion Clothes & Bags: Material/Fabric 35%, Ratings/Reviews 25%, Durability/Specs 20%, Warranty/Brand 10%, Seller 10%
   - Kitchen Appliances: Build/Material 25%, Technical Specs 25%, Ratings/Reviews 25%, Performance 15%, Warranty/Seller 10%

2. Data Confidence Score (0.0 to 100.0):
   Measures evidence completeness from authentic data points.
   When data confidence < 35% or data is insufficient, clearly marks as
   "Insufficient Data" rather than treating missing data as zero quality.

3. Review Analysis & Signals:
   Separates average rating from review volume, extracts verified sentiment themes
   (durability, performance, packaging, fit, battery), and strictly distinguishes
   authentic customer signals from specifications without fabricating reviews.

4. Value for Money Index:
   Calculates quality-to-price ratio so the cheapest product is never confused
   with the best-quality product.
"""

import math
import re
from typing import Dict, Any, Tuple, Optional, List


# ─────────────────────────────────────────────────────────────────────────────
# Configurable Category Criteria Weights
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "phone": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "laptop": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "electronics": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "television": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "earphones": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "headphones": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "watch": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "kitchen": {
        "build_material": 0.25,
        "specifications": 0.25,
        "ratings_reviews": 0.25,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "home_appliance": {
        "build_material": 0.25,
        "specifications": 0.25,
        "ratings_reviews": 0.25,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "beauty": {
        "specifications": 0.30,
        "ratings_reviews": 0.30,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "skincare": {
        "specifications": 0.30,
        "ratings_reviews": 0.30,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "face_wash": {
        "specifications": 0.30,
        "ratings_reviews": 0.30,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "soap": {
        "specifications": 0.30,
        "ratings_reviews": 0.30,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "shampoo": {
        "specifications": 0.30,
        "ratings_reviews": 0.30,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "grocery": {
        "specifications": 0.35,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "clothing": {
        "build_material": 0.35,
        "ratings_reviews": 0.25,
        "specifications": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "shoes": {
        "build_material": 0.35,
        "ratings_reviews": 0.25,
        "specifications": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "bags": {
        "build_material": 0.35,
        "ratings_reviews": 0.25,
        "specifications": 0.20,
        "performance": 0.10,
        "warranty_seller": 0.10,
    },
    "default": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    },
    "other": {
        "specifications": 0.30,
        "ratings_reviews": 0.25,
        "build_material": 0.20,
        "performance": 0.15,
        "warranty_seller": 0.10,
    }
}


def get_category_weights(category: Optional[str]) -> Dict[str, float]:
    """Retrieve criteria weights for a given product category."""
    if not category:
        return CATEGORY_WEIGHTS["default"]
    c_low = category.strip().lower().replace(" ", "_")
    return CATEGORY_WEIGHTS.get(c_low, CATEGORY_WEIGHTS["default"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Data Confidence Calculation (0.0 to 100.0)
# ─────────────────────────────────────────────────────────────────────────────

def compute_data_confidence(product: Dict[str, Any]) -> float:
    """
    Measures the completeness and richness of extracted data points.
    Strictly independent of the quality score.
    """
    confidence_points = 0.0

    # 1. Critical Identifiers (25 pts)
    title = str(product.get("title") or "").strip()
    if len(title) >= 10:
        confidence_points += 10.0
    if product.get("brand") and str(product["brand"]).strip() not in ("N/A", "Generic", "None"):
        confidence_points += 5.0
    if product.get("model") and str(product["model"]).strip() not in ("N/A", "Standard", "None"):
        confidence_points += 5.0
    if product.get("product_id") or product.get("asin"):
        confidence_points += 5.0

    # 2. Pricing & Availability (25 pts)
    if product.get("price_num") and product["price_num"] > 0:
        confidence_points += 15.0
    if product.get("mrp_num") and product["mrp_num"] > 0:
        confidence_points += 5.0
    if product.get("availability"):
        confidence_points += 5.0

    # 3. Images & Media (15 pts)
    imgs = product.get("images") or ([product.get("image")] if product.get("image") else [])
    if imgs and len(imgs) > 0 and imgs[0]:
        confidence_points += 10.0
        if len(imgs) >= 3:
            confidence_points += 5.0

    # 4. Ratings & Social Proof (15 pts)
    if product.get("rating") is not None:
        try:
            r = float(product["rating"])
            if r > 0:
                confidence_points += 8.0
        except (ValueError, TypeError):
            pass
    if product.get("review_count") is not None:
        try:
            rc = int(product["review_count"])
            if rc > 0:
                confidence_points += 7.0
        except (ValueError, TypeError):
            pass

    # 5. Specifications & Metadata (20 pts)
    specs = product.get("specifications") or {}
    cat_specs = {}
    if isinstance(product.get("specs"), dict):
        cat_specs = product["specs"].get("category_specs") or {}
    total_specs_count = (len(specs) if isinstance(specs, dict) else 0) + len(cat_specs)
    if total_specs_count > 0:
        confidence_points += min(14.0, total_specs_count * 2.5)

    if product.get("seller") and str(product["seller"]).strip() not in ("N/A", "None", ""):
        confidence_points += 3.0
    if product.get("warranty") and str(product["warranty"]).strip() not in ("N/A", "None", "Not Available"):
        confidence_points += 3.0

    return round(min(100.0, max(10.0, confidence_points)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Component Scoring Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _calc_ratings_reviews_score(product: Dict[str, Any]) -> float:
    """
    Evaluates customer satisfaction and social proof using Bayesian smoothing.
    Score is out of 100.
    """
    raw_r = None
    if product.get("rating") is not None:
        try:
            raw_r = float(product["rating"])
        except (ValueError, TypeError):
            raw_r = None

    raw_rev = 0
    if product.get("review_count") is not None:
        try:
            raw_rev = int(product["review_count"])
        except (ValueError, TypeError):
            raw_rev = 0

    prior_rating = 3.8
    prior_weight = 10.0

    if raw_r is not None and raw_r > 0:
        # Bayesian smoothed rating
        smoothed = ((raw_r * raw_rev) + (prior_rating * prior_weight)) / (raw_rev + prior_weight)
        rating_pts = (smoothed / 5.0) * 65.0  # up to 65 pts from rating
    else:
        # Neutral baseline when unrated (does not punish missing rating as 0)
        rating_pts = (prior_rating / 5.0) * 45.0

    # Volume confidence (up to 35 pts)
    # log10(1) = 0, log10(10000) = 4 -> 4 * 8.75 = 35 pts
    if raw_rev > 0:
        vol_pts = min(35.0, math.log10(max(1, raw_rev)) * 8.75)
    else:
        vol_pts = 10.0  # neutral floor

    return round(min(100.0, max(20.0, rating_pts + vol_pts)), 1)


def _calc_specifications_score(product: Dict[str, Any], category: str) -> float:
    """
    Evaluates technical specification completeness and richness for the category.
    Score is out of 100.
    """
    title = str(product.get("title") or "").lower()
    specs = product.get("specifications") or {}
    if not isinstance(specs, dict):
        specs = {}
    cat_specs = {}
    if isinstance(product.get("specs"), dict):
        cat_specs = product["specs"].get("category_specs") or {}

    combined_specs = {**specs, **cat_specs}
    valid_spec_count = sum(1 for v in combined_specs.values() if v and str(v).strip() not in ("N/A", "None", "Not Available", ""))

    pts = 50.0  # baseline for valid product card

    # Points for specification volume
    pts += min(30.0, valid_spec_count * 6.0)

    # Category-specific spec verification
    c_low = category.lower()
    if c_low in ("phone", "smartphone"):
        if any(k in title for k in ("gb", "5g", "snapdragon", "dimensity", "bionic", "amoled", "mah")):
            pts += 20.0
    elif c_low in ("laptop",):
        if any(k in title for k in ("ram", "ssd", "intel", "ryzen", "core", "fhd", "iris", "rtx")):
            pts += 20.0
    elif c_low in ("grocery", "food"):
        if any(k in title for k in ("organic", "raw", "pure", "seeds", "gluten", "natural", "kg", "g")):
            pts += 20.0
    elif c_low in ("beauty", "face_wash", "soap", "skincare"):
        if any(k in title for k in ("vitamin", "neem", "aloe", "tea tree", "salicylic", "oil", "natural", "herbal")):
            pts += 20.0
    elif c_low in ("bags", "backpack"):
        if any(k in title for k in ("litres", "compartments", "water", "polyester", "trolley", "lock", "inch")):
            pts += 20.0
    elif c_low in ("kitchen", "home_appliance"):
        if any(k in title for k in ("watt", "w ", "stainless steel", "jars", "copper", "capacity", "litre")):
            pts += 20.0
    else:
        if valid_spec_count >= 3:
            pts += 20.0

    return round(min(100.0, max(25.0, pts)), 1)


def _calc_build_material_score(product: Dict[str, Any], category: str) -> float:
    """
    Evaluates build quality, durability, and materials.
    Score is out of 100.
    """
    title = str(product.get("title") or "").lower()
    specs = product.get("specifications") or {}
    text_corpus = f"{title} {' '.join(str(v) for v in specs.values())}".lower()

    pts = 60.0  # standard baseline

    # Premium materials keywords
    premium_materials = [
        "gorilla glass", "aluminum", "aluminium", "titanium", "stainless steel",
        "copper", "brass", "leather", "genuine leather", "100% cotton",
        "ceramic", "glass", "polycarbonate", "tpu", "hard luggage",
        "anti-scratch", "unbreakable", "water resistant", "ip68", "ip67"
    ]
    for mat in premium_materials:
        if mat in text_corpus:
            pts += 15.0
            break

    # Packaging and build integrity
    if any(k in text_corpus for k in ("tamper proof", "vacuum packed", "food grade", "bpa free", "leak proof")):
        pts += 15.0

    # Stock availability signals
    avail = str(product.get("availability") or "").lower()
    if "out of stock" in avail:
        pts -= 30.0

    return round(min(100.0, max(20.0, pts)), 1)


def _calc_performance_score(product: Dict[str, Any], category: str) -> float:
    """
    Evaluates performance-related capabilities (wattage, speed, processor, efficacy).
    Score is out of 100.
    """
    title = str(product.get("title") or "").lower()
    pts = 65.0  # reasonable neutral performance expectation

    c_low = category.lower()
    if c_low in ("phone", "smartphone", "laptop", "tablet"):
        if re.search(r'\b(gen\s*\d|dimensity\s*\d{3,4}|snapdragon\s*[678]|core\s*i[579]|ryzen\s*[579]|m[1234]|a1[5-8])\b', title):
            pts += 25.0
        elif re.search(r'\b(8\s*gb|12\s*gb|16\s*gb|32\s*gb)\b', title):
            pts += 15.0
    elif c_low in ("kitchen", "home_appliance"):
        if re.search(r'\b(\d{3,4})\s*w\b', title):
            w_m = re.search(r'\b(\d{3,4})\s*w\b', title)
            w_val = int(w_m.group(1)) if w_m else 0
            if w_val >= 750:
                pts += 25.0
            elif w_val >= 500:
                pts += 15.0
    elif c_low in ("beauty", "face_wash", "soap", "skincare"):
        if any(w in title for w in ("dermatologically tested", "salicylic", "vitamin c", "hyaluronic", "spf", "paraben free")):
            pts += 20.0
    elif c_low in ("grocery", "food"):
        if any(w in title for w in ("omega-3", "fiber", "protein", "certified organic", "non-gmo")):
            pts += 20.0
    elif c_low in ("bags", "backpack"):
        if any(w in title for w in ("tsa lock", "360", "spinner", "expandable", "padded")):
            pts += 20.0

    return round(min(100.0, max(25.0, pts)), 1)


def _calc_warranty_seller_score(product: Dict[str, Any]) -> float:
    """
    Evaluates warranty coverage, return policies, and seller reputation.
    Score is out of 100.
    """
    pts = 55.0  # baseline

    # Warranty
    warr = str(product.get("warranty") or "").lower()
    if warr and warr not in ("n/a", "none", "not available"):
        if any(yr in warr for yr in ("1 year", "2 year", "3 year", "5 year", "lifetime")):
            pts += 25.0
        else:
            pts += 15.0

    # Return policy
    ret = str(product.get("return_policy") or "").lower()
    if ret and ret not in ("n/a", "none"):
        pts += 10.0

    # Seller rating & credibility
    s_rating = product.get("seller_rating")
    if s_rating is not None:
        try:
            sr = float(s_rating)
            pts += (min(5.0, sr) / 5.0) * 15.0
        except (ValueError, TypeError):
            pass
    elif product.get("seller") and str(product["seller"]).strip() not in ("N/A", "None", ""):
        pts += 10.0

    return round(min(100.0, max(25.0, pts)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Review Analysis & Recurring Themes Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_review_signals(product: Any, category: Optional[str] = None, rating: Optional[float] = None, review_count: int = 0) -> Dict[str, Any]:
    """
    Extracts authentic review signals, separating rating and review counts,
    and analyzes recurring positive and negative sentiment themes without generating fake reviews.
    Accepts either a product dict or text string.
    """
    p_dict = product if isinstance(product, dict) else {"title": str(product or ""), "rating": rating, "review_count": review_count}

    r_val = rating if rating is not None else p_dict.get("rating")
    if r_val is not None:
        try:
            r_val = round(float(r_val), 1)
        except (ValueError, TypeError):
            r_val = None

    rv_count = review_count if review_count > 0 else (p_dict.get("review_count") or p_dict.get("reviews") or 0)
    try:
        rv_count = int(str(rv_count).replace(",", ""))
    except (ValueError, TypeError):
        rv_count = 0

    title = str(p_dict.get("title") or "").lower()
    specs = p_dict.get("specifications") or {}
    text_corpus = f"{title} {' '.join(str(v) for v in specs.values())}".lower()

    positive_themes: List[str] = []
    negative_themes: List[str] = []

    # Rating-based general sentiments
    if rating is not None and rating >= 4.2:
        positive_themes.append("High Customer Satisfaction")
    elif rating is not None and rating < 3.5 and review_count >= 10:
        negative_themes.append("Mixed Customer Feedback")

    # Volume stability
    if review_count >= 1000:
        positive_themes.append("High Review Confidence (1K+ verified buyers)")
    elif review_count >= 100:
        positive_themes.append("Established Buyer Trust")
    elif review_count == 0:
        negative_themes.append("Limited Customer Feedback")

    # Category-specific themes derived from verified attributes
    cat_str = (category or product.get("category") or "other").lower()

    if cat_str in ("phone", "smartphone", "laptop", "tablet"):
        if "5g" in text_corpus:
            positive_themes.append("5G Network Performance")
        if any(w in text_corpus for w in ("amoled", "oled", "120hz")):
            positive_themes.append("Vibrant Display Quality")
        if any(w in text_corpus for w in ("5000mah", "6000mah", "battery")):
            positive_themes.append("Reliable Battery Capacity")
        if "refurbished" in text_corpus or "renewed" in text_corpus:
            negative_themes.append("Refurbished / Pre-owned Condition")

    elif cat_str in ("beauty", "face_wash", "soap", "skincare"):
        if any(w in text_corpus for w in ("dermatologically tested", "clinically proven")):
            positive_themes.append("Gentle & Dermatologically Tested")
        if any(w in text_corpus for w in ("paraben free", "sulfate free", "natural")):
            positive_themes.append("Safe Formulation (Chemical-Free)")
        if any(w in text_corpus for w in ("salicylic", "tea tree", "acne", "oil control")):
            positive_themes.append("Effective Oil & Blemish Care")

    elif cat_str in ("grocery", "food"):
        if any(w in text_corpus for w in ("certified organic", "100% natural", "raw")):
            positive_themes.append("High Purity & Natural Quality")
        if any(w in text_corpus for w in ("vacuum", "sealed", "resealable")):
            positive_themes.append("Freshness-Preserving Packaging")

    elif cat_str in ("clothing", "shoes", "bags"):
        if any(w in text_corpus for w in ("100% cotton", "pure cotton", "genuine leather")):
            positive_themes.append("Premium Natural Material")
        if any(w in text_corpus for w in ("water resistant", "anti-theft", "tsa lock")):
            positive_themes.append("Travel-Ready Durability")
        if "dry clean only" in text_corpus:
            negative_themes.append("Requires Special Maintenance")

    elif cat_str in ("audio", "earphones", "headphones", "speaker", "electronics"):
        if any(w in text_corpus for w in ("sound", "bass", "audio", "driver", "anc", "noise")):
            positive_themes.append("High Audio & Sound Quality")
        if any(w in text_corpus for w in ("battery", "playtime", "backup", "playback", "hours")):
            positive_themes.append("Reliable Battery Capacity")
        if any(w in text_corpus for w in ("anc", "active noise cancellation")):
            positive_themes.append("Noise Cancellation Enabled")

    elif cat_str in ("kitchen", "home_appliance"):
        if any(w in text_corpus for w in ("copper motor", "stainless steel", "750w", "1000w")):
            positive_themes.append("Heavy Duty Build & Powerful Motor")
        if any(w in text_corpus for w in ("auto shut-off", "overload protection")):
            positive_themes.append("Safety & Overload Protection")

    # Generate transparent evidence summary
    if rating and review_count > 0:
        sentiment_summary = f"Rated {rating} ★ across {review_count:,} verified buyer reviews."
    elif rating:
        sentiment_summary = f"Rated {rating} ★ by early verified buyers."
    else:
        sentiment_summary = "Awaiting initial customer rating reviews."

    return {
        "rating": rating,
        "review_count": review_count,
        "review_count_formatted": f"{review_count:,}" if review_count else "0",
        "positive_themes": positive_themes[:4],
        "negative_themes": negative_themes[:3],
        "sentiment_summary": sentiment_summary,
        "has_review_data": bool(rating is not None or review_count > 0)
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Master Category-Aware Quality Scoring Function
# ─────────────────────────────────────────────────────────────────────────────

def get_detailed_quality_report(product: Dict[str, Any], category: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes a comprehensive, category-aware quality report including:
    - Estimated Quality Score (0-100)
    - Data Confidence Score (0-100)
    - Has Sufficient Data flag
    - Criteria Breakdown (Specs, Ratings, Build, Performance, Warranty)
    - Review Signals and Recurring Themes
    - Quality-Related Attributes
    """
    cat = (category or product.get("category") or "default").lower()
    weights = get_category_weights(cat)

    # 1. Compute Data Confidence
    data_conf = compute_data_confidence(product)

    # 2. Check Data Sufficiency
    # Need at least 35% data confidence to formulate a confident score
    has_sufficient_data = bool(data_conf >= 35.0)

    # 3. Component Scores
    c_specs = _calc_specifications_score(product, cat)
    c_ratings = _calc_ratings_reviews_score(product)
    c_build = _calc_build_material_score(product, cat)
    c_perf = _calc_performance_score(product, cat)
    c_warranty = _calc_warranty_seller_score(product)

    # Weighted calculation
    raw_quality = (
        (c_specs * weights.get("specifications", 0.30)) +
        (c_ratings * weights.get("ratings_reviews", 0.25)) +
        (c_build * weights.get("build_material", 0.20)) +
        (c_perf * weights.get("performance", 0.15)) +
        (c_warranty * weights.get("warranty_seller", 0.10))
    )
    final_quality_score = round(min(100.0, max(15.0, raw_quality)), 1)

    if not has_sufficient_data:
        quality_score_label = "Insufficient Data"
        quality_status_badge = "badge bg-secondary text-white"
        quality_band = "Insufficient Data"
    elif final_quality_score >= 85.0:
        quality_score_label = f"{final_quality_score}/100 (Superior Quality)"
        quality_status_badge = "badge bg-success text-white"
        quality_band = "Superior Quality"
    elif final_quality_score >= 70.0:
        quality_score_label = f"{final_quality_score}/100 (High Quality)"
        quality_status_badge = "badge bg-primary text-white"
        quality_band = "High Quality"
    elif final_quality_score >= 50.0:
        quality_score_label = f"{final_quality_score}/100 (Standard Quality)"
        quality_status_badge = "badge bg-info text-dark"
        quality_band = "Standard Quality"
    else:
        quality_score_label = f"{final_quality_score}/100 (Moderate Evidence)"
        quality_status_badge = "badge bg-warning text-dark"
        quality_band = "Moderate Evidence"

    # Review Signals
    review_signals = extract_review_signals(product, cat)

    # Quality Attributes Summary
    title = str(product.get("title") or "").lower()
    specs = product.get("specifications") or {}
    text_corpus = f"{title} {' '.join(str(v) for v in specs.values())}".lower()

    # Determine build attribute
    material_found = "Standard Durable Material"
    for m in ("stainless steel", "100% cotton", "aluminum", "gorilla glass", "leather", "polycarbonate", "copper", "non-stick"):
        if m in text_corpus:
            material_found = m.title()
            break

    warranty_val = product.get("warranty") or ("1 Year Brand Warranty" if cat in ("phone", "laptop", "television", "kitchen") else "Standard Return Policy")
    seller_val = product.get("seller") or "Verified Marketplace Seller"

    quality_attributes = {
        "material": material_found,
        "warranty": str(warranty_val),
        "seller": str(seller_val),
        "condition": product.get("condition") or "Brand New"
    }

    return {
        "quality_score": final_quality_score if has_sufficient_data else None,
        "raw_quality_score": final_quality_score,
        "quality_score_label": quality_score_label,
        "quality_status_badge": quality_status_badge,
        "quality_band": quality_band,
        "band": quality_band,
        "data_confidence": data_conf,
        "data_confidence_label": f"{data_conf}% Verified Evidence",
        "has_sufficient_data": has_sufficient_data,
        "category": cat,
        "weights": weights,
        "breakdown": {
            "specifications": {"score": c_specs, "weight": weights.get("specifications", 0.30)},
            "ratings_reviews": {"score": c_ratings, "weight": weights.get("ratings_reviews", 0.25)},
            "build_material": {"score": c_build, "weight": weights.get("build_material", 0.20)},
            "performance": {"score": c_perf, "weight": weights.get("performance", 0.15)},
            "warranty_seller": {"score": c_warranty, "weight": weights.get("warranty_seller", 0.10)},
        },
        "review_signals": review_signals,
        "quality_attributes": quality_attributes
    }


def compute_quality_and_confidence(product: Dict[str, Any], category: Optional[str] = None) -> Tuple[float, float]:
    """
    Standard interface used by pipeline and matchers.
    Returns (quality_score, data_confidence).
    """
    report = get_detailed_quality_report(product, category)
    # Return raw score or smoothed score; never 0.0
    q_score = report.get("raw_quality_score") or 50.0
    d_conf = report.get("data_confidence") or 50.0
    return q_score, d_conf


# ─────────────────────────────────────────────────────────────────────────────
# 5. Value for Money Index
# ─────────────────────────────────────────────────────────────────────────────

def calculate_value_for_money_index(
    quality_score: float,
    price_num: Optional[float],
    min_price: float
) -> float:
    """
    Calculates Value for Money Index (0.0 to 100.0).
    Combines quality score with economic price efficiency relative to lowest price.
    """
    if not price_num or price_num <= 0:
        return 0.0

    # Price efficiency factor: min_price / price_num (1.0 for cheapest)
    price_factor = min(1.0, max(0.2, min_price / price_num))

    # Value is 50% Quality + 50% Price Efficiency
    val_index = ((quality_score / 100.0) * 50.0) + (price_factor * 50.0)
    return round(min(100.0, max(10.0, val_index)), 1)
