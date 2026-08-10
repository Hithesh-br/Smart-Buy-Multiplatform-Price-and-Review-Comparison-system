import sys
import io
import bs4
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('live_amazon.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

soup = bs4.BeautifulSoup(html, 'html.parser')

items = soup.select('div[data-component-type="s-search-result"]')
print(f"Found {len(items)} items")

for idx, item in enumerate(items[:8]):
    title = ""
    h2 = item.find('h2')
    if h2:
        title = h2.get_text(strip=True)
    
    price_whole = item.select_one('.a-price-whole')
    if price_whole:
        price = price_whole.get_text(strip=True)
        print(f"[{idx}] {title[:40]} | Price: {price}")
    else:
        print(f"[{idx}] {title[:40]} | Price: NOT FOUND (whole)")
        
        prices = item.find_all('span', class_=re.compile('price'))
        for p in prices:
            print(f"     span.{' '.join(p.get('class', []))}: {p.get_text(strip=True)}")
            
        print(f"    Raw Text Snippet: {item.get_text(separator=' ', strip=True)[:150]}")
