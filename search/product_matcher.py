"""
search/product_matcher.py
=========================
SmartBuy Authoritative Multi-Signal Product Matching & Hard Rejection Engine.

Implements strict 5-tier classification:
- EXACT_MATCH: All core identifiers (brand, model, variant, storage/RAM/weight/pack) strictly agree.
- VARIANT_MATCH: Same brand and model family, but differs in an attribute (RAM/ROM/size/pack/weight).
- SIMILAR_PRODUCT: Same brand & category, alternative model/configuration.
- RELATED_PRODUCT: Same category or complementary product.
- REJECTED: Disqualified due to hard conflicts (accessories, cross-categories, model generation mismatch).

Enforces Hard Rejection Rules BEFORE weighted scoring:
- Category conflicts: Device vs Accessory (phone vs cover/case/glass, laptop vs bag, phone vs charger).
- Model generational conflicts: Vivo T4 vs Vivo T5e, iPhone 15 vs iPhone 14.
- Brand conflicts: Apple vs Samsung.
- Generic title rejection: "vivo" cannot match "Vivo T4 5G 8GB 128GB" as EXACT_MATCH without explicit model evidence.
- Suspicious price protection: Extreme price deviation (e.g. ₹186 vs ₹18,000) flagged as PRICE/IDENTITY UNVERIFIED.
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional, List
from rapidfuzz import fuzz

from search.query_parser import parse_query_entities
from search.quantity_normalizer import normalize_quantity_and_pack
from search.category_detector import detect_category

logger = logging.getLogger("smartbuy.search.product_matcher")

ACCESSORY_TERMS = {
    'case', 'cases', 'cover', 'covers', 'backcover', 'backcovers', 'back cover', 'back covers',
    'tempered glass', 'screen protector', 'screen protectors', 'screen guard', 'screen guards',
    'lens protector', 'skin', 'skins', 'guard', 'guards', 'cable', 'cables', 'strap', 'straps',
    'band', 'bands', 'pouch', 'pouches', 'sleeve', 'sleeves', 'bumper', 'bumpers', 'stand', 'stands',
    'holder', 'holders', 'mount', 'mounts', 'stylus', 'ear tips', 'silicone case', 'flip cover',
    'wallet case', 'camera glass', 'bag', 'backpack'
}


def is_accessory_conflict(canonical_category: str, candidate_title: str, query_is_accessory: bool = False) -> bool:
    """
    Detects if candidate is an accessory when user did not search for an accessory.
    Examples:
    - Vivo T4 5G phone vs Vivo T4 phone cover => True (REJECT)
    - HP laptop vs HP laptop bag => True (REJECT)
    - iPhone 15 vs iPhone 15 case => True (REJECT)
    - Vivo phone vs Vivo charger => True (REJECT)
    """
    if query_is_accessory:
        return False

    t_low = candidate_title.lower()

    # If canonical is a phone, tablet, laptop, or audio device:
    if canonical_category in ('phone', 'smartphone', 'mobile', 'tablet', 'laptop', 'computer', 'earphones', 'headphones'):
        # Check charger conflict: phone vs charger
        if canonical_category in ('phone', 'smartphone', 'mobile', 'tablet', 'laptop'):
            if any(k in t_low for k in ('charger', 'adapter', 'charging cable', 'power cord', 'power supply')):
                return True

        for acc in ACCESSORY_TERMS:
            # Home textiles containing 'cover' (pillow covers, bedsheets) are not phone cases
            if acc in ('cover', 'covers') and any(h in t_low for h in ('pillow', 'cushion', 'sofa', 'bed')):
                continue
            if re.search(r'\b' + re.escape(acc) + r'\b', t_low):
                return True

    # If canonical is a charger: reject phone cases, phone covers, phones
    elif canonical_category == 'charger':
        if any(acc in t_low for acc in ('case', 'cover', 'tempered glass', 'screen guard', 'skin', 'pouch')):
            return True
        # If candidate is a full phone or laptop rather than charger/adapter:
        if not any(k in t_low for k in ('charger', 'adapter', 'charging', 'power bank', 'cable', 'watt', 'w ')):
            return True

    return False


def check_hard_rejections(
    target_info: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Evaluates hard compatibility gates BEFORE any weighted scoring.
    Returns (is_rejected, reason).
    """
    t_title = str(candidate.get('title') or '').strip()
    t_low = t_title.lower()
    if not t_title or len(t_title) < 4:
        return True, "Empty or invalid candidate title"

    target_brand = (target_info.get("brand") or "").strip().lower()
    cand_brand = (candidate.get("brand") or "").strip().lower()

    # 1. Hard Brand Conflict
    if target_brand and target_brand not in ('generic', 'none', 'unknown', ''):
        # Target brand must be present either in candidate brand or candidate title
        if cand_brand and cand_brand not in ('generic', 'none', 'unknown', ''):
            if target_brand != cand_brand and target_brand not in cand_brand and cand_brand not in target_brand:
                return True, f"Brand conflict: expected '{target_brand.title()}', found '{cand_brand.title()}'"
        else:
            if not re.search(r'\b' + re.escape(target_brand) + r'\b', t_low):
                return True, f"Brand mismatch: target brand '{target_brand.title()}' missing from candidate"

    # 2. Category / Accessory Conflict
    target_cat = str(target_info.get("category") or target_info.get("product_type") or "other").lower()
    if is_accessory_conflict(target_cat, t_title, query_is_accessory=target_info.get("is_accessory", False)):
        return True, f"Accessory conflict: candidate is an accessory for '{target_cat}'"

    # Cross-Category Conflict (e.g. soap vs face wash, laptop vs bag)
    cand_cat = str(candidate.get("category") or detect_category(title=t_title)).lower()
    raw_q = str(target_info.get("raw_query") or "").lower()
    if ('face wash' in raw_q or 'facewash' in raw_q or target_cat in ('face_wash', 'facewash')) and 'soap' in t_low and 'wash' not in t_low:
        return True, "Product type conflict: soap instead of face wash"
    if ('soap' in raw_q or target_cat in ('soap',)) and ('face wash' in t_low or 'facewash' in t_low) and 'soap' not in t_low:
        return True, "Product type conflict: face wash instead of soap"
    if ('laptop' in raw_q or target_cat == 'laptop') and any(b in t_low for b in ('bag', 'backpack', 'sleeve', 'cover')) and not target_info.get("is_accessory", False):
        return True, "Accessory conflict: candidate is a bag/accessory for laptop"
    if target_cat in ('charger',) and not any(k in t_low for k in ('charger', 'adapter', 'charging', 'cord', 'power bank')):
        return True, "Category mismatch: device instead of charger"

    # 3. Model Conflict (e.g. Vivo T4 5G vs Vivo T5e, or iPhone 15 vs iPhone 14)
    target_model = (target_info.get("model") or "").strip().lower()
    if target_model and target_model not in ('standard', 'general', 'none', 'n/a', ''):
        cand_model = (candidate.get("model") or "").strip().lower()
        
        # Phone model generation conflicts
        model_conflicts = [
            (r'\bt4\s*5g\b', [r'\bt5e\b', r'\bt5\b', r'\bt3\b', r'\bt2\b', r'\bt1\b']),
            (r'\bt4\s*pro\b', [r'\bt4\s*lite\b', r'\bt5\b', r'\bt3\b', r'\bt2\b']),
            (r'\bt4\b', [r'\bt5e\b', r'\bt5\b', r'\bt3\b', r'\bt2\b', r'\bt1\b']),
            (r'\biphone\s*15\b', [r'\biphone\s*16\b', r'\biphone\s*14\b', r'\biphone\s*13\b', r'\biphone\s*12\b', r'\biphone\s*11\b']),
            (r'\biphone\s*14\b', [r'\biphone\s*15\b', r'\biphone\s*13\b', r'\biphone\s*12\b']),
            (r'\bs24\b', [r'\bs23\b', r'\bs22\b', r'\bs21\b', r'\bs20\b']),
        ]
        for t_pat, conf_pats in model_conflicts:
            if re.search(t_pat, target_model) or re.search(t_pat, target_info.get("raw_query", "").lower()):
                for cp in conf_pats:
                    if re.search(cp, t_low) and not re.search(t_pat, t_low):
                        return True, f"Conflicting model generation: candidate contains '{cp}' instead of '{target_model}'"

        if cand_model and cand_model not in ('standard', 'general', 'none', 'n/a', ''):
            if target_model != cand_model and target_model not in cand_model and cand_model not in target_model:
                return True, f"Model conflict: target '{target_model}', candidate '{cand_model}'"

    # 4. Generic Title Rejection (Section 3: Amazon titles such as "vivo")
    # A single brand word title cannot match a multi-token query specifying a model or variant
    cleaned_tokens = [w for w in re.findall(r'[a-zA-Z0-9]+', t_title) if len(w) > 1]
    if len(cleaned_tokens) <= 1:
        if target_model or target_info.get("ram") or target_info.get("storage") or target_info.get("network"):
            return True, f"Generic brand name rejected: candidate title '{t_title}' lacks model/variant evidence"

    return False, ""


def evaluate_product_match(
    target_info: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[str, float, Dict[str, float], List[str]]:
    """
    Evaluates candidate against target query or canonical product.
    Returns: (match_status, match_score, breakdown, reasons)
    Match statuses:
    - EXACT_MATCH
    - VARIANT_MATCH
    - SIMILAR_PRODUCT
    - RELATED_PRODUCT
    - REJECTED
    """
    # ── 1. Hard Rejection Checks ──────────────────────────────────────────────
    is_rejected, reject_reason = check_hard_rejections(target_info, candidate)
    if is_rejected:
        return "REJECTED", 0.0, {"rejection": 0.0}, [reject_reason]

    breakdown: Dict[str, float] = {}
    reasons: List[str] = []

    t_title = str(candidate.get("title") or "").strip()
    t_low = t_title.lower()

    # ── 2. Brand Scoring (20 pts) ─────────────────────────────────────────────
    target_brand = (target_info.get("brand") or "").strip().lower()
    cand_brand = (candidate.get("brand") or "").strip().lower()

    if target_brand:
        if target_brand == cand_brand or re.search(r'\b' + re.escape(target_brand) + r'\b', t_low):
            brand_pts = 20.0
            reasons.append(f"Brand verified: {target_brand.title()}")
        else:
            brand_pts = 5.0
    else:
        brand_pts = 15.0  # neutral
    breakdown["brand"] = brand_pts

    # ── 3. Model Scoring (25 pts) ─────────────────────────────────────────────
    target_model = (target_info.get("model") or "").strip().lower()
    cand_model = (candidate.get("model") or "").strip().lower()
    has_model_match = False

    if target_model and target_model not in ('standard', 'general', 'none', 'n/a', ''):
        if target_model in t_low or (cand_model and target_model == cand_model):
            model_pts = 25.0
            has_model_match = True
            reasons.append(f"Exact model verified: {target_model.upper()}")
        elif cand_model and (target_model in cand_model or cand_model in target_model):
            model_pts = 18.0
            has_model_match = True
            reasons.append(f"Compatible model family: {cand_model.upper()}")
        else:
            # Model not verified
            model_pts = 0.0
    else:
        # Non-model category (e.g. chia seeds, face wash)
        model_pts = 20.0
        has_model_match = True
    breakdown["model"] = model_pts

    # ── 4. Variant Attributes Scoring (RAM / Storage / Wattage) (20 pts) ──────
    variant_pts = 20.0
    is_variant_diff = False

    # Check RAM
    tgt_ram = target_info.get("ram")
    cand_ram = candidate.get("ram")
    if not cand_ram:
        m_ram_exp = re.search(r'\b(\d+)\s*gb\s*ram\b', t_low)
        if m_ram_exp:
            cand_ram = f"{m_ram_exp.group(1)}GB"
        else:
            m_ram = re.search(r'\b(\d+)\s*gb\b', t_low)
            if m_ram and int(m_ram.group(1)) <= 32:
                cand_ram = f"{m_ram.group(1)}GB"

    if tgt_ram and cand_ram:
        if str(cand_ram).upper().replace(" ", "") == str(tgt_ram).upper().replace(" ", ""):
            reasons.append(f"RAM verified: {tgt_ram}")
        else:
            variant_pts -= 5.0
            is_variant_diff = True
            reasons.append(f"RAM variant difference ({cand_ram} vs {tgt_ram})")

    # Check Storage
    tgt_storage = target_info.get("storage")
    cand_storage = candidate.get("storage")
    if not cand_storage:
        # Check explicit storage/rom token first
        m_st_exp = re.search(r'\b(\d+)\s*(?:gb|tb)\s*(?:storage|rom|internal)?\b', t_low)
        all_st = re.findall(r'\b(\d+)\s*(gb|tb)\b', t_low)
        for val_num, val_unit in all_st:
            tok = f"{val_num}{val_unit.upper()}"
            if re.search(r'\b' + val_num + r'\s*' + val_unit + r'\s*(?:storage|rom|internal)', t_low):
                cand_storage = tok
                break
            elif tgt_storage and tok.upper() == str(tgt_storage).upper().replace(" ", ""):
                cand_storage = tok
                break
            elif int(val_num) >= 32 and (not cand_ram or tok != str(cand_ram).upper().replace(" ", "")):
                cand_storage = tok

    if tgt_storage and cand_storage:
        if str(cand_storage).upper().replace(" ", "") == str(tgt_storage).upper().replace(" ", ""):
            reasons.append(f"Storage verified: {tgt_storage}")
        else:
            variant_pts -= 5.0
            is_variant_diff = True
            reasons.append(f"Storage variant difference ({cand_storage} vs {tgt_storage})")

    # Check Network (5G vs 4G)
    tgt_net = target_info.get("network")
    if tgt_net:
        if tgt_net.lower() in t_low:
            reasons.append(f"Network verified: {tgt_net}")
        elif tgt_net.upper() == "5G" and "4g" in t_low and "5g" not in t_low:
            variant_pts -= 5.0
            is_variant_diff = True
            reasons.append("Network difference (4G vs 5G)")

    variant_pts = max(0.0, variant_pts)
    breakdown["variant"] = variant_pts

    # ── 5. Quantity & Pack Count Scoring (15 pts) ─────────────────────────────
    qty_pts = 15.0
    tgt_pack = target_info.get("pack_count")
    if tgt_pack and tgt_pack > 1:
        cand_pack = int(candidate.get("pack_quantity") or 1)
        if cand_pack == tgt_pack:
            reasons.append(f"Pack count verified: {tgt_pack}")
        else:
            qty_pts -= 10.0
            is_variant_diff = True
            reasons.append(f"Pack size variant ({cand_pack} vs {tgt_pack})")

    tgt_wt = target_info.get("weight")
    if tgt_wt:
        cand_wt = candidate.get("weight")
        if cand_wt and str(cand_wt).lower().replace(" ", "") != str(tgt_wt).lower().replace(" ", ""):
            qty_pts -= 10.0
            is_variant_diff = True
            reasons.append(f"Weight variant ({cand_wt} vs {tgt_wt})")
    qty_pts = max(0.0, qty_pts)
    breakdown["quantity"] = qty_pts

    # ── 6. Title Token Similarity (20 pts) ────────────────────────────────────
    target_q = target_info.get("raw_query") or ""
    q_norm = re.sub(r'(\d+)\s*([a-zA-Z]+)', r'\1 \2', target_q.lower())
    t_norm = re.sub(r'(\d+)\s*([a-zA-Z]+)', r'\1 \2', t_low)
    q_tokens = [w for w in re.findall(r'[a-zA-Z0-9]+', q_norm) if len(w) > 0]
    t_tokens = set(re.findall(r'[a-zA-Z0-9]+', t_norm))
    if q_tokens:
        matched_cnt = sum(1 for tok in q_tokens if tok in t_tokens)
        title_pts = round((matched_cnt / len(q_tokens)) * 20.0, 1)
    else:
        title_pts = 15.0
    breakdown["title_similarity"] = title_pts

    total_score = round(sum(breakdown.values()), 1)
    total_score = max(0.0, min(100.0, total_score))

    # ── 7. Classify Final Status ──────────────────────────────────────────────
    if total_score >= 85.0 and not is_variant_diff:
        if target_model and not has_model_match:
            status = "SIMILAR_PRODUCT"
        else:
            status = "EXACT_MATCH"
    elif is_variant_diff and has_model_match and total_score >= 60.0:
        status = "VARIANT_MATCH"
    elif total_score >= 50.0:
        status = "SIMILAR_PRODUCT"
    elif total_score >= 35.0:
        status = "RELATED_PRODUCT"
    else:
        status = "REJECTED"
        reasons.append("Low overall similarity score")

    return status, total_score, breakdown, reasons


def check_suspicious_price(
    product: Dict[str, Any],
    all_products: List[Dict[str, Any]]
) -> Tuple[bool, str]:
    """
    Section 17: Suspicious Price Protection.
    Detects extreme price anomalies:
    If product price is suspiciously low (< 25% of the median price of valid branded products)
    and cannot be conclusively proven as the exact target unit/model,
    flags as PRICE/IDENTITY UNVERIFIED so it does not falsely win Best Deal.
    """
    p_num = product.get("price_num")
    if not p_num or p_num <= 0:
        return False, ""

    valid_prices = [
        it.get("price_num") for it in all_products
        if it.get("price_num") and it.get("price_num") > 0 and it.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH")
    ]
    if len(valid_prices) < 2:
        return False, ""

    valid_prices.sort()
    median_price = valid_prices[len(valid_prices) // 2]

    # Extreme low price detection (< 25% of median market price)
    if median_price >= 1000 and p_num < (median_price * 0.25):
        # Check if candidate lacks explicit model or specifications
        specs = product.get("specifications") or {}
        model = product.get("model")
        if not model or model == "N/A" or len(specs) < 3:
            return True, f"Suspicious price (₹{p_num:,} vs median ₹{int(median_price):,}) with incomplete specifications"

    return False, ""
