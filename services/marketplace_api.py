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
        self.amazon_key = os.getenv("AMAZON_API_KEY", "").strip()
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
        logger.info(f"[API] Querying official Amazon API for '{query}'...")
        try:
            endpoint = os.getenv("AMAZON_API_ENDPOINT", "https://webservices.amazon.in/paapi5/searchitems")
            partner_tag = os.getenv("AMAZON_PARTNER_TAG", "smartbuy-21")
            payload = {
                "Keywords": query,
                "PartnerTag": partner_tag,
                "PartnerType": "Associates",
                "Marketplace": "www.amazon.in",
                "Resources": ["ItemInfo.Title", "Offers.Listings.Price", "Images.Primary.Medium"]
            }
            headers = {"Authorization": f"Bearer {self.amazon_key or self.unified_key}"}
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("SearchResult", {}).get("Items", [])
                products = []
                for it in items:
                    title = it.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "")
                    price = it.get("Offers", {}).get("Listings", [{}])[0].get("Price", {}).get("DisplayAmount")
                    url = it.get("DetailPageURL", "")
                    img = it.get("Images", {}).get("Primary", {}).get("Medium", {}).get("URL")
                    if title:
                        products.append(create_normalized_product(
                            platform="amazon",
                            title=title,
                            price=price,
                            url=url,
                            image=img,
                            source="api",
                            scrape_status=ScrapeStatus.SUCCESS
                        ))
                return products, ScrapeStatus.SUCCESS, None
            else:
                logger.warning(f"[API] Amazon API returned {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            logger.warning(f"[API] Amazon API request failed: {e}")
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
