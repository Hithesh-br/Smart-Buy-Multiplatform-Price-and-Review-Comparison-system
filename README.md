# Smart-Buy: Multiplatform Price Review Comparison System

**Smart-Buy: Multiplatform Price Review Comparison System** is a dynamic, full-stack product comparison engine that performs real-time price, rating, and review comparisons across **Amazon**, **Flipkart**, and **Meesho**.

---

## Key Features

- 🔍 **Dynamic Universal Search**: Search for *any* product (electronics, groceries, fashion, home appliances, beauty, books, furniture, etc.) without relying on hardcoded product catalogs.
- ⚡ **Parallel Multi-Platform Scraping**: Concurrently queries Amazon, Flipkart, and Meesho via `ThreadPoolExecutor` for maximum speed.
- 🛡️ **Scraper Fault Isolation**: Scraper errors or blocks are isolated per platform. If one scraper fails, the application continues seamlessly and displays a **"<Platform> temporarily unavailable"** notification for that platform while showing live results from all active platforms.
- 🎯 **Strict Similarity Matching (>= 90%)**: Powered by **RapidFuzz** (`token_set_ratio`, `token_sort_ratio`) with anti-pattern filters that reject accessories (cases, covers, screen guards), wrong model codes, and storage variant contradictions.
- 🚀 **1-Hour In-Memory Caching**: Built-in `cachetools.TTLCache` caches processed search results, reducing repeat query response times to **~0.03 seconds**.
- 🏆 **Smart Deal Highlights**: Automatically identifies and highlights **Lowest Price**, **Best Rated**, **Best Discount**, and **Best Value** deals.
- 🌙 **Dark Mode Toggle**: Built-in dark mode with automatic device preference detection and `localStorage` persistence.

---

## Modular Backend Architecture

The application is structured into single-responsibility Python modules:

```
smartbuy/
├── app.py              # Main Flask entry point & server setup
├── api.py              # Flask Blueprint API & route handlers
├── search_engine.py    # Parallel fetcher & core search pipeline coordinator
├── amazon_scraper.py   # Dynamic Amazon.in scraper
├── flipkart_scraper.py # Dynamic Flipkart.com scraper
├── meesho_scraper.py   # Dynamic Meesho.com scraper (Firefox stealth engine)
├── matching.py         # Top-level export for RapidFuzz 90% matching engine
├── ranking.py          # Top-level export for ranking & badge annotation
├── filters.py          # Top-level export for dynamic UI parameter filtering
├── utils.py            # Price parsing, text cleaning, error formatters
├── cache.py            # TTLCache in-memory cache layer
├── database.py         # SQLite search history & analytics tracker
├── ai_compare.py       # Side-by-side deal analysis & optional Gemini AI summary
├── autocomplete_engine.py # Trie-based live autocomplete engine
├── search/             # Underlying search package algorithms
│   ├── matching.py
│   ├── ranking.py
│   ├── filters.py
│   ├── normalizer.py
│   └── specs_extractor.py
├── templates/          # HTML5 templates (index, results, feedback)
└── static/             # CSS & JavaScript assets
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Playwright Chromium & Firefox browsers

### 1. Install Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium firefox
```

### 2. Configure Environment (Optional)
Create a `.env` file in the project root:
```env
PORT=5000
SECRET_KEY=smartbuy_super_secret_key
# Optional: GOOGLE_API_KEY=your_gemini_api_key
```

### 3. Start Application
```bash
python app.py
```
Open your browser and navigate to: `http://127.0.0.1:5000`

---

## API Endpoints

- **`GET /`**: Home page with category hints and trending searches.
- **`GET /search?q={query}`**: Side-by-side product comparison UI.
- **`GET /api/search?q={query}`**: JSON endpoint returning normalized multi-platform search data and platform status.
- **`GET /autocomplete?q={prefix}`**: Returns live autocomplete suggestions.
- **`GET /api/health`**: System status and total query count.
