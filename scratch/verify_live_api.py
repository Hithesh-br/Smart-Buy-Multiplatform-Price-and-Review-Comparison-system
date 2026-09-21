import sys
import json
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = 'http://127.0.0.1:5000/api/search?q=vivo+charger&fresh=1'
req = urllib.request.urlopen(url)
data = json.loads(req.read().decode('utf-8'))

print("Query:", data.get("query"))
for p in ["amazon", "flipkart", "meesho"]:
    p_info = data.get(p, {})
    count = len(p_info.get("products", []))
    status = p_info.get("status")
    print(f"Platform: {p} | Status: {status} | Count: {count}")

comp = data.get("comparison", {})
bd = comp.get("best_deal")
if bd:
    print(f"Best Deal: {bd.get('platform')} @ {bd.get('formatted_price')} - {bd.get('title')[:45]}")
    print(f"Reasons: {bd.get('reasons')}")
else:
    print("Best Deal: None")

specs = comp.get("specifications") or []
print(f"Specification rows: {len(specs)}")
for s in specs[:5]:
    print(f"  {s.get('specification')}: Amz={s.get('amazon')} | FK={s.get('flipkart')} | Mee={s.get('meesho')}")
