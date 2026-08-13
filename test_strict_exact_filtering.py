import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath('.'))

from search.identity_matcher import is_exact_product, group_exact_and_similar_products
from search_engine import process_results

def test_vivo_t4_5g():
    query = "Vivo T4 5G"
    
    # Scraped candidates
    item_amazon_exact = {"title": "Vivo T4 5G (Starlight Blue, 128 GB)", "platform": "Amazon", "price": "₹19,999", "price_num": 19999, "rating": "4.5", "reviews": "1,200"}
    item_amazon_lite  = {"title": "Vivo T4 Lite 5G (Starlight Gold, 128 GB)", "platform": "Amazon", "price": "₹16,999", "price_num": 16999}
    item_amazon_case  = {"title": "Vivo T4 5G Back Cover & Camera Lens Protector Case", "platform": "Amazon", "price": "₹299", "price_num": 299}
    item_fk_exact     = {"title": "Vivo T4 5G (Metallic Grey, 128 GB)", "platform": "Flipkart", "price": "₹19,499", "price_num": 19499, "rating": "4.6", "reviews": "850"}
    item_fk_pro       = {"title": "Vivo T4 Pro 5G (Midnight Black, 256 GB)", "platform": "Flipkart", "price": "₹24,999", "price_num": 24999}
    item_meesho_case  = {"title": "Vivo T4 5G Cases & Covers Silicone Soft Back Cover", "platform": "Meesho", "price": "₹199", "price_num": 199}

    # 1. is_exact_product direct assertion
    assert is_exact_product(query, item_amazon_exact) is True, "Vivo T4 5G exact must be ACCEPTED"
    assert is_exact_product(query, item_amazon_lite) is False, "Vivo T4 Lite must be REJECTED"
    assert is_exact_product(query, item_amazon_case) is False, "Vivo T4 Case must be REJECTED"
    assert is_exact_product(query, item_fk_exact) is True, "Vivo T4 5G exact must be ACCEPTED"
    assert is_exact_product(query, item_fk_pro) is False, "Vivo T4 Pro must be REJECTED"
    assert is_exact_product(query, item_meesho_case) is False, "Vivo T4 Case on Meesho must be REJECTED"

    # 2. Pipeline processing assertion
    raw_results = {
        "Amazon": [item_amazon_exact, item_amazon_lite, item_amazon_case],
        "Flipkart": [item_fk_exact, item_fk_pro],
        "Meesho": [item_meesho_case]
    }

    processed = process_results(query, raw_results)
    
    # Counts must count ONLY exact match products
    assert len(processed["platform_results"]["Amazon"]) == 1, "Amazon count must be 1"
    assert len(processed["platform_results"]["Flipkart"]) == 1, "Flipkart count must be 1"
    assert len(processed["platform_results"]["Meesho"]) == 0, "Meesho count must be 0"

    # Specification Table exact matches check
    exact_matches = processed["exact_matching_data"]["exact_matches"]
    assert exact_matches["Amazon"]["title"] == item_amazon_exact["title"]
    assert exact_matches["Flipkart"]["title"] == item_fk_exact["title"]
    assert exact_matches["Meesho"] is None, "Meesho exact match must be NONE"

    print("[OK] test_vivo_t4_5g passed.")


def test_iphone_15_128gb():
    query = "iPhone 15 128GB"

    item_128gb = {"title": "Apple iPhone 15 (128 GB) - Black", "platform": "Amazon", "price": "₹65,999", "price_num": 65999}
    item_256gb = {"title": "Apple iPhone 15 (256 GB) - Blue", "platform": "Amazon", "price": "₹75,999", "price_num": 75999}
    item_pro   = {"title": "Apple iPhone 15 Pro (128 GB) - Natural Titanium", "platform": "Flipkart", "price": "₹1,24,900", "price_num": 124900}
    item_iph14 = {"title": "Apple iPhone 14 (128 GB) - Midnight", "platform": "Flipkart", "price": "₹55,999", "price_num": 55999}
    item_case  = {"title": "iPhone 15 Silicone Case with MagSafe - Black", "platform": "Meesho", "price": "₹499", "price_num": 499}

    assert is_exact_product(query, item_128gb) is True, "iPhone 15 128GB must be ACCEPTED"
    assert is_exact_product(query, item_256gb) is False, "iPhone 15 256GB storage mismatch must be REJECTED"
    assert is_exact_product(query, item_pro) is False, "iPhone 15 Pro variant mismatch must be REJECTED"
    assert is_exact_product(query, item_iph14) is False, "iPhone 14 model mismatch must be REJECTED"
    assert is_exact_product(query, item_case) is False, "iPhone 15 Case accessory must be REJECTED"

    print("[OK] test_iphone_15_128gb passed.")


def test_hp_victus_laptop():
    query = "HP Victus i5 13th Gen 16GB 512GB"

    item_exact   = {"title": "HP Victus Gaming Laptop 13th Gen Intel Core i5-13420H 16GB DDR5 512GB SSD RTX 3050", "platform": "Amazon", "price": "₹62,990", "price_num": 62990}
    item_pavilion= {"title": "HP Pavilion Gaming Laptop 13th Gen Intel Core i5 16GB 512GB", "platform": "Amazon", "price": "₹59,990", "price_num": 59990}
    item_i7      = {"title": "HP Victus Gaming Laptop 13th Gen Intel Core i7 16GB 512GB", "platform": "Flipkart", "price": "₹82,990", "price_num": 82990}
    item_8gb     = {"title": "HP Victus Gaming Laptop 13th Gen Intel Core i5 8GB 512GB", "platform": "Flipkart", "price": "₹55,990", "price_num": 55990}
    item_1tb     = {"title": "HP Victus Gaming Laptop 13th Gen Intel Core i5 16GB 1TB", "platform": "Meesho", "price": "₹68,990", "price_num": 68990}
    item_bag     = {"title": "HP Victus Waterproof Laptop Backpack Bag", "platform": "Meesho", "price": "₹1,299", "price_num": 1299}

    assert is_exact_product(query, item_exact) is True, "Exact HP Victus spec must be ACCEPTED"
    assert is_exact_product(query, item_pavilion) is False, "HP Pavilion series mismatch must be REJECTED"
    assert is_exact_product(query, item_i7) is False, "Core i7 CPU mismatch must be REJECTED"
    assert is_exact_product(query, item_8gb) is False, "8GB RAM mismatch must be REJECTED"
    assert is_exact_product(query, item_1tb) is False, "1TB storage mismatch must be REJECTED"
    assert is_exact_product(query, item_bag) is False, "Laptop Bag accessory must be REJECTED"

    print("[OK] test_hp_victus_laptop passed.")


def test_nike_running_shoes():
    query = "Men's Black Nike Running Shoes Size 9"

    item_exact = {"title": "Nike Men's Revolution 7 Running Shoes (Black, Size 9 UK)", "platform": "Amazon", "price": "₹3,695", "price_num": 3695}
    item_women = {"title": "Nike Women's Revolution 7 Running Shoes (Black, Size 9 UK)", "platform": "Amazon", "price": "₹3,695", "price_num": 3695}
    item_blue  = {"title": "Nike Men's Revolution 7 Running Shoes (Blue, Size 9 UK)", "platform": "Flipkart", "price": "₹3,495", "price_num": 3495}
    item_size10= {"title": "Nike Men's Revolution 7 Running Shoes (Black, Size 10 UK)", "platform": "Flipkart", "price": "₹3,695", "price_num": 3695}
    item_adidas= {"title": "Adidas Men's Galaxy 6 Running Shoes (Black, Size 9 UK)", "platform": "Meesho", "price": "₹2,999", "price_num": 2999}
    item_socks = {"title": "Nike Everyday Cushion Ankle Socks (Pack of 3)", "platform": "Meesho", "price": "₹499", "price_num": 499}

    assert is_exact_product(query, item_exact) is True, "Exact Nike Men Black Size 9 must be ACCEPTED"
    assert is_exact_product(query, item_women) is False, "Women gender mismatch must be REJECTED"
    assert is_exact_product(query, item_blue) is False, "Blue color mismatch must be REJECTED"
    assert is_exact_product(query, item_size10) is False, "Size 10 size mismatch must be REJECTED"
    assert is_exact_product(query, item_adidas) is False, "Adidas brand mismatch must be REJECTED"
    assert is_exact_product(query, item_socks) is False, "Socks product type mismatch must be REJECTED"

    print("[OK] test_nike_running_shoes passed.")


if __name__ == "__main__":
    test_vivo_t4_5g()
    test_iphone_15_128gb()
    test_hp_victus_laptop()
    test_nike_running_shoes()
    print("\n==================================================")
    print("ALL STRICT EXACT-PRODUCT FILTERING TESTS PASSED 100%!")
    print("==================================================")
