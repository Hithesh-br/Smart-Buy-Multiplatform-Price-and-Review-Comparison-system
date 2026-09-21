import time
from playwright.sync_api import sync_playwright
import bs4

t0 = time.time()
p = sync_playwright().start()
b = p.firefox.launch(headless=True)
ctx = b.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    viewport={"width": 1366, "height": 768},
    locale="en-IN",
    timezone_id="Asia/Kolkata"
)
page = ctx.new_page()
page.route("**/*", lambda r: r.abort() if r.request.resource_type in ["image", "media", "font"] else r.continue_())
page.goto("https://www.meesho.com/search?q=chia+seeds", wait_until="domcontentloaded", timeout=15000)
dur = round(time.time() - t0, 2)
print(f"Loaded Meesho in {dur}s | Title: {page.title()}")

# Wait a brief moment or scroll slightly for hydration
page.evaluate("window.scrollBy(0, 600);")
time.sleep(1)

soup = bs4.BeautifulSoup(page.content(), "html.parser")
anchors = soup.select('a[href*="/p/"]')
print(f"Found {len(anchors)} product anchors on Meesho!")
if anchors:
    a0 = anchors[0]
    print(f"Sample product link: {a0.get('href')}")
    print(f"Sample product text: {a0.get_text(' | ', strip=True)[:100]}")

ctx.close()
b.close()
p.stop()
