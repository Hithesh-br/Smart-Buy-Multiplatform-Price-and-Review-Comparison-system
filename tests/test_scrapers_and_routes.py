"""Unit and integration tests for Scrapers, Cache, and Flask Search Routes.
"""
import os
import pytest
from scrapers.scraper_result import ScrapeStatus, ScraperResult, create_normalized_product
from cache import (
    get_platform_cached_results,
    set_platform_cached_results,
    clear_cache,
    build_platform_cache_key
)
from app import app


def test_scraper_result_structure():
    """Verify ScraperResult default values and product schema."""
    res = ScraperResult(platform="meesho", status=ScrapeStatus.SUCCESS, products=[])
    assert res.platform == "meesho"
    assert res.status == ScrapeStatus.SUCCESS
    assert res.products == []
    assert res.error_message is None

    prod = create_normalized_product(
        platform="meesho",
        title="Ghar Soaps Magic Soap 100g",
        price=199.0,
        mrp=250.0,
        rating=4.3,
        review_count=120,
        url="https://meesho.com/p/123",
        image="https://meesho.com/img.jpg",
        brand="Ghar Soaps",
        weight="100g",
        pack_quantity="1",
        availability="In Stock"
    )
    assert prod["platform"] == "meesho"
    assert prod["title"] == "Ghar Soaps Magic Soap 100g"
    assert prod["price_num"] == 199
    assert prod["weight"] == "100g"
    assert prod["brand"] == "Ghar Soaps"
    assert prod["review_count"] == 120


def test_cache_platform_isolation_and_fresh_bypass():
    """Verify that caching isolates platforms and obeys fresh parameter."""
    import os
    os.environ["SCRAPER_CACHE_ENABLED"] = "true"
    query = "test isolated query xyz"
    sample_prods = [{"title": "Test Prod", "price": 100, "price_num": 100}]

    clear_cache()

    set_platform_cached_results("amazon", query, sample_prods, "success")

    # Amazon cache hit
    cached_amazon = get_platform_cached_results("amazon", query)
    assert cached_amazon is not None
    assert len(cached_amazon["results"]) == 1

    # Fresh bypass test
    cached_bypassed = get_platform_cached_results("amazon", query, bypass_fresh=True)
    assert cached_bypassed is None

    # Flipkart cache miss
    cached_flipkart = get_platform_cached_results("flipkart", query)
    assert cached_flipkart is None

    # Meesho cache miss
    cached_meesho = get_platform_cached_results("meesho", query)
    assert cached_meesho is None

    # Test cache cleanup
    clear_cache()
    assert get_platform_cached_results("amazon", query) is None


def test_api_search_route():
    """Verify /api/search endpoint response schema and status handling."""
    client = app.test_client()

    # Search with empty query
    res = client.get("/api/search?q=")
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data

    # Perform a fast cached test search structure validation
    test_q = "brandx soap"
    mock_amazon = [
        create_normalized_product(
            platform="amazon",
            title="BrandX Soap 100g",
            price=150.0,
            mrp=200.0,
            rating=4.5,
            review_count=50,
            url="https://amazon.in/dp/mock1",
            image="https://amazon.in/mock1.jpg",
            brand="BrandX",
            weight="100g",
            pack_quantity="1",
            availability="In Stock"
        )
    ]
    mock_flipkart = [
        create_normalized_product(
            platform="flipkart",
            title="BrandX Soap 100g",
            price=140.0,
            mrp=190.0,
            rating=4.4,
            review_count=40,
            url="https://flipkart.com/p/mock2",
            image="https://flipkart.com/mock2.jpg",
            brand="BrandX",
            weight="100g",
            pack_quantity="1",
            availability="In Stock"
        )
    ]
    mock_meesho = [
        create_normalized_product(
            platform="meesho",
            title="BrandX Soap 100g Pack of 1",
            price=120.0,
            mrp=160.0,
            rating=4.2,
            review_count=30,
            url="https://meesho.com/p/mock3",
            image="https://meesho.com/mock3.jpg",
            brand="BrandX",
            weight="100g",
            pack_quantity="1",
            availability="In Stock"
        )
    ]
    os.environ["SCRAPER_CACHE_ENABLED"] = "true"
    set_platform_cached_results("amazon", test_q, mock_amazon, "success")
    set_platform_cached_results("flipkart", test_q, mock_flipkart, "success")
    set_platform_cached_results("meesho", test_q, mock_meesho, "success")

    res = client.get(f"/api/search?q={test_q}")
    assert res.status_code == 200
    data = res.get_json()

    assert data["status"] == "success"
    assert "amazon" in data
    assert "flipkart" in data
    assert "meesho" in data
    assert len(data["amazon"]["products"]) == 1
    assert len(data["flipkart"]["products"]) == 1
    assert len(data["meesho"]["products"]) == 1

    # Check best deal structure
    assert "best_deal" in data
    best_deal = data["best_deal"]
    assert best_deal is not None
    assert best_deal["platform"].lower() == "meesho"
    assert best_deal["price"] == 120
    assert "reasons" in best_deal
    assert len(best_deal["reasons"]) > 0

    # Check comparison and match_pairs
    assert "comparison" in data
    assert "specification_table" in data or "specifications_matrix" in data.get("comparison", {})
    assert "match_pairs" in data

    # Clear mock cache
    clear_cache()
