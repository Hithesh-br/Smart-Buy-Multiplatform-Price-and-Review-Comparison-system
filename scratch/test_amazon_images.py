import sys
sys.path.insert(0, '.')
import time
from playwright.sync_api import sync_playwright
import bs4

p = sync_playwright().start()
b = p.chromium.launch(
    headless=True,
    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
)
ctx = b.new_context(
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport={'width': 1366, 'height': 768},
    locale="en-IN"
)
page = ctx.new_page()
page.route("**/*", lambda r: r.abort() if r.request.resource_type in ["image", "media", "font"] else r.continue_())
page.goto("https://www.amazon.in/s?k=chia+seeds", wait_until="domcontentloaded", timeout=18000)

soup = bs4.BeautifulSoup(page.content(), "html.parser")
cards = soup.select('div[data-component-type="s-search-result"]')
print(f"Total cards: {len(cards)}")

from scrapers.amazon.parser import parse_amazon_card
valid_parsed = 0
for i, c in enumerate(cards[:5]):
    item = parse_amazon_card(c)
    if item:
        valid_parsed += 1
        print(f"Card {i+1}:")
        print(f"  Title: {item['title'][:50]}")
        print(f"  Price: {item.get('price_num')}")
        print(f"  Image: {item.get('image')}")
        print(f"  URL: {item.get('url', '')[:60]}")

print(f"Valid parsed: {valid_parsed}")

ctx.close()
b.close()
p.stop()
