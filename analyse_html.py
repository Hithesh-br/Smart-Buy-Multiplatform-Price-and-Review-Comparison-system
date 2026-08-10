"""Targeted CSS class analysis for Flipkart and Meesho HTML files."""
import sys, io, bs4, re
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ─── FLIPKART ────────────────────────────────────────────────────────────────
print("=" * 60)
print("FLIPKART")
print("=" * 60)

with open('fk.html', 'r', encoding='utf-8', errors='ignore') as f:
    fk_html = f.read()
soup = bs4.BeautifulSoup(fk_html, 'html.parser')

product_links = [l for l in soup.find_all('a', href=True) if '/p/' in l.get('href','')]
print(f"/p/ links: {len(product_links)}")

# Check key classes from frequency list
for cls in ['hZ3P6w', 'T6hTMI', 'R7Cntx', 'b0bTm6', 'nZIRY7', 'jIjQ8S', 'RG5Slk', 
            'ZFwe0M', 'SJekt1', 'FJ7IAS', 'MaiFhH', 'QiMO5r', 'lWX0_T', 'UHMz4K', 
            'AF1m2F', 'HZ0E6r', 'Rm9_cy']:
    elems = soup.select('.' + cls)
    if elems:
        t = elems[0].get_text(separator=' ', strip=True)[:70].replace('\n', ' ')
        has_price = bool(re.search(r'[0-9]{3,}', t))
        print(f"  .{cls}: {len(elems)} | price={has_price} | {t}")

# Walk up from first product link to find price 
print("\n--- Parent tree of first product link:")
l = product_links[0]
node = l.parent
for depth in range(10):
    if not node or node.name in ('body', 'html'): break
    cls = ' '.join(node.get('class', []))
    txt = node.get_text(separator=' ', strip=True)[:100].replace('\n', ' ')
    has_price = bool(re.search(r'[0-9]{3,}', txt))
    print(f"  d={depth} cls={cls[:45]} price={has_price}")
    node = node.parent

# Find actual price elements
print("\n--- Elements containing Rs signs:")
price_elems = []
for tag in soup.find_all(True):
    txt = tag.get_text(strip=True)
    if re.match(r'^[0-9,]{3,8}$', txt) or re.match(r'^[\u20b9][0-9,]+$', txt):
        cls = ' '.join(tag.get('class', []))
        if cls and tag.name in ('div', 'span', 'p'):
            price_elems.append((tag.name, cls, txt))
for name, cls, txt in price_elems[:10]:
    print(f"  <{name}> .{cls[:40]} = '{txt}'")

# ─── MEESHO ────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 60)
print("MEESHO")
print("=" * 60)

with open('meesho.html', 'r', encoding='utf-8', errors='ignore') as f:
    meesho_html = f.read()
soup2 = bs4.BeautifulSoup(meesho_html, 'html.parser')

for sel in ['div[class*="NewProductCard"]', 'div[class*="ProductCard"]', 
            'div[class*="CardStyled"]', 'a[href*="/p/"]', 'h5']:
    found = soup2.select(sel)
    print(f"  '{sel}': {len(found)}")

div_cls2 = Counter()
for d in soup2.find_all(['div','h5','span','p']):
    for c in d.get('class', []):
        if len(c) > 4:
            div_cls2[c] += 1

print("\n--- Meesho top element classes:")
for cls, cnt in div_cls2.most_common(25):
    print(f"  .{cls}: {cnt}")

# Find price elements in Meesho
print("\n--- Meesho price-containing elements:")
for tag in soup2.find_all(['h5', 'span', 'p', 'div']):
    txt = tag.get_text(strip=True)
    if re.match(r'^[0-9,]{2,6}$', txt) or re.search(r'[\u20b9][0-9,]+', txt):
        cls = ' '.join(tag.get('class', []))
        if cls:
            print(f"  <{tag.name}> .{cls[:50]} = '{txt[:30]}'")
            if len([x for x in [y for y in [0]] if True]) > 8:
                break

# Find product titles in Meesho
print("\n--- Meesho p elements (first 5):")
for p in soup2.find_all('p')[:8]:
    cls = ' '.join(p.get('class', []))
    txt = p.get_text(strip=True)[:60]
    if cls and len(txt) > 5:
        print(f"  .{cls[:40]} = '{txt}'")
