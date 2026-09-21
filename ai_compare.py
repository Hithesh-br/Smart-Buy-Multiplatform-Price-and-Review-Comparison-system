import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
)


def _parse_price(price_str):
    if price_str is None or price_str == "N/A":
        return None
    if isinstance(price_str, (int, float)):
        return int(price_str)
    digits = "".join(c for c in str(price_str) if c.isdigit())
    return int(digits) if digits else None


def get_best_deals(platform_results):
    """Return the cheapest product per platform and the overall best deal."""
    best_per_platform = {}
    overall_best = None

    for platform, items in platform_results.items():
        for item in items:
            price_val = _parse_price(item.get("price"))
            if price_val is None:
                continue
            current = best_per_platform.get(platform)
            if current is None or price_val < current["price_val"]:
                best_per_platform[platform] = {**item, "price_val": price_val}

            if overall_best is None or price_val < overall_best["price_val"]:
                overall_best = {**item, "price_val": price_val}

    return best_per_platform, overall_best


def get_ai_comparison(query, platform_results):
    """Use Google Gemini REST API to summarize the side-by-side comparison."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    lines = [f'User searched for: "{query}"\n']
    for platform, items in platform_results.items():
        lines.append(f"\n{platform}:")
        if not items:
            lines.append("  No results found.")
            continue
        for i, item in enumerate(items[:3], 1):
            lines.append(
                f"  {i}. {item['title']} | {item['price']} | "
                f"Rating: {item.get('rating', 'N/A')} | Reviews: {item.get('reviews', '0')}"
            )

    prompt = (
        "You are a shopping assistant for SmartBuy. Based on these product search results "
        "from Amazon, Flipkart, and Meesho, write a brief 2-3 sentence comparison. "
        "Mention which platform has the best price, best rating, and any buying recommendation. "
        "Be concise and helpful.\n\n"
        + "\n".join(lines)
    )

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        # Fallback local comparison summary generator
        best_deals, overall = get_best_deals(platform_results)
        if overall and overall.get('platform'):
            cheapest_platform = overall['platform']
            price = overall.get('price', 'N/A')
            title = overall.get('title', query)
            return (f"Based on real-time comparison across Amazon, Flipkart, and Meesho for '{query}', "
                    f"{cheapest_platform} offers the lowest price ({price}) for '{title[:45]}...'. "
                    f"Check individual cards below for ratings and stock availability.")
        return f"Compare live deals for '{query}' across Amazon, Flipkart, and Meesho below."


def calculate_best_deal(platform_results, query=""):
    """
    Calculate the authentic best deal across platforms, excluding accessories
    when the query is for a primary product (like a phone or laptop).
    """
    query_low = (query or "").lower()
    accessory_terms = ["cover", "case", "protector", "tempered", "pouch", "skin", "stand"]
    is_device = any(d in query_low for d in ["phone", "5g", "laptop", "mobile", "vivo", "iphone", "samsung", "realme"])

    best_plat = None
    best_price = None
    best_item = None

    for platform, items in platform_results.items():
        for item in items:
            title = (item.get("title") or item.get("name") or "").lower()
            if is_device and any(term in title for term in accessory_terms):
                continue
            
            p_val = item.get("price_num")
            if p_val is None:
                p_val = _parse_price(item.get("price"))
            
            if p_val is not None and p_val > 0:
                if best_price is None or p_val < best_price:
                    best_price = p_val
                    best_plat = platform
                    best_item = item

    return {
        "best_platform": best_plat or "Not Available",
        "best_price": best_price,
        "product": best_item
    }

