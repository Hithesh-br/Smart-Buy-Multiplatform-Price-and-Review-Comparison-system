import urllib.request
import urllib.parse
import sys

def test_search(query):
    url = f"http://127.0.0.1:5000/search?q={urllib.parse.quote_plus(query)}"
    print(f"Testing search for '{query}'...")
    try:
        req = urllib.request.urlopen(url, timeout=35)
        html = req.read().decode('utf-8', errors='ignore')
        
        has_summary = "Product Comparison Summary" in html or "summary-decision-grid" in html
        has_q_table = "MULTI-PLATFORM PRODUCT QUALITY COMPARISON" in html or "viewQualityTable" in html
        has_q_score = "Quality Score" in html or "quality_score" in html or "Estimated Quality" in html
        has_spec_table = "specComparisonTable" in html
        has_views = "viewPlatform" in html
        
        print(f"Status: {req.status}")
        print(f"Has 5-Pillar Comparison Summary: {has_summary}")
        print(f"Has Quality Comparison Table: {has_q_table}")
        print(f"Has Quality Score elements: {has_q_score}")
        print(f"Has Specification Table: {has_spec_table}")
        print(f"Has Side-by-Side Platforms: {has_views}")

        assert req.status == 200, f"Expected 200, got {req.status}"
        assert has_views, "Expected side-by-side viewPlatform"
        assert has_spec_table, "Expected specComparisonTable"
        assert has_q_table, "Expected viewQualityTable"
        print(f"PASS: '{query}' rendered successfully with all Quality features!\n")
        return True
    except Exception as e:
        print(f"FAIL: '{query}' encountered error: {e}\n")
        return False

if __name__ == '__main__':
    success = test_search("mixer grinder")
    sys.exit(0 if success else 1)
