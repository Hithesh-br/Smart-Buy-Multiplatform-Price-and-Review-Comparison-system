import time
from playwright.sync_api import sync_playwright
import bs4

def test_fast_browser(platform_name, url, card_selector):
    print(f"\n--- Testing Playwright for {platform_name} ---")
    p = sync_playwright().start()
    t0 = time.time()
    browser = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        viewport={'width': 1366, 'height': 768},
        locale="en-IN",
        timezone_id="Asia/Kolkata"
    )
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
    """)
    # Resource routing to speed up page loads and prevent timeouts
    page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=18000)
        dur = round(time.time() - t0, 2)
        print(f"Page loaded in {dur}s | Title: {page.title()[:60]}")
        soup = bs4.BeautifulSoup(page.content(), "html.parser")
        cards = soup.select(card_selector)
        print(f"Cards extracted with '{card_selector}': {len(cards)}")
    except Exception as e:
        print(f"Error on {platform_name}: {e}")
    finally:
        context.close()
        browser.close()
        p.stop()

if __name__ == "__main__":
    test_fast_browser("Amazon", "https://www.amazon.in/s?k=chia+seeds", 'div[data-component-type="s-search-result"]')
    test_fast_browser("Flipkart", "https://www.flipkart.com/search?q=chia+seeds", 'div[data-id], div.slAVV4, div.jIjQ8S, div._1AtVbE')
    test_fast_browser("Meesho", "https://www.meesho.com/search?q=chia+seeds", 'div[class*="ProductList__GridCol"], div[class*="ProductCard"], a[href*="/p/"]')
