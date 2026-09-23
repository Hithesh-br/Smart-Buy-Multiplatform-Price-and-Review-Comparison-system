import urllib.request
import urllib.parse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:5000"

def test_query(query, expected_category=None):
    print(f"\n==================================================")
    print(f"Testing Category Query: '{query}'")
    print(f"==================================================")
    url = f"{BASE_URL}/search?q={urllib.parse.quote_plus(query)}"
    try:
        req = urllib.request.urlopen(url, timeout=90)
        html = req.read().decode('utf-8', errors='ignore')
        
        assert req.status == 200, f"HTTP status was {req.status}"
        assert "summary-decision-grid" in html or "Product Comparison Summary" in html, "Missing 5-Pillar Comparison Summary"
        assert "viewQualityTable" in html, "Missing viewQualityTable"
        assert "specComparisonTable" in html, "Missing specComparisonTable"
        assert "data-view=\"qualityTable\"" in html or "id=\"tabQualityTable\"" in html, "Missing Quality Table tab"
        assert "Quality Score" in html, "Missing Quality Score text"
        assert "Data Confidence" in html or "Verified Evidence" in html or "Data Availability" in html, "Missing Data Confidence element"

        print(f" [PASS] HTML Search results page for '{query}' rendered successfully (200 OK)")
        return True
    except Exception as e:
        print(f" [FAIL] Query '{query}' failed: {e}")
        return False

def test_api_json(query):
    print(f"\nTesting JSON API for '{query}'...")
    url = f"{BASE_URL}/api/search?q={urllib.parse.quote_plus(query)}"
    try:
        req = urllib.request.urlopen(url, timeout=90)
        data = json.loads(req.read().decode('utf-8'))
        
        assert "comparison_summary" in data, "API missing comparison_summary"
        assert "quality_comparison_table" in data, "API missing quality_comparison_table"
        summary = data["comparison_summary"]
        print(f" [PASS] API returned comparison_summary keys: {list(summary.keys())}")
        table = data["quality_comparison_table"]
        print(f" [PASS] API returned quality_comparison_table with {len(table)} platform rows")
        if table:
            sample = table[0]
            print(f"        Sample Platform: {sample.get('platform')}, Quality Score: {sample.get('estimated_quality_score')}, Conf: {sample.get('data_confidence')}%")
        return True
    except Exception as e:
        print(f" [FAIL] API query failed: {e}")
        return False

def test_profile_page():
    print(f"\nTesting Profile Page UI with authenticated test client...")
    try:
        from app import app
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 'test_user_quality_123'
                sess['user_email'] = 'test_quality@example.com'
                sess['user_name'] = 'Test Quality User'
            resp = client.get('/profile')
            html = resp.get_data(as_text=True)
            assert resp.status_code == 200, f"Profile page returned {resp.status_code}"
            assert "modalQualityBadge" in html, "Profile missing modalQualityBadge"
            assert "Quality" in html, "Profile missing Quality keyword"
            assert "openSearchDetailModal" in html, "Profile missing openSearchDetailModal function"
            print(f" [PASS] Profile page contains modalQualityBadge and Quality elements (200 OK)")
            return True
    except Exception as e:
        print(f" [FAIL] Profile page check failed: {e}")
        return False

if __name__ == "__main__":
    results = []
    # Test JSON API first
    results.append(test_api_json("mixer grinder"))
    # Test HTML for mixer grinder (kitchen)
    results.append(test_query("mixer grinder", "kitchen"))
    # Test HTML for samsung galaxy (phone)
    results.append(test_query("samsung galaxy", "phone"))
    # Test Profile page
    results.append(test_profile_page())
    
    all_passed = all(results)
    print(f"\n{'ALL TESTS PASSED!' if all_passed else 'SOME TESTS FAILED!'}")
    sys.exit(0 if all_passed else 1)
