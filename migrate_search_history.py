"""
migrate_search_history.py
==========================
One-time backfill migration script for MongoDB smartbuy_db.search_history records.
Recalculates best_platform and best_price for existing search history documents
that are missing best_platform or have best_platform set to "Not Available" / "SmartBuy".
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, '.')

from database import init_db, _sanitize_best_platform_and_price
import database

def run_migration():
    print("==================================================================")
    print("STARTING SEARCH HISTORY DATABASE BACKFILL MIGRATION")
    print("==================================================================")

    init_db()
    db = database.db
    if db is None:
        print("ERROR: Could not connect to MongoDB database.")
        return

    cursor = db.search_history.find({})
    total_docs = db.search_history.count_documents({})
    print(f"Found {total_docs} total search history records in database.\n")

    updated_count = 0

    for doc in cursor:
        doc_id = doc.get("_id")
        old_plat = doc.get("best_platform")
        old_price = doc.get("best_price")

        sanitized = _sanitize_best_platform_and_price(dict(doc))
        new_plat = sanitized.get("best_platform")
        new_price = sanitized.get("best_price")

        # Update document if best_platform or best_price changed
        if new_plat != old_plat or new_price != old_price:
            db.search_history.update_one(
                {"_id": doc_id},
                {"$set": {
                    "best_platform": new_plat,
                    "best_price": new_price
                }}
            )
            updated_count += 1
            print(f"Updated Search ID {doc_id}:")
            print(f"  Old: platform='{old_plat}', price={old_price}")
            print(f"  New: platform='{new_plat}', price={new_price}")

    print("\n==================================================================")
    print(f"MIGRATION COMPLETE: Updated {updated_count} / {total_docs} documents.")
    print("==================================================================")

if __name__ == "__main__":
    run_migration()
