import json
from amazon_scraper import get_amazon_products
from flipkart_scraper import get_flipkart_products

if __name__ == "__main__":
    query = "iphone 15"
    print(f"--- Testing scrapers with query: '{query}' ---")
    
    print("\n[ Amazon ]")
    amazon_data = get_amazon_products(query)
    print(json.dumps(amazon_data, indent=2))
    
    print("\n[ Flipkart ]")
    flipkart_data = get_flipkart_products(query)
    print(json.dumps(flipkart_data, indent=2))
