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

from search.query_parser import parse_query_entities, extract_specific_product_type, KNOWN_BRANDS, NON_BRAND_TERMS
from search.quantity_normalizer import normalize_quantity_and_pack
from search.category_detector import detect_category, get_category_family

logger = logging.getLogger("smartbuy.search.product_matcher")

ANIMAL_PET_KEYWORDS = frozenset({
    'pig', 'pigs', 'pigerry', 'swine', 'piglet', 'piglets', 'boar', 'sow',
    'fish food', 'fish feed', 'aquarium', 'pellet fish', 'goldfish food', 'royal oscar',
    'dog food', 'puppy food', 'cat food', 'kitten food', 'pet food',
    'bird food', 'bird seed', 'animal feed', 'cattle feed', 'poultry feed',
    'veterinary', 'livestock', 'horse feed', 'aquatic feed', 'turtle food'
})

ESSENTIAL_TYPE_KEYWORDS = {
    'pistachios': ('pistachio', 'pistachios', 'pista', 'pistas'),
    'almonds': ('almond', 'almonds', 'badam'),
    'cashews': ('cashew', 'cashews', 'kaju'),
    'walnuts': ('walnut', 'walnuts', 'akhrot'),
    'raisins': ('raisin', 'raisins', 'kishmish'),
    'dates': ('date', 'dates', 'khajur'),
    'coconut_oil': ('coconut oil', 'nariyal tel', 'coconut'),
    'mustard_oil': ('mustard oil', 'sarson tel'),
    'olive_oil': ('olive oil',),
    'face_wash': ('face wash', 'facewash', 'facial cleanser', 'face cleanser', 'face & beard wash', 'face and beard wash', 'face & body wash', 'beard wash'),
    'soap': ('soap', 'soaps', 'bathing bar'),
    'shampoo': ('shampoo', 'hair wash'),
    'smartwatch': ('smartwatch', 'smart watch', 'watch'),
    'smartphone': ('smartphone', 'smart phone', 'phone', 'mobile'),
    'laptop': ('laptop', 'notebook', 'macbook', 'chromebook'),
    'water_bottle': ('bottle', 'flask', 'sipper', 'thermosteel'),
    'pressure_cooker': ('cooker', 'pressure cooker'),
    'mixer_grinder': ('mixer', 'grinder', 'blender'),
    'electric_kettle': ('kettle',),
    'pen_drive': ('pen drive', 'pendrive', 'flash drive', 'usb drive', 'thumb drive'),
}

# Clear Match Status Constants (Section 2 & 8)
STATUS_EXACT_MATCH = "Exact Match"
STATUS_VARIANT_MATCH = "Same Product – Different Variant"
STATUS_PARTIAL_MATCH = "Partial Match"
STATUS_SIMILAR_PRODUCT = "Similar Product"
STATUS_DIFFERENT_PRODUCT = "Different Product"
STATUS_NOT_COMPARABLE = "Different Product"
STATUS_INSUFFICIENT_DATA = "Insufficient Data"

MATCH_EXACT = "EXACT_MATCH"
MATCH_VARIANT = "VARIANT_MATCH"
MATCH_PARTIAL = "PARTIAL_MATCH"
MATCH_SIMILAR = "SIMILAR_PRODUCT"
MATCH_REJECT_ACCESSORY = "REJECTED"
MATCH_DIFFERENT = "REJECTED"

ACCESSORY_TERMS = {
    'case', 'cases', 'cover', 'covers', 'backcover', 'backcovers', 'back cover', 'back covers',
    'tempered glass', 'screen protector', 'screen protectors', 'screen guard', 'screen guards',
    'lens protector', 'camera lens protector', 'camera lens guard', 'camera glass', 'lens glass',
    'camera protector', 'camera guard', 'camera ring', 'lens film', 'membrane', 'skin', 'skins',
    'mobile skin', 'skin wrap', 'body skin', 'protective film', 'guard', 'guards', 'cable', 'cables',
    'charging cable', 'usb cable', 'type c cable', 'lightning cable', 'strap', 'straps', 'watch strap',
    'watch band', 'band', 'bands', 'pouch', 'pouches', 'mobile pouch', 'sleeve', 'sleeves', 'laptop sleeve',
    'bumper', 'bumpers', 'stand', 'stands', 'mobile stand', 'holder', 'holders', 'mobile holder',
    'mount', 'mounts', 'car mount', 'stylus', 'stylus pen', 'ear tips', 'silicone case', 'flip cover',
    'wallet case', 'bag', 'backpack', 'laptop bag', 'laptop backpack', 'laptop case', 'laptop cover',
    'charger', 'adapter', 'power adapter', 'fast charger', 'power bank', 'cooling pad', 'keyboard cover',
    'keyguard', 'privacy screen', 'dust plug', 'pop socket', 'ring holder', 'dock', 'docking station',
    # Appliance Replacement Parts & Accessories
    'gasket', 'gaskets', 'sealing ring', 'sealing rings', 'safety valve', 'safety valves',
    'weight valve', 'whistle', 'whistles', 'cooker handle', 'cooker handles', 'lid handle',
    'pressure regulator', 'vent weight', 'rubber ring', 'silicone ring', 'rubber gasket',
    'mixer jar', 'mixer jars', 'grinder jar', 'grinder jars', 'chutney jar', 'chutney jars',
    'wet jar', 'dry jar', 'mixer blade', 'grinder blade', 'coupler', 'couplers', 'jar lid',
    'coupler gear', 'jar handle', 'kettle base', 'power base', 'kettle cord', 'heating plate',
    'inlet pipe', 'drain hose', 'pulsator', 'lint filter', 'machine cover', 'washing machine cover',
    'trolley stand', 'anti vibration pad', 'anti vibration pads'
}


def get_match_status_label(raw_status: str) -> str:
    """Normalize internal status codes to standard display strings."""
    s = str(raw_status or "").strip().upper()
    if s in ("EXACT_MATCH", "EXACT MATCH"):
        return STATUS_EXACT_MATCH
    if s in ("VARIANT_MATCH", "VARIANT MATCH", "VARIANT", "SAME_PRODUCT_DIFFERENT_VARIANT", "SAME PRODUCT – DIFFERENT VARIANT", "SAME PRODUCT - DIFFERENT VARIANT"):
        return STATUS_VARIANT_MATCH
    if s in ("PARTIAL_MATCH", "PARTIAL MATCH", "PARTIAL"):
        return STATUS_PARTIAL_MATCH
    if s in ("SIMILAR_PRODUCT", "SIMILAR PRODUCT", "SIMILAR"):
        return STATUS_SIMILAR_PRODUCT
    if s in ("INSUFFICIENT_DATA", "INSUFFICIENT DATA"):
        return STATUS_INSUFFICIENT_DATA
    return STATUS_DIFFERENT_PRODUCT


def is_accessory_conflict(
    canonical_category: str,
    candidate_title: str,
    query_is_accessory: bool = False,
    raw_query: str = ""
) -> bool:
    """
    Detects if candidate is an accessory or replacement part when user did not search for an accessory.
    Examples:
    - Vivo X300 FE mobile vs Vivo X300 FE camera lens protector => True (REJECT)
    - Vivo T4 5G phone vs Vivo T4 phone cover => True (REJECT)
    - HP laptop vs HP laptop bag / charger => True (REJECT)
    - iPhone 15 vs iPhone 15 case / screen protector => True (REJECT)
    - Pressure Cooker vs Pressure Cooker Gasket / Sealing Ring / Safety Valve / Whistle => True (REJECT)
    - Mixer Grinder vs Mixer Jar / Coupler / Blade => True (REJECT)
    - Electric Kettle vs Kettle Base / Cord => True (REJECT)
    - Washing Machine vs Inlet Pipe / Machine Cover => True (REJECT)
    """
    if query_is_accessory:
        return False

    q_text = f"{canonical_category} {raw_query}".lower()
    # If the user specifically queried for an accessory or replacement part, do not reject
    user_wanted_accessory = any(
        re.search(r'\b' + re.escape(acc) + r'\b', q_text)
        for acc in (
            'case', 'cover', 'protector', 'guard', 'charger', 'adapter', 'cable', 'bag',
            'backpack', 'sleeve', 'strap', 'holder', 'stand', 'skin', 'gasket', 'sealing ring',
            'whistle', 'safety valve', 'jar', 'blade', 'coupler', 'pipe', 'hose'
        )
    )
    if user_wanted_accessory:
        return False

    t_low = candidate_title.lower()
    c_cat = str(canonical_category or "").lower()

    # 1. Phone / Smartphone / Mobile target
    is_phone_target = c_cat in ('phone', 'smartphone', 'smartphones', 'mobile', 'mobiles', 'cellphone') or any(
        w in q_text for w in ('phone', 'mobile', 'smartphone', 'galaxy', 'iphone', 'redmi', 'realme', 'vivo', 'oppo', 'oneplus', 'iqoo', 'pixel')
    )
    if is_phone_target:
        phone_acc_patterns = [
            r'\b(lens|camera\s*lens)\s*(?:protector|guard|glass|film|ring)\b',
            r'\bcamera\s*(?:glass|guard|protector|ring)\b',
            r'\b(?:tempered\s*glass|screen\s*protector|screen\s*guard|edge\s*to\s*edge|privacy\s*glass)\b',
            r'\b(?:back\s*cover|back\s*case|phone\s*case|phone\s*cover|flip\s*cover|wallet\s*case|silicone\s*cover|tpu\s*case)\b',
            r'\b(?:mobile\s*skin|skin\s*wrap|body\s*skin|protective\s*film)\b',
            r'\b(?:charger|adapter|charging\s*cable|power\s*adapter|fast\s*charger|data\s*cable|type\s*c\s*cable)\b',
            r'\b(?:mobile\s*holder|mobile\s*stand|car\s*mount|ring\s*holder|pop\s*socket)\b',
            r'\b(?:mobile\s*pouch|holster)\b',
            r'\b(?:stylus|stylus\s*pen)\b',
        ]
        for pat in phone_acc_patterns:
            if re.search(pat, t_low):
                return True

        for acc in ('case', 'cases', 'cover', 'covers', 'guard', 'pouch', 'bumper', 'skin', 'skins'):
            if acc in ('cover', 'covers') and any(h in t_low for h in ('pillow', 'cushion', 'sofa', 'bed', 'book')):
                continue
            if re.search(r'\b' + re.escape(acc) + r'\b', t_low):
                return True

    # 2. Laptop target
    is_laptop_target = c_cat in ('laptop', 'laptops', 'notebook', 'computer') or any(
        w in q_text for w in ('laptop', 'notebook', 'macbook', 'thinkpad', 'vivobook', 'ideapad', 'pavilion')
    )
    if is_laptop_target:
        laptop_acc_patterns = [
            r'\b(?:laptop\s*bag|laptop\s*backpack|backpack|backpacks|trolley|duffel)\b',
            r'\b(?:laptop\s*sleeve|sleeve\s*case|laptop\s*case|laptop\s*cover|sleeve|pouch)\b',
            r'\b(?:laptop\s*skin|keyboard\s*cover|keyboard\s*protector|keyguard)\b',
            r'\b(?:laptop\s*charger|laptop\s*adapter|power\s*adapter|power\s*cable|charging\s*cable)\b',
            r'\b(?:cooling\s*pad|laptop\s*stand|laptop\s*table|laptop\s*holder)\b',
            r'\b(?:screen\s*protector|screen\s*guard|privacy\s*filter)\b',
        ]
        for pat in laptop_acc_patterns:
            if re.search(pat, t_low):
                return True

    # 3. Audio / Earphones / Headphones target
    is_audio_target = c_cat in ('earphones', 'headphones', 'audio', 'earbuds', 'headset')
    if is_audio_target:
        audio_acc_patterns = [
            r'\b(?:silicone\s*case|protective\s*case|earphone\s*case|earbuds\s*case|charging\s*case\s*cover)\b',
            r'\b(?:ear\s*tips|foam\s*tips|replacement\s*cushions|ear\s*pads)\b',
            r'\b(?:headphone\s*stand|headphone\s*holder|headphone\s*cable)\b',
        ]
        for pat in audio_acc_patterns:
            if re.search(pat, t_low):
                return True

    # 4. Charger target (reject phones or cases)
    if c_cat == 'charger':
        if any(acc in t_low for acc in ('case', 'cover', 'tempered glass', 'screen guard', 'skin', 'pouch')):
            return True
        if not any(k in t_low for k in ('charger', 'adapter', 'charging', 'power bank', 'cable', 'watt', 'w ')):
            return True

    # 5. Pressure Cooker target (Pressure Cooker != Pressure Cooker Gasket / Sealing Ring / Whistle / Valve)
    is_cooker_target = (
        c_cat in ('pressure_cooker', 'cooker') or
        'cooker' in q_text or
        ('kitchen' in c_cat and 'cooker' in q_text)
    )
    if is_cooker_target:
        cooker_part_patterns = [
            r'\b(?:gasket|gaskets|rubber\s*gasket|silicone\s*gasket)\b',
            r'\b(?:sealing\s*ring|sealing\s*rings|rubber\s*ring|silicone\s*ring)\b',
            r'\b(?:safety\s*valve|safety\s*valves|weight\s*valve|whistle|whistles|vent\s*weight)\b',
            r'\b(?:pressure\s*regulator|cooker\s*handle|cooker\s*handles|lid\s*handle|body\s*handle)\b',
            r'\b(?:separator\s*set|cooker\s*separator|steamer\s*basket)\b',
        ]
        for pat in cooker_part_patterns:
            if re.search(pat, t_low):
                return True

    # 6. Mixer Grinder target (Mixer Grinder != Mixer Jar / Coupler / Blade)
    is_mixer_target = (
        c_cat in ('mixer_grinder', 'mixer') or
        'mixer' in q_text or
        'grinder' in q_text
    )
    if is_mixer_target:
        mixer_part_patterns = [
            r'\b(?:mixer\s*jar|grinder\s*jar|chutney\s*jar|wet\s*jar|dry\s*jar|juicer\s*jar|grinding\s*jar|steel\s*jar)\b',
            r'\b(?:mixer\s*blade|grinder\s*blade|chutney\s*blade)\b',
            r'\b(?:coupler|couplers|coupler\s*gear|mixer\s*coupler|motor\s*coupler)\b',
            r'\b(?:jar\s*lid|dome\s*lid|jar\s*handle)\b',
            r'\b(?:jar|jars)\s+(?:with\s+lid\s+)?(?:for|compatible\s+with)\b',
        ]
        for pat in mixer_part_patterns:
            if re.search(pat, t_low):
                return True
        if re.search(r'\b(?:jar|jars)\b', t_low) and not any(w in t_low for w in ('watt', 'watts', '750w', '500w', '1000w', 'motor', 'mixer grinder')):
            return True

    # 7. Electric Kettle target (Electric Kettle != Kettle Base / Cord)
    is_kettle_target = (
        c_cat in ('electric_kettle', 'kettle') or
        'kettle' in q_text
    )
    if is_kettle_target:
        kettle_part_patterns = [
            r'\b(?:kettle\s*base|power\s*base|swivel\s*base|360\s*base|kettle\s*cord|heating\s*plate)\b',
            r'\b(?:replacement\s+)?(?:360\s*(?:degree\s*)?)?(?:swivel\s*)?base\s+(?:for|compatible\s+with)\b',
            r'\b(?:kettle\s*lid|replacement\s*lid)\b',
        ]
        for pat in kettle_part_patterns:
            if re.search(pat, t_low):
                return True
        if re.search(r'\b(?:base|swivel\s*base)\b', t_low) and any(w in t_low for w in ('kettle', 'electric kettle')) and not any(w in t_low for w in ('1.5l', '1.8l', '1.2l', 'litre', 'litres', 'liters', 'liter')):
            return True

    # 8. Washing Machine target (Washing Machine != Inlet Pipe / Machine Cover)
    is_washer_target = (
        c_cat in ('washing_machine', 'washer') or
        'washing machine' in q_text
    )
    if is_washer_target:
        washer_part_patterns = [
            r'\b(?:inlet\s*pipe|water\s*inlet\s*pipe|inlet\s*hose|drain\s*hose|drain\s*pipe)\b',
            r'\b(?:pulsator|lint\s*filter|washing\s*machine\s*cover|machine\s*cover)\b',
            r'\b(?:cover|covers)\s+(?:for|compatible\s+with)\s+(?:[a-z0-9\s-]+\s+)?washing\s*machine\b',
            r'\b(?:trolley\s*stand|machine\s*stand|anti\s*vibration\s*pads?)\b',
        ]
        for pat in washer_part_patterns:
            if re.search(pat, t_low):
                return True
        if re.search(r'\b(?:cover|covers)\b', t_low) and 'washing machine' in t_low and not any(k in t_low for k in ('inverter', 'motor', 'rpm', 'fully automatic', 'semi automatic')):
            return True

    # 9. Smartwatch target (Smartwatch != Replacement Strap / Band / Screen Protector)
    is_watch_target = (
        c_cat in ('watch', 'smartwatch') or
        'smartwatch' in q_text or
        ('watch' in q_text and not any(w in q_text for w in ('face wash', 'body wash', 'washing machine')))
    )
    if is_watch_target and not any(w in q_text for w in ('strap', 'band')):
        watch_acc_patterns = [
            r'\b(?:watch\s*strap|replacement\s*strap|silicone\s*strap|leather\s*strap|magnetic\s*strap|milanese\s*loop)\b',
            r'\b(?:watch\s*band|replacement\s*band|silicone\s*band|wrist\s*band)\b',
            r'\b(?:strap|band)\s+(?:for|compatible\s+with)\b',
            r'\b(?:screen\s*protector|tempered\s*glass|dial\s*protector|watch\s*case|bumper\s*case)\b',
        ]
        for pat in watch_acc_patterns:
            if re.search(pat, t_low):
                return True
        if re.search(r'\b(?:strap|straps)\b', t_low) and not any(w in t_low for w in ('display', 'amoled', 'calling', 'bluetooth calling', 'battery', 'mah')):
            return True

    # 10. Water Bottle target (Water Bottle != Cleaning Brush / Cover / Pouch)
    is_bottle_target = (
        c_cat in ('water_bottle', 'bottle', 'flask') or
        'bottle' in q_text or
        'flask' in q_text
    )
    if is_bottle_target and not any(w in q_text for w in ('brush', 'cleaner', 'pouch', 'cover')):
        bottle_acc_patterns = [
            r'\b(?:cleaning\s*brush|bottle\s*brush|cleaning\s*kit|cleaner)\b',
            r'\b(?:bottle\s*cover|bottle\s*pouch|bottle\s*sleeve|bottle\s*holder|bottle\s*bag|bottle\s*carrier)\b',
        ]
        for pat in bottle_acc_patterns:
            if re.search(pat, t_low):
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

    raw_q = str(target_info.get("raw_query") or target_info.get("title") or "").lower()
    target_cat = str(target_info.get("category") or target_info.get("product_type") or "other").lower()

    # ── 1. Animal / Pet Product vs Human Product Gate ─────────────────────────
    target_family = get_category_family(target_cat)
    cand_cat = str(candidate.get("category") or detect_category(title=t_title)).lower()
    cand_family = get_category_family(cand_cat)

    is_target_pet = (target_family == "pet" or target_cat == "pet_supplies" or any(w in raw_q for w in ('dog', 'cat', 'pet', 'fish food', 'aquarium', 'pig', 'pigerry')))
    has_cand_animal = bool(re.search(r'\b(pigs?|pigerry|swine|piglets?|boar|sow|fish\s*food|fish\s*feed|aquarium|pellet\s*fish|goldfish|royal\s*oscar|dog\s*food|cat\s*food|puppy|kitten|bird\s*food|animal\s*feed|cattle\s*feed|poultry\s*feed|veterinary|livestock|aquatic\s*feed)\b', t_low))

    if not is_target_pet and has_cand_animal:
        return True, f"Incompatible domain: candidate is pet/animal feed or health product while search is human '{target_cat}'"
    if is_target_pet and not has_cand_animal and cand_family in ('grocery', 'electronics', 'beauty', 'fashion'):
        return True, f"Incompatible domain: candidate is human product while search is pet/animal '{target_cat}'"

    # ── 2. Category Family Gate ───────────────────────────────────────────────
    if target_family != "other" and cand_family != "other" and target_family != cand_family:
        return True, f"Category family conflict: candidate is '{cand_family}' ({cand_cat}) while search expected '{target_family}' ({target_cat})"

    # ── 3. Specific Product Type Gate ─────────────────────────────────────────
    target_type = target_info.get("product_type") or extract_specific_product_type(raw_q, target_cat)
    cand_type = candidate.get("product_type") or extract_specific_product_type(t_title, cand_cat)

    if target_type and target_type != "other":
        # Tailored specific messages for existing test suites
        if target_type == 'face_wash' and (cand_type == 'serum' or 'serum' in t_low):
            return True, "Product type conflict: face serum instead of face wash"
        if target_type == 'face_wash' and (cand_type == 'soap' or 'soap' in t_low):
            return True, "Product type conflict: soap instead of face wash"
        if target_type == 'slippers' and (cand_type == 'shoes' or any(w in t_low for w in ('shoe', 'shoes', 'sneakers', 'running shoes'))):
            return True, "Product type conflict: shoes/sneakers instead of slippers"

        # 3a. Disallow mismatched specific product types
        if cand_type and cand_type != "other" and cand_type != target_type:
            return True, f"Product type mismatch: candidate is '{cand_type}' while search expected '{target_type}'"

        # 3b. Mandatory type keyword check
        if target_type in ESSENTIAL_TYPE_KEYWORDS:
            req_kws = ESSENTIAL_TYPE_KEYWORDS[target_type]
            if not any(kw in t_low for kw in req_kws):
                return True, f"Missing required product type keyword for '{target_type}': none of {req_kws} found in candidate"

    # ── 4. Category / Accessory Conflict ──────────────────────────────────────
    if is_accessory_conflict(target_cat, t_title, query_is_accessory=target_info.get("is_accessory", False), raw_query=raw_q):
        return True, f"Accessory conflict: candidate is an accessory for '{target_cat}'"

    # ── 5. Strict Brand Conflict Gate ─────────────────────────────────────────
    target_brand = (target_info.get("brand") or "").strip().lower()
    cand_brand = (candidate.get("brand") or "").strip().lower()

    if target_brand and target_brand not in ('generic', 'none', 'unknown', '', 'n/a') and target_brand not in NON_BRAND_TERMS:
        # 5a. Explicit candidate brand conflict
        if cand_brand and cand_brand not in ('generic', 'none', 'unknown', '', 'n/a') and cand_brand not in NON_BRAND_TERMS:
            if target_brand != cand_brand and target_brand not in cand_brand and cand_brand not in target_brand:
                return True, f"Brand conflict: expected '{target_brand.title()}', found '{cand_brand.title()}'"

        # 5b. Conflicting known brand mentioned in candidate title
        cand_known_brands = [b.lower() for b in KNOWN_BRANDS if re.search(r'\b' + re.escape(b.lower()) + r'\b', t_low)]
        if cand_known_brands and target_brand not in cand_known_brands:
            # Check if this is a known brand conflict
            other_brands = [b for b in cand_known_brands if b != target_brand and b not in target_brand and target_brand not in b]
            if other_brands and not re.search(r'\b' + re.escape(target_brand) + r'\b', t_low):
                return True, f"Brand conflict: candidate contains brand '{other_brands[0].title()}' instead of target brand '{target_brand.title()}'"

        # 5c. Target brand presence in candidate title
        if not re.search(r'\b' + re.escape(target_brand) + r'\b', t_low):
            is_unbranded_fashion = (
                target_cat in ('clothing', 'fashion', 'shoes', 'footwear')
                and not cand_known_brands
                and (not cand_brand or cand_brand in ('generic', 'none', 'unknown', '', 'n/a'))
            )
            if not is_unbranded_fashion:
                target_model = (target_info.get("model") or "").strip().lower()
                has_exact_model = bool(target_model and target_model not in ('standard', 'general', 'none', 'n/a', '') and (target_model in t_low or candidate.get("model") == target_model))
                if not has_exact_model:
                    return True, f"Brand mismatch: target brand '{target_brand.title()}' missing from candidate title"

    # ── 6. Beauty & Skincare cross-category rejections ────────────────────────
    is_facewash_target = ('face wash' in raw_q or 'facewash' in raw_q or target_cat in ('face_wash', 'facewash') or target_type == 'face_wash')
    if is_facewash_target:
        if 'soap' in t_low and not any(w in t_low for w in ('face wash', 'facewash', 'facial cleanser')):
            return True, "Product type conflict: soap instead of face wash"
        if any(w in t_low for w in ('cream', 'moisturizer', 'moisturiser', 'lotion', 'body butter')) and not any(w in t_low for w in ('face wash', 'facewash', 'cleanser')):
            return True, "Product type conflict: face cream/moisturizer instead of face wash"
        if any(w in t_low for w in ('sunscreen', 'sun screen', 'sunblock', 'spf 50', 'spf 30')) and not any(w in t_low for w in ('face wash', 'facewash', 'cleanser')):
            return True, "Product type conflict: sunscreen instead of face wash"
        if 'serum' in t_low and not any(w in t_low for w in ('face wash', 'facewash', 'cleanser', 'wash')):
            return True, "Product type conflict: face serum instead of face wash"
        if any(w in t_low for w in ('foundation', 'compact', 'concealer', 'blush')):
            return True, "Product type conflict: makeup/foundation instead of face wash"
        if any(w in t_low for w in ('lipstick', 'lip stick', 'lip gloss', 'lip balm')):
            return True, "Product type conflict: lipstick instead of face wash"

    if ('soap' in raw_q or target_cat in ('soap',)) and ('face wash' in t_low or 'facewash' in t_low) and 'soap' not in t_low:
        return True, "Product type conflict: face wash instead of soap"
    if ('serum' in raw_q) and ('face wash' in t_low or 'facewash' in t_low) and 'serum' not in t_low:
        return True, "Product type conflict: face wash instead of face serum"

    is_moisturizer_target = ('moisturizer' in raw_q or 'moisturiser' in raw_q or 'face cream' in raw_q or 'day cream' in raw_q or 'night cream' in raw_q)
    if is_moisturizer_target:
        if any(w in t_low for w in ('face wash', 'facewash', 'facial cleanser')) and not any(w in t_low for w in ('cream', 'moisturizer', 'moisturiser')):
            return True, "Product type conflict: face wash instead of moisturizer/cream"
        if any(w in t_low for w in ('lipstick', 'lip stick', 'foundation', 'compact', 'shampoo')):
            return True, "Product type conflict: incompatible cosmetics instead of moisturizer"

    if ('sunscreen' in raw_q or 'sun screen' in raw_q or 'sunblock' in raw_q):
        if any(w in t_low for w in ('face wash', 'facewash', 'lipstick', 'foundation', 'shampoo')) and not any(w in t_low for w in ('sunscreen', 'sun screen', 'sunblock', 'spf')):
            return True, "Product type conflict: candidate is not sunscreen"

    if ('foundation' in raw_q):
        if any(w in t_low for w in ('face wash', 'lipstick', 'lip gloss', 'shampoo', 'soap')):
            return True, "Product type conflict: candidate is not foundation"

    if ('lipstick' in raw_q or 'lip stick' in raw_q):
        if any(w in t_low for w in ('face wash', 'foundation', 'shampoo', 'soap', 'nail polish')):
            return True, "Product type conflict: candidate is not lipstick"

    # ── 7. Appliance Complete vs Replacement Part hard rejections ─────────────
    is_cooker_q = bool(re.search(r'\b(pressure\s*cooker|cooker)\b', raw_q)) or target_cat in ('cooker', 'pressure_cooker')
    if is_cooker_q:
        if re.search(r'\b(gasket|sealing\s*ring|safety\s*valve|weight\s*valve|whistle|cooker\s*handle|lid\s*handle|body\s*handle|separator\s*set)\b', t_low):
            return True, "Accessory / Replacement part conflict: cooker replacement part instead of pressure cooker"

    is_mixer_q = bool(re.search(r'\b(mixer\s*grinder|mixer|grinder)\b', raw_q)) or target_cat in ('mixer_grinder', 'mixer')
    if is_mixer_q:
        if re.search(r'\b(mixer\s*jar|grinder\s*jar|chutney\s*jar|mixer\s*blade|grinder\s*blade|coupler|jar\s*lid|jar\s*handle)\b', t_low):
            return True, "Accessory / Replacement part conflict: mixer jar/part instead of mixer grinder"

    is_kettle_q = bool(re.search(r'\b(electric\s*kettle|kettle)\b', raw_q)) or target_cat in ('electric_kettle', 'kettle')
    if is_kettle_q:
        if re.search(r'\b(kettle\s*base|power\s*base|kettle\s*cord|heating\s*plate)\b', t_low):
            return True, "Accessory / Replacement part conflict: kettle part instead of electric kettle"

    is_washer_q = bool(re.search(r'\b(washing\s*machine|washer)\b', raw_q)) or target_cat in ('washing_machine', 'washer')
    if is_washer_q:
        if re.search(r'\b(inlet\s*pipe|drain\s*hose|pulsator|lint\s*filter|machine\s*cover|washing\s*machine\s*cover)\b', t_low):
            return True, "Accessory / Replacement part conflict: washing machine accessory instead of washing machine"

    # ── 8. Slippers vs Shoes Conflict ─────────────────────────────────────────
    is_slipper_q = bool(re.search(r'\b(slipper|slippers|flip\s*flop|flip\s*flops|chappal|chappals|slides?)\b', raw_q))
    is_shoe_q = bool(re.search(r'\b(shoe|shoes|sneaker|sneakers|boots?|loafers?|running\s*shoes)\b', raw_q))
    if is_slipper_q and not is_shoe_q:
        if re.search(r'\b(shoe|shoes|sneaker|sneakers|boots?|loafers?)\b', t_low) and not re.search(r'\b(slipper|slippers|flip\s*flop|chappal|slides?)\b', t_low):
            return True, "Product type conflict: shoes/sneakers instead of slippers"
    if is_shoe_q and not is_slipper_q:
        if re.search(r'\b(slipper|slippers|flip\s*flop|chappal|slides?)\b', t_low) and not re.search(r'\b(shoe|shoes|sneaker|sneakers|boots?|loafers?)\b', t_low):
            return True, "Product type conflict: slippers instead of shoes"

    # ── 9. Storage Device / Pen Drive Target ──────────────────────────────────
    is_pendrive_target = (
        target_cat in ('pen_drive', 'storage_device') or
        bool(re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive|thumb\s*drive|memory\s*card)\b', raw_q))
    )
    if is_pendrive_target:
        if re.search(r'\b(printer|printers|all-in-one|inkjet|laserjet|pixma|ecotank|hdmi|vga\s*cable|aux\s*cable|displayport|laptop|desktop|monitor|camera|projector)\b', t_low) and not re.search(r'\b(pen\s*drive|pendrive|usb\s*flash\s*drive|flash\s*drive|thumb\s*drive)\b', t_low):
            return True, "Product type conflict: candidate is a printer, cable or PC instead of a storage device"
        if re.search(r'\b(bag|backpack|sleeve|laptop\s*bag|carrying\s*case|cover)\b', t_low) and not re.search(r'\b(pen\s*drive|pendrive|flash\s*drive)\b', t_low):
            return True, "Accessory conflict: candidate is a bag/case instead of a storage device"

    if ('laptop' in raw_q or target_cat == 'laptop') and any(b in t_low for b in ('bag', 'backpack', 'sleeve', 'case', 'cover')) and not target_info.get("is_accessory", False):
        return True, "Accessory conflict: candidate is a bag/case for laptop"
    if target_cat in ('phone', 'smartphone') and cand_cat in ('bags', 'charger'):
        return True, "Category conflict: accessory instead of smartphone"

    # ── 10. Model Conflict (e.g. Vivo T4 5G vs Vivo T5e, or iPhone 15 vs iPhone 14) ──
    target_model = (target_info.get("model") or "").strip().lower()
    if target_model and target_model not in ('standard', 'general', 'none', 'n/a', ''):
        cand_model = (candidate.get("model") or "").strip().lower()
        
        model_conflicts = [
            (r'\bt4\s*5g\b', [r'\bt5e\b', r'\bt5\b', r'\bt3\b', r'\bt2\b', r'\bt1\b']),
            (r'\bt4\s*pro\b', [r'\bt4\s*lite\b', r'\bt5\b', r'\bt3\b', r'\bt2\b']),
            (r'\bt4\b', [r'\bt5e\b', r'\bt5\b', r'\bt3\b', r'\bt2\b', r'\bt1\b']),
            (r'\biphone\s*15\b', [r'\biphone\s*16\b', r'\biphone\s*14\b', r'\biphone\s*13\b', r'\biphone\s*12\b', r'\biphone\s*11\b']),
            (r'\biphone\s*14\b', [r'\biphone\s*15\b', r'\biphone\s*13\b', r'\biphone\s*12\b']),
            (r'\bs24\b', [r'\bs23\b', r'\bs22\b', r'\bs21\b', r'\bs20\b']),
            (r'\bx300\s*fe\b', [r'\bx200\b', r'\bx100\b', r'\bx90\b']),
        ]
        for t_pat, conf_pats in model_conflicts:
            if re.search(t_pat, target_model) or re.search(t_pat, raw_q):
                for cp in conf_pats:
                    if re.search(cp, t_low) and not re.search(t_pat, t_low):
                        return True, f"Conflicting model generation: candidate contains '{cp}' instead of '{target_model}'"

        if cand_model and cand_model not in ('standard', 'general', 'none', 'n/a', ''):
            if target_model != cand_model and target_model not in cand_model and cand_model not in target_model:
                return True, f"Model conflict: target '{target_model}', candidate '{cand_model}'"

    # ── 11. Generic Title Rejection (e.g. Amazon search card that only says "vivo") ──
    cleaned_tokens = [w for w in re.findall(r'[a-zA-Z0-9]+', t_title) if len(w) > 1]
    if len(cleaned_tokens) <= 1:
        if target_model or target_info.get("ram") or target_info.get("storage") or target_info.get("network") or target_info.get("model"):
            return True, f"Generic brand name rejected: candidate title '{t_title}' lacks model/variant evidence"

    # ── 12. Jeans / Pants vs Belts & Accessories ─────────────────────────────
    is_jeans_target = 'jeans' in raw_q or target_type == 'jeans'
    if is_jeans_target:
        if re.search(r'\b(belt|belts|buckle|wallet|wallets|socks|shoes|sneakers|watch|perfume)\b', t_low):
            return True, "Product type conflict: belt/accessory instead of jeans"
        if not re.search(r'\b(jeans|denim|trousers|pants|pant)\b', t_low):
            return True, "Product type conflict: candidate is not jeans/denim"

    return False, ""


def evaluate_product_match(
    target_info: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[str, float, Dict[str, float], List[str]]:
    """
    Evaluates candidate against target query or canonical product.
    Returns: (match_status, match_score, breakdown, reasons)
    Match statuses:
    - EXACT_MATCH ("Exact Match")
    - VARIANT_MATCH / PARTIAL_MATCH ("Partial Match")
    - SIMILAR_PRODUCT ("Similar Product")
    - REJECTED ("Different Product – Not Comparable")
    - INSUFFICIENT_DATA ("Insufficient Data")
    """
    # ── 1. Hard Rejection Checks ──────────────────────────────────────────────
    is_rejected, reject_reason = check_hard_rejections(target_info, candidate)
    if is_rejected:
        return "REJECTED", 0.0, {"rejection": 0.0}, [reject_reason]

    breakdown: Dict[str, float] = {}
    reasons: List[str] = []

    t_title = str(candidate.get("title") or "").strip()
    t_low = t_title.lower()
    raw_q = str(target_info.get("raw_query") or target_info.get("title") or "").lower()
    target_cat = str(target_info.get("category") or target_info.get("product_type") or "other").lower()

    # ── 2. Brand Scoring (20 pts) ─────────────────────────────────────────────
    target_brand = (target_info.get("brand") or "").strip().lower()
    cand_brand = (candidate.get("brand") or "").strip().lower()

    if target_brand and target_brand not in NON_BRAND_TERMS:
        if target_brand == cand_brand or re.search(r'\b' + re.escape(target_brand) + r'\b', t_low):
            brand_pts = 20.0
            reasons.append(f"Brand verified: {target_brand.title()}")
        else:
            brand_pts = 5.0
    else:
        brand_pts = 20.0  # neutral - no specific brand queried
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
            model_pts = 0.0
    else:
        model_pts = 20.0
        has_model_match = True
    breakdown["model"] = model_pts

    # ── 4. Variant Attributes Scoring (RAM / Storage / Wattage / Size) (20 pts) ──────
    variant_pts = 20.0
    is_variant_diff = False

    # Check RAM (e.g. 4GB vs 8GB, 8GB vs 16GB)
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
        norm_t_ram = str(tgt_ram).upper().replace(" ", "")
        norm_c_ram = str(cand_ram).upper().replace(" ", "")
        if norm_t_ram == norm_c_ram:
            reasons.append(f"RAM verified: {tgt_ram}")
        else:
            variant_pts -= 10.0
            is_variant_diff = True
            reasons.append(f"RAM variant difference ({cand_ram} vs {tgt_ram})")

    # Check Storage (e.g. 128GB vs 256GB)
    tgt_storage = target_info.get("storage")
    cand_storage = candidate.get("storage")
    if not cand_storage:
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
        norm_t_st = str(tgt_storage).upper().replace(" ", "")
        norm_c_st = str(cand_storage).upper().replace(" ", "")
        if norm_t_st == norm_c_st:
            reasons.append(f"Storage verified: {tgt_storage}")
        else:
            variant_pts -= 10.0
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

    # Check Wattage
    tgt_w = target_info.get("wattage") or (target_info.get("specs") or {}).get("wattage")
    if not tgt_w:
        m_tw = re.search(r'\b(\d{3,4})\s*(?:w|watt)\b', str(target_info.get("title") or "").lower())
        if m_tw:
            tgt_w = f"{m_tw.group(1)}W"
    if tgt_w:
        cand_w = candidate.get("wattage") or (candidate.get("specs") or {}).get("wattage")
        if not cand_w:
            m_w = re.search(r'\b(\d{3,4})\s*(?:w|watt)\b', t_low)
            if m_w:
                cand_w = f"{m_w.group(1)}W"
        if cand_w and str(cand_w).lower().replace(" ", "") != str(tgt_w).lower().replace(" ", ""):
            variant_pts -= 15.0
            is_variant_diff = True
            reasons.append(f"Wattage variant difference ({cand_w} vs {tgt_w})")

    # Check Capacity / Size (e.g. 3L vs 5L, 55cm vs 65cm, 20L vs 30L)
    tgt_cap = target_info.get("capacity") or (target_info.get("specs") or {}).get("capacity")
    if not tgt_cap:
        m_tc = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:l|litres?|liter|liters?|ltr)\b', str(target_info.get("title") or "").lower())
        if not m_tc:
            m_tc = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:l|litres?|liter|liters?|ltr)\b', raw_q)
        if m_tc:
            tgt_cap = f"{m_tc.group(1)}L"
    if tgt_cap:
        cand_cap = candidate.get("capacity") or (candidate.get("specs") or {}).get("capacity")
        if not cand_cap:
            m_cap = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:l|litres?|liter|liters?|ltr)\b', t_low)
            if m_cap:
                cand_cap = f"{m_cap.group(1)}L"
        if cand_cap and str(cand_cap).lower().replace(" ", "").replace("litres", "l").replace("litre", "l") != str(tgt_cap).lower().replace(" ", "").replace("litres", "l").replace("litre", "l"):
            variant_pts -= 15.0
            is_variant_diff = True
            reasons.append(f"Capacity variant difference ({cand_cap} vs {tgt_cap})")

    # Check Clothing Size (S, M, L, XL, etc.)
    tgt_size = target_info.get("size")
    cand_size = candidate.get("size")
    if not cand_size:
        m_sz = re.search(r'\b(size\s*[:\s-]*([smlx0-9]+)|(small|medium|large|extra\s*large))\b', t_low)
        if m_sz:
            cand_size = m_sz.group(0)
    if tgt_size and cand_size and str(tgt_size).lower() != str(cand_size).lower():
        is_variant_diff = True
        reasons.append(f"Size difference ({cand_size} vs {tgt_size})")

    # Check Volume / Net Quantity (e.g. 15 ml vs 50 ml vs 100 ml)
    tgt_vol = target_info.get("volume")
    if not tgt_vol:
        m_tv = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:ml|l)\b', raw_q)
        if m_tv:
            tgt_vol = f"{m_tv.group(1)}ml"
    cand_vol = candidate.get("volume")
    if not cand_vol:
        m_cv = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:ml|l)\b', t_low)
        if m_cv:
            cand_vol = f"{m_cv.group(1)}ml"
    if tgt_vol and cand_vol and str(tgt_vol).lower().replace(" ", "") != str(cand_vol).lower().replace(" ", ""):
        variant_pts -= 15.0
        is_variant_diff = True
        reasons.append(f"Volume variant difference ({cand_vol} vs {tgt_vol})")

    # Check Formulation / Active Ingredient (e.g. Vitamin C vs Tea Tree vs Volcanic Lava Ash)
    formulations = [
        'vitamin c', 'salicylic acid', 'tea tree', 'neem', 'aloe vera',
        'charcoal', 'hyaluronic', 'papaya', 'coffee', 'ubtan', 'glycolic',
        'volcanic', 'squalan', 'retinol', 'niacinamide', 'sandalwood'
    ]
    tgt_form = next((f for f in formulations if f in raw_q), None)
    cand_form = next((f for f in formulations if f in t_low), None)
    if tgt_form and cand_form and tgt_form != cand_form:
        variant_pts -= 15.0
        is_variant_diff = True
        reasons.append(f"Different formulation variant ({cand_form.title()} vs {tgt_form.title()})")

    variant_pts = max(0.0, variant_pts)
    breakdown["variant"] = variant_pts

    # ── 5. Quantity & Pack Count Scoring (15 pts) ─────────────────────────────
    qty_pts = 15.0
    tgt_pack_raw = target_info.get("pack_count") or target_info.get("pack_quantity")
    tgt_pack = 1
    if tgt_pack_raw is not None:
        try:
            m = re.search(r'\d+', str(tgt_pack_raw))
            if m:
                tgt_pack = int(m.group(0))
        except (ValueError, TypeError):
            tgt_pack = 1

    cand_pack_raw = candidate.get("pack_quantity")
    cand_pack = 1
    if cand_pack_raw is not None:
        try:
            m_c = re.search(r'\d+', str(cand_pack_raw))
            if m_c:
                cand_pack = int(m_c.group(0))
        except (ValueError, TypeError):
            cand_pack = 1
    else:
        m_cp = re.search(r'\b(?:pack\s*of\s*|pack-)(\d+)\b', t_low)
        if m_cp:
            cand_pack = int(m_cp.group(1))

    # Detect combo vs single unit
    is_combo_in_cand = any(w in t_low for w in ('combo', 'pack of 2', 'pack of 3', 'pack of 4', 'pack of 5', 'set of 2', 'set of 3'))
    is_combo_in_tgt = any(w in str(target_info.get("raw_query") or "").lower() for w in ('combo', 'pack of 2', 'pack of 3', 'pack of 4', 'pack of 5', 'set of 2', 'set of 3'))
    if is_combo_in_cand != is_combo_in_tgt:
        is_variant_diff = True
        reasons.append("Pack/Combo variant difference (Combo vs Single unit)")
        qty_pts -= 10.0
    elif cand_pack != tgt_pack:
        is_variant_diff = True
        reasons.append(f"Pack size variant ({cand_pack} vs {tgt_pack})")
        qty_pts -= 10.0
    else:
        reasons.append(f"Pack count verified: {tgt_pack}")

    tgt_wt = target_info.get("weight") or target_info.get("quantity")
    if tgt_wt:
        norm_t_qty = normalize_quantity_and_pack(str(tgt_wt))
        cand_wt_str = candidate.get("weight") or candidate.get("quantity") or ""
        norm_c_qty = normalize_quantity_and_pack(f"{cand_wt_str} {t_low}")

        t_grams = norm_t_qty.get("quantity_in_grams")
        c_grams = norm_c_qty.get("quantity_in_grams")

        if t_grams and c_grams:
            if abs(t_grams - c_grams) > 1.0:
                qty_pts -= 10.0
                is_variant_diff = True
                reasons.append(f"Weight variant ({norm_c_qty.get('total_quantity') or cand_wt_str} vs {norm_t_qty.get('total_quantity') or tgt_wt})")
            else:
                reasons.append(f"Weight verified: {norm_t_qty.get('total_quantity')}")
        elif cand_wt_str and str(cand_wt_str).lower().replace(" ", "").replace("gm", "g") != str(tgt_wt).lower().replace(" ", "").replace("gm", "g"):
            qty_pts -= 10.0
            is_variant_diff = True
            reasons.append(f"Weight variant ({cand_wt_str} vs {tgt_wt})")
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

    # ── 7. Classify Final Status (Section 2 & 14) ─────────────────────────────
    # VARIANT_MATCH is ONLY permitted if:
    # 1. Brand is verified (brand_pts >= 15.0 or brand matches).
    # 2. Specific product type matches (target_type == cand_type or both compatible).
    # 3. Candidate title similarity is not trivial (title_pts >= 5.0).
    # 4. Overall score >= 55.0.
    # Otherwise, difference is incompatible -> REJECTED!
    cand_cat_eval = str(candidate.get("category") or detect_category(title=t_title)).lower()
    tgt_type_eval = target_info.get("product_type") or extract_specific_product_type(raw_q, target_info.get("category") or "other")
    cand_type_eval = candidate.get("product_type") or extract_specific_product_type(t_title, cand_cat_eval)
    types_compatible = bool(not tgt_type_eval or tgt_type_eval == "other" or tgt_type_eval == cand_type_eval or not cand_type_eval or cand_type_eval == "other")

    if is_variant_diff:
        if brand_pts >= 15.0 and types_compatible and total_score >= 55.0 and title_pts >= 5.0:
            status = "VARIANT_MATCH"  # Displays as "Variant Match Found"
        else:
            status = "REJECTED"
            reasons.append("Incompatible candidate: variant differences cannot override brand or product type disparity")
    elif total_score >= 82.0:
        if target_model and not has_model_match:
            status = "SIMILAR_PRODUCT"
        else:
            status = "EXACT_MATCH"
    elif total_score >= 55.0 and brand_pts >= 15.0 and types_compatible:
        status = "SIMILAR_PRODUCT"
    elif total_score >= 35.0:
        status = "RELATED_PRODUCT"
    else:
        status = "REJECTED"
        reasons.append("Low overall similarity score")

    # Section 24: Backend logging for every candidate evaluation
    logger.info(
        f"[MATCH EVAL] QUERY: '{raw_q}' | PLATFORM: {candidate.get('platform', 'N/A')} | "
        f"CANDIDATE: '{t_title[:60]}' | CATEGORY: {cand_cat_eval} (EXP: {target_cat}) | "
        f"DECISION: {status} ({total_score:.1f} pts) | REASON: {'; '.join(reasons) if reasons else 'Verified'}"
    )

    return status, total_score, breakdown, reasons


def validate_product_for_comparison(
    target_info: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[bool, str, str]:
    """
    Section 2: Product-matching validation function before inserting products into the comparison table.
    Display a clear status:
    * Exact Match
    * Same Product – Different Variant
    * Similar Product
    * Different Product – Not Comparable
    * Insufficient Data

    Only products with a verified match (Exact Match or allowed Same Product – Different Variant)
    are permitted into the multi-platform specification comparison matrix.
    """
    if not candidate or not isinstance(candidate, dict):
        return False, STATUS_INSUFFICIENT_DATA, "Candidate product data is missing or empty"

    p_title = str(candidate.get("title") or candidate.get("product_name") or "").strip()
    p_price = candidate.get("price_num")

    if not p_title or len(p_title) < 4:
        return False, STATUS_INSUFFICIENT_DATA, "Insufficient specification data: missing title"

    # Evaluate match status
    status_code, match_score, breakdown, reasons = evaluate_product_match(target_info, candidate)

    # Check for hard rejections or accessory conflicts
    if status_code == "REJECTED":
        reason_str = reasons[0] if reasons else "Unrelated product / accessory mismatch"
        return False, STATUS_NOT_COMPARABLE, reason_str

    # Insufficient data check: no price and no specifications
    has_specs = bool(candidate.get("specifications") or (candidate.get("specs") and candidate["specs"].get("category_specs")))
    if (p_price is None or p_price <= 0) and not has_specs:
        return False, STATUS_INSUFFICIENT_DATA, "Insufficient verified specification data for comparison"

    # Check suspicious price
    is_susp, susp_reason = check_suspicious_price(candidate, [candidate])
    if is_susp:
        return False, STATUS_NOT_COMPARABLE, susp_reason

    # Map to clear display status
    if status_code == "EXACT_MATCH":
        return True, STATUS_EXACT_MATCH, "Exact matching product across brand, model, and specifications"
    elif status_code in ("VARIANT_MATCH", "PARTIAL_MATCH"):
        reason_str = ", ".join(r for r in reasons if "difference" in r or "variant" in r) or "Same product with variant difference"
        ret_label = STATUS_VARIANT_MATCH if status_code == "VARIANT_MATCH" else STATUS_PARTIAL_MATCH
        return True, ret_label, reason_str
    elif status_code == "SIMILAR_PRODUCT":
        return False, STATUS_SIMILAR_PRODUCT, "Similar product in the same category (not an exact or variant match)"
    else:
        return False, STATUS_DIFFERENT_PRODUCT, "Product cannot be compared with the target search"


# Alias for backward compatibility
classify_product_relationship = evaluate_product_match


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

    valid_prices: list[float] = []
    for it in all_products:
        p_val = it.get("price_num")
        if isinstance(p_val, (int, float)) and p_val > 0 and it.get("match_status") in ("EXACT_MATCH", "VARIANT_MATCH", STATUS_EXACT_MATCH, STATUS_PARTIAL_MATCH):
            valid_prices.append(float(p_val))

    if len(valid_prices) < 2:
        return False, ""

    valid_prices.sort()
    median_price = valid_prices[len(valid_prices) // 2]

    # Extreme low price detection (< 25% of median market price)
    if median_price >= 1000 and p_num < (median_price * 0.25):
        specs = product.get("specifications") or {}
        model = product.get("model")
        if not model or model == "N/A" or len(specs) < 3:
            return True, f"Suspicious price (₹{int(p_num):,} vs median ₹{int(median_price):,}) with incomplete specifications"

    return False, ""
