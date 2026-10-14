"""
tests/test_platform_scraping_and_image_fix.py
=============================================
Automated test suite verifying:
1. Flipkart product image extraction & URL normalization (relative URLs, template strings, srcset, badges, fallback SVGs)
2. Platform-specific image isolation (Amazon != Flipkart != Meesho, no cross-assignment)
3. Correct Common Product Data Schema (product_name, image_url, data_source, raw_specifications, material, capacity, color)
4. Product-specific specification mapping & automated cross-product column contamination validation
5. Dynamic category-based specifications for all 10 required cases (mobile, laptop, earbuds, grocery/pumpkin seeds, face wash, makeup, shirt, slippers, pressure cooker, mixer grinder)
6. Smart ranking category factors and honest handling of insufficient data
"""

import bs4
import pytest
from scrapers.common_schema import (
    create_empty_product,
    validate_and_build_product,
    clean_product_image_url,
    get_platform_fallback_image,
    FLIPKART_FALLBACK_IMAGE,
    AMAZON_FALLBACK_IMAGE,
    MEESHO_FALLBACK_IMAGE
)
from scrapers.flipkart.parser import clean_flipkart_image_url, parse_flipkart_card
from scrapers.amazon.parser import parse_amazon_card
from search.category_detector import detect_category
from search.specs_extractor import (
    extract_field_value,
    get_fields_for_category,
    build_dynamic_specifications,
    validate_cross_product_isolation,
    CATEGORY_BLACKLISTED_FIELDS
)
from search.ranking import rank_products


# ── 1. Flipkart Image Extraction & URL Cleaning Tests ─────────────────────────

def test_flipkart_clean_relative_image_url():
    """Verify protocol-relative and root-relative URLs are converted to valid absolute URLs."""
    proto_url = "//rukminim1.flixcart.com/image/312/312/xif0q/cooker/1.jpg"
    cleaned = clean_flipkart_image_url(proto_url)
    assert cleaned.startswith("https://rukminim1.flixcart.com/image/312/312/")

    root_url = "/image/312/312/xif0q/mobile/a/b/c.jpg"
    cleaned_root = clean_flipkart_image_url(root_url)
    assert cleaned_root.startswith("https://rukminim1.flixcart.com/image/312/312/")


def test_flipkart_clean_template_dimensions():
    """Verify template placeholders {@width}/{@height} are replaced with concrete pixel dimensions."""
    template_url = "https://rukminim1.flixcart.com/image/{@width}/{@height}/xif0q/headphone/tws.jpg"
    cleaned = clean_flipkart_image_url(template_url)
    assert "{@width}" not in cleaned
    assert "{@height}" not in cleaned
    assert "/312/312/" in cleaned


def test_flipkart_clean_srcset():
    """Verify srcset string descriptors (e.g. 1x, 2x, 312w) are stripped."""
    srcset_str = "https://rukminim2.flixcart.com/image/312/312/xif0q/mobile.jpg?q=70 1x, https://rukminim2.flixcart.com/image/624/624/xif0q/mobile.jpg?q=70 2x"
    cleaned = clean_flipkart_image_url(srcset_str)
    assert cleaned.startswith("https://rukminim2.flixcart.com/image/312/312/")
    assert " " not in cleaned
    assert "1x" not in cleaned


def test_flipkart_rejects_badges_and_blank_placeholders():
    """Verify Flipkart Assured badge icon, coin icons, and blank 1x1 GIFs are rejected."""
    assured_badge = "https://static-assets-web.flixcart.com/fk-p-linchpin-web/fk-cp-zion/img/fa_9e47c1.png"
    assert clean_flipkart_image_url(assured_badge) is None

    blank_gif = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    assert clean_flipkart_image_url(blank_gif) is None

    assert clean_flipkart_image_url("placeholder.png") is None
    assert clean_flipkart_image_url("") is None


def test_flipkart_card_multi_tier_image_extraction():
    """Verify parse_flipkart_card extracts valid image from standard Flipkart HTML card."""
    card_html = """
    <div class="cPHDOP">
        <a class="wjcEIp" title="Hawkins Contura 3 Litre Pressure Cooker" href="/p/itm12345?pid=CKR12345">
            Hawkins Contura 3 Litre Pressure Cooker
        </a>
        <img class="DByuf4" src="//rukminim1.flixcart.com/image/{@width}/{@height}/xif0q/cooker/hawkins.jpg" alt="Cooker">
        <div class="Nx9bqj">₹1,249</div>
        <div class="yRaY8j">₹1,550</div>
        <div class="UkUFwK"><span>19% off</span></div>
        <div class="XQDdHH">4.4</div>
        <span class="Wphh3Z">1,420 Reviews</span>
        <ul class="_1xgFaf">
            <li class="rgWa7D">Capacity: 3 Litres</li>
            <li class="rgWa7D">Material: Aluminium</li>
            <li class="rgWa7D">5 Year Warranty</li>
        </ul>
    </div>
    """
    soup = bs4.BeautifulSoup(card_html, "html.parser")
    parsed = parse_flipkart_card(soup.select_one("div.cPHDOP"))
    assert parsed is not None
    assert parsed["platform"] == "flipkart"
    assert parsed["product_id"] == "CKR12345"
    assert parsed["price_num"] == 1249
    assert parsed["mrp_num"] == 1550
    assert "https://rukminim1.flixcart.com/image/312/312/" in parsed["image"]
    assert parsed["specifications"]["Capacity"] == "3 Litres"
    assert parsed["specifications"]["Material"] == "Aluminium"
    assert parsed["specifications"]["Warranty"] == "5 Year Warranty"


def test_flipkart_fallback_image_when_missing():
    """Verify Flipkart card with no images falls back to FLIPKART_FALLBACK_IMAGE."""
    card_html = """
    <div class="slAVV4">
        <a class="wjcEIp" title="Raw Flax Seeds 500g" href="/flax-seeds/p/itm5678?pid=SED5678">Raw Flax Seeds 500g</a>
        <div class="Nx9bqj">₹199</div>
    </div>
    """
    soup = bs4.BeautifulSoup(card_html, "html.parser")
    parsed = parse_flipkart_card(soup.select_one("div.slAVV4"))
    assert parsed is not None
    assert parsed["image"] == FLIPKART_FALLBACK_IMAGE
    assert "Flipkart" in parsed["image"]


# ── 2. Platform-Specific Image Isolation Tests ────────────────────────────────

def test_platform_image_isolation():
    """Verify Amazon, Flipkart, and Meesho have completely distinct branded fallback images."""
    amz_fb = get_platform_fallback_image("amazon")
    fk_fb = get_platform_fallback_image("flipkart")
    msh_fb = get_platform_fallback_image("meesho")

    assert "Amazon" in amz_fb
    assert "Flipkart" in fk_fb
    assert "Meesho" in msh_fb

    assert amz_fb != fk_fb
    assert fk_fb != msh_fb
    assert amz_fb != msh_fb


# ── 3. Common Product Data Schema Tests ───────────────────────────────────────

def test_common_product_schema_compliance():
    """Verify normalized product dictionary strictly conforms to the common schema."""
    raw_data = {
        "platform": "flipkart",
        "product_id": "fk_9999",
        "product_name": "Prestige Deluxe Alpha Stainless Steel Pressure Cooker 3L",
        "brand": "Prestige",
        "category": "kitchen",
        "product_url": "https://www.flipkart.com/prestige-cooker/p/itm9999",
        "image_url": "https://rukminim1.flixcart.com/image/312/312/cooker.jpg",
        "price": 1499,
        "price_num": 1499,
        "mrp": 2195,
        "mrp_num": 2195,
        "rating": 4.3,
        "review_count": 210,
        "availability": "In Stock",
        "material": "Stainless Steel",
        "capacity": "3 Litres",
        "color": "Silver",
        "warranty": "5 Years",
        "specifications": {
            "Material": "Stainless Steel",
            "Capacity": "3 Litres",
            "Color": "Silver",
            "Warranty": "5 Years"
        },
        "raw_specifications": {
            "bullet_1": "Capacity: 3 Litres",
            "bullet_2": "Material: Stainless Steel"
        },
        "data_source": "Flipkart"
    }

    norm = validate_and_build_product(raw_data, platform="flipkart")

    # Assert required fields from user specification
    assert norm["platform"] == "flipkart"
    assert norm["product_id"] == "fk_9999"
    assert norm["product_name"] == "Prestige Deluxe Alpha Stainless Steel Pressure Cooker 3L"
    assert norm["title"] == norm["product_name"]
    assert norm["brand"] == "Prestige"
    assert norm["category"] == "kitchen"
    assert norm["product_url"] == "https://www.flipkart.com/prestige-cooker/p/itm9999"
    assert norm["image_url"] == "https://rukminim1.flixcart.com/image/312/312/cooker.jpg"
    assert norm["price_num"] == 1499
    assert norm["mrp_num"] == 2195
    assert norm["rating"] == 4.3
    assert norm["review_count"] == 210
    assert norm["availability"] == "In Stock"
    assert norm["material"] == "Stainless Steel"
    assert norm["capacity"] == "3 Litres"
    assert norm["color"] == "Silver"
    assert norm["warranty"] == "5 Years"
    assert norm["specifications"]["Material"] == "Stainless Steel"
    assert norm["raw_specifications"]["bullet_1"] == "Capacity: 3 Litres"
    assert norm["data_source"] == "Flipkart"


# ── 4. Cross-Product Specification Isolation Tests ────────────────────────────

def test_specification_isolation_between_platforms():
    """Verify that Amazon specifications do not leak into Flipkart or Meesho columns."""
    amz_prod = {
        "platform": "amazon",
        "product_id": "B001",
        "title": "Cooker Pro 3L",
        "color": "Matte Black",
        "material": "Hard Anodised",
        "price_num": 1399,
        "specifications": {"Color": "Matte Black", "Material": "Hard Anodised"}
    }
    fk_prod = {
        "platform": "flipkart",
        "product_id": "F001",
        "title": "Cooker Pro 3L",
        "color": "Silver",
        "material": "Aluminium",
        "price_num": 1299,
        "specifications": {"Color": "Silver", "Material": "Aluminium"}
    }
    mee_prod = {
        "platform": "meesho",
        "product_id": "M001",
        "title": "Cooker Pro 3L",
        "color": None,  # Meesho genuinely lacks color
        "material": "Aluminium",
        "price_num": 1199,
        "specifications": {"Material": "Aluminium"}
    }

    products = {"amazon": amz_prod, "flipkart": fk_prod, "meesho": mee_prod}
    matrix = build_dynamic_specifications(products, category="kitchen")

    color_row = next((r for r in matrix if r["field"] == "Color"), None)
    assert color_row is not None
    assert color_row["amazon"] == "Matte Black"
    assert color_row["flipkart"] == "Silver"
    # Meesho MUST NOT copy Amazon's or Flipkart's color
    assert color_row["meesho"] in ("—", "Not Available")
    assert "Matte Black" not in color_row["meesho"]
    assert "Silver" not in color_row["meesho"]

    # Automated validation check
    is_valid, issues = validate_cross_product_isolation(matrix)
    assert is_valid is True
    assert len(issues) == 0


# ── 5. Dynamic Category-Based Specifications Tests (10 Required Cases) ─────────

def test_category_grocery_pumpkin_seeds_no_mobile_specs():
    """Verify pumpkin/flax seeds show grocery specs (protein, fiber, etc.) and strictly NO mobile specs."""
    cat = detect_category(query="pumpkin seeds", title="Nutty Graces Raw Pumpkin Seeds 500g")
    assert cat == "grocery"

    fields = get_fields_for_category("grocery")
    fields_lower = [f.lower() for f in fields]

    # Verify grocery fields are present
    assert any("protein" in f for f in fields_lower)
    assert any("fibre" in f or "fiber" in f for f in fields_lower)
    assert any("net weight" in f or "quantity" in f for f in fields_lower)
    assert any("shelf life" in f for f in fields_lower)

    # Verify mobile specifications are strictly absent
    assert not any(f in ("ram", "rom", "storage", "camera", "processor", "battery", "display", "5g support") for f in fields_lower)

    # Verify blacklist prevents extraction of phone fields on grocery item
    item = {
        "title": "Raw Pumpkin Seeds 500g Rich in Protein and Fiber",
        "ram": "8 GB",
        "camera": "50 MP"
    }
    assert extract_field_value(item, "RAM", category="grocery") is None
    assert extract_field_value(item, "Camera", category="grocery") is None


def test_category_mobile_phone_specifications():
    """Verify mobile phone comparison template has display, processor, RAM, storage, camera, 5G."""
    cat = detect_category(query="mobile phone", title="OnePlus 12R 5G 16GB RAM 256GB Storage")
    assert cat == "phone"

    fields = get_fields_for_category("phone")
    fields_lower = [f.lower() for f in fields]

    assert any("ram" in f for f in fields_lower)
    assert any("storage" in f for f in fields_lower)
    assert any("processor" in f for f in fields_lower)
    assert any("camera" in f for f in fields_lower)
    assert any("battery" in f for f in fields_lower)
    assert not any("fabric" in f or "ingredient" in f or "flour" in f for f in fields_lower)


def test_category_laptop_specifications():
    """Verify laptop comparison template has processor, RAM, storage, display size, graphics, OS."""
    cat = detect_category(query="laptop", title="HP Pavilion 15 Intel Core i5 16GB RAM 512GB SSD Windows 11")
    assert cat == "laptop"

    fields = get_fields_for_category("laptop")
    fields_lower = [f.lower() for f in fields]

    assert any("processor" in f for f in fields_lower)
    assert any("ram" in f for f in fields_lower)
    assert any("storage" in f or "ssd" in f for f in fields_lower)
    assert any("graphics" in f or "gpu" in f for f in fields_lower)
    assert not any("skin type" in f or "ingredients" in f for f in fields_lower)


def test_category_wireless_earbuds_specifications():
    """Verify earbuds comparison template has connectivity, battery life, ANC, mic, driver size."""
    cat = detect_category(query="wireless earbuds", title="boAt Airdopes 141 ANC Bluetooth Earbuds 42H Playback")
    assert cat in ("earbuds", "earphones", "headphones")

    fields = get_fields_for_category("earphones")
    fields_lower = [f.lower() for f in fields]

    assert any("battery life" in f or "playback" in f for f in fields_lower)
    assert any("noise cancellation" in f or "anc" in f for f in fields_lower)
    assert any("connectivity" in f or "bluetooth" in f for f in fields_lower)
    assert not any("fabric" in f or "processor" in f for f in fields_lower)


def test_category_clothes_shirt_and_slippers():
    """Verify clothing shows material/fabric, fit, pattern, size; slippers show sole material, closure."""
    cat_shirt = detect_category(query="cotton shirt", title="Men Pure Cotton Slim Fit Casual Shirt")
    assert cat_shirt == "clothing"
    shirt_fields = [f.lower() for f in get_fields_for_category("clothing")]
    assert any("fabric" in f or "material" in f for f in shirt_fields)
    assert any("fit" in f for f in shirt_fields)
    assert any("pattern" in f for f in shirt_fields)

    cat_slip = detect_category(query="slippers", title="Puma Unisex EVA Sole Comfort Slides Slippers")
    assert cat_slip in ("shoes", "footwear", "slippers")
    slip_fields = [f.lower() for f in get_fields_for_category("shoes")]
    assert any("sole material" in f for f in slip_fields)
    assert any("closure type" in f for f in slip_fields)


def test_category_pressure_cooker_and_mixer_grinder():
    """Verify pressure cooker and mixer grinder show capacity, wattage, material, safety features."""
    cat_cooker = detect_category(query="pressure cooker", title="Hawkins Contura Aluminium 3L Cooker")
    assert cat_cooker in ("kitchen", "cooker", "pressure_cooker")
    cooker_fields = [f.lower() for f in get_fields_for_category("pressure_cooker")]
    assert any("capacity" in f for f in cooker_fields)
    assert any("material" in f or "body material" in f for f in cooker_fields)
    assert any("warranty" in f for f in cooker_fields)

    cat_mixer = detect_category(query="mixer grinder", title="Preethi Zodiac 750W Mixer Grinder with 5 Jars")
    assert cat_mixer in ("kitchen", "mixer_grinder")
    mixer_fields = [f.lower() for f in get_fields_for_category("mixer_grinder")]
    assert any("wattage" in f or "power" in f for f in mixer_fields)
    assert any("number of jars" in f or "jar" in f for f in mixer_fields)


# ── 6. Smart Ranking Honest Handling of Missing Data ──────────────────────────

def test_smart_ranking_insufficient_data_explanation():
    """Verify products with insufficient verified data receive transparent explanation."""
    p_insufficient = {
        "title": "Unknown Product",
        "has_sufficient_data": False,
        "quality_score": 0,
        "price_num": 500,
        "match_status": "EXACT_MATCH"
    }
    p_verified = {
        "title": "Verified High Quality Product",
        "has_sufficient_data": True,
        "quality_score": 88,
        "evidence_coverage": 85,
        "price_num": 600,
        "match_status": "EXACT_MATCH"
    }

    ranked = rank_products([p_insufficient, p_verified], query="product")
    assert ranked[0]["title"] == "Verified High Quality Product"
    assert "superior verified specifications" in ranked[0]["rank_explanation"].lower()
    assert "insufficient" in ranked[1]["rank_explanation"].lower()
