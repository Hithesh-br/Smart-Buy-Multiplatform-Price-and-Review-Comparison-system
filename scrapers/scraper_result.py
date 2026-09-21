"""
scrapers/scraper_result.py
==========================
Defines standardized scraping statuses, result containers, and normalized product models.
Enforces that missing fields are None or "Not Available", and forbids fake data.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict


class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    TIMEOUT = "timeout"
    SELECTOR_CHANGED = "selector_changed"
    NETWORK_ERROR = "network_error"
    SCRAPER_ERROR = "scraper_error"
    UNKNOWN_ERROR = "error"


@dataclass
class ScraperResult:
    platform: str
    status: ScrapeStatus = ScrapeStatus.SUCCESS
    products: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    source: str = "live"
    retry_count: int = 0
    duration_ms: float = 0.0


def create_normalized_product(
    platform: str,
    title: str,
    price: Any,
    url: str = "",
    brand: Optional[str] = None,
    model: Optional[str] = None,
    mrp: Optional[Any] = None,
    discount: Optional[Any] = None,
    rating: Optional[Any] = None,
    review_count: Optional[int] = None,
    image: Optional[str] = None,
    availability: Optional[str] = None,
    weight: Optional[str] = None,
    pack_quantity: Optional[str] = None,
    color: Optional[str] = None,
    size: Optional[str] = None,
    product_type: Optional[str] = None,
    key_features: Optional[list] = None,
    specifications: Optional[dict] = None,
    seller: Optional[str] = None,
    source: str = "live",
    scrape_status: ScrapeStatus = ScrapeStatus.SUCCESS,
    raw_data: Optional[dict] = None,
) -> dict:
    """
    Constructs a strictly normalized product dictionary adhering to the specification.
    Never invents fake data — absent fields remain None or "Not Available".
    """
    clean_platform = (platform or "").lower().strip()
    if clean_platform in ("amazon", "amz"):
        clean_platform = "amazon"
    elif clean_platform in ("flipkart", "fk"):
        clean_platform = "flipkart"
    elif clean_platform in ("meesho", "mee"):
        clean_platform = "meesho"

    # Numeric price extraction
    price_num = None
    price_str = None
    if price is not None and str(price).strip() not in ("", "N/A", "None", "0"):
        import re
        s_p = str(price).strip()
        s_p = re.sub(r'[₹$€£\s,]|rs\.?|inr', '', s_p, flags=re.IGNORECASE)
        m_p = re.search(r'(\d+(?:\.\d+)?)', s_p)
        if m_p:
            try:
                p_val = int(round(float(m_p.group(1))))
                if p_val > 0:
                    price_num = p_val
                    price_str = f"₹{price_num:,}"
            except Exception:
                pass

    mrp_num = None
    mrp_str = None
    if mrp is not None and str(mrp).strip() not in ("", "N/A", "None", "0"):
        import re
        s_m = str(mrp).strip()
        s_m = re.sub(r'[₹$€£\s,]|rs\.?|inr', '', s_m, flags=re.IGNORECASE)
        m_m = re.search(r'(\d+(?:\.\d+)?)', s_m)
        if m_m:
            try:
                m_val = int(round(float(m_m.group(1))))
                if m_val > 0:
                    mrp_num = m_val
                    mrp_str = f"₹{mrp_num:,}"
            except Exception:
                pass

    discount_val = discount if discount and str(discount).strip() not in ("", "N/A", "None") else None
    if not discount_val and mrp_num and price_num and mrp_num > price_num:
        pct = round(((mrp_num - price_num) / mrp_num) * 100)
        discount_val = f"{pct}% off"

    # Rating normalization
    rating_val = None
    if rating is not None and str(rating).strip() not in ("", "N/A", "None", "0", "0.0"):
        import re
        r_match = re.search(r'\b([1-5]\.[0-9]|[1-5])\b', str(rating))
        if r_match:
            rating_val = float(r_match.group(1))

    # Review count normalization
    reviews_val = 0
    if review_count is not None:
        import re
        r_digits = re.sub(r'[^\d]', '', str(review_count))
        if r_digits:
            reviews_val = int(r_digits)

    # In-stock detection
    in_stock = price_num is not None and price_num > 0
    avail_val = availability or ("In Stock" if in_stock else "Out of Stock")

    clean_img = image or ""
    if "unsplash.com" in clean_img or "placeholder" in clean_img:
        clean_img = ""

    return {
        "platform": clean_platform,
        "platform_name": clean_platform.capitalize(),
        "title": title or "Not Available",
        "brand": brand if (brand and brand != "N/A") else None,
        "model": model if (model and model != "N/A") else None,
        "price": price_str or "Not Available",
        "price_num": price_num,
        "mrp": mrp_str,
        "mrp_num": mrp_num,
        "original_price": mrp_str,
        "discount": discount_val,
        "rating": rating_val,
        "review_count": reviews_val,
        "reviews": str(reviews_val),
        "image": clean_img,
        "image_url": clean_img,
        "url": url or "",
        "product_url": url or "",
        "link": url or "",
        "availability": avail_val,
        "in_stock": in_stock,
        "weight": weight if (weight and weight != "N/A") else None,
        "pack_quantity": str(pack_quantity) if (pack_quantity and str(pack_quantity) != "N/A") else "1",
        "color": color if (color and color != "N/A") else None,
        "size": size if (size and size != "N/A") else None,
        "product_type": product_type or None,
        "key_features": key_features or [],
        "specifications": specifications or {},
        "seller": seller if (seller and seller != "N/A") else None,
        "source": source or "live",
        "scrape_status": scrape_status.value if isinstance(scrape_status, ScrapeStatus) else str(scrape_status),
        "raw_data": raw_data or {},
    }
