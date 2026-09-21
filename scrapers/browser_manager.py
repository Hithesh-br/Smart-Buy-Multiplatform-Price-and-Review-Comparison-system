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
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("smartbuy.browser_manager")

PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT", "30000"))
NAVIGATION_TIMEOUT = int(os.getenv("NAVIGATION_TIMEOUT", "30000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAYS = [2, 5, 10]

DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FIREFOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0"
)


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

    def new_page(self, engine: str = "chromium") -> tuple[Page, BrowserContext]:
        """
        Creates a new isolated browser context and page.
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

        # Mask automation properties
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
