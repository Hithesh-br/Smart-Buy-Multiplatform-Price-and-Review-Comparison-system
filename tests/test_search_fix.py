"""
tests/test_search_fix.py
========================
Tests verifying complete fix for SmartBuy search:
1. Search input detection: product name vs Flipkart / Amazon / Meesho URLs (including dl.flipkart.com/s/...)
2. Flipkart short URL resolution
3. Search router execution: product URL vs product name
4. POST /api/search endpoint specification
5. GET /search?q=<URL> automatic routing to URL comparison
6. Zero regression for product name searches
"""

import pytest
from unittest.mock import patch, MagicMock

from app import app
from url_detector import detect_search_type, validate_and_detect_url
from search.url_resolver import is_short_or_share_url, resolve_product_url
from search.search_router import route_search


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.test_client() as client:
        yield client


# =============================================================================
# 1. Search Input Detection Tests
# =============================================================================

def test_detect_search_type_product_names():
    names = [
        "Samsung Galaxy S24",
        "nike shoes",
        "vivo charger",
        "boAt Rockerz 450",
        "cotton t-shirt for men"
    ]
    for q in names:
        res = detect_search_type(q)
        assert res["type"] == "product_name", f"Failed for query '{q}'"


def test_detect_search_type_flipkart_short_url():
    url = "https://dl.flipkart.com/s/0chNErNNNN"
    res = detect_search_type(url)
    assert res["type"] == "product_url"
    assert res["platform"] == "flipkart"
    assert "dl.flipkart.com" in res["url"]


def test_detect_search_type_flipkart_standard_url():
    url = "https://www.flipkart.com/metronaut-relaxed-men-beige-trousers/p/itmdcd6be9e2eab3?pid=TROHKG8CBE3JMM5Y"
    res = detect_search_type(url)
    assert res["type"] == "product_url"
    assert res["platform"] == "flipkart"


def test_detect_search_type_amazon_url():
    urls = [
        "https://www.amazon.in/dp/B0CHX1W1XY",
        "https://amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY",
        "https://www.amazon.co.in/gp/product/B0CHX1W1XY",
        "https://amzn.to/3xyz123"
    ]
    for u in urls:
        res = detect_search_type(u)
        assert res["type"] == "product_url", f"Failed for {u}"
        assert res["platform"] == "amazon", f"Failed for {u}"


def test_detect_search_type_meesho_url():
    urls = [
        "https://www.meesho.com/s/p/4abc12",
        "https://meesho.com/stylish-men-trousers/p/xyz789"
    ]
    for u in urls:
        res = detect_search_type(u)
        assert res["type"] == "product_url", f"Failed for {u}"
        assert res["platform"] == "meesho", f"Failed for {u}"


# =============================================================================
# 2. Short URL Detection and Resolver Tests
# =============================================================================

def test_is_short_or_share_url():
    assert is_short_or_share_url("https://dl.flipkart.com/s/0chNErNNNN") is True
    assert is_short_or_share_url("https://amzn.to/3xyz") is True
    assert is_short_or_share_url("https://amzn.in/d/9abc") is True
    assert is_short_or_share_url("https://www.flipkart.com/some-product/p/itm123") is False
    assert is_short_or_share_url("https://www.amazon.in/dp/B0CHX1W1XY") is False


def test_resolve_product_url_with_http_redirect():
    short_url = "https://amzn.to/3xyz123"
    resolved_target = "https://www.amazon.in/dp/B0CHX1W1XY"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = resolved_target

    with patch("requests.Session.get", return_value=mock_resp):
        out = resolve_product_url(short_url, platform="amazon")
        assert out == resolved_target


def test_resolve_flipkart_short_url():
    short_url = "https://dl.flipkart.com/s/0chNErNNNN"
    resolved_target = "https://www.flipkart.com/metronaut-relaxed-men-beige-trousers/p/itmdcd6be9e2eab3?pid=TROHKG8CBE3JMM5Y"

    mock_bm = MagicMock()
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    mock_page.url = resolved_target
    mock_bm.new_page.return_value = (mock_page, mock_ctx)

    with patch("search.url_resolver.BrowserManager.get_instance", return_value=mock_bm):
        out = resolve_product_url(short_url, platform="flipkart")
        assert out == resolved_target
        assert "dl.flipkart.com/s/" not in out


# =============================================================================
# 3. Search Router Tests
# =============================================================================

def test_route_search_url():
    target_url = "https://dl.flipkart.com/s/0chNErNNNN"
    mock_comp = {
        "success": True,
        "source_platform": "flipkart",
        "source_platform_name": "Flipkart",
        "source_url": target_url,
        "source_product": {"title": "Metronaut Relaxed Men Beige Trousers", "price_num": 499},
        "matches": {
            "flipkart": {"title": "Metronaut Relaxed Men Beige Trousers", "price_num": 499},
            "amazon": {"title": "Metronaut Relaxed Fit Trousers", "price_num": 529},
            "meesho": None
        },
        "specifications_matrix": [
            {"specification": "Price", "flipkart": "₹499", "amazon": "₹529", "meesho": "Not Available"}
        ],
        "best_deal": {"platform": "Flipkart", "price": 499, "formatted_price": "499"},
        "platform_status": {
            "Flipkart": {"status": "success", "available": True},
            "Amazon": {"status": "success", "available": True},
            "Meesho": {"status": "success", "available": True}
        }
    }

    with patch("search.search_router.compare_by_product_url", return_value=mock_comp) as mock_cmp:
        result = route_search(target_url)
        assert result["search_type"] == "product_url"
        assert result["source_platform"] == "flipkart"
        assert result["best_deal"]["platform"] == "Flipkart"
        assert len(result["comparison"]["specifications"]) > 0
        mock_cmp.assert_called_once_with(target_url, fresh=False)


def test_route_search_product_name():
    query = "Samsung Galaxy S24"
    mock_raw = {
        "Amazon": [{"title": "Samsung Galaxy S24 5G", "price_num": 74999}],
        "Flipkart": [{"title": "Samsung Galaxy S24 5G (Onyx Black)", "price_num": 74999}],
        "Meesho": []
    }
    mock_status = {
        "Amazon": {"status": "success", "available": True},
        "Flipkart": {"status": "success", "available": True},
        "Meesho": {"status": "success", "available": True}
    }
    mock_processed = {
        "total": 2,
        "platform_results": mock_raw,
        "comparison_data": {
            "amazon": mock_raw["Amazon"][0],
            "flipkart": mock_raw["Flipkart"][0],
            "meesho": None,
            "specifications": [{"specification": "Price", "amazon": "₹74,999", "flipkart": "₹74,999", "meesho": "N/A"}]
        },
        "best_deal": {"platform": "Amazon", "price": 74999}
    }

    with patch("search.search_router.fetch_all_products_with_fallbacks", return_value=(mock_raw, mock_status)), \
         patch("search.search_router.process_results", return_value=mock_processed):
        result = route_search(query)
        assert result["search_type"] == "product_name"
        assert result["query"] == query
        assert len(result["products"]["amazon"]) == 1
        assert len(result["products"]["flipkart"]) == 1


# =============================================================================
# 4. POST /api/search Endpoint Tests
# =============================================================================

def test_api_search_post_url(client):
    target_url = "https://dl.flipkart.com/s/0chNErNNNN"
    mock_routed = {
        "search_type": "product_url",
        "source_platform": "flipkart",
        "source_product": {"title": "Metronaut Relaxed Men Beige Trousers"},
        "products": {"amazon": [], "flipkart": [{"title": "Metronaut Trousers"}], "meesho": []},
        "matches": {"amazon": None, "flipkart": {"title": "Metronaut Trousers"}, "meesho": None},
        "comparison": {"specifications": [{"specification": "Price"}]},
        "best_deal": {"platform": "Flipkart", "price": 499},
        "success": True
    }

    with patch("api.route_search", return_value=mock_routed) as mock_rt:
        res = client.post("/api/search", json={"query": target_url})
        assert res.status_code == 200
        data = res.get_json()
        assert data["search_type"] == "product_url"
        assert data["source_platform"] == "flipkart"
        assert "matches" in data
        assert "comparison" in data
        assert "best_deal" in data
        mock_rt.assert_called_once()


def test_api_search_post_product_name(client):
    query = "Samsung Galaxy S24"
    mock_routed = {
        "search_type": "product_name",
        "source_platform": None,
        "source_product": None,
        "query": query,
        "products": {"amazon": [], "flipkart": [], "meesho": []},
        "matches": {"amazon": None, "flipkart": None, "meesho": None},
        "comparison": {"specifications": []},
        "best_deal": None,
        "success": True
    }

    with patch("api.route_search", return_value=mock_routed):
        res = client.post("/api/search", json={"query": query})
        assert res.status_code == 200
        data = res.get_json()
        assert data["search_type"] == "product_name"
        assert data["source_platform"] is None


def test_api_search_post_empty(client):
    res = client.post("/api/search", json={"query": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"


# =============================================================================
# 5. GET /search?q=<URL> Automatic Routing
# =============================================================================

def test_get_search_with_url_in_q_param(client):
    """
    CRITICAL USER REQUIREMENT:
    When a user pastes ANY valid product URL into SmartBuy's main search box (?q=...),
    it must NOT treat it as literal text and return 0 results. It must automatically
    route to URL comparison.
    """
    url = "https://dl.flipkart.com/s/0chNErNNNN"
    mock_comp = {
        "success": True,
        "source_platform": "flipkart",
        "source_platform_name": "Flipkart",
        "source_product": {"title": "Metronaut Trousers", "price_num": 499},
        "matches": {
            "flipkart": {"title": "Metronaut Trousers", "price_num": 499},
            "amazon": None,
            "meesho": None
        },
        "specifications_matrix": [],
        "best_deal": {"platform": "Flipkart", "price": 499, "formatted_price": "499"},
        "platform_status": {
            "Flipkart": {"status": "success", "available": True},
            "Amazon": {"status": "success", "available": True},
            "Meesho": {"status": "success", "available": True}
        }
    }

    with patch("api.compare_by_product_url", return_value=mock_comp) as mock_cmp:
        resp = client.get(f"/search?q={url}")
        assert resp.status_code == 200
        # Check that compare_by_product_url was called with the detected URL
        mock_cmp.assert_called_once()
        assert "Metronaut Trousers" in resp.get_data(as_text=True)
