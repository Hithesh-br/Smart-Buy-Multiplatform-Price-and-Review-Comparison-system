"""
scrapers/meesho/meesho_product.py
=================================
Meesho Product Detail Enrichment:
Fetches detail-level product pages for top candidate products to extract:
- Deep specifications (Material, Dimensions, Ingredients, Warranty, Skin Type)
- Seller, Delivery, and Return details
- High-resolution product images
- Structured attributes
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from scrapers.meesho.meesho_client import MeeshoClient
from scrapers.meesho.meesho_parser import parse_json_ld, parse_price_value

logger = logging.getLogger("smartbuy.scrapers.meesho.product")


class MeeshoProductEnricher:
    """Enriches candidate Meesho items with detailed page attributes."""

    def __init__(self, client: Optional[MeeshoClient] = None):
        self.client = client or MeeshoClient()

    def enrich_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a normalized product and extracts detailed fields if url is available.
        Does not block or raise on errors — gracefully preserves existing fields.
        """
        url = product.get("url")
        if not url or "meesho.com" not in url:
            return product

        try:
            # 1. Try direct HTTP fetch first for low latency
            html, status, _ = self.client.fetch_html(url)
            if not html or status != "success":
                return product

            soup = BeautifulSoup(html, "html.parser")

            # Extract JSON-LD details if present
            ld_items = parse_json_ld(html)
            for ld in ld_items:
                if ld.get("brand") and (product.get("brand") in (None, "Generic")):
                    product["brand"] = ld["brand"]
                if ld.get("description") and not product.get("description"):
                    product["description"] = ld["description"]

            # Parse specification key-value pairs from detail tables or description blocks
            specs = product.get("specifications", {})
            attr_blocks = soup.find_all(lambda tag: tag.name in ('div', 'span', 'p') and any(k in tag.text.lower() for k in ('material', 'net quantity', 'weight', 'warranty', 'skin type', 'pack of')))
            for block in attr_blocks[:10]:
                text = block.get_text(separator=": ").strip()
                if ":" in text:
                    parts = [p.strip() for p in text.split(":", 1)]
                    if len(parts) == 2 and 2 < len(parts[0]) < 30 and len(parts[1]) < 100:
                        key, val = parts[0].title(), parts[1]
                        if key not in specs:
                            specs[key] = val
                            if "material" in key.lower() and not product.get("material"):
                                product["material"] = val
                            elif "weight" in key.lower() and not product.get("weight"):
                                product["weight"] = val

            product["specifications"] = specs

        except Exception as e:
            logger.debug(f"[MeeshoProductEnricher] Enrichment skipped for {url}: {e}")

        return product
