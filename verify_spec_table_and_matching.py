import requests
import json

base_url = "http://127.0.0.1:5000"

def test_query(q):
    print(f"\n=======================================================")
    print(f"TESTING QUERY: '{q}'")
    print(f"=======================================================")
    
    resp = requests.get(f"{base_url}/api/search", params={"q": q}, timeout=120)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    data = resp.json()
    amz_count = data.get('amazon', {}).get('count', 0)
    fk_count = data.get('flipkart', {}).get('count', 0)
    mee_count = data.get('meesho', {}).get('count', 0)
    print(f"Products Scraped: Amazon={amz_count}, Flipkart={fk_count}, Meesho={mee_count}")
    
    comp = data.get('comparison', {})
    has_match = comp.get('has_match', False)
    spec_table = comp.get('specification_table', {})
    best_deal = data.get('best_deal')
    
    print(f"Has Cross-Platform Exact Match: {has_match}")
    print(f"Specification Table Has Match: {spec_table.get('has_match')}")
    best_p = str(best_deal.get('formatted_price')).replace('₹', 'Rs.') if best_deal else 'N/A'
    best_plat = best_deal.get('platform') if best_deal else 'None'
    print(f"Best Deal: {best_plat} @ {best_p}")
    
    rows = spec_table.get('rows', [])
    print(f"Specification Table Rows: {len(rows)}")
    if rows:
        print("\nFirst 5 Specification Rows:")
        for r in rows[:5]:
            spec_name = r.get('specification')
            amz_val = str(r.get('amazon')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            fk_val = str(r.get('flipkart')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            mee_val = str(r.get('meesho')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            print(f"  {spec_name:15} | Amz: {amz_val:25} | Fk: {fk_val:25} | Mee: {mee_val:25}")
            
    # Verification assertions
    if not has_match:
        assert best_deal is None, "Best Deal must be None when no cross-platform match exists!"
        print("[PASS] Unmatched products correctly handled without fake Best Deal or false table comparison.")
    else:
        assert len(rows) > 0, "Specification table rows must be populated when has_match is True!"
        print(f"[PASS] Cross-platform match correctly generated with {len(rows)} specification rows.")
        
    return data

if __name__ == "__main__":
    test_query("ghar")
    print("\nALL AUTOMATED VERIFICATION CHECKS PASSED!")
