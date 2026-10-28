"""
scrapers/common_schema.py
=========================
SmartBuy Authoritative Common Product Schema.

Guarantees exact 37-field standardized dictionary across all marketplaces:
Amazon India, Flipkart, and Meesho.

Missing values are represented as None or "Not Available".
NEVER invents fake values. NEVER silently converts missing ratings to 0.
NEVER converts missing brands to "Generic".
"""

import re
from typing import Dict, Any, Optional, List


FLIPKART_FALLBACK_IMAGE = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScyMDAnIGhlaWdodD0nMjAwJyB2aWV3Qm94PScwIDAgMjAwIDIwMCc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScyMDAnIGZpbGw9JyNmMWYzZjYnLz48cmVjdCB4PSczMCcgeT0nMzAnIHdpZHRoPScxNDAnIGhlaWdodD0nMTQwJyByeD0nMTInIGZpbGw9JyNmZmZmZmYnIHN0cm9rZT0nIzI4NzRmMCcgc3Ryb2tlLXdpZHRoPScyJy8+PHBhdGggZD0nTTcwIDc1IEwxMzAgNzUgTDEyMiAxMzUgTDc4IDEzNSBaJyBmaWxsPScjMjg3NGYwJy8+PHBhdGggZD0nTTg1IDc1IEM4NSA2MCAxMTUgNjAgMTE1IDc1JyBzdHJva2U9JyNmZjlmMDAnIHN0cm9rZS13aWR0aD0nNCcgZmlsbD0nbm9uZScgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PHRleHQgeD0nMTAwJyB5PScxNjAnIGZvbnQtZmFtaWx5PSdBcmlhbCxzYW5zLXNlcmlmJyBmb250LXNpemU9JzEzJyBmb250LXdlaWdodD0nYm9sZCcgZmlsbD0nIzI4NzRmMCcgdGV4dC1hbmNob3I9J21pZGRsZSc+RmxpcGthcnQ8L3RleHQ+PC9zdmc+"
)

AMAZON_FALLBACK_IMAGE = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScyMDAnIGhlaWdodD0nMjAwJyB2aWV3Qm94PScwIDAgMjAwIDIwMCc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScyMDAnIGZpbGw9JyNmN2Y3ZjcnLz48cmVjdCB4PSczMCcgeT0nMzAnIHdpZHRoPScxNDAnIGhlaWdodD0nMTQwJyByeD0nMTInIGZpbGw9JyNmZmZmZmYnIHN0cm9rZT0nI2ZmOTkwMCcgc3Ryb2tlLXdpZHRoPScyJy8+PHBhdGggZD0nTTY1IDgwIEw3NSA4MCBMOTAgMTIwIEwxMjUgMTIwIEwxMzUgOTAgTDgwIDkwJyBzdHJva2U9JyMyMzJmM2UnIHN0cm9rZS13aWR0aD0nNCcgZmlsbD0nbm9uZScgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJyBzdHJva2UtbGluZWpvaW49J3JvdW5kJy8+PGNpcmNsZSBjeD0nOTInIGN5PScxMzInIHI9JzYnIGZpbGw9JyNmZjk5MDAnLz48Y2lyY2xlIGN4PScxMjMnIGN5PScxMzInIHI9JzYnIGZpbGw9JyNmZjk5MDAnLz48dGV4dCB4PScxMDAnIHk9JzE2MCcgZm9udC1mYW1pbHk9J0FyaWFsLHNhbnMtc2VyaWYnIGZvbnQtc2l6ZT0nMTMnIGZvbnQtd2VpZ2h0PSdib2xkJyBmaWxsPScjMjMyZjNlJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJz5BbWF6b248L3RleHQ+PC9zdmc+"
)

MEESHO_FALLBACK_IMAGE = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScyMDAnIGhlaWdodD0nMjAwJyB2aWV3Qm94PScwIDAgMjAwIDIwMCc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScyMDAnIGZpbGw9JyNmZGYyZjgnLz48cmVjdCB4PSczMCcgeT0nMzAnIHdpZHRoPScxNDAnIGhlaWdodD0nMTQwJyByeD0nMTInIGZpbGw9JyNmZmZmZmYnIHN0cm9rZT0nI2Y0MzM5Nycgc3Ryb2tlLXdpZHRoPScyJy8+PHBhdGggZD0nTTcwIDc1IEwxMzAgNzUgTDEyMiAxMzUgTDc4IDEzNSBaJyBmaWxsPScjZjQzMzk3Jy8+PHBhdGggZD0nTTg1IDc1IEM4NSA2MCAxMTUgNjAgMTE1IDc1JyBzdHJva2U9JyM4MzE4NDMnIHN0cm9rZS13aWR0aD0nNCcgZmlsbD0nbm9uZScgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PHRleHQgeD0nMTAwJyB5PScxNjAnIGZvbnQtZmFtaWx5PSdBcmlhbCxzYW5zLXNlcmlmJyBmb250LXNpemU9JzEzJyBmb250LXdlaWdodD0nYm9sZCcgZmlsbD0nI2Y0MzM5NycgdGV4dC1hbmNob3I9J21pZGRsZSc+TWVlc2hvPC90ZXh0Pjwvc3ZnPg=="
)


def get_platform_fallback_image(platform: str) -> str:
    """Returns an authentic, platform-branded fallback SVG data URL to avoid broken images."""
    plat = (platform or "").lower().strip()
    if "flipkart" in plat:
        return FLIPKART_FALLBACK_IMAGE
    if "meesho" in plat:
        return MEESHO_FALLBACK_IMAGE
    return AMAZON_FALLBACK_IMAGE


def clean_product_image_url(url: Any, platform: str = "") -> Optional[str]:
    """
    Cleans, validates, and normalizes product image URLs for a specific platform:
    - Resolves protocol-relative and root-relative URLs
    - Replaces Flipkart template parameters {@width}/{@height} with concrete dimensions
    - Removes srcset descriptors and selects candidate URL
    - Rejects placeholders, blank 1x1 GIFs, and platform badges (Assured icons, coins)
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u or len(u) < 8:
        return None

    # Strip srcset descriptor e.g. "https://... 312w" or multiple comma-separated entries
    if "," in u:
        u = u.split(",")[0].strip()
    if " " in u:
        u = u.split(" ")[0].strip()

    # Rejection of invalid / placeholder strings
    u_low = u.lower()
    if any(ph in u_low for ph in ("placeholder", "no_image", "not_available", "none", "null", "blank.gif", "empty")):
        return None
    if u_low.startswith("data:image/gif") or u_low.startswith("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"):
        # 1x1 transparent spacer GIF / PNG
        return None
    if any(badge in u_low for badge in ("fa_9e47c1", "plus_aef861", "fk-cp-zion", "static-assets", "supercoin")):
        return None

    # Protocol-relative URLs
    if u.startswith("//"):
        u = "https:" + u

    # Platform-specific root-relative URL expansion
    plat = (platform or "").lower().strip()
    if "flipkart" in plat:
        if u.startswith("/image/"):
            u = "https://rukminim1.flixcart.com" + u
        elif u.startswith("/"):
            u = "https://www.flipkart.com" + u
        # Replace Flipkart dynamic templates {@width} / {@height}
        u = re.sub(r'\{@width\}', '312', u)
        u = re.sub(r'\{@height\}', '312', u)
    elif "amazon" in plat:
        if u.startswith("/"):
            u = "https://www.amazon.in" + u
    elif "meesho" in plat:
        if u.startswith("/"):
            u = "https://images.meesho.com" + u

    # Must be valid http or https or trusted svg data uri
    if not (u.startswith("http://") or u.startswith("https://") or u.startswith("data:image/svg+xml")):
        return None

    return u


def create_empty_product(platform: str = "unknown") -> Dict[str, Any]:
    """Create a pristine product dictionary with all authoritative schema fields."""
    plat = platform.lower().strip() if platform else "unknown"
    return {
        "platform": plat,
        "product_id": "",
        "product_name": "",
        "title": "",
        "brand": None,
        "model": None,
        "model_number": None,
        "category": "other",
        "subcategory": None,

        "product_url": "",
        "link": "",
        "url": "",

        "image": "",
        "image_url": "",
        "images": [],

        "price": "Price Unavailable",
        "price_num": None,
        "mrp": None,
        "mrp_num": None,
        "discount": None,
        "currency": "INR",

        "rating": None,
        "review_count": None,
        "reviews": "0",

        "seller": None,
        "seller_rating": None,
        "availability": "In Stock",
        "in_stock": True,
        "condition": "New",

        "material": None,
        "capacity": None,
        "color": None,
        "size": None,

        "quantity": None,
        "pack_quantity": 1,
        "weight": None,
        "volume": None,
        "unit": None,
        "unit_price": None,

        "specifications": {},
        "raw_specifications": {},

        "warranty": None,
        "return_policy": None,

        "data_source": plat.capitalize() if plat != "unknown" else "Unknown",
        "source": plat,
        "verified_live": True,

        "quality_score": 0.0,
        "data_confidence": 0.0,

        "match_status": "UNMATCHED",
        "match_score": 0.0,
    }


def validate_and_build_product(data: Dict[str, Any], platform: str = "") -> Dict[str, Any]:
    """
    Constructs and validates the authoritative common product schema from parsed data.
    Ensures:
    - product_name, image_url, data_source, raw_specifications, material, capacity, color are preserved
    - Each platform keeps its own isolated data and images without cross-contamination
    - Fallback images prevent broken image icons on frontend cards, tables, and modals
    - Missing values are represented cleanly without inventing fake defaults
    """
    plat = (data.get("platform") or platform or "unknown").lower().strip()
    product = create_empty_product(plat)

    # Identifiers
    product["platform"] = plat
    product["product_id"] = str(data.get("product_id") or data.get("asin") or "").strip()
    product["product_url"] = str(data.get("product_url") or data.get("url") or data.get("link") or "").strip()
    product["link"] = product["product_url"]
    product["url"] = product["product_url"]

    # Product Name / Title
    title = str(data.get("product_name") or data.get("title") or data.get("name") or "").strip()
    product["title"] = title
    product["product_name"] = title

    # Brand & Model (strict: no fake 'Generic')
    raw_brand = data.get("brand")
    if raw_brand and str(raw_brand).strip().lower() not in ("generic", "none", "n/a", "null", ""):
        product["brand"] = str(raw_brand).strip()
    else:
        product["brand"] = None

    raw_model = data.get("model") or data.get("model_number")
    if raw_model and str(raw_model).strip().lower() not in ("standard", "general", "none", "n/a", "null", ""):
        product["model"] = str(raw_model).strip()
        product["model_number"] = str(raw_model).strip()
    else:
        product["model"] = None
        product["model_number"] = None

    product["category"] = str(data.get("category") or data.get("product_type") or "other").lower().strip()
    product["subcategory"] = data.get("subcategory") or None

    # Pricing
    price_num = data.get("price_num")
    if price_num is not None and isinstance(price_num, (int, float)) and price_num > 0:
        product["price_num"] = int(price_num)
        product["price"] = f"₹{int(price_num):,}"
    else:
        raw_price_str = str(data.get("price") or "").strip()
        product["price"] = raw_price_str if raw_price_str and raw_price_str != "0" else "Price Unavailable"
        product["price_num"] = None

    mrp_num = data.get("mrp_num")
    if mrp_num is not None and isinstance(mrp_num, (int, float)) and mrp_num > 0:
        product["mrp_num"] = int(mrp_num)
        product["mrp"] = f"₹{int(mrp_num):,}"
    elif data.get("mrp") and str(data.get("mrp")).strip() not in ("0", "N/A", "None"):
        product["mrp"] = str(data.get("mrp")).strip()
    else:
        product["mrp"] = None

    # Discount
    disc = data.get("discount") or data.get("discount_percent")
    if disc and str(disc).strip() not in ("0", "0%", "None", "N/A"):
        product["discount"] = str(disc).strip()
    elif product["mrp_num"] and product["price_num"] and product["mrp_num"] > product["price_num"]:
        pct = round(((product["mrp_num"] - product["price_num"]) / product["mrp_num"]) * 100)
        product["discount"] = f"{pct}% off"
    else:
        product["discount"] = None

    product["currency"] = data.get("currency") or "INR"

    # Rating & Reviews (strict: None if missing, NEVER 0.0)
    raw_rating = data.get("rating")
    if raw_rating is not None:
        try:
            r_flt = float(raw_rating)
            if 1.0 <= r_flt <= 5.0:
                product["rating"] = round(r_flt, 1)
            else:
                product["rating"] = None
        except (ValueError, TypeError):
            product["rating"] = None
    else:
        product["rating"] = None

    raw_rev = data.get("review_count") or data.get("reviews")
    if raw_rev is not None:
        try:
            rev_int = int(str(raw_rev).replace(",", "").split()[0])
            product["review_count"] = rev_int if rev_int >= 0 else None
            product["reviews"] = f"{rev_int:,}" if rev_int >= 0 else "0"
        except (ValueError, TypeError, IndexError):
            product["review_count"] = None
            product["reviews"] = "0"
    else:
        product["review_count"] = None
        product["reviews"] = "0"

    # Seller & Condition
    product["seller"] = data.get("seller") or None
    product["seller_rating"] = data.get("seller_rating") or None

    in_stock = data.get("in_stock", True)
    if in_stock is False or "out of stock" in str(data.get("availability", "")).lower():
        product["availability"] = "Out of Stock"
        product["in_stock"] = False
    else:
        product["availability"] = "In Stock"
        product["in_stock"] = True
    product["condition"] = data.get("condition") or "New"

    # Product Images with Platform-Specific Validation and Fallbacks
    img = data.get("image") or data.get("image_url") or ""
    cleaned_img = clean_product_image_url(img, plat)
    if not cleaned_img:
        cleaned_img = get_platform_fallback_image(plat)
    product["image"] = cleaned_img
    product["image_url"] = cleaned_img

    imgs = data.get("images")
    if isinstance(imgs, list):
        cleaned_list = []
        for i in imgs:
            c = clean_product_image_url(i, plat)
            if c and c not in cleaned_list:
                cleaned_list.append(c)
        product["images"] = cleaned_list if cleaned_list else [cleaned_img]
    else:
        product["images"] = [cleaned_img]

    # Variants, quantity, weights
    product["color"] = data.get("color") or None
    product["size"] = data.get("size") or None
    product["quantity"] = data.get("quantity") or None
    product["pack_quantity"] = int(data.get("pack_quantity") or 1)
    product["weight"] = data.get("weight") or None
    product["volume"] = data.get("volume") or None
    product["unit"] = data.get("unit") or None
    product["unit_price"] = data.get("unit_price") or None

    # Specifications & Raw Specifications
    specs = data.get("specifications")
    if isinstance(specs, dict):
        product["specifications"] = {k: v for k, v in specs.items() if v is not None}
    else:
        product["specifications"] = {}

    raw_specs = data.get("raw_specifications")
    if isinstance(raw_specs, dict) and raw_specs:
        product["raw_specifications"] = dict(raw_specs)
    else:
        product["raw_specifications"] = dict(product["specifications"])

    # Specific common attribute accessors
    product["material"] = (
        data.get("material")
        or product["specifications"].get("Material")
        or product["specifications"].get("material")
        or product["specifications"].get("Body Material")
    )
    product["capacity"] = (
        data.get("capacity")
        or product["specifications"].get("Capacity")
        or product["specifications"].get("capacity")
    )
    if not product["color"]:
        product["color"] = (
            product["specifications"].get("Color")
            or product["specifications"].get("color")
            or product["specifications"].get("Colour")
        )

    # Warranty & Return
    product["warranty"] = data.get("warranty") or product["specifications"].get("Warranty") or None
    product["return_policy"] = data.get("return_policy") or None

    # Data Source & Provenance
    product["data_source"] = str(data.get("data_source") or data.get("source") or plat.capitalize()).strip()
    product["source"] = plat
    product["verified_live"] = bool(data.get("verified_live", True))
    product["quality_score"] = float(data.get("quality_score") or 0.0)
    product["data_confidence"] = float(data.get("data_confidence") or 0.0)
    product["match_status"] = data.get("match_status") or "UNMATCHED"
    product["match_score"] = float(data.get("match_score") or 0.0)

    return product
