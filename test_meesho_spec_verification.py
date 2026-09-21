import requests
import json

base_url = "http://127.0.0.1:5000"

def run_test(query):
    print(f"\n" + "=" * 60)
    print(f"AUTOMATED TEST: '{query}'")
    print("=" * 60)
    resp = requests.get(f"{base_url}/api/search", params={"q": query}, timeout=120)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    data = resp.json()
    comp = data.get('comparison', {})
    spec_table = comp.get('specification_table', {})
    has_match = comp.get('has_match', False)
    rows = spec_table.get('rows', [])
    best_deal = data.get('best_deal')
    
    amz_p = data.get('amazon', {}).get('count', 0)
    fk_p = data.get('flipkart', {}).get('count', 0)
    mee_p = data.get('meesho', {}).get('count', 0)
    print(f"Scraped Counts: Amazon={amz_p}, Flipkart={fk_p}, Meesho={mee_p}")
    print(f"Has Exact Cross-Platform Match: {has_match}")
    print(f"Category: {comp.get('category')}")
    print(f"Total Specification Rows: {len(rows)}")
    
    if rows:
        print("\nSpecification Table Content (First 10 rows):")
        for r in rows[:10]:
            name = r.get('name') or r.get('specification')
            amz = str(r.get('amazon')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            fk = str(r.get('flipkart')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            mee = str(r.get('meesho')).replace('₹', 'Rs.').replace('★', '*').encode('ascii', errors='replace').decode('ascii')[:25]
            print(f"  {name:18} | Amz: {amz:25} | Fk: {fk:25} | Mee: {mee:25}")
            
    # Check Meesho items
    meesho_items = data.get('meesho', {}).get('products', [])
    if meesho_items:
        top_mee = meesho_items[0]
        t_clean = str(top_mee.get('title')).replace('₹', 'Rs.').encode('ascii', errors='replace').decode('ascii')[:60]
        print(f"\nTop Meesho Product Card:")
        print(f"  Title: {t_clean}")
        print(f"  Price: {str(top_mee.get('price')).replace('₹', 'Rs.')}")
        print(f"  Brand: {top_mee.get('brand')}")
        print(f"  Rating: {top_mee.get('rating')}")
        print(f"  Match Type: {top_mee.get('match_type')}")
        print(f"  Raw Data Saved: {'raw_data' in top_mee}")
        print(f"  Normalized Specs Extracted: {len(top_mee.get('specifications', {}))} fields")

    return data

if __name__ == "__main__":
    run_test("ghar soap")
    run_test("iPhone 15")
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
