from playwright.sync_api import sync_playwright
import time

def test_meesho_stealth():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
            )
            page = context.new_page()
            # Try to mask webdriver
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page.goto('https://www.meesho.com/search?q=milk', wait_until='domcontentloaded')
            page.wait_for_timeout(2000)
            html = page.content()
            print(f'Chromium (masked) fetched: {len(html)} bytes')
            if 'Access Denied' in html or 'Permission to access' in html:
                print('Chromium BLOCKED')
            else:
                print('Chromium SUCCESS')
            browser.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    test_meesho_stealth()
