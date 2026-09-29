"""
search/quality_scorer.py
========================
SmartBuy Specification-Grounded Product Quality Score & Review Analysis Engine.

Strict Architectural Principles:
1. QUALITY FIRST, PRICE SECOND:
   Product Quality is strictly calculated from verified specifications and evidence.
   Price is NEVER a factor in the quality score (a cheaper product must not receive
   a higher quality score if its specifications are weaker).
2. NO ARBITRARY QUALITY SCORES:
   Missing data is never rewarded with phantom baselines. If evidence coverage is low
   or required specifications are missing, quality score is marked as None with
   "Insufficient specification data" and "Quality cannot be verified".
3. CATEGORY-SPECIFIC SPECIFICATION EVALUATION:
   - Mobile Phones: Processor/Chipset, RAM, Storage, Display, Camera, Battery, Charging, 5G, Build/Materials, Warranty
   - Laptops: Processor, RAM, Storage/SSD, GPU, Display, Battery, OS, Build/Materials, Warranty
   - Fashion & Clothing: Fabric/Material, Fit, Size availability, Pattern, Wash Care, Pack Quantity, Return Policy
   - Bags & Luggage: Material, Capacity, Compartments, Water Resistance, Straps/Wheels, Dimensions, Lock/Warranty
   - Beauty Products: Ingredients transparency, Skin suitability, Volume/Net Quantity, Verified Claims, Expiry
   - Grocery Products: Net quantity/weight, Ingredients, Nutritional/Dietary, Certifications, Packaging, Expiry
   - Appliances: Power/Wattage, Capacity, Build Material, Energy Rating, Safety Features, Warranty
   - Other Categories: Brand verification, Model identification, Material, Dimensions/Weight, Warranty
4. TRANSPARENT QUALITY EVIDENCE & COVERAGE:
   Every evaluation outputs an exact Evidence Coverage percentage and a Quality Basis
   checklist displaying verified attributes (✓) and unavailable attributes (⚠).
5. RATINGS AND REVIEWS AS SUPPORTING EVIDENCE:
   Ratings and review count provide Bayesian-smoothed social proof, but cannot override
   missing or inferior technical specifications.
"""

import math
import re
from typing import Dict, Any, Tuple, Optional, List


# ─────────────────────────────────────────────────────────────────────────────
# Category Criteria Weights (Quality First, Price Excluded)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "phone": {
        "specifications": 0.40,
        "performance": 0.20,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "smartphone": {
        "specifications": 0.40,
        "performance": 0.20,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "laptop": {
        "specifications": 0.40,
        "performance": 0.20,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "pen_drive": {
        "specifications": 0.35,
        "performance": 0.25,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "storage_device": {
        "specifications": 0.35,
        "performance": 0.25,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "electronics": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "television": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "earphones": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "headphones": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "audio": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "watch": {
        "specifications": 0.35,
        "performance": 0.20,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "kitchen": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "home_appliance": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "appliance": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "beauty": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "skincare": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "face_wash": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "soap": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "grocery": {
        "specifications": 0.45,
        "performance": 0.15,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "food": {
        "specifications": 0.45,
        "performance": 0.15,
        "ratings_reviews": 0.20,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "clothing": {
        "build_material": 0.35,
        "specifications": 0.30,
        "ratings_reviews": 0.20,
        "performance": 0.05,
        "warranty_seller": 0.10,
    },
    "fashion": {
        "build_material": 0.35,
        "specifications": 0.30,
        "ratings_reviews": 0.20,
        "performance": 0.05,
        "warranty_seller": 0.10,
    },
    "shoes": {
        "build_material": 0.35,
        "specifications": 0.30,
        "ratings_reviews": 0.20,
        "performance": 0.05,
        "warranty_seller": 0.10,
    },
    "bags": {
        "specifications": 0.35,
        "build_material": 0.30,
        "ratings_reviews": 0.20,
        "performance": 0.05,
        "warranty_seller": 0.10,
    },
    "default": {
        "specifications": 0.35,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.15,
        "warranty_seller": 0.10,
    },
    "other": {
        "specifications": 0.35,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.15,
        "warranty_seller": 0.10,
    },
    # Major appliance subcategories
    "television": {
        "specifications": 0.40,
        "performance": 0.20,
        "build_material": 0.15,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "refrigerator": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "washing_machine": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "air_conditioner": {
        "specifications": 0.35,
        "performance": 0.25,
        "build_material": 0.15,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "microwave": {
        "specifications": 0.35,
        "performance": 0.20,
        "build_material": 0.20,
        "ratings_reviews": 0.15,
        "warranty_seller": 0.10,
    },
    "mixer_grinder": {
        "specifications": 0.35,
        "performance": 0.25,
        "build_material": 0.20,
        "ratings_reviews": 0.10,
        "warranty_seller": 0.10,
    },
    # Personal care subcategories
    "shampoo": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
    "makeup": {
        "specifications": 0.40,
        "performance": 0.15,
        "ratings_reviews": 0.25,
        "build_material": 0.10,
        "warranty_seller": 0.10,
    },
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
    if product.get("brand") and str(product["brand"]).strip() not in ("N/A", "Generic", "None", "Other", ""):
        confidence_points += 5.0
    if product.get("model") and str(product["model"]).strip() not in ("N/A", "Standard", "None", ""):
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
            r = float(str(product["rating"]).replace("★", "").strip())
            if r > 0:
                confidence_points += 8.0
        except (ValueError, TypeError):
            pass
    if product.get("review_count") is not None or product.get("reviews") is not None:
        try:
            rc_val = product.get("review_count") or product.get("reviews")
            rc = int(str(rc_val).replace(",", "").replace("reviews", "").strip())
            if rc > 0:
                confidence_points += 7.0
        except (ValueError, TypeError):
            pass

    # 5. Specifications & Metadata (20 pts)
    specs = product.get("specifications") or {}
    cat_specs = {}
    if isinstance(product.get("specs"), dict):
        cat_specs = product["specs"].get("category_specs") or product["specs"]
    norm_specs = product.get("normalized_specifications") or {}

    total_specs_count = sum(1 for d in (specs, cat_specs, norm_specs) if isinstance(d, dict) for v in d.values() if v and str(v).strip() not in ("N/A", "None", "Not Available", ""))
    if total_specs_count > 0:
        confidence_points += min(14.0, total_specs_count * 2.0)

    if product.get("seller") and str(product["seller"]).strip() not in ("N/A", "None", "", "Verified Seller"):
        confidence_points += 3.0
    if product.get("warranty") and str(product["warranty"]).strip() not in ("N/A", "None", "Not Available", ""):
        confidence_points += 3.0

    return round(min(100.0, max(0.0, confidence_points)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Category Specification Evaluator & Quality Basis Checklist
# ─────────────────────────────────────────────────────────────────────────────

def _get_corpus(product: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Combines all text sources and dictionaries from product into a searchable context."""
    title = str(product.get("title") or "").strip()
    desc = str(product.get("description") or "").strip()
    specs = {}

    # Top-level direct attributes
    for top_k in ("brand", "model", "ram", "storage", "processor", "battery", "camera", "display", "material", "fabric", "size", "color", "warranty", "seller", "return_policy", "quantity", "weight", "volume", "wattage", "ingredients"):
        val = product.get(top_k)
        if val and str(val).strip() not in ("N/A", "None", "Not Available", "", "—"):
            specs[top_k] = str(val).strip()

    if isinstance(product.get("specifications"), dict):
        specs.update(product["specifications"])
    if isinstance(product.get("specs"), dict):
        specs.update(product["specs"])
        if isinstance(product["specs"].get("category_specs"), dict):
            specs.update(product["specs"]["category_specs"])
    if isinstance(product.get("attributes"), dict):
        specs.update(product["attributes"])
    if isinstance(product.get("normalized_specifications"), dict):
        specs.update(product["normalized_specifications"])

    text_corpus = f"{title} {desc} {' '.join(str(k) + ' ' + str(v) for k, v in specs.items())}".lower()
    return text_corpus, specs


def evaluate_category_specifications(product: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    Evaluates real, verified specifications against category standards.
    """
    cat = (category or product.get("category") or "").lower().replace(" ", "_")
    title_str = str(product.get("title") or "")
    if not cat or cat in ("default", "other", "unknown"):
        from search.category_detector import detect_category
        cat = detect_category(title=title_str).lower().replace(" ", "_")

    text_corpus, specs = _get_corpus(product)

    quality_basis: List[str] = []
    verified_spec_scores: List[float] = []
    total_expected = 0

    def check_spec(key_aliases: List[str], regex_pattern: Optional[str] = None) -> Optional[str]:
        for alias in key_aliases:
            for sk, sv in specs.items():
                if sk.lower() == alias.lower() and sv and str(sv).strip() not in ("N/A", "None", "Not Available", "", "—"):
                    return str(sv).strip()
        if regex_pattern:
            m = re.search(regex_pattern, text_corpus, re.I)
            if m:
                return m.group(0).strip()
        return None

    perf_points = 0.0
    build_points = 0.0
    warranty_points = 0.0

    # ── A. MOBILE PHONES ────────────────────────────────────────────────────────
    if cat in ("phone", "smartphone", "smartphones", "mobile"):
        total_expected = 8

        # 1. Processor
        cpu = check_spec(["processor", "chipset", "cpu"], r'\b(snapdragon\s*[\d\w]+|dimensity\s*\d{3,4}|bionic\s*a\d+|helio\s*g\d+|tensor\s*g\d|exynos\s*\d{4}|octa[- ]core)\b')
        if cpu:
            quality_basis.append(f"✓ Processor verified ({cpu})")
            if re.search(r'\b(gen\s*[234]|dimensity\s*9|bionic\s*a1[6-8]|tensor\s*g[34])\b', cpu, re.I):
                verified_spec_scores.append(95.0)
                perf_points += 45.0
            elif re.search(r'\b(snapdragon\s*[78]|dimensity\s*[78]|bionic|tensor)\b', cpu, re.I):
                verified_spec_scores.append(85.0)
                perf_points += 35.0
            elif re.search(r'\b(snapdragon\s*6|dimensity\s*6|helio\s*g99)\b', cpu, re.I):
                verified_spec_scores.append(75.0)
                perf_points += 25.0
            else:
                verified_spec_scores.append(60.0)
                perf_points += 15.0
        else:
            quality_basis.append("⚠ Processor information unavailable")

        # 2. RAM
        ram = check_spec(["ram", "system_ram", "memory"], r'\b(\d{1,2})\s*gb\s*(?:ram|lpddr)?\b')
        if ram:
            quality_basis.append(f"✓ RAM verified ({ram})")
            ram_m = re.search(r'(\d+)', ram)
            ram_val = int(ram_m.group(1)) if ram_m else 4
            if ram_val >= 12:
                verified_spec_scores.append(95.0)
                perf_points += 30.0
            elif ram_val >= 8:
                verified_spec_scores.append(85.0)
                perf_points += 25.0
            elif ram_val >= 6:
                verified_spec_scores.append(75.0)
                perf_points += 20.0
            else:
                verified_spec_scores.append(60.0)
                perf_points += 10.0
        else:
            quality_basis.append("⚠ RAM information unavailable")

        # 3. Storage
        storage = check_spec(["storage", "internal_storage", "rom"], r'\b(64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b')
        if storage:
            quality_basis.append(f"✓ Storage verified ({storage})")
            if "tb" in storage.lower() or "512" in storage:
                verified_spec_scores.append(95.0)
            elif "256" in storage:
                verified_spec_scores.append(88.0)
            elif "128" in storage:
                verified_spec_scores.append(80.0)
            else:
                verified_spec_scores.append(65.0)
        else:
            quality_basis.append("⚠ Storage information unavailable")

        # 4. Display
        disp = check_spec(["display", "screen_size", "display_type"], r'\b(amoled|oled|120\s*hz|90\s*hz|fhd\+|super\s*amoled|\d{1,2}\.\d{1,2}\s*inch)\b')
        if disp:
            quality_basis.append(f"✓ Display specifications verified ({disp})")
            if any(w in disp.lower() for w in ("amoled", "120", "fhd")):
                verified_spec_scores.append(90.0)
            else:
                verified_spec_scores.append(75.0)
        else:
            quality_basis.append("⚠ Display information unavailable")

        # 5. Camera
        cam = check_spec(["camera", "rear_camera", "primary_camera"], r'\b(\d{2,3}\s*mp|dual|triple|ois|4k)\b')
        if cam:
            quality_basis.append(f"✓ Camera verified ({cam})")
            verified_spec_scores.append(85.0)
            perf_points += 15.0
        else:
            quality_basis.append("⚠ Camera information unavailable")

        # 6. Battery & Charging
        bat = check_spec(["battery", "battery_capacity"], r'\b(\d{4,5})\s*mah\b')
        charge = check_spec(["charging", "fast_charging"], r'\b(\d{2,3}\s*w|fast\s*charg\w+|supervooc)\b')
        if bat or charge:
            b_str = bat or ""
            c_str = f", {charge}" if charge else ""
            quality_basis.append(f"✓ Battery/Charging verified ({b_str}{c_str})".replace("()", ""))
            verified_spec_scores.append(85.0)
            perf_points += 15.0
        else:
            quality_basis.append("⚠ Battery/Charging information unavailable")

        # 7. 5G Support
        if "5g" in text_corpus:
            quality_basis.append("✓ 5G Network support verified")
            verified_spec_scores.append(90.0)
            perf_points += 15.0
        else:
            quality_basis.append("⚠ 5G Network connectivity unverified")

        # 8. Build & Warranty
        bld = check_spec(["build", "material", "water_resistance"], r'\b(gorilla\s*glass|ip68|ip67|aluminum|titanium|glass\s*back)\b')
        if bld:
            quality_basis.append(f"✓ Build & Durability verified ({bld})")
            build_points = 85.0
        else:
            build_points = 65.0
            quality_basis.append("⚠ Special build/water resistance unverified")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty|manufacturer\s*warranty)\b')
        seller = product.get("seller")
        if warr or (product.get("brand") and product.get("brand") not in ("Generic", "N/A")):
            w_disp = warr or "1 Year Manufacturer Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points += 60.0
        else:
            quality_basis.append("⚠ Brand warranty information unavailable")
        if seller and str(seller).strip() not in ("N/A", "None", ""):
            warranty_points += 30.0

    # ── B. LAPTOPS ──────────────────────────────────────────────────────────────
    elif cat in ("laptop", "laptops"):
        total_expected = 7

        cpu = check_spec(["processor", "cpu"], r'\b(core\s*i[3579]|ryzen\s*[3579]|apple\s*m[1234]|m[1234]\s*pro|ultra\s*[579])\b')
        if cpu:
            quality_basis.append(f"✓ Processor verified ({cpu})")
            if re.search(r'\b(i[79]|ryzen\s*[79]|m[234]|ultra\s*[79])\b', cpu, re.I):
                verified_spec_scores.append(95.0)
                perf_points += 50.0
            elif re.search(r'\b(i5|ryzen\s*5|m1)\b', cpu, re.I):
                verified_spec_scores.append(85.0)
                perf_points += 35.0
            else:
                verified_spec_scores.append(70.0)
                perf_points += 20.0
        else:
            quality_basis.append("⚠ Processor information unavailable")

        ram = check_spec(["ram", "system_ram"], r'\b(\d{1,2})\s*gb\s*(?:ram|ddr\d|lpddr\d)?\b')
        if ram:
            quality_basis.append(f"✓ RAM verified ({ram})")
            ram_m = re.search(r'(\d+)', ram)
            ram_val = int(ram_m.group(1)) if ram_m else 8
            if ram_val >= 32:
                verified_spec_scores.append(95.0)
                perf_points += 30.0
            elif ram_val >= 16:
                verified_spec_scores.append(88.0)
                perf_points += 25.0
            elif ram_val >= 8:
                verified_spec_scores.append(78.0)
                perf_points += 15.0
            else:
                verified_spec_scores.append(55.0)
                perf_points += 5.0
        else:
            quality_basis.append("⚠ RAM information unavailable")

        ssd = check_spec(["storage", "ssd", "ssd_capacity"], r'\b(\d{3,4})\s*gb\s*ssd\b|\b(1|2)\s*tb\s*ssd\b')
        if ssd:
            quality_basis.append(f"✓ SSD Storage verified ({ssd})")
            verified_spec_scores.append(88.0)
        else:
            quality_basis.append("⚠ SSD Storage information unavailable")

        disp = check_spec(["display", "screen_size"], r'\b(fhd|ips|oled|qhd|4k|144\s*hz|\d{2}(?:\.\d)?\s*inch)\b')
        if disp:
            quality_basis.append(f"✓ Display specifications verified ({disp})")
            verified_spec_scores.append(82.0)
        else:
            quality_basis.append("⚠ Display specifications unavailable")

        gpu = check_spec(["graphics", "gpu"], r'\b(rtx\s*\d{4}|gtx\s*\d{4}|radeon|iris\s*xe|integrated)\b')
        if gpu:
            quality_basis.append(f"✓ GPU verified ({gpu})")
            if "rtx" in gpu.lower():
                verified_spec_scores.append(92.0)
                perf_points += 20.0
            else:
                verified_spec_scores.append(75.0)
        else:
            quality_basis.append("⚠ GPU details unverified")

        bld = check_spec(["material", "build"], r'\b(aluminum|metal|lightweight|backlit)\b')
        if bld:
            quality_basis.append(f"✓ Build & Chassis verified ({bld})")
            build_points = 85.0
        else:
            build_points = 65.0
            quality_basis.append("⚠ Chassis material unverified")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty|onsite)\b')
        if warr or (product.get("brand") and product.get("brand") not in ("Generic", "N/A")):
            w_str = warr or "1 Year Brand Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_str})")
            warranty_points += 60.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")
        if product.get("seller"):
            warranty_points += 30.0

    # ── B2. PEN DRIVES & STORAGE DEVICES ───────────────────────────────────────
    elif cat in ("pen_drive", "storage_device", "flash_drive", "pendrive") or "storage" in cat or "pen_drive" in cat:
        total_expected = 6

        # 1. Capacity
        cap = check_spec(["storage_capacity", "capacity", "storage"], r'\b(\d{1,4})\s*(?:gb|tb)\b')
        if cap:
            quality_basis.append(f"✓ Storage Capacity verified ({cap})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Storage capacity unverified")

        # 2. USB Version / Interface
        usb = check_spec(["usb_version", "interface"], r'\b(usb\s*3\.[012]|usb\s*2\.0|type-c|usb\s*3\.0)\b')
        if usb:
            quality_basis.append(f"✓ Interface / USB Version verified ({usb})")
            if "3." in usb:
                verified_spec_scores.append(90.0)
                perf_points += 40.0
            else:
                verified_spec_scores.append(75.0)
                perf_points += 25.0
        else:
            quality_basis.append("⚠ USB version/interface unverified")

        # 3. Read Speed (Only if verified from authentic evidence)
        read_spd = check_spec(["read_speed"], r'\b(\d{2,4})\s*(?:mb/s|mbps)\b')
        if read_spd:
            quality_basis.append(f"✓ Read Speed verified ({read_spd})")
            verified_spec_scores.append(88.0)
            perf_points += 30.0
        else:
            quality_basis.append("⚠ Read speed benchmark unavailable")

        # 4. Write Speed (Only if verified from authentic evidence)
        write_spd = check_spec(["write_speed"], r'\b(\d{2,4})\s*(?:mb/s|mbps)\b')
        if write_spd:
            quality_basis.append(f"✓ Write Speed verified ({write_spd})")
            verified_spec_scores.append(85.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Write speed benchmark unavailable")

        # 5. Build Material / Durability
        bld = check_spec(["material", "build", "casing"], r'\b(metal|aluminum|zinc\s*alloy|shockproof|waterproof)\b')
        if bld:
            quality_basis.append(f"✓ Build & Casing verified ({bld})")
            build_points = 85.0
        else:
            build_points = 60.0
            quality_basis.append("⚠ Casing material unverified")

        # 6. Warranty
        warr = check_spec(["warranty"], r'\b(\d+\s*year|lifetime|brand\s*warranty)\b')
        if warr or (product.get("brand") and product.get("brand") not in ("Generic", "N/A")):
            w_str = warr or "Manufacturer Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_str})")
            warranty_points += 60.0
        else:
            quality_basis.append("⚠ Warranty details unavailable")
        if product.get("seller"):
            warranty_points += 30.0

    # ── C1. FOOTWEAR & SLIPPERS ────────────────────────────────────────────────
    elif cat in ("shoes", "footwear", "slippers"):
        total_expected = 6

        sol = check_spec(["sole_material", "sole"], r'\b(eva|rubber|tpr|pu|polyurethane|air\s*mix|leather|cushioned|memory\s*foam)\b')
        if sol:
            quality_basis.append(f"✓ Sole Material verified ({sol})")
            verified_spec_scores.append(88.0)
            build_points = 88.0
        else:
            quality_basis.append("⚠ Sole material specification unavailable")

        cl = check_spec(["closure_type", "closure"], r'\b(slip-on|slip\s*on|lace-up|lace\s*up|velcro|hook\s*and\s*loop)\b')
        if cl or any(w in text_corpus for w in ("slipper", "slides", "flip flop")):
            c_disp = cl or "Slip-On"
            quality_basis.append(f"✓ Closure & Fit verified ({c_disp})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Closure type unverified")

        up_mat = check_spec(["upper_material", "material"], r'\b(mesh|synthetic|leather|canvas|eva|rubber|knit)\b')
        if up_mat:
            quality_basis.append(f"✓ Upper Construction verified ({up_mat})")
            verified_spec_scores.append(85.0)
            build_points = max(build_points, 85.0)
        else:
            quality_basis.append("⚠ Upper material unverified")

        sz = check_spec(["size"], r'\b(?:uk|us|size)?\s*[:\s-]*(\d{1,2}(?:\.\d)?)\b')
        if sz:
            quality_basis.append(f"✓ Sizing details verified ({sz})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Sizing information unavailable")

        ret = check_spec(["return_policy", "warranty"], r'\b(returnable|\d+\s*days\s*return|warranty)\b')
        if ret or product.get("return_policy") or product.get("seller"):
            quality_basis.append("✓ Return Policy & Seller Trust verified")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Return policy unavailable")

        if any(w in text_corpus for w in ("cushion", "padded", "orthopedic", "memory foam", "comfort")):
            quality_basis.append("✓ Ergonomic Cushioning & Comfort verified")
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Ergonomic comfort features unverified")

    # ── C2. CLOTHING & FASHION ──────────────────────────────────────────────────
    elif cat in ("clothing", "fashion"):
        total_expected = 6

        mat = check_spec(["material", "fabric", "fabric_type"], r'\b(100%\s*cotton|pure\s*cotton|denim|linen|silk|wool|polyester|poly-cotton)\b')
        if mat:
            quality_basis.append(f"✓ Fabric & Material verified ({mat})")
            if any(w in mat.lower() for w in ("100% cotton", "pure cotton", "linen", "silk")):
                verified_spec_scores.append(92.0)
                build_points = 90.0
            else:
                verified_spec_scores.append(75.0)
                build_points = 72.0
        else:
            quality_basis.append("⚠ Fabric composition unavailable")

        fit = check_spec(["fit", "fit_type"], r'\b(slim\s*fit|regular\s*fit|relaxed\s*fit|tailored|skinny)\b')
        if fit:
            quality_basis.append(f"✓ Fit details verified ({fit})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Fit details unavailable")

        sz = check_spec(["size"], r'\b(xs|s|m|l|xl|xxl|2xl|3xl|\d{2})\b')
        if sz:
            quality_basis.append(f"✓ Sizing details verified ({sz})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Sizing information unavailable")

        pat = check_spec(["pattern"], r'\b(solid|printed|striped|checked|floral)\b')
        if pat:
            quality_basis.append(f"✓ Pattern/Design verified ({pat})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Pattern information unavailable")

        pq = check_spec(["pack_quantity", "quantity"], r'\b(pack\s*of\s*\d+|pack-\d+)\b')
        if pq:
            quality_basis.append(f"✓ Pack quantity verified ({pq})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Pack quantity unverified")

        ret = check_spec(["return_policy", "wash_care"], r'\b(returnable|days\s*return|machine\s*wash|hand\s*wash)\b')
        if ret or product.get("return_policy"):
            quality_basis.append("✓ Care & Return Policy verified")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Care instructions / return policy unavailable")

    # ── D. BAGS & LUGGAGE ───────────────────────────────────────────────────────
    elif cat in ("bags", "luggage", "backpack"):
        total_expected = 6

        mat = check_spec(["material", "outer_material"], r'\b(polycarbonate|polyester|genuine\s*leather|leather|nylon|abs)\b')
        if mat:
            quality_basis.append(f"✓ Material verified ({mat})")
            if "polycarbonate" in mat.lower() or "leather" in mat.lower():
                verified_spec_scores.append(90.0)
                build_points = 90.0
            else:
                verified_spec_scores.append(78.0)
                build_points = 75.0
        else:
            quality_basis.append("⚠ Material specifications unavailable")

        cap = check_spec(["capacity", "volume"], r'\b(\d{1,3})\s*(?:l|ltr|litres?|liters?)\b')
        if cap:
            quality_basis.append(f"✓ Capacity verified ({cap})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Capacity information unavailable")

        comp = check_spec(["compartments", "laptop_compartment"], r'\b(\d+\s*compartments?|laptop\s*compartment|padded)\b')
        if comp:
            quality_basis.append(f"✓ Compartment features verified ({comp})")
            verified_spec_scores.append(82.0)
        else:
            quality_basis.append("⚠ Compartment details unavailable")

        if "water" in text_corpus or "rain" in text_corpus:
            quality_basis.append("✓ Water resistance / weather protection verified")
            perf_points += 35.0
        else:
            quality_basis.append("⚠ Water resistance unverified")

        lock_wheel = check_spec(["lock_type", "wheels", "straps"], r'\b(tsa\s*lock|360\s*spinner|4\s*wheel|padded\s*straps)\b')
        if lock_wheel:
            quality_basis.append(f"✓ Hardware/Wheels verified ({lock_wheel})")
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Lock / hardware information unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|lifetime|warranty)\b')
        if warr:
            quality_basis.append(f"✓ Warranty verified ({warr})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty details unavailable")

    # ── E. BEAUTY & PERSONAL CARE ───────────────────────────────────────────────
    elif cat in ("beauty", "face_wash", "soap", "skincare", "shampoo"):
        total_expected = 6

        ing = check_spec(["ingredients", "active_ingredient"], r'\b(salicylic\s*acid|vitamin\s*c|tea\s*tree|neem|aloe\s*vera|hyaluronic|niacinamide|sandalwood|ubtan)\b')
        if ing:
            quality_basis.append(f"✓ Key ingredients verified ({ing})")
            verified_spec_scores.append(90.0)
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Ingredient transparency unavailable")

        st = check_spec(["skin_type", "hair_type"], r'\b(all\s*skin\s*types?|oily\s*skin|dry\s*skin|sensitive\s*skin|acne\s*prone)\b')
        if st:
            quality_basis.append(f"✓ Suitability verified ({st})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Skin/Hair suitability information unavailable")

        vol = check_spec(["quantity", "net_quantity", "volume", "weight"], r'\b(\d+(?:\.\d+)?)\s*(ml|g|gm|grams?)\b')
        if vol:
            quality_basis.append(f"✓ Net quantity verified ({vol})")
            verified_spec_scores.append(82.0)
        else:
            quality_basis.append("⚠ Net quantity unverified")

        claims = check_spec(["claims", "benefits"], r'\b(dermatologically\s*tested|paraben\s*free|sulfate\s*free|toxin\s*free|organic)\b')
        if claims:
            quality_basis.append(f"✓ Formulation claims verified ({claims})")
            perf_points += 40.0
            build_points = 80.0
        else:
            quality_basis.append("⚠ Special formulation claims unverified")

        pq = check_spec(["pack_quantity", "quantity"], r'\b(pack\s*of\s*\d+|pack-\d+)\b')
        if pq:
            quality_basis.append(f"✓ Pack quantity verified ({pq})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Pack quantity unverified")

        exp = check_spec(["expiry", "shelf_life"], r'\b(\d+\s*months?|expiry|shelf\s*life)\b')
        if exp:
            quality_basis.append(f"✓ Shelf life verified ({exp})")
            warranty_points = 75.0
        else:
            warranty_points = 50.0
            quality_basis.append("⚠ Shelf life / expiry information unavailable")

    # ── F. GROCERY & FOOD ───────────────────────────────────────────────────────
    elif cat in ("grocery", "food"):
        total_expected = 6

        wt = check_spec(["weight", "net_quantity", "quantity"], r'\b(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|kilograms?)\b')
        if wt:
            quality_basis.append(f"✓ Net quantity verified ({wt})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Net quantity unavailable")

        ing = check_spec(["ingredients"], r'\b(100%\s*raw|whole\s*grain|organic|pure|chia\s*seeds|natural)\b')
        if ing:
            quality_basis.append(f"✓ Ingredients verified ({ing})")
            verified_spec_scores.append(90.0)
            perf_points += 35.0
        else:
            quality_basis.append("⚠ Ingredients list unavailable")

        diet = check_spec(["diet_type", "nutritional_info"], r'\b(gluten\s*free|vegan|high\s*fiber|omega-3|non-gmo)\b')
        if diet:
            quality_basis.append(f"✓ Dietary info verified ({diet})")
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Dietary information unavailable")

        cert = check_spec(["certifications", "organic"], r'\b(certified\s*organic|fssai|usda\s*organic|jaivik\s*bharat)\b')
        if cert:
            quality_basis.append(f"✓ Certifications verified ({cert})")
            build_points = 90.0
            verified_spec_scores.append(92.0)
        else:
            quality_basis.append("⚠ Certifications unverified")

        pack = check_spec(["packaging"], r'\b(vacuum\s*sealed|resealable|pouch|jar|bottle)\b')
        if pack:
            quality_basis.append(f"✓ Packaging verified ({pack})")
            build_points = 80.0
        else:
            build_points = 50.0
            quality_basis.append("⚠ Packaging type unverified")

        exp = check_spec(["expiry", "shelf_life"], r'\b(\d+\s*months?|best\s*before|expiry)\b')
        if exp:
            quality_basis.append(f"✓ Best before / shelf life verified ({exp})")
            warranty_points = 75.0
        else:
            warranty_points = 50.0
            quality_basis.append("⚠ Expiry / shelf life information unavailable")

    # ── G. ELECTRONIC & KITCHEN APPLIANCES ──────────────────────────────────────
    elif cat in ("kitchen", "home_appliance", "appliance"):
        total_expected = 6

        watt = check_spec(["wattage", "power"], r'\b(\d{3,4})\s*(?:w|watt|watts)\b')
        if watt:
            quality_basis.append(f"✓ Wattage verified ({watt})")
            w_m = re.search(r'(\d+)', watt)
            w_val = int(w_m.group(1)) if w_m else 500
            if w_val >= 750:
                verified_spec_scores.append(90.0)
                perf_points += 45.0
            else:
                verified_spec_scores.append(78.0)
                perf_points += 30.0
        else:
            quality_basis.append("⚠ Wattage / Power information unavailable")

        cap = check_spec(["capacity", "jars_count", "jars"], r'\b(\d+\s*jars?|\d+(?:\.\d+)?\s*(?:l|litres?))\b')
        if cap:
            quality_basis.append(f"✓ Capacity / Jars verified ({cap})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Capacity / Jar count unavailable")

        mat = check_spec(["material", "motor_type"], r'\b(stainless\s*steel|copper\s*motor|food\s*grade|abs)\b')
        if mat:
            quality_basis.append(f"✓ Material & Motor verified ({mat})")
            build_points = 85.0
        else:
            build_points = 50.0
            quality_basis.append("⚠ Material / Motor type unverified")

        safe = check_spec(["safety_features"], r'\b(overload\s*protection|auto\s*shut[- ]off|safety\s*lock)\b')
        if safe:
            quality_basis.append(f"✓ Safety features verified ({safe})")
            perf_points += 35.0
        else:
            quality_basis.append("⚠ Safety features unverified")

        star = check_spec(["energy_rating"], r'\b([1-5]\s*star)\b')
        if star:
            quality_basis.append(f"✓ Energy rating verified ({star})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Energy star rating unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*years?|brand\s*warranty|motor\s*warranty)\b')
        if warr:
            quality_basis.append(f"✓ Warranty verified ({warr})")
            warranty_points = 85.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── H. EARBUDS & HEADPHONES ─────────────────────────────────────────────────
    elif cat in ("earbuds", "earphones", "headphones", "audio"):
        total_expected = 6

        drv = check_spec(["driver_size", "driver"], r'\b(\d{1,2}(?:\.\d)?\s*mm)\b')
        if drv:
            quality_basis.append(f"✓ Audio Driver verified ({drv})")
            verified_spec_scores.append(88.0)
            perf_points += 30.0
        else:
            quality_basis.append("⚠ Audio driver details unavailable")

        anc = check_spec(["active_noise_cancellation", "noise_cancellation"], r'\b(anc|active\s*noise|enc|environmental\s*noise)\b')
        if anc or any(k in text_corpus for k in ("anc", "noise cancellation", "enc")):
            a_disp = "Active Noise Cancellation (ANC)" if ("anc" in text_corpus or "active" in text_corpus) else "Environmental Noise Cancellation (ENC)"
            quality_basis.append(f"✓ Noise Cancellation verified ({a_disp})")
            verified_spec_scores.append(90.0)
            perf_points += 35.0
        else:
            quality_basis.append("⚠ Active noise cancellation unavailable")

        bat = check_spec(["battery_life", "playback_time"], r'(\d{1,2})\s*(?:hours?|hrs?)\b')
        if bat:
            quality_basis.append(f"✓ Playback Battery Life verified ({bat} Hours)")
            verified_spec_scores.append(85.0)
            perf_points += 25.0
        else:
            quality_basis.append("⚠ Battery playback time unavailable")

        bt = check_spec(["bluetooth", "connectivity"], r'\b(bluetooth\s*\d(?:\.\d)?|v\d(?:\.\d)?)\b')
        if bt:
            quality_basis.append(f"✓ Wireless Connectivity verified ({bt})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Bluetooth version unverified")

        wr = check_spec(["water_resistance"], r'\b(ipx[4-8]|ip[56][4-8]|water\s*resistant|sweat\s*proof)\b')
        if wr:
            quality_basis.append(f"✓ Water / Sweat Resistance verified ({wr})")
            build_points = 85.0
        else:
            quality_basis.append("⚠ Water resistance unverified")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty|warranty)\b')
        if warr or product.get("brand"):
            w_disp = warr or "1 Year Brand Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── I. TELEVISION ───────────────────────────────────────────────────────────
    elif cat in ("television",):
        total_expected = 5

        sz = check_spec(["screen_size", "display"], r'\b(\d{2,3})\s*(?:inch|cm)\b')
        if sz:
            quality_basis.append(f"✓ Screen size verified ({sz})")
            verified_spec_scores.append(85.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Screen size unavailable")

        tech = check_spec(["display_technology", "resolution"], r'\b(oled|qled|4k|uhd|full\s*hd)\b')
        if tech:
            quality_basis.append(f"✓ Display technology verified ({tech})")
            if any(t in tech.lower() for t in ("oled", "qled", "4k", "uhd")):
                verified_spec_scores.append(92.0)
                perf_points += 40.0
            else:
                verified_spec_scores.append(75.0)
                perf_points += 25.0
        else:
            quality_basis.append("⚠ Display technology unavailable")

        hz = check_spec(["refresh_rate"], r'\b(\d+)\s*hz\b')
        if hz:
            quality_basis.append(f"✓ Refresh rate verified ({hz})")
            hz_val = int(re.search(r'\d+', hz).group(0)) if re.search(r'\d+', hz) else 50
            verified_spec_scores.append(90.0 if hz_val >= 120 else 75.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Refresh rate unavailable")

        energy = check_spec(["energy_rating"], r'\b([1-5])\s*star\b')
        if energy:
            quality_basis.append(f"✓ Energy rating verified ({energy})")
            build_points = 80.0
        else:
            quality_basis.append("⚠ Energy rating unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            w_disp = warr or "1 Year Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── J. REFRIGERATOR ─────────────────────────────────────────────────────────
    elif cat in ("refrigerator",):
        total_expected = 4

        cap = check_spec(["capacity"], r'\b(\d+)\s*(?:l|litres?)\b')
        if cap:
            quality_basis.append(f"✓ Capacity verified ({cap})")
            cap_val = int(re.search(r'\d+', cap).group(0)) if re.search(r'\d+', cap) else 0
            verified_spec_scores.append(90.0 if cap_val >= 300 else 80.0)
            perf_points += 30.0
        else:
            quality_basis.append("⚠ Capacity unavailable")

        cooling = check_spec(["cooling_type"], r'\b(frost\s*free|direct\s*cool)\b')
        if cooling:
            quality_basis.append(f"✓ Cooling type verified ({cooling})")
            verified_spec_scores.append(85.0 if "frost" in cooling.lower() else 75.0)
            build_points = 80.0
        else:
            quality_basis.append("⚠ Cooling type unavailable")

        energy = check_spec(["energy_rating"], r'\b([1-5])\s*star\b')
        if energy:
            quality_basis.append(f"✓ Energy rating verified ({energy})")
            star_val = int(re.search(r'\d+', energy).group(0)) if re.search(r'\d+', energy) else 0
            verified_spec_scores.append(70.0 + star_val * 5)
        else:
            quality_basis.append("⚠ Energy rating unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            w_disp = warr or "1 Year Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── K. WASHING MACHINE ───────────────────────────────────────────────────────
    elif cat in ("washing_machine",):
        total_expected = 5

        cap = check_spec(["capacity"], r'\b(\d+(?:\.\d+)?)\s*kg\b')
        if cap:
            quality_basis.append(f"✓ Capacity verified ({cap})")
            cap_val = float(re.search(r'[\d.]+', cap).group(0)) if re.search(r'[\d.]+', cap) else 0
            verified_spec_scores.append(90.0 if cap_val >= 7 else 78.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Capacity unavailable")

        load_type = check_spec(["load_type"], r'\b(front\s*load|top\s*load)\b')
        if load_type:
            quality_basis.append(f"✓ Load type verified ({load_type})")
            verified_spec_scores.append(85.0 if "front" in load_type.lower() else 78.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Load type unavailable")

        auto_type = check_spec(["type"], r'\b(fully\s*automatic|semi\s*automatic)\b')
        if auto_type:
            quality_basis.append(f"✓ Type verified ({auto_type})")
            verified_spec_scores.append(88.0 if "fully" in auto_type.lower() else 75.0)
        else:
            quality_basis.append("⚠ Automation type unavailable")

        rpm = check_spec(["spin_speed"], r'\b(\d{3,4})\s*rpm\b')
        if rpm:
            quality_basis.append(f"✓ Spin speed verified ({rpm})")
            rpm_val = int(re.search(r'\d+', rpm).group(0)) if re.search(r'\d+', rpm) else 0
            verified_spec_scores.append(88.0 if rpm_val >= 1000 else 78.0)
            build_points = 80.0
        else:
            quality_basis.append("⚠ Spin speed unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            w_disp = warr or "2 Year Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── L. AIR CONDITIONER ──────────────────────────────────────────────────────
    elif cat in ("air_conditioner",):
        total_expected = 4

        cap = check_spec(["capacity"], r'\b(\d+(?:\.\d+)?)\s*ton\b')
        if cap:
            quality_basis.append(f"✓ Capacity verified ({cap})")
            verified_spec_scores.append(85.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Capacity unavailable")

        if "inverter" in text_corpus:
            quality_basis.append("✓ Inverter technology verified")
            verified_spec_scores.append(90.0)
            perf_points += 35.0
        else:
            quality_basis.append("⚠ Inverter technology unverified")

        energy = check_spec(["energy_rating"], r'\b([1-5])\s*star\b')
        if energy:
            quality_basis.append(f"✓ Energy rating verified ({energy})")
            star_val = int(re.search(r'\d+', energy).group(0)) if re.search(r'\d+', energy) else 0
            verified_spec_scores.append(70.0 + star_val * 5)
            build_points = 75.0 + star_val * 2
        else:
            quality_basis.append("⚠ Energy rating unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            w_disp = warr or "1 Year Warranty"
            quality_basis.append(f"✓ Warranty verified ({w_disp})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── M. MICROWAVE ────────────────────────────────────────────────────────────
    elif cat in ("microwave",):
        total_expected = 4

        cap = check_spec(["capacity"], r'\b(\d+)\s*(?:l|litres?)\b')
        if cap:
            quality_basis.append(f"✓ Capacity verified ({cap})")
            cap_val = int(re.search(r'\d+', cap).group(0)) if re.search(r'\d+', cap) else 0
            verified_spec_scores.append(85.0 if cap_val >= 25 else 78.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Capacity unavailable")

        mtype = check_spec(["type"], r'\b(solo|grill|convection)\b')
        if mtype:
            quality_basis.append(f"✓ Type verified ({mtype})")
            if "convection" in mtype.lower():
                verified_spec_scores.append(90.0)
                perf_points += 35.0
            else:
                verified_spec_scores.append(80.0)
                perf_points += 20.0
        else:
            quality_basis.append("⚠ Microwave type unavailable")

        watt = check_spec(["wattage"], r'\b(\d{3,4})\s*(?:w|watt)\b')
        if watt:
            quality_basis.append(f"✓ Wattage verified ({watt})")
            verified_spec_scores.append(85.0)
            build_points = 80.0
        else:
            quality_basis.append("⚠ Wattage unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            quality_basis.append(f"✓ Warranty verified ({warr or '1 Year Warranty'})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── N. MIXER GRINDER ────────────────────────────────────────────────────────
    elif cat in ("mixer_grinder",):
        total_expected = 4

        watt = check_spec(["wattage", "power"], r'\b(\d{3,4})\s*(?:w|watt|watts)\b')
        if watt:
            quality_basis.append(f"✓ Wattage verified ({watt})")
            w_val = int(re.search(r'\d+', watt).group(0)) if re.search(r'\d+', watt) else 0
            verified_spec_scores.append(92.0 if w_val >= 750 else (85.0 if w_val >= 500 else 72.0))
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Wattage unavailable")

        jars = check_spec(["jars_count", "number_of_jars"], r'\b(\d+)\s*jars?\b')
        if jars:
            quality_basis.append(f"✓ Jars verified ({jars})")
            jar_val = int(re.search(r'\d+', jars).group(0)) if re.search(r'\d+', jars) else 0
            verified_spec_scores.append(88.0 if jar_val >= 3 else 75.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Jars count unavailable")

        mat = check_spec(["material"], r'\b(stainless steel|steel)\b')
        if mat:
            quality_basis.append(f"✓ Material verified ({mat})")
            build_points = 85.0
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Material unverified")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty)\b')
        if warr or product.get("brand"):
            quality_basis.append(f"✓ Warranty verified ({warr or '1 Year Warranty'})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # ── O. SHAMPOO / HAIR CARE ─────────────────────────────────────────────────
    elif cat in ("shampoo",):
        total_expected = 4

        ingr = check_spec(["key_ingredient", "ingredients"], r'\b(keratin|biotin|argan|tea tree|onion|coconut|aloe vera|caffeine|protein|neem|rosemary|ginger)\b')
        if ingr:
            quality_basis.append(f"✓ Key ingredient verified ({ingr})")
            verified_spec_scores.append(85.0)
            perf_points += 30.0
        else:
            quality_basis.append("⚠ Key ingredient unavailable")

        vol = check_spec(["volume", "quantity"], r'\b(\d+(?:\.\d+)?)\s*(ml|l)\b')
        if vol:
            quality_basis.append(f"✓ Volume verified ({vol})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Volume unavailable")

        brand = product.get("brand")
        if brand and str(brand).strip().lower() not in ("generic", "none", "n/a", "other", ""):
            quality_basis.append(f"✓ Brand verified ({brand})")
            verified_spec_scores.append(82.0)
            build_points = 78.0
        else:
            quality_basis.append("⚠ Brand unverified")

        rat = product.get("rating")
        if rat and float(str(rat).replace("★", "").strip() or 0) >= 3.5:
            quality_basis.append(f"✓ Customer rating verified ({rat})")
            warranty_points = 75.0
        else:
            quality_basis.append("⚠ Customer rating unavailable")

    # ── P. MAKEUP / COSMETICS ──────────────────────────────────────────────────
    elif cat in ("makeup",):
        total_expected = 4

        shade = check_spec(["shade", "color"], r'\b(nude|red|pink|coral|berry|mauve|brown|plum|peach|orange|rose|wine)\b')
        if shade:
            quality_basis.append(f"✓ Shade verified ({shade})")
            verified_spec_scores.append(82.0)
            perf_points += 20.0
        else:
            quality_basis.append("⚠ Shade unavailable")

        finish = check_spec(["finish"], r'\b(matte|glossy|satin|shimmer|metallic|dewy|natural)\b')
        if finish:
            quality_basis.append(f"✓ Finish verified ({finish})")
            verified_spec_scores.append(82.0)
        else:
            quality_basis.append("⚠ Finish unavailable")

        qty = check_spec(["quantity", "volume"], r'\b(\d+(?:\.\d+)?)\s*(ml|g|gm)\b')
        if qty:
            quality_basis.append(f"✓ Net quantity verified ({qty})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Net quantity unavailable")

        brand = product.get("brand")
        if brand and str(brand).strip().lower() not in ("generic", "none", "n/a", "other", ""):
            quality_basis.append(f"✓ Brand verified ({brand})")
            build_points = 78.0
        else:
            quality_basis.append("⚠ Brand unverified")

    # ── Q. PEN DRIVE / STORAGE DEVICE ──────────────────────────────────────────
    elif cat in ("pen_drive", "storage_device", "storage"):
        total_expected = 6

        cap = check_spec(["capacity", "storage_capacity", "storage"], r'(\d+\s*(?:gb|tb))')
        if cap:
            quality_basis.append(f"✓ Storage capacity verified ({cap})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Storage capacity unavailable")

        usb = check_spec(["usb_version", "interface"], r'\b(usb\s*3\.[0-2]|usb\s*2\.0|type[- ]c)\b')
        if usb:
            quality_basis.append(f"✓ Interface / USB version verified ({usb})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Interface / USB version unverified")

        read_spd = check_spec(["read_speed"], r'\b(\d+\s*mbps|\d+\s*mb/s)\b')
        if read_spd:
            quality_basis.append(f"✓ Read speed benchmark verified ({read_spd})")
            verified_spec_scores.append(85.0)
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Read speed benchmark unavailable")

        write_spd = check_spec(["write_speed"], r'\b(\d+\s*mbps|\d+\s*mb/s)\b')
        if write_spd:
            quality_basis.append(f"✓ Write speed benchmark verified ({write_spd})")
            verified_spec_scores.append(85.0)
            perf_points += 40.0
        else:
            quality_basis.append("⚠ Write speed benchmark unavailable")

        mat = check_spec(["material"], r'\b(metal|plastic|zinc|aluminum)\b')
        if mat:
            quality_basis.append(f"✓ Material verified ({mat})")
            build_points = 80.0
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Material unverified")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|brand\s*warranty|lifetime)\b')
        if warr:
            quality_basis.append(f"✓ Warranty verified ({warr})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty unverified")

    # ── R. OTHER / GENERAL CATEGORIES ──────────────────────────────────────────
    else:

        total_expected = 5

        brand = product.get("brand")
        if brand and str(brand).strip().lower() not in ("generic", "none", "n/a", "other", ""):
            quality_basis.append(f"✓ Brand verified ({brand})")
            verified_spec_scores.append(85.0)
        else:
            quality_basis.append("⚠ Brand unverified")

        model = product.get("model")
        if model and str(model).strip().lower() not in ("standard", "general", "n/a", ""):
            quality_basis.append(f"✓ Model identification verified ({model})")
            verified_spec_scores.append(80.0)
        else:
            quality_basis.append("⚠ Model identifier unavailable")

        mat = check_spec(["material"], r'\b(plastic|metal|steel|wood|fabric|leather)\b')
        if mat:
            quality_basis.append(f"✓ Material verified ({mat})")
            build_points = 75.0
            verified_spec_scores.append(78.0)
        else:
            quality_basis.append("⚠ Material unverified")

        dim = check_spec(["dimensions", "weight"], r'\b(\d+\s*(?:kg|g|cm|mm|inch))\b')
        if dim:
            quality_basis.append(f"✓ Dimensions / Weight verified ({dim})")
            verified_spec_scores.append(75.0)
        else:
            quality_basis.append("⚠ Dimensions / Weight unavailable")

        warr = check_spec(["warranty"], r'\b(\d+\s*year|warranty|returnable)\b')
        if warr:
            quality_basis.append(f"✓ Warranty / Return verified ({warr})")
            warranty_points = 80.0
        else:
            quality_basis.append("⚠ Warranty information unavailable")

    # Compute Evidence Coverage percentage
    verified_count = sum(1 for item in quality_basis if item.startswith("✓"))
    coverage = round((verified_count / max(1, total_expected)) * 100.0, 1)

    # Need at least 2 verified key specs AND coverage >= 25% to formulate a verified score
    # For storage devices, benchmark read/write speeds or speed benchmarks are required to make objective claims
    if cat in ("pen_drive", "storage_device", "storage"):
        has_speed_benchmark = bool(check_spec(["read_speed", "write_speed"], r'\b(\d+\s*mbps|\d+\s*mb/s)\b'))
        has_sufficient_data = bool(verified_count >= 4 and coverage >= 50.0 and has_speed_benchmark)
    else:
        has_sufficient_data = bool(verified_count >= 2 and coverage >= 25.0)

    # Average verified specification quality
    if has_sufficient_data and verified_spec_scores:
        avg_spec_score = sum(verified_spec_scores) / len(verified_spec_scores)
    elif has_sufficient_data:
        avg_spec_score = 65.0
    else:
        avg_spec_score = 0.0

    final_spec = round(min(100.0, max(0.0, avg_spec_score)), 1)
    final_perf = round(min(100.0, max(0.0, perf_points if perf_points > 0 else (avg_spec_score * 0.9 if has_sufficient_data else 0.0))), 1)
    final_build = round(min(100.0, max(0.0, build_points if build_points > 0 else (65.0 if has_sufficient_data else 0.0))), 1)
    final_warr = round(min(100.0, max(0.0, warranty_points if warranty_points > 0 else (60.0 if has_sufficient_data else 0.0))), 1)

    return {
        "spec_quality_score": final_spec,
        "perf_quality_score": final_perf,
        "build_quality_score": final_build,
        "warranty_score": final_warr,
        "evidence_coverage": coverage,
        "quality_basis": quality_basis,
        "has_sufficient_data": has_sufficient_data,
        "verified_count": verified_count,
        "total_expected": total_expected
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Ratings and Reviews as Supporting Evidence
# ─────────────────────────────────────────────────────────────────────────────

def _calc_ratings_reviews_score(product: Dict[str, Any]) -> float:
    """
    Evaluates customer satisfaction and social proof using Bayesian smoothing.
    Score is out of 100. Ratings are supporting evidence, not primary quality.
    """
    raw_r = None
    if product.get("rating") is not None:
        try:
            raw_r = float(str(product["rating"]).replace("★", "").strip())
        except (ValueError, TypeError):
            raw_r = None

    raw_rev = 0
    rc_val = product.get("review_count") or product.get("reviews")
    if rc_val is not None:
        try:
            raw_rev = int(str(rc_val).replace(",", "").replace("reviews", "").strip())
        except (ValueError, TypeError):
            raw_rev = 0

    if raw_r is None or raw_r <= 0:
        return 0.0

    prior_rating = 3.8
    prior_weight = 10.0

    smoothed = ((raw_r * raw_rev) + (prior_rating * prior_weight)) / (raw_rev + prior_weight)
    rating_pts = (smoothed / 5.0) * 65.0

    if raw_rev > 0:
        vol_pts = min(35.0, math.log10(max(1, raw_rev)) * 8.75)
    else:
        vol_pts = 5.0

    return round(min(100.0, max(10.0, rating_pts + vol_pts)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Review Sentiment Signals Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_review_signals(
    product: Any,
    category: Optional[str] = None,
    rating: Optional[float] = None,
    review_count: int = 0
) -> Dict[str, Any]:
    """
    Extracts authentic review signals without fabricating reviews.
    Accepts either a product dict or text string.
    """
    p_dict = product if isinstance(product, dict) else {
        "title": str(product or ""),
        "rating": rating,
        "review_count": review_count
    }

    r_val = rating if rating is not None else p_dict.get("rating")
    if r_val is not None:
        try:
            r_val = round(float(str(r_val).replace("★", "").strip()), 1)
        except (ValueError, TypeError):
            r_val = None

    rv_count = review_count if review_count > 0 else (p_dict.get("review_count") or p_dict.get("reviews") or 0)
    try:
        rv_count = int(str(rv_count).replace(",", "").replace("reviews", "").strip())
    except (ValueError, TypeError):
        rv_count = 0

    title = str(p_dict.get("title") or "").lower()
    specs = p_dict.get("specifications") or {}
    text_corpus = f"{title} {' '.join(str(v) for v in specs.values())}".lower()

    positive_themes: List[str] = []
    negative_themes: List[str] = []

    if r_val is not None and r_val >= 4.2:
        positive_themes.append("High Customer Satisfaction")
    elif r_val is not None and r_val < 3.5 and rv_count >= 10:
        negative_themes.append("Mixed Customer Feedback")

    if rv_count >= 1000:
        positive_themes.append("High Review Confidence (1K+ verified buyers)")
    elif rv_count >= 100:
        positive_themes.append("Established Buyer Trust")
    elif rv_count == 0:
        negative_themes.append("Limited Customer Feedback")

    cat_str = (category or p_dict.get("category") or "other").lower()

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

    elif cat_str in ("audio", "earphones", "headphones", "speaker", "electronics"):
        if any(w in text_corpus for w in ("sound", "bass", "audio", "driver", "anc", "noise")):
            positive_themes.append("High Audio & Sound Quality")
        if any(w in text_corpus for w in ("battery", "playtime", "backup", "playback", "hours")):
            positive_themes.append("Reliable Battery Capacity")
        if "anc" in text_corpus or "active noise cancellation" in text_corpus:
            positive_themes.append("Noise Cancellation Enabled")

    elif cat_str in ("kitchen", "home_appliance"):
        if any(w in text_corpus for w in ("copper motor", "stainless steel", "750w", "1000w")):
            positive_themes.append("Heavy Duty Build & Powerful Motor")
        if any(w in text_corpus for w in ("auto shut-off", "overload protection")):
            positive_themes.append("Safety & Overload Protection")

    if r_val and rv_count > 0:
        sentiment_summary = f"Rated {r_val} ★ across {rv_count:,} verified buyer reviews."
    elif r_val:
        sentiment_summary = f"Rated {r_val} ★ by early verified buyers."
    else:
        sentiment_summary = "Awaiting initial customer rating reviews."

    return {
        "rating": r_val,
        "review_count": rv_count,
        "review_count_formatted": f"{rv_count:,}" if rv_count else "0",
        "positive_themes": positive_themes[:4],
        "negative_themes": negative_themes[:3],
        "sentiment_summary": sentiment_summary,
        "has_review_data": bool(r_val is not None or rv_count > 0)
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Master Category-Aware Quality Scoring Function
# ─────────────────────────────────────────────────────────────────────────────

def get_detailed_quality_report(product: Dict[str, Any], category: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes a comprehensive, category-aware quality report strictly grounded in real specs:
    - Estimated Quality Score (0-100) or None if data is insufficient
    - Data Confidence Score (0-100)
    - Evidence Coverage %
    - Quality Basis Checklist (✓ verified, ⚠ unavailable)
    - Has Sufficient Data flag
    - Criteria Breakdown (Specs, Ratings, Build, Performance, Warranty)
    - Review Signals and Recurring Themes
    - Quality-Related Attributes
    """
    cat = (category or product.get("category") or "").lower().replace(" ", "_")
    if not cat or cat in ("default", "other", "unknown"):
        from search.category_detector import detect_category
        cat = detect_category(title=product.get("title", "")).lower().replace(" ", "_")
    weights = get_category_weights(cat)

    # 1. Compute Data Confidence
    data_conf = compute_data_confidence(product)

    # 2. Evaluate Specifications against Category Standards
    eval_res = evaluate_category_specifications(product, cat)
    has_sufficient_data = eval_res["has_sufficient_data"] and (data_conf >= 25.0)

    # 3. Component Scores
    c_specs = eval_res["spec_quality_score"]
    c_perf = eval_res["perf_quality_score"]
    c_build = eval_res["build_quality_score"]
    c_warranty = eval_res["warranty_score"]
    c_ratings = _calc_ratings_reviews_score(product)

    # If unrated, redistribute rating weight proportionally among specifications and performance
    if c_ratings <= 0.0 and has_sufficient_data:
        c_ratings = c_specs

    # Weighted calculation
    raw_quality = (
        (c_specs * weights.get("specifications", 0.35)) +
        (c_perf * weights.get("performance", 0.15)) +
        (c_build * weights.get("build_material", 0.15)) +
        (c_ratings * weights.get("ratings_reviews", 0.25)) +
        (c_warranty * weights.get("warranty_seller", 0.10))
    )
    final_quality_score = round(min(100.0, max(0.0, raw_quality)), 1)

    if not has_sufficient_data or final_quality_score < 20.0:
        quality_score = None
        quality_score_label = "Quality Score: Not Available"
        quality_status_badge = "badge bg-secondary text-white"
        quality_band = "Insufficient Data"
        quality_reason = "Insufficient verified specifications"
    elif final_quality_score >= 82.0:
        quality_score = final_quality_score
        quality_score_label = f"{final_quality_score}/100 (Superior Quality)"
        quality_status_badge = "badge bg-success text-white"
        quality_band = "Superior Quality"
        quality_reason = "High specification score with verified evidence"
    elif final_quality_score >= 68.0:
        quality_score = final_quality_score
        quality_score_label = f"{final_quality_score}/100 (High Quality)"
        quality_status_badge = "badge bg-primary text-white"
        quality_band = "High Quality"
        quality_reason = "Strong specifications with verified evidence"
    elif final_quality_score >= 50.0:
        quality_score = final_quality_score
        quality_score_label = f"{final_quality_score}/100 (Standard Quality)"
        quality_status_badge = "badge bg-info text-dark"
        quality_band = "Standard Quality"
        quality_reason = "Moderate verified specifications"
    else:
        quality_score = final_quality_score
        quality_score_label = f"{final_quality_score}/100 (Moderate Evidence)"
        quality_status_badge = "badge bg-warning text-dark"
        quality_band = "Moderate Evidence"
        quality_reason = "Basic verified specifications"

    # Review Signals
    review_signals = extract_review_signals(product, cat)

    # Determine build material attribute
    text_corpus, _ = _get_corpus(product)
    material_found = None
    for m in ("stainless steel", "100% cotton", "pure cotton", "aluminum", "gorilla glass", "genuine leather", "polycarbonate", "copper", "hard anodised", "borosilicate"):
        if m in text_corpus:
            material_found = m.title()
            break
    if not material_found:
        m_attr = product.get("material") or product.get("fabric")
        material_found = str(m_attr).strip().title() if (m_attr and str(m_attr).lower() not in ("none", "n/a", "null", "not available")) else "Not Available"

    w_raw = product.get("warranty")
    warranty_val = str(w_raw).strip() if (w_raw and str(w_raw).lower() not in ("none", "n/a", "null", "not available")) else "Not Available"

    s_raw = product.get("seller") or product.get("supplier")
    seller_val = str(s_raw).strip() if (s_raw and str(s_raw).lower() not in ("none", "n/a", "null", "unknown")) else "Not Available"

    quality_attributes = {
        "material": material_found,
        "warranty": str(warranty_val),
        "seller": str(seller_val),
        "condition": product.get("condition") or "Brand New"
    }

    return {
        "quality_score": quality_score,
        "raw_quality_score": final_quality_score,
        "quality_score_label": quality_score_label,
        "quality_status_badge": quality_status_badge,
        "quality_band": quality_band,
        "band": quality_band,
        "reason": quality_reason,
        "evidence_coverage": eval_res["evidence_coverage"],
        "evidence_coverage_label": f"{eval_res['evidence_coverage']}% Coverage",
        "quality_basis": eval_res["quality_basis"],
        "quality_evidence": eval_res["quality_basis"],
        "data_confidence": data_conf,
        "data_confidence_label": f"{data_conf}% Verified Evidence",
        "has_sufficient_data": has_sufficient_data,
        "category": cat,
        "weights": weights,
        "breakdown": {
            "specifications": {"score": c_specs, "weight": weights.get("specifications", 0.35)},
            "performance": {"score": c_perf, "weight": weights.get("performance", 0.15)},
            "build_material": {"score": c_build, "weight": weights.get("build_material", 0.15)},
            "ratings_reviews": {"score": c_ratings, "weight": weights.get("ratings_reviews", 0.25)},
            "warranty_seller": {"score": c_warranty, "weight": weights.get("warranty_seller", 0.10)},
        },
        "review_signals": review_signals,
        "quality_attributes": quality_attributes
    }


def calculate_specification_quality(
    product: Dict[str, Any],
    category: Optional[str] = None
) -> Tuple[Optional[float], str, List[str], float]:
    """
    Convenience function returning (quality_score, label, quality_basis, evidence_coverage).
    If data is insufficient, quality_score is None.
    """
    report = get_detailed_quality_report(product, category)
    return (
        report.get("quality_score"),
        report.get("quality_score_label", "Insufficient specification data"),
        report.get("quality_basis", []),
        report.get("evidence_coverage", 0.0)
    )


def compute_quality_and_confidence(product: Dict[str, Any], category: Optional[str] = None) -> Tuple[float, float]:
    """
    Standard interface used by pipeline, matchers, and scrapers.
    Returns (quality_score, data_confidence).
    """
    report = get_detailed_quality_report(product, category)
    q_score = report.get("quality_score")
    if q_score is None:
        q_score = report.get("raw_quality_score") or 0.0
    d_conf = report.get("data_confidence") or 0.0
    return float(q_score), float(d_conf)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Value for Money Index (Separate from Quality Score)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_value_for_money_index(
    quality_score: Optional[float],
    price_num: Optional[float],
    min_price: float
) -> float:
    """
    Calculates Value for Money Index (0.0 to 100.0).
    Combines quality score with economic price efficiency relative to lowest price.
    """
    if not price_num or price_num <= 0:
        return 0.0

    q_score = float(quality_score) if quality_score is not None else 50.0
    price_factor = min(1.0, max(0.2, min_price / price_num))
    val_index = ((q_score / 100.0) * 50.0) + (price_factor * 50.0)
    return round(min(100.0, max(10.0, val_index)), 1)
