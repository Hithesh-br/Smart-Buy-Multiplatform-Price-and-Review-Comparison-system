import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database

def main():
    database.init_db()
    db = database.db
    
    # 1. Update Nutritoz Meesho
    res1 = db.selected_products.update_many(
        {"product_name": {"$regex": "Nutritoz.*Raw Pumpkin", "$options": "i"}, "platform": "Meesho"},
        {"$set": {"price": "₹182", "price_num": 182}}
    )
    print("Nutritoz Meesho updated:", res1.modified_count)

    # 2. Update Nutritoz Flipkart
    res2 = db.selected_products.update_many(
        {"product_name": {"$regex": "Nutritoz.*Pumpkin", "$options": "i"}, "platform": "Flipkart"},
        {"$set": {"price": "₹198", "price_num": 198}}
    )
    print("Nutritoz Flipkart updated:", res2.modified_count)

    # 3. Update KDA Buds
    res3 = db.selected_products.update_many(
        {"product_name": {"$regex": "KDA Premium Buds", "$options": "i"}},
        {"$set": {"price": "₹999", "price_num": 999}}
    )
    print("KDA Buds updated:", res3.modified_count)

    # 4. Check for any remaining empty prices
    cursor = db.selected_products.find({"price": {"$in": ["", None, "N/A", "Best Deal Available"]}})
    for doc in cursor:
        fmt = database._format_selected_product(doc)
        db.selected_products.update_one(
            {"_id": doc["_id"]},
            {"$set": {"price": fmt.get("price", "₹999"), "price_num": fmt.get("price_num", 999)}}
        )
        print("Updated fallback for:", doc["_id"])

    # 5. Link pupkin seeds search_history to Meesho selection
    ps_search = db.search_history.find_one({"product_name": "pupkin seeds"})
    if ps_search:
        db.search_history.update_one(
            {"_id": ps_search["_id"]},
            {"$set": {
                "selected_platform": "Meesho",
                "selected_price": 182,
                "selected_price_formatted": "₹182",
                "selected_product_title": "Nutritoz Premium Raw Pumpkin Seeds 200g High Protein Zinc Rich Healthy Snack Best Superfood",
                "selected_product_url": "https://www.meesho.com/nutritoz-premium-raw-pumpkin-seeds-200g-high-protein-zinc-rich-healthy-snack-best-superfood/p/bc4rhd"
            }}
        )
        print("pupkin seeds search history linked to selected platform Meesho Rs.182")

    # 6. Link nothing buds to KDA Flipkart selection
    nb_search = db.search_history.find_one({"product_name": "nothing  buds"})
    if nb_search:
        db.search_history.update_one(
            {"_id": nb_search["_id"]},
            {"$set": {
                "selected_platform": "Flipkart",
                "selected_price": 999,
                "selected_price_formatted": "₹999",
                "selected_product_title": "KDA Premium Buds 2a, 42 dB ANC, 12.4mm Driver Bluetooth Headset",
                "selected_product_url": "https://www.flipkart.com"
            }}
        )
        print("nothing buds search history linked to selected platform Flipkart Rs.999")

    # 7. Link safari trolly bags to SAFARI Small Cabin Suitcase Flipkart selection
    safari_search = db.search_history.find_one({"product_name": "safari trolly bags"})
    if safari_search:
        db.search_history.update_one(
            {"_id": safari_search["_id"]},
            {"$set": {
                "selected_platform": "Flipkart",
                "selected_price": 999,
                "selected_price_formatted": "₹999",
                "selected_product_title": "SAFARI Small Cabin Suitcase (55 cm) 8 Wheels Trolley Bag",
                "selected_product_url": "https://www.flipkart.com"
            }}
        )
        print("safari trolly bags search history linked to selected platform Flipkart Rs.999")

if __name__ == "__main__":
    main()
