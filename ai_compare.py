import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
)


def _parse_price(price_str):
    if not price_str or price_str == "N/A":
        return None
    digits = "".join(c for c in price_str if c.isdigit())
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
