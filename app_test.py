"""Test normalizer fix and HTML-based scraper parsing."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

# ─── 1. Normalizer Fix Test ──────────────────────────────────────────────────
print("=" * 60)
print("1. NORMALIZER FIX TEST")
print("=" * 60)
from search.normalizer import detect_query_type
from search.matching import get_adaptive_threshold, calculate_similarity

test_queries = [
    # Should be generic or category (NOT brand_model)
    ('milk',                'generic'),
    ('rice 5kg',            'generic'),
    ('milk 500ml',          'generic'),
    ('soap 100g',           'generic'),
    ('protein powder 1kg',  'category'),
    ('running shoes',       'generic'),
    ('baby diapers',        'generic'),
    # Should be brand_model
    ('Samsung Galaxy S24',  'brand_model'),
    ('iPhone 15 Pro',       'brand_model'),
    ('OnePlus 12R',         'brand_model'),
    ('Realme 12 Pro',       'brand_model'),
    # Should be specific or category
    ('wireless headphones noise cancelling', 'specific'),
    ('gaming laptop under 50000',           'category'),
]

all_pass = True
for query, expected in test_queries:
    got = detect_query_type(query)
    thresh = get_adaptive_threshold(query)
    ok = 'PASS' if got == expected else f'FAIL (got {got})'
    if got != expected:
        all_pass = False
    print(f"  [{ok}] {query!r:40s} -> {got} (threshold={thresh})")

# ─── 2. Similarity Scoring for Grocery Queries ──────────────────────────────
print()
print("=" * 60)
print("2. SIMILARITY SCORES — GROCERY QUERIES")
print("=" * 60)
grocery_tests = [
    ('milk', 'Amul Toned Milk 500ml Pack of 6', 45),
    ('rice 5kg', 'Fortune Basmati Rice 5 kg', 45),
    ('soap', 'Dove Beauty Soap 100g Pack of 3', 45),
    ('shampoo', 'Head & Shoulders Anti-Dandruff Shampoo 340ml', 45),
    ('protein powder 1kg', 'MuscleBlaze Whey Protein 1kg Chocolate', 45),
    ('Samsung Galaxy S24', 'Samsung Galaxy S24 5G 8GB 256GB', 72),
    ('OnePlus 12R', 'OnePlus 12R 5G 8GB 128GB', 72),
]
for q, t, thresh in grocery_tests:
    score = calculate_similarity(q, t)
    ok = 'PASS' if score >= thresh else 'FAIL'
    print(f"  [{ok}] {q!r:30s} | {t[:40]:42s} | score={score:.1f} >= {thresh}")

# ─── 3. Test Flipkart HTML parsing with new scraper logic ────────────────────
print()
print("=" * 60)
print("3. FLIPKART HTML PARSING TEST")
print("=" * 60)

import bs4, re

def _parse_price(text):
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None

def _find_price_in_container(container):
    price_str, price_num, orig_str, orig_num = "N/A", None, "N/A", None
    for cls in ['hZ3P6w', 'Nx9bqj', '_30jeq3']:
        elems = container.select('.' + cls)
        for e in elems:
            txt = e.get_text(strip=True)
            n = _parse_price(txt)
            if n and n > 10:
                price_str = f"INR{n:,}"
                price_num = n
                break
        if price_num: break
    if not price_num:
        for elem in container.find_all(['div','span']):
            txt = elem.get_text(strip=True)
            if re.match(r'^[0-9,]{3,8}$', txt) or re.match(r'^[\u20b9][0-9,]+$', txt):
                n = _parse_price(txt)
                if n and n > 10:
                    price_str = f"INR{n:,}"
                    price_num = n
                    break
    return price_str, price_num, orig_str, orig_num

with open('fk.html', 'r', encoding='utf-8', errors='ignore') as f:
    fk_html = f.read()
soup = bs4.BeautifulSoup(fk_html, 'html.parser')

cards = soup.select('div.jIjQ8S')
print(f"jIjQ8S cards: {len(cards)}")
products_parsed = 0
for card in cards[:5]:
    title = ''
    for a in card.find_all('a', href=True):
        if '/p/' in a.get('href',''):
            img = a.find('img')
            if img:
                alt = img.get('alt','').strip()
                if alt and len(alt) > 8:
                    title = alt[:70]
                    break
    price_str, price_num, _, _ = _find_price_in_container(card)
    if title and price_num:
        products_parsed += 1
        print(f"  OK: {title[:60]} | {price_str}")
    else:
        print(f"  MISS: title='{title[:40]}' price_num={price_num}")

# ─── 4. Test Meesho HTML parsing ─────────────────────────────────────────────
print()
print("=" * 60)
print("4. MEESHO HTML PARSING TEST")
print("=" * 60)

with open('meesho.html', 'r', encoding='utf-8', errors='ignore') as f:
    m_html = f.read()
soup2 = bs4.BeautifulSoup(m_html, 'html.parser')

cards2 = soup2.select('div[class*="NewProductCardstyled__CardStyled"]')
print(f"NewProductCardstyled__CardStyled cards: {len(cards2)}")
for card in cards2[:5]:
    # Title from span[class*=Caption3]
    title = ''
    for span in card.find_all('span'):
        cls = ' '.join(span.get('class',[]))
        if 'Caption3' in cls:
            t = span.get_text(strip=True)
            if t and len(t) > 5:
                title = t[:60]
                break
    # Price from h5
    h5s = card.find_all('h5')
    price_num = None
    for h5 in h5s:
        n = _parse_price(h5.get_text(strip=True))
        if n and n > 0:
            price_num = n
            break
    if title and price_num:
        print(f"  OK: {title[:55]} | INR{price_num:,}")
    else:
        card_txt = card.get_text(separator=' ',strip=True)[:80]
        print(f"  MISS: title='{title[:30]}' price={price_num} | {card_txt[:60]}")

print()
if all_pass:
    print("=== ALL NORMALIZER TESTS PASSED ===")
else:
    print("=== SOME NORMALIZER TESTS FAILED — check above ===")
