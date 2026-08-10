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
    print(f"Results returned: {len(results)}")
    for i, r in enumerate(results[:5]):
        print(f"  [{i+1}] {r['title'][:60]} | {r['price']}")

print("\n=== DIAGNOSING MEESHO ===")
for q in queries:
    print(f"\nSearching Meesho for: {q}")
    results = get_meesho_products(q)
    print(f"Results returned: {len(results)}")
    for i, r in enumerate(results[:5]):
        print(f"  [{i+1}] {r['title'][:60]} | {r['price']}")
