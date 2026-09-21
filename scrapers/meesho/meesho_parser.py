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


def parse_next_data(html_content: str) -> List[Dict[str, Any]]:
    """Extract products from __NEXT_DATA__ or embedded hydration state."""
    products = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = json.loads(script.string)
            props = data.get("props", {}).get("pageProps", {})
            raw_products = props.get("initialState", {}).get("search", {}).get("products") or props.get("products")
            if isinstance(raw_products, list):
                for p in raw_products:
                    if isinstance(p, dict):
                        p_id = p.get("id") or p.get("product_id")
                        title = p.get("name") or p.get("title")
                        slug = p.get("slug") or p.get("url")
                        if slug and not title:
                            title = extract_title_from_slug(slug)
                        price = p.get("price") or p.get("discounted_price")
                        mrp = p.get("mrp") or p.get("original_price")
                        rating = p.get("rating") or p.get("average_rating")
                        reviews = p.get("rating_count") or p.get("reviews_count")
                        image = p.get("image") or p.get("images", [None])[0]

                        url = f"https://www.meesho.com/{slug}/p/{p_id}" if slug and p_id else (slug or "")
                        if title and price:
                            products.append({
                                "product_id": str(p_id or ""),
                                "title": title,
                                "price": price,
                                "mrp": mrp,
                                "rating": rating,
                                "review_count": reviews,
                                "image": image,
                                "url": url,
                                "source": "next_data"
                            })
    except Exception as e:
        logger.debug(f"[MeeshoParser] Next.js data parse error: {e}")
    return products
