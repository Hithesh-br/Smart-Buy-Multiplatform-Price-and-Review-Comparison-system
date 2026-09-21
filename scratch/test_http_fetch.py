import time
import requests
import bs4

print("--- Testing HTTP for Amazon ---")
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-IN,en;q=0.9',
})
try:
    r = s.get('https://www.amazon.in/s?k=chia+seeds', timeout=10)
    print("Amazon HTTP status:", r.status_code, "length:", len(r.text))
    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    cards = soup.select('div[data-component-type="s-search-result"]')
    print("Amazon HTTP cards:", len(cards))
except Exception as e:
    print("Amazon HTTP error:", e)

print("\n--- Testing HTTP for Flipkart ---")
try:
    r = s.get('https://www.flipkart.com/search?q=chia+seeds', timeout=10)
    print("Flipkart HTTP status:", r.status_code, "length:", len(r.text))
    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    cards = soup.select('div[data-id]')
    print("Flipkart HTTP cards:", len(cards))
except Exception as e:
    print("Flipkart HTTP error:", e)
