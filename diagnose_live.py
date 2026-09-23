"""Script to diagnose Amazon and Meesho live."""
import sys
sys.path.insert(0, '.')
import time
from amazon_scraper import get_amazon_products
from meesho_scraper import get_meesho_products

queries = ['milk', 'wireless mouse']

print("=== DIAGNOSING AMAZON ===")
for q in queries:
    print(f"\nSearching Amazon for: {q}")
    results = get_amazon_products(q)
    if isinstance(results, list):
        print(f"Results returned: {len(results)}")
        for i, r in enumerate(results[:5]):
            if isinstance(r, dict):
                title = str(r.get('title', ''))
                print(f"  [{i+1}] {title[:60]} | {r.get('price')}")

print("\n=== DIAGNOSING MEESHO ===")
for q in queries:
    print(f"\nSearching Meesho for: {q}")
    results = get_meesho_products(q)
    if isinstance(results, list):
        print(f"Results returned: {len(results)}")
        for i, r in enumerate(results[:5]):
            if isinstance(r, dict):
                title = str(r.get('title', ''))
                print(f"  [{i+1}] {title[:60]} | {r.get('price')}")
