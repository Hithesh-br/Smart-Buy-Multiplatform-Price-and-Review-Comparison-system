"""
scrapers/browser_manager.py
===========================
Reusable Playwright Browser Manager.
Maintains persistent browser instances rather than re-launching for every search query.
Provides isolated contexts/pages with realistic viewports, anti-detection flags,
and exponential backoff retry mechanics.
"""

import os
import time
import logging
import threading
from typing import Optional

from playwright_bootstrap import configure_playwright_environment

configure_playwright_environment()

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("smartbuy.browser_manager")

PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT", "18000"))
NAVIGATION_TIMEOUT = int(os.getenv("NAVIGATION_TIMEOUT", "18000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
RETRY_DELAYS = [1, 3]

DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FIREFOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) "
    "Gecko/20100101 Firefox/146.0"
)

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
BLOCKED_DOMAINS = [
    "demdex.net", "omtrdc.net", "analytics", "criteo", "doubleclick.net",
    "nr-data.net", "adsystem", "adnxs.com", "scorecardresearch", "facebook.net",
    "clarity.ms", "googlesyndication.com", "google-analytics.com", "amazon-adsystem.com",
    "bat.bing.com", "connect.facebook.net", "hotjar.com"
]


def _filter_route(route):
    """Abort binary media, web fonts, and heavy tracking pixels while preserving HTML & scripts."""
    try:
        req = route.request
        url = req.url.lower()
        if req.resource_type in BLOCKED_RESOURCE_TYPES:
            route.abort()
            return
        for domain in BLOCKED_DOMAINS:
            if domain in url:
                route.abort()
                return
        route.continue_()
    except Exception:
        try:
            route.abort()
        except Exception:
            pass


class BrowserManager:
    _instance: Optional['BrowserManager'] = None
    _lock = threading.Lock()
    _local = threading.local()

    def __init__(self):
        self.headless = os.getenv("SCRAPER_HEADLESS", "true").lower() in ("true", "1", "yes")

    @classmethod
    def get_instance(cls) -> 'BrowserManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = BrowserManager()
        return cls._instance

    def _get_thread_state(self):
        if not hasattr(self._local, "playwright") or self._local.playwright is None:
            self._local.playwright = sync_playwright().start()
            self._local.chromium_browser = None
            self._local.firefox_browser = None
        return self._local

    def get_chromium_browser(self) -> Browser:
        state = self._get_thread_state()
        if state.chromium_browser is None or not state.chromium_browser.is_connected():
            logger.info(f"[BrowserManager] Launching Thread Chromium (headless={self.headless})...")
            state.chromium_browser = state.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-position=0,0',
                    '--ignore-certifcate-errors',
                    '--ignore-certifcate-errors-spki-list',
                ]
            )
        return state.chromium_browser

    def get_firefox_browser(self) -> Browser:
        state = self._get_thread_state()
        if state.firefox_browser is None or not state.firefox_browser.is_connected():
            logger.info(f"[BrowserManager] Launching Thread Firefox (headless={self.headless})...")
            state.firefox_browser = state.playwright.firefox.launch(
                headless=self.headless,
            )
        return state.firefox_browser

    def new_page(self, engine: str = "chromium", filter_routes: bool = True) -> tuple[Page, BrowserContext]:
        """
        Creates a new isolated browser context and page with optional route aborting.
        Caller is responsible for calling context.close() when finished.
        """
        browser = self.get_firefox_browser() if engine == "firefox" else self.get_chromium_browser()
        ua = FIREFOX_USER_AGENT if engine == "firefox" else DEFAULT_USER_AGENT

        context = browser.new_context(
            user_agent=ua,
            viewport=DEFAULT_VIEWPORT,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            ignore_https_errors=True,
        )

        page = context.new_page()
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        page.set_default_timeout(PAGE_TIMEOUT)

        if filter_routes:
            try:
                page.route("**/*", _filter_route)
            except Exception as e:
                logger.debug(f"[BrowserManager] Could not set route filter: {e}")

        # Mask automation properties
        if engine == "firefox":
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
        else:
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

        return page, context

    def execute_with_retry(self, action_callable, engine: str = "chromium", retries: int = MAX_RETRIES):
        """
        Executes a web scraping action callable(page) with exponential retry delays.
        """
        last_exception = None
        for attempt in range(retries):
            page, context = None, None
            try:
                page, context = self.new_page(engine=engine)
                result = action_callable(page)
                return result
            except Exception as exc:
                last_exception = exc
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"[BrowserManager] Attempt {attempt + 1}/{retries} on {engine} failed: {exc}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            finally:
                if context:
                    try:
                        context.close()
                    except Exception:
                        pass

        raise last_exception or RuntimeError(f"Action failed after {retries} retries")

    def close_all(self):
        state = getattr(self._local, "playwright", None)
        if state:
            try:
                if getattr(self._local, "chromium_browser", None):
                    self._local.chromium_browser.close()
                if getattr(self._local, "firefox_browser", None):
                    self._local.firefox_browser.close()
                self._local.playwright.stop()
            except Exception:
                pass
            finally:
                self._local.playwright = None
                self._local.chromium_browser = None
                self._local.firefox_browser = None
        logger.info("[BrowserManager] Thread browsers closed.")
