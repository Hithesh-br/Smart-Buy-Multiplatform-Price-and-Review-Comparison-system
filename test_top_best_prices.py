import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

from search.ranking import get_top_best_prices_data, extract_numeric_price

def test_extract_numeric_price():
    assert extract_numeric_price({"price_num": 62999}) == 62999.0
    assert extract_numeric_price({"price_num": None, "price": "₹62,999"}) == 62999.0
    assert extract_numeric_price({"price_num": None, "price": "N/A"}) is None
    assert extract_numeric_price({"price_num": 0}) is None
    assert extract_numeric_price({"price_num": -100}) is None
    assert extract_numeric_price(None) is None
    assert extract_numeric_price({}) is None
    print("[OK] extract_numeric_price tests passed.")

def test_get_top_best_prices_all_platforms():
    mock_platform_results = {
        "Amazon": [
            {"platform": "Amazon", "title": "Samsung Galaxy S24 256GB", "price": "₹62,999", "price_num": 62999, "rating": "4.5", "reviews": "1,200", "link": "https://amazon.in/samsung-s24", "image": "http://img.com/s24_amz.jpg"},
            {"platform": "Amazon", "title": "Samsung Galaxy S24 128GB", "price": "₹65,000", "price_num": 65000, "rating": "4.4", "reviews": "500", "link": "https://amazon.in/samsung-s24-2", "image": "http://img.com/s24_amz2.jpg"},
        ],
        "Flipkart": [
            {"platform": "Flipkart", "title": "Samsung Galaxy S24 256GB", "price": "₹61,499", "price_num": 61499, "rating": "4.4", "reviews": "900", "link": "https://flipkart.com/samsung-s24", "image": "http://img.com/s24_fk.jpg"},
        ],
        "Meesho": [
            {"platform": "Meesho", "title": "Samsung Galaxy S24 256GB", "price": "₹60,999", "price_num": 60999, "rating": "4.3", "reviews": "150", "link": "https://meesho.com/samsung-s24", "image": "http://img.com/s24_meesho.jpg"},
        ]
    }

    res = get_top_best_prices_data(mock_platform_results)
    top_prices = res["top_prices"]
    best_overall = res["best_overall"]
    savings_info = res["savings_info"]

    assert top_prices["Amazon"]["price_num"] == 62999
    assert top_prices["Flipkart"]["price_num"] == 61499
    assert top_prices["Meesho"]["price_num"] == 60999

    assert top_prices["Meesho"]["is_overall_best"] is True
    assert top_prices["Amazon"]["is_overall_best"] is False
    assert top_prices["Flipkart"]["is_overall_best"] is False

    assert best_overall["platform"] == "Meesho"
    assert best_overall["price_num"] == 60999

    # highest (62999) - lowest (60999) = 2000
    assert savings_info["amount"] == 2000
    assert savings_info["compared_platform"] == "Amazon"
    print("[OK] test_get_top_best_prices_all_platforms passed.")

def test_missing_platform():
    mock_platform_results = {
        "Amazon": [
            {"platform": "Amazon", "title": "Samsung Galaxy S24", "price": "₹62,999", "price_num": 62999, "link": "https://amazon.in/s24"},
        ],
        "Flipkart": [
            {"platform": "Flipkart", "title": "Samsung Galaxy S24", "price": "₹61,499", "price_num": 61499, "link": "https://flipkart.com/s24"},
        ],
        "Meesho": []  # Meesho has no results
    }

    res = get_top_best_prices_data(mock_platform_results)
    top_prices = res["top_prices"]
    savings_info = res["savings_info"]

    assert top_prices["Amazon"]["available"] is True
    assert top_prices["Flipkart"]["available"] is True
    assert top_prices["Meesho"]["available"] is False
    assert top_prices["Meesho"]["title"] == "No product available"

    assert top_prices["Flipkart"]["is_overall_best"] is True
    assert savings_info["amount"] == 1500  # 62999 - 61499
    print("[OK] test_missing_platform passed.")

def test_single_platform_available():
    mock_platform_results = {
        "Amazon": [
            {"platform": "Amazon", "title": "Samsung Galaxy S24", "price": "₹62,999", "price_num": 62999, "link": "https://amazon.in/s24"},
        ],
        "Flipkart": [],
        "Meesho": []
    }

    res = get_top_best_prices_data(mock_platform_results)
    top_prices = res["top_prices"]
    savings_info = res["savings_info"]

    assert top_prices["Amazon"]["available"] is True
    assert top_prices["Amazon"]["is_overall_best"] is True
    assert top_prices["Flipkart"]["available"] is False
    assert top_prices["Meesho"]["available"] is False

    # Savings info should be None when < 2 valid platform prices
    assert savings_info is None
    print("[OK] test_single_platform_available passed.")

def test_none_types_and_invalid_prices():
    mock_platform_results = {
        "Amazon": [
            {"platform": "Amazon", "title": "Invalid Item 1", "price": "N/A", "price_num": None},
            {"platform": "Amazon", "title": "Invalid Item 2", "price": None, "price_num": 0},
            {"platform": "Amazon", "title": "Valid Item", "price": "₹15,000", "price_num": 15000, "link": "http://amz.com"},
        ],
        "Flipkart": None,
        "Meesho": {}
    }

    res = get_top_best_prices_data(mock_platform_results)
    top_prices = res["top_prices"]
    assert top_prices["Amazon"]["available"] is True
    assert top_prices["Amazon"]["price_num"] == 15000
    assert top_prices["Flipkart"]["available"] is False
    assert top_prices["Meesho"]["available"] is False
    print("[OK] test_none_types_and_invalid_prices passed.")

if __name__ == "__main__":
    test_extract_numeric_price()
    test_get_top_best_prices_all_platforms()
    test_missing_platform()
    test_single_platform_available()
    test_none_types_and_invalid_prices()
    print("\nALL TOP BEST PRICE LOGIC TESTS PASSED SUCCESSFULLY!")
