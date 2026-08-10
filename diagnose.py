"""
Diagnostic script — tests each scraper in isolation and reports:
1. How many raw items each scraper returns
2. How many survive the similarity filter
3. Which items get filtered out and why
4. Price_num issues (main blocker in pipeline)
"""
import sys
sys.path.insert(0, '.')

from search.matching import calculate_similarity, get_adaptive_threshold, is_relevant
from search.normalizer import detect_query_type

def test_scraper(scraper_fn, platform_name, query):
    print(f"\n{'='*60}")
    print(f"Testing {platform_name} for query: '{query}'")
    print('='*60)
    try:
        results = scraper_fn(query)
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    print(f"  Raw items returned: {len(results)}")
    if not results:
        print("  WARNING: No items returned at all!")
        return

    threshold = get_adaptive_threshold(query)
    query_type = detect_query_type(query)
    print(f"  Query type: {query_type}, Threshold: {threshold}")

    passed = 0
    failed_no_price = 0
    failed_similarity = []

    for i, item in enumerate(results[:25]):
        title = item.get('title', '')
        price_num = item.get('price_num')
        score = calculate_similarity(query, title)

        if price_num is None:
            failed_no_price += 1
            if i < 5:
                print(f"  [{i+1}] NO PRICE | {title[:60]} | price='{item.get('price','')}'")
        elif score < threshold:
            failed_similarity.append((score, title[:60]))
            if i < 3:
                print(f"  [{i+1}] LOW SCORE {score:.1f}<{threshold} | {title[:60]}")
        else:
            passed += 1
            if i < 3:
                print(f"  [{i+1}] PASS {score:.1f} | {title[:60]} | ₹{price_num}")

    print(f"\n  SUMMARY: {passed} pass, {failed_no_price} no-price, {len(failed_similarity)} low-similarity")
    if failed_similarity:
        avg_score = sum(s for s,_ in failed_similarity) / len(failed_similarity)
        print(f"  Avg rejected score: {avg_score:.1f} (threshold={threshold})")
        print("  Rejected samples:")
        for s, t in failed_similarity[:3]:
            print(f"    score={s:.1f}: {t}")

# Run tests
queries = ['milk', 'laptop', 'Samsung Galaxy S24']

for q in queries:
    # Test each scraper individually to isolate failures
    print(f"\n\n{'#'*70}")
    print(f"# QUERY: {q}")
    print(f"{'#'*70}")
    
    try:
        from amazon_scraper import get_amazon_products
        test_scraper(get_amazon_products, 'Amazon', q)
    except Exception as e:
        print(f"Amazon import error: {e}")
    
    print("\n... (run full test by uncommenting other scrapers)")
    break  # Only run first query for speed in diagnosis
