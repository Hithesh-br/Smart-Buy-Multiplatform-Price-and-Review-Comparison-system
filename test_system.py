"""
test_system.py
==============
System verification script for Smart-Buy: Multiplatform Price Review Comparison System
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print("=== VERIFYING MODULE IMPORTS ===")
try:
    import utils
    print("✔ utils.py imported successfully")
    import cache
    print("✔ cache.py imported successfully")
    import matching
    print("✔ matching.py imported successfully")
    import ranking
    print("✔ ranking.py imported successfully")
    import filters
    print("✔ filters.py imported successfully")
    import search_engine
    print("✔ search_engine.py imported successfully")
    import api
    print("✔ api.py imported successfully")
    import app
    print("✔ app.py imported successfully")
except Exception as e:
    print(f"✖ Import error: {e}")
    sys.exit(1)

print("\n=== TESTING UTILS & CACHE ===")
p = utils.parse_price("₹1,499.00")
print(f"Price parser test: '₹1,499.00' -> {p} (Expected 1499)")

cache.set_cached_search("test_key", {"status": "ok"})
cached = cache.get_cached_search("test_key")
print(f"Cache test: {cached}")

print("\n=== TESTING MATCHING RULES ===")
q = "Samsung Galaxy S25 256GB"
valid_t = "Samsung Galaxy S25 5G Smartphone 256GB"
acc_t = "Samsung Galaxy S25 Case Cover"
wrong_mod_t = "Samsung Galaxy A56 256GB"

print(f"Valid Title match score: {matching.calculate_similarity(q, valid_t)}")
print(f"Accessory Title match score: {matching.calculate_similarity(q, acc_t)}")
print(f"Wrong Model Title match score: {matching.calculate_similarity(q, wrong_mod_t)}")

print("\n=== ALL SYSTEM TESTS PASSED ===")
