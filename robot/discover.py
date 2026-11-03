"""Discovery run 31: Kaufland SK store ids (Poprad = 1020). Does the overview tell the store name? Find Kezmarok."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

F.DELAY_S = 0.8
API = "https://endpoints.leaflets.schwarz/v4"
r = F.get(f"{API}/overview?client_locale=kaufland%2Fsk-SK&store_id=1020", as_json=True)
j = r.json() if r is not None else {}
print("keys:", list(j.keys()))
print("non-category fields:", json.dumps({k: v for k, v in j.items() if k not in ("categories", "translations")}, ensure_ascii=False)[:800])
for c in j.get("categories", []):
    for s in c.get("subcategories", []):
        print("  sub", s.get("name"), [(f.get("title"), f.get("flyerUrlAbsolute")) for f in s.get("flyers", [])][:3])
# flyer detail may carry store info
fl = [f for c in j.get("categories", []) for s in c.get("subcategories", []) if s.get("name") == "KDZ" for f in s.get("flyers", [])]
if fl:
    fr = F.get(f"{API}/flyer?flyer_identifier={fl[0]['id']}&store_id=1020", as_json=True)
    fj = fr.json() if fr is not None else {}
    txt = json.dumps(fj, ensure_ascii=False)
    print("store-ish strings:", sorted(set(re.findall(r'"(store[A-Za-z]*|branch[A-Za-z]*)"\s*:\s*("[^"]{0,60}"|\d+)', txt)))[:20])
# probe ids: which return a KDZ leaflet, and what region code
found = {}
for sid in list(range(1000, 1100)) + list(range(2000, 2010)) + list(range(6600, 6610)):
    rr = F.get(f"{API}/overview?client_locale=kaufland%2Fsk-SK&store_id={sid}", as_json=True)
    if rr is None:
        continue
    urls = [f.get("flyerUrlAbsolute") for c in rr.json().get("categories", []) for s in c.get("subcategories", []) if s.get("name") == "KDZ" for f in s.get("flyers", [])]
    if urls:
        found[sid] = urls[0]
print("store ids with KDZ:", len(found))
for k, v in found.items():
    print("  ", k, v)
