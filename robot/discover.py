"""Discovery run 29: Lidl leaflet product data (structured prices?), kupi.sk structure, Kaufland SK leaflet types."""
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import fetch_prices as F  # noqa: E402

API = "https://endpoints.leaflets.schwarz/v4"
for loc, sub in (("lidl/cs-CZ", "Akční letáky"), ("lidl/sk-SK", "Letáky")):
    r = F.get(f"{API}/overview?client_locale={urllib.parse.quote(loc, safe='')}", as_json=True)
    fl = [f for c in r.json().get("categories", []) for s in c.get("subcategories", []) if s.get("name") == sub for f in s.get("flyers", [])]
    print("==", loc, [(f.get("title"), f.get("id")[:8]) for f in fl])
    for f in fl:
        fr = F.get(f"{API}/flyer?flyer_identifier={urllib.parse.quote(f['id'])}", as_json=True)
        fj = fr.json().get("flyer", {}) if fr is not None else {}
        prods = fj.get("products") or {}
        vals = list(prods.values()) if isinstance(prods, dict) else prods
        food = [p for p in vals if F.match_items(p.get("title") or "")]
        print(f"  flyer {f.get('title')}: products {len(vals)}, matching our items {len(food)}")
        for p in food[:2]:
            print("   FULL:", json.dumps(p, ensure_ascii=False)[:1800])
        for p in food[:25]:
            pr = p.get("price") or {}
            print("   ", F.match_items(p.get("title") or ""), "|", p.get("title"), "|", json.dumps({k: p.get(k) for k in ("price", "basePrice", "packaging", "priceText", "lidlPlus", "page", "pageNumber")}, ensure_ascii=False)[:300])
        if food:
            break

print("== kupi.sk")
r = F.session.get("https://www.kupi.sk/robots.txt", timeout=20)
print(r.status_code, r.text[:800])
for path in ("/", "/zlavy/vajcia", "/hladaj?f=vajcia", "/akcie/vajcia"):
    rr = F.get("https://www.kupi.sk" + path)
    if rr is None:
        print("  ", path, "failed"); continue
    t = rr.text
    print(f"  {path}: {len(t)//1000} kB, ld+json {len(re.findall('application/ld', t))}, shops {sorted(set(re.findall(r'(Kaufland|Tesco|Lidl|Billa|Coop Jednota|Fresh)', t)))[:8]}")
    m = re.findall(r'<a[^>]+href="(/zlava/[^"]+|/zlavy/[^"]+)"', t)
    print("    sample links:", m[:10])
    i = t.find("€")
    print("    around €:", re.sub(r"\s+", " ", t[max(0, i - 600):i + 200])[:800])

print("== Kaufland SK (store 6670) leaflet types")
r = F.get(f"{API}/overview?client_locale=kaufland%2Fsk-SK&store_id=6670", as_json=True)
for c in r.json().get("categories", []):
    for s in c.get("subcategories", []):
        print("  sub", s.get("name"), [(f.get("title"), f.get("offerStartDate"), f.get("offerEndDate"), f.get("flyerUrlAbsolute")) for f in s.get("flyers", [])][:12])
