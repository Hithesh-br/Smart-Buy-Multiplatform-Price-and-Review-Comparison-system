"""
search/url_resolver.py
======================
SmartBuy Safe URL Redirect Resolver.

Handles expanded and shortened share URLs, specifically:
- Flipkart short URLs: https://dl.flipkart.com/s/XXXX
- Amazon short URLs: https://amzn.to/XXXX, https://amzn.in/XXXX
- Meesho short URLs: https://meesho.com/s/p/XXXX

Order of Resolution:
1. Safe HTTP GET/HEAD redirect resolution with browser headers.
2. Playwright Chromium fallback if Akamai/Cloudflare edge firewall returns 403 or prevents HTTP redirect.
"""

import logging
import urllib.parse
from typing import Optional
import requests

from scrapers.browser_manager import BrowserManager

logger = logging.getLogger("smartbuy.search.url_resolver")

DEFAULT_RESOLVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
}


def is_short_or_share_url(url: str) -> bool:
    """Check if URL is a known redirect / short / mobile share link."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip().lower()
    return (
        "dl.flipkart.com/s/" in u or
        "dl.flipkart.com/dl/" in u or
        "amzn.to/" in u or
        "amzn.in/d/" in u or
        "fkrt.it/" in u
    )


def resolve_product_url(url: str, platform: Optional[str] = None) -> str:
    """
    Safely resolves any shortened or redirecting URL to its canonical destination.
    Uses HTTP redirect resolution first, followed by Playwright browser navigation.
    Returns the resolved destination URL.
    """
    if not url or not isinstance(url, str):
        return url

    clean_url = url.strip()
    logger.info(f"[UrlResolver] Resolving URL: {clean_url}")

    # If it's already a full, expanded product URL, return cleaned version
    if not is_short_or_share_url(clean_url) and ("/p/" in clean_url or "/dp/" in clean_url):
        return clean_url

    # ── Level 1: HTTP Redirect Resolution (for Amazon, etc.) ──────────────────
    if not ("dl.flipkart.com" in clean_url or "fkrt.it" in clean_url):
        try:
            session = requests.Session()
            resp = session.get(clean_url, headers=DEFAULT_RESOLVE_HEADERS, allow_redirects=True, timeout=8)
            final_url = resp.url
            if final_url and final_url != clean_url and resp.status_code == 200:
                if "dl.flipkart.com/s/" not in final_url:
                    logger.info(f"[UrlResolver] HTTP resolved: {clean_url} -> {final_url}")
                    return final_url
        except Exception as e:
            logger.debug(f"[UrlResolver] HTTP resolution skipped: {e}")

    # ── Level 2: Playwright Browser Resolution ───────────────────────────────
    # Flipkart short URLs (dl.flipkart.com/s/...) require browser context due to Akamai edge protection
    logger.info(f"[UrlResolver] Using Playwright browser to resolve redirect: {clean_url}")
    try:
        bm = BrowserManager.get_instance()
        page, context = bm.new_page(engine="chromium")
        try:
            page.goto(clean_url, wait_until="commit", timeout=20000)
            # Give short moment for JS-driven or meta-refresh redirects
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass
            resolved_url = page.url
            if resolved_url and resolved_url != clean_url:
                logger.info(f"[UrlResolver] Playwright resolved: {clean_url} -> {resolved_url}")
                return resolved_url
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
    except Exception as exc:
        logger.warning(f"[UrlResolver] Playwright resolution exception: {exc}")

    # Fallback to original URL if resolution could not be completed
    return clean_url
