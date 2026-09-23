import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database

def main():
    database.init_db()
    db = database.db
    # Update unpriced selected_products
    cursor = db.selected_products.find({})
    updated = 0
    for doc in cursor:
        p_val = str(doc.get("price") or "").strip()
        p_num = doc.get("price_num")
        p_name = str(doc.get("product_name") or "")
        
        needs_update = False
        updates = {}
        if not p_val or p_val.lower() in ("", "none", "n/a", "not available", "best deal available", "best deal", "0"):
            needs_update = True
            fmt = database._format_selected_product(doc)
            updates["price"] = fmt.get("price", "₹999")
            updates["price_num"] = fmt.get("price_num", 999)
            
        if needs_update:
            db.selected_products.update_one({"_id": doc["_id"]}, {"$set": updates})
            updated += 1
            print(f"Updated {doc['_id']} -> {ascii(updates)}")
            
    print(f"Total updated: {updated}")

if __name__ == "__main__":
    main()
