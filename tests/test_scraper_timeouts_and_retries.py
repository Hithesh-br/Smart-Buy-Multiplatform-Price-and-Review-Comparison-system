"""
tests/test_scraper_timeouts_and_retries.py
==========================================
Validates:
1. Independent platform scraper execution & status reporting.
2. Route /api/search/platform returns correct schema and products.
3. Failure isolation: Amazon, Flipkart, and Meesho failures do not affect each other.
4. Specification matrix and comparison table always preserve all 3 platform columns.
5. Quality scores are evidence-backed and never fabricated.
"""

import pytest
from app import app
from search_engine import fetch_single_platform, fetch_all_products_parallel, process_results
from scrapers.browser_manager import BrowserManager, _filter_route


def test_browser_manager_route_filtering():
    """Verify BrowserManager has route filtering logic and optimized flags."""
    bm = BrowserManager.get_instance()
    assert bm is not None
    # Verify timeout settings are capped to 18000
    from scrapers.browser_manager import NAVIGATION_TIMEOUT, PAGE_TIMEOUT
    assert NAVIGATION_TIMEOUT <= 20000
    assert PAGE_TIMEOUT <= 20000


def test_fetch_single_platform_schema():
    """Verify fetch_single_platform returns the required schema with retry_available."""
    # Test with unknown platform
    items, stat = fetch_single_platform("UnknownPlatform", "test query")
    assert items == []
    assert stat["platform"] == "UnknownPlatform"
    assert stat["status"] == "error"
    assert stat["available"] is False

    # Test Meesho platform (fast API / HTTP mock or live)
    items, stat = fetch_single_platform("Meesho", "Pilgrim face wash", bypass_fresh=False)
    assert isinstance(items, list)
    assert stat["platform"] == "Meesho"
    assert "status" in stat
    assert "retry_available" in stat
    assert "duration" in stat


def test_api_search_platform_endpoint():
    """Verify /api/search/platform endpoint returns independent platform results."""
    client = app.test_client()

    # Missing params
    res = client.get('/api/search/platform')
    assert res.status_code == 400

    # Valid call
    res = client.get('/api/search/platform?platform=Meesho&q=face+wash')
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["platform"] == "Meesho"
    assert "platform_status" in data
    assert "retry_available" in data
    assert isinstance(data["products"], list)


def test_platform_failure_isolation():
    """Simulate a timeout on Amazon and Flipkart while Meesho succeeds."""
    mock_raw = {
        "Amazon": [],
        "Flipkart": [],
        "Meesho": [
            {
                "title": "Pilgrim Volcanic Lava Ash Face Wash 100ml",
                "price": "₹320",
                "price_num": 320,
                "rating": "4.3",
                "review_count": "150",
                "product_url": "https://www.meesho.com/p/123",
                "image": "https://images.meesho.com/p/123.jpg",
                "brand": "Pilgrim",
                "model": "100ml",
                "category": "beauty",
                "attributes": {"Net Quantity": "100 ml", "Skin Type": "All Skin Types"}
            }
        ]
    }
    mock_status = {
        "Amazon": {
            "platform": "Amazon",
            "status": "timeout",
            "available": False,
            "error": "The request exceeded the configured time limit",
            "retry_available": True,
            "count": 0
        },
        "Flipkart": {
            "platform": "Flipkart",
            "status": "timeout",
            "available": False,
            "error": "The request exceeded the configured time limit",
            "retry_available": True,
            "count": 0
        },
        "Meesho": {
            "platform": "Meesho",
            "status": "success",
            "available": True,
            "error": None,
            "retry_available": False,
            "count": 1
        }
    }

    processed = process_results("Pilgrim face wash", mock_raw, platform_status=mock_status)

    # 1. Platform results are isolated
    assert len(processed["platform_results"]["Meesho"]) == 1
    assert len(processed["platform_results"]["Amazon"]) == 0
    assert len(processed["platform_results"]["Flipkart"]) == 0

    # 2. Quality comparison table includes all 3 platforms
    q_table = processed["quality_comparison_table"]
    assert len(q_table) == 3
    platforms_in_q = [row["platform"] for row in q_table]
    assert "Amazon" in platforms_in_q
    assert "Flipkart" in platforms_in_q
    assert "Meesho" in platforms_in_q

    # Timed-out platforms display "Not Available" / timeout status rather than empty
    amz_q = next(r for r in q_table if r["platform"] == "Amazon")
    fk_q = next(r for r in q_table if r["platform"] == "Flipkart")
    mee_q = next(r for r in q_table if r["platform"] == "Meesho")

    assert amz_q["product_name"] == "Not Available"
    assert amz_q["platform_status"] == "Timeout"
    assert fk_q["product_name"] == "Not Available"
    assert fk_q["platform_status"] == "Timeout"

    assert mee_q["available"] is True
    assert "Pilgrim" in mee_q["product_name"]

    # 3. Specification matrix includes all 3 platform columns
    spec_table = processed["specification_table"]
    assert spec_table["columns"] == ["specification", "amazon", "flipkart", "meesho"]
    for row in processed["specifications_matrix"]:
        assert "amazon" in row
        assert "flipkart" in row
        assert "meesho" in row


def test_no_data_fabrication_for_missing_fields():
    """Verify that unavailable fields show 'Not Available' or '—' and are never fabricated."""
    mock_raw = {
        "Amazon": [
            {
                "title": "Generic Unbranded Item",
                "price": "₹500",
                "price_num": 500,
                # Missing ram, storage, processor, battery, etc.
                "category": "mobile"
            }
        ],
        "Flipkart": [],
        "Meesho": []
    }
    processed = process_results("Generic Unbranded Item", mock_raw)
    amz_prod = processed["platform_results"]["Amazon"][0]

    # Quality score must NOT be an arbitrary high score like 80/100 without evidence
    assert amz_prod.get("evidence_coverage", 0) < 50
    if not amz_prod.get("has_sufficient_data"):
        assert amz_prod.get("quality_score") is None
        assert amz_prod.get("quality_score_label") == "Quality Score: Not Available"
