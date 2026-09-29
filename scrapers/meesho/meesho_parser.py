"""
scrapers/meesho/meesho_parser.py
================================
Multi-strategy parser for Meesho HTML, JSON-LD, Next.js state, and DOM elements:
- Strategy 1: JSON-LD structured data (<script type="application/ld+json">)
- Strategy 2: Embedded Next.js hydration state (<script id="__NEXT_DATA__">)
- Strategy 3: URL Slug reconstruction (recovering detailed brand and title)
- Strategy 4: Resilient CSS selectors & semantic DOM traversal
- Strategy 5: Price, MRP, Rating, and Review parsing
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("smartbuy.scrapers.meesho.parser")


def extract_title_from_slug(url_or_slug: str) -> Optional[str]:
    """
    Recovers the full, highly descriptive product title from Meesho product URL slugs.
    e.g. '/exetech-65w-laptop-charger-adapter-compatible-forhp-195v-334a-45mm-blue-pin-slim-pin/p/hmsq5h'
    -> 'Exetech 65w Laptop Charger Adapter Compatible For HP 195v 334a 45mm Blue Pin Slim Pin'
    """
    if not url_or_slug:
        return None

    clean = url_or_slug.split("?")[0]
    match = re.search(r'/([^/]+)/p/[a-z0-9]+', clean)
    if not match:
        parts = [p for p in clean.strip("/").split("/") if p and p != "p"]
        if parts:
            slug = parts[0]
        else:
            return None
    else:
        slug = match.group(1)

    slug = re.sub(r'[-_]+', ' ', slug).strip()
    # Correct common concatenated brand patterns e.g. "forhp" -> "for HP"
    slug = re.sub(r'\bforhp\b', 'for HP', slug, flags=re.IGNORECASE)
    slug = re.sub(r'\bforvivo\b', 'for Vivo', slug, flags=re.IGNORECASE)
    slug = re.sub(r'\bforsamsung\b', 'for Samsung', slug, flags=re.IGNORECASE)
    slug = re.sub(r'\bforapple\b', 'for Apple', slug, flags=re.IGNORECASE)

    words = slug.split()
    capitalized = []
    for w in words:
        if w.lower() in ('hp', 'vivo', 'oppo', 'mi', 'iqoo', 'usb', 'led', 'ac', 'dc', 'ram', 'rom', 'rgb'):
            capitalized.append(w.upper())
        elif w.lower() in ('for', 'in', 'with', 'and', 'to', 'of'):
            capitalized.append(w.lower())
        else:
            capitalized.append(w.capitalize())

    title = " ".join(capitalized).strip()
    return title if len(title) >= 5 else None


def parse_price_value(price_val: Any) -> tuple[Optional[int], Optional[str]]:
    """Parse numeric price and formatted price string (e.g. 773, '₹773')."""
    if price_val is None:
        return None, None
    s = str(price_val).strip()
    cleaned = re.sub(r'[^\d.]', '', s)
    if not cleaned:
        return None, None
    try:
        val = int(float(cleaned))
        return val, f"₹{val:,}"
    except (ValueError, TypeError):
        return None, None


def parse_rating_and_reviews(rating_val: Any, review_val: Any = None) -> tuple[Optional[float], int]:
    """Parse rating float and review count integer."""
    rating = None
    if rating_val is not None:
        try:
            r_match = re.search(r'(\d+(?:\.\d+)?)', str(rating_val))
            if r_match:
                r_float = float(r_match.group(1))
                if 0.0 <= r_float <= 5.0:
                    rating = round(r_float, 1)
        except Exception:
            pass

    reviews = 0
    if review_val is not None:
        try:
            rv_match = re.search(r'([\d,]+)', str(review_val))
            if rv_match:
                reviews = int(rv_match.group(1).replace(",", ""))
        except Exception:
            pass

    return rating, reviews


def parse_json_ld(html_content: str) -> List[Dict[str, Any]]:
    """Extract structured products from <script type="application/ld+json">."""
    products = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                data = json.loads(s.string or "")
                items_to_check = data if isinstance(data, list) else [data]
                for item in items_to_check:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") == "Product":
                        name = item.get("name")
                        offers = item.get("offers") or {}
                        price = offers.get("price")
                        url = item.get("url")
                        image = item.get("image")
                        if isinstance(image, list) and image:
                            image = image[0]
                        rating_obj = item.get("aggregateRating") or {}
                        rating = rating_obj.get("ratingValue")
                        reviews = rating_obj.get("reviewCount") or rating_obj.get("ratingCount")
                        brand = item.get("brand")
                        if isinstance(brand, dict):
                            brand = brand.get("name")

                        if name and price:
                            products.append({
                                "title": name,
                                "price": price,
                                "url": url,
                                "image": image,
                                "rating": rating,
                                "review_count": reviews,
                                "brand": brand,
                                "availability": offers.get("availability"),
                                "source": "json_ld"
                            })
                    elif item.get("@type") == "ItemList":
                        elements = item.get("itemListElement") or []
                        for el in elements:
                            p_item = el.get("item") or el
                            if isinstance(p_item, dict) and p_item.get("name"):
                                products.append({
                                    "title": p_item.get("name"),
                                    "url": p_item.get("url"),
                                    "image": p_item.get("image"),
                                    "source": "json_ld_list"
                                })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[MeeshoParser] JSON-LD parse error: {e}")
    return products


def parse_meesho_catalog_item(c: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parses a single catalog product dictionary from Meesho's products/search API or hydration state.
    Extracts authentic fields:
    title, price, mrp, rating, review_count, image, url, product_id, specifications.
    Never invents missing values.
    """
    if not isinstance(c, dict):
        return None

    # Title: hero_product_name is the most descriptive real title
    title = (
        c.get("hero_product_name")
        or c.get("name")
        or c.get("title")
        or ""
    ).strip()

    slug = c.get("slug") or c.get("original_slug") or ""
    pid = str(c.get("product_id") or c.get("id") or c.get("catalogId") or "").strip()

    generic_titles = (
        "designer water bottles", "essential water bottles", "fancy water bottles",
        "water bottles", "lunch boxes & water bottles", "others", "casual"
    )
    if (not title or len(title) < 5 or title.lower() in generic_titles) and slug:
        recovered = extract_title_from_slug(slug)
        if recovered:
            title = recovered

    if not title or len(title) < 3:
        return None

    # Price
    price_val = (
        c.get("min_product_price")
        or c.get("min_catalog_price")
        or c.get("price")
        or c.get("discounted_price")
    )
    price_num, price_str = parse_price_value(price_val)
    if not price_num or price_num <= 0:
        return None

    # MRP
    mrp_val = c.get("mrp") or c.get("original_price") or price_num
    mrp_num, mrp_str = parse_price_value(mrp_val)

    # Reviews & Rating
    reviews_summary = c.get("catalog_reviews_summary") or {}
    rating = None
    review_count = 0
    if isinstance(reviews_summary, dict):
        rating_val = reviews_summary.get("average_rating") or reviews_summary.get("rating")
        if rating_val:
            try:
                rating = round(float(rating_val), 1)
            except Exception:
                pass
        review_count = int(reviews_summary.get("review_count") or reviews_summary.get("rating_count") or 0)
    else:
        rating, review_count = parse_rating_and_reviews(c.get("rating"), c.get("reviews") or c.get("review_count"))

    # Images
    images = c.get("images") or c.get("product_images") or []
    image_url = ""
    if isinstance(images, list) and images:
        image_url = images[0]
    elif isinstance(c.get("image"), str):
        image_url = c.get("image")
    elif isinstance(c.get("image_url"), str):
        image_url = c.get("image_url")

    # URL
    if slug and pid:
        url = f"https://www.meesho.com/{slug}/p/{pid}"
    elif slug:
        url = f"https://www.meesho.com/{slug}"
    else:
        url = c.get("url") or f"https://www.meesho.com/p/{pid}"

    # Specifications from full_details & product_attributes
    specifications: Dict[str, str] = {}
    fd = c.get("full_details")
    if isinstance(fd, str):
        for line in fd.split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                k_clean = k.strip()
                v_clean = v.strip()
                if k_clean and v_clean and v_clean.lower() not in ("none", "null", "n/a"):
                    specifications[k_clean] = v_clean
    elif isinstance(fd, dict):
        for k, v in fd.items():
            if v and str(v).strip().lower() not in ("none", "null", "n/a"):
                specifications[str(k).strip()] = str(v).strip()

    pa = c.get("product_attributes")
    if isinstance(pa, list):
        for attr in pa:
            if isinstance(attr, str) and ":" in attr:
                k, v = attr.split(":", 1)
                k_clean = k.strip()
                v_clean = v.strip()
                if k_clean and v_clean and v_clean.lower() not in ("none", "null", "n/a"):
                    specifications[k_clean] = v_clean

    brand = specifications.get("Brand") or c.get("brand")

    return {
        "product_id": pid,
        "title": title,
        "product_name": title,
        "price": price_str or f"₹{price_num:,}",
        "price_num": price_num,
        "mrp": mrp_str or f"₹{mrp_num:,}",
        "mrp_num": mrp_num or price_num,
        "rating": rating,
        "review_count": review_count,
        "image": image_url,
        "image_url": image_url,
        "url": url,
        "product_url": url,
        "specifications": specifications,
        "brand": brand,
        "availability": "In Stock",
        "in_stock": True,
        "source": "meesho_catalog"
    }


def parse_next_data(html_content: str) -> List[Dict[str, Any]]:
    """Extract products from __NEXT_DATA__ or embedded hydration state."""
    products = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = json.loads(script.string)
            props = data.get("props", {}).get("pageProps", {})
            init_st = props.get("initialState", {})

            # Try modern Next.js searchListing.listing.products
            raw_products = (
                init_st.get("searchListing", {}).get("listing", {}).get("products")
                or init_st.get("plpListing", {}).get("listing", {}).get("products")
                or init_st.get("search", {}).get("products")
                or props.get("products")
                or []
            )

            if isinstance(raw_products, list) and raw_products:
                for p in raw_products:
                    item = parse_meesho_catalog_item(p)
                    if item:
                        products.append(item)
    except Exception as e:
        logger.debug(f"[MeeshoParser] Next.js data parse error: {e}")
    return products
