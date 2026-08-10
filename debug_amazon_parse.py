import bs4
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("test_amazon.html", encoding="utf-8") as f:
    soup = bs4.BeautifulSoup(f.read(), "html.parser")

containers = soup.find_all("div", {"data-component-type": "s-search-result"})
print("containers", len(containers))

for i, item in enumerate(containers[:5]):
    print("---", i, "---")
    title_elem = item.select_one(
        "h2.a-size-medium span, h2.a-size-base-plus span, h2.a-text-normal span, h2 span"
    )
    price_elem = item.select_one("span.a-price-whole")
    offscreen = item.select_one(".a-price span.a-offscreen, span.a-offscreen")
    rating_elem = item.select_one("span.a-icon-alt")
    print("title:", title_elem.text.strip()[:70] if title_elem else None)
    print("price_whole:", price_elem.text.strip() if price_elem else None)
    print("offscreen:", offscreen.get_text(strip=True) if offscreen else None)
    print("rating:", rating_elem.get_text(strip=True) if rating_elem else None)

    for a in item.select("a"):
        aria = a.get("aria-label", "")
        if aria and ("rating" in aria.lower() or "review" in aria.lower()):
            print("review aria:", aria)

    for span in item.select("span.a-size-base.s-underline-text, span.a-size-mini"):
        t = span.get_text(strip=True)
        if re.search(r"\d", t):
            print("review span:", t)
