"""
services/marketplace_api.py
===========================
Authorized Marketplace API provider abstraction.
Supports optional official API integrations when credentials are provided in .env:
- AMAZON_API_KEY
- FLIPKART_API_KEY
- MEESHO_API_KEY
- PRODUCT_SEARCH_API_KEY

If not configured or if an API call fails, cleanly returns None so that
the scraper fallback chain (Playwright) engages automatically.
Never returns fake/mock data in production.
"""

import os
import logging
from typing import Optional
import requests
from scrapers.scraper_result import ScrapeStatus, create_normalized_product

logger = logging.getLogger("smartbuy.marketplace_api")


class MarketplaceAPIService:
    def __init__(self):
        self.amazon_key = os.getenv("AMAZON_CREATORS_API_KEY", "").strip() or os.getenv("AMAZON_API_KEY", "").strip()
        self.flipkart_key = os.getenv("FLIPKART_API_KEY", "").strip()
        self.meesho_key = os.getenv("MEESHO_API_KEY", "").strip()
        self.unified_key = os.getenv("PRODUCT_SEARCH_API_KEY", "").strip()

    def is_configured(self, platform: str) -> bool:
        plat = platform.lower().strip()
        if plat == "amazon":
            return bool(self.amazon_key or self.unified_key)
        elif plat == "flipkart":
            return bool(self.flipkart_key or self.unified_key)
        elif plat == "meesho":
            return bool(self.meesho_key or self.unified_key)
        return False

    def fetch_amazon(self, query: str) -> Optional[tuple[list[dict], ScrapeStatus, Optional[str]]]:
        if not self.is_configured("amazon"):
            return None
        logger.info(f"[API] Querying official Amazon Creators API for '{query}'...")
        try:
            # Amazon PA-API 5 is deprecated; use Amazon Creators API
            endpoint = os.getenv("AMAZON_CREATORS_API_ENDPOINT", "https://creator-api.amazon.in/v1/products/search")
            partner_tag = os.getenv("AMAZON_PARTNER_TAG", "smartbuy-21")
            token = self.amazon_key or self.unified_key
            headers = {
                "Authorization": f"Bearer {token}",
                "x-api-key": token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "query": query,
                "partner_tag": partner_tag,
                "marketplace": "amazon.in",
                "item_count": 10
            }
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                # Support Creators API schema or SearchResult schema
                items = data.get("products") or data.get("items") or data.get("SearchResult", {}).get("Items", [])
                products = []
                for it in items:
                    asin = it.get("asin") or it.get("ASIN") or ""
                    title = it.get("title") or it.get("name") or it.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "")
                    price = it.get("price") or it.get("amount") or it.get("Offers", {}).get("Listings", [{}])[0].get("Price", {}).get("DisplayAmount")
                    mrp = it.get("mrp") or it.get("original_price")
                    url = it.get("product_url") or it.get("url") or it.get("DetailPageURL") or (f"https://www.amazon.in/dp/{asin}" if asin else "")
                    img = it.get("main_image_url") or it.get("image") or it.get("Images", {}).get("Primary", {}).get("Medium", {}).get("URL")
                    rating = it.get("rating")
                    reviews = it.get("review_count") or it.get("reviews")
                    brand = it.get("brand") or it.get("ItemInfo", {}).get("ByLineInfo", {}).get("Brand", {}).get("DisplayValue")
                    specs = it.get("specifications") or {}
                    if title:
                        products.append(create_normalized_product(
                            platform="amazon",
                            title=title,
                            price=price,
                            mrp=mrp,
                            url=url,
                            image=img,
                            rating=rating,
                            review_count=reviews,
                            brand=brand,
                            specifications=specs,
                            product_id=asin,
                            source="creators_api",
                            scrape_status=ScrapeStatus.SUCCESS
                        ))
                if products:
                    return products, ScrapeStatus.SUCCESS, None
                return [], ScrapeStatus.NO_RESULTS, "No products returned from Amazon Creators API"
            else:
                logger.warning(f"[API] Amazon Creators API returned {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            logger.warning(f"[API] Amazon Creators API request failed: {e}")
            return None

    def fetch_flipkart(self, query: str) -> Optional[tuple[list[dict], ScrapeStatus, Optional[str]]]:
        if not self.is_configured("flipkart"):
            return None
        logger.info(f"[API] Querying Flipkart API for '{query}'...")
        try:
            endpoint = os.getenv("FLIPKART_API_ENDPOINT", "https://affiliate-api.flipkart.net/affiliate/1.0/search.json")
            headers = {"Fk-Affiliate-Id": os.getenv("FLIPKART_AFFILIATE_ID", ""), "Fk-Affiliate-Token": self.flipkart_key or self.unified_key}
            resp = requests.get(endpoint, params={"query": query, "resultCount": 20}, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("products", [])
                products = []
                for it in items:
                    base = it.get("productBaseInfoV1", {})
                    title = base.get("title", "")
                    price = base.get("flipkartSellingPrice", {}).get("amount")
                    mrp = base.get("maximumRetailPrice", {}).get("amount")
                    url = base.get("productUrl", "")
                    img = base.get("imageUrls", {}).get("400x400") or base.get("imageUrls", {}).get("200x200")
                    if title:
                        products.append(create_normalized_product(
                            platform="flipkart",
                            title=title,
                            price=price,
                            mrp=mrp,
                            url=url,
                            image=img,
                            source="api",
                            scrape_status=ScrapeStatus.SUCCESS
                        ))
                return products, ScrapeStatus.SUCCESS, None
            else:
                logger.warning(f"[API] Flipkart API returned {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"[API] Flipkart API request failed: {e}")
            return None

    def fetch_meesho(self, query: str) -> Optional[tuple[list[dict], ScrapeStatus, Optional[str]]]:
        if not self.is_configured("meesho"):
            return None
        logger.info(f"[API] Querying Meesho Partner API for '{query}'...")
        try:
            endpoint = os.getenv("MEESHO_API_ENDPOINT", "https://api.meesho.com/v1/products/search")
            headers = {"Authorization": f"Bearer {self.meesho_key or self.unified_key}"}
            resp = requests.get(endpoint, params={"q": query}, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("products", [])
                products = []
                for it in items:
                    title = it.get("name") or it.get("title", "")
                    price = it.get("price") or it.get("discounted_price")
                    mrp = it.get("mrp")
                    url = it.get("product_url") or it.get("url", "")
                    img = it.get("image_url") or it.get("image", "")
                    if title:
                        products.append(create_normalized_product(
                            platform="meesho",
                            title=title,
                            price=price,
                            mrp=mrp,
                            url=url,
                            image=img,
                            source="api",
                            scrape_status=ScrapeStatus.SUCCESS
                        ))
                return products, ScrapeStatus.SUCCESS, None
            else:
                logger.warning(f"[API] Meesho API returned {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"[API] Meesho API request failed: {e}")
            return None


_api_service_instance = None

def get_marketplace_api_service() -> MarketplaceAPIService:
    global _api_service_instance
    if _api_service_instance is None:
        _api_service_instance = MarketplaceAPIService()
    return _api_service_instance
