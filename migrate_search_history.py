"""
migrate_search_history.py
==========================
One-time backfill migration script for MongoDB smartbuy_db records:
1. Recalculates best_platform and best_price for search_history documents.
2. Normalizes platform, price, and ratings for selected_products documents.
"""

import os
import sys
import io
from dotenv import load_dotenv

load_dotenv()

# Safe UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

from database import init_db, _sanitize_best_platform_and_price, _format_selected_product
import database

def run_migration():
    print("==================================================================")
    print("STARTING SMARTBUY DATABASE BACKFILL MIGRATION")
    print("==================================================================")

    init_db()
    db = database.db
    if db is None:
        print("ERROR: Could not connect to MongoDB database.")
        return

    # 1. Search History Migration
    cursor = db.search_history.find({})
    total_searches = db.search_history.count_documents({})
    print(f"Found {total_searches} total search history records in database.\n")

    updated_search_count = 0
    for doc in cursor:
        doc_id = doc.get("_id")
        old_plat = doc.get("best_platform")
        old_price = doc.get("best_price")

        sanitized = _sanitize_best_platform_and_price(dict(doc))
        new_plat = sanitized.get("best_platform")
        new_price = sanitized.get("best_price")

        if new_plat != old_plat or new_price != old_price:
            db.search_history.update_one(
                {"_id": doc_id},
                {"$set": {
                    "best_platform": new_plat,
                    "best_price": new_price
                }}
            )
            updated_search_count += 1
            print(f"Updated Search ID {doc_id} ('{doc.get('search_query', '')}'):")
            print(f"  Platform: '{old_plat}' -> '{new_plat}'")
            print(f"  Price: {old_price} -> {new_price}")

    print(f"\nSearch History Backfill Complete: Updated {updated_search_count} / {total_searches} records.")

    # 2. Selected Products Migration
    prod_cursor = db.selected_products.find({})
    total_prods = db.selected_products.count_documents({})
    print(f"\nFound {total_prods} total selected products records in database.\n")

    updated_prod_count = 0
    for p in prod_cursor:
        p_id = p.get("_id")
        old_plat = p.get("platform")
        old_price = p.get("price")
        old_rating = p.get("rating")

        formatted = _format_selected_product(dict(p))
        new_plat = formatted.get("platform")
        new_price = formatted.get("price")
        new_rating = formatted.get("rating")

        updates = {}
        if new_plat != old_plat:
            updates["platform"] = new_plat
        if new_price != old_price and new_price:
            updates["price"] = new_price
        if formatted.get("price_num") and not p.get("price_num"):
            updates["price_num"] = formatted.get("price_num")
        if new_rating != old_rating:
            updates["rating"] = new_rating

        if updates:
            db.selected_products.update_one({"_id": p_id}, {"$set": updates})
            updated_prod_count += 1
            print(f"Updated Selected Product ID {p_id} ('{p.get('product_name', '')[:30]}'):")
            for k, v in updates.items():
                print(f"  {k}: {p.get(k)} -> {v}")

    print(f"\nSelected Products Backfill Complete: Updated {updated_prod_count} / {total_prods} records.")
    print("==================================================================")
    print("DATABASE MIGRATION COMPLETED SUCCESSFULLY")
    print("==================================================================")

if __name__ == "__main__":
    run_migration()
