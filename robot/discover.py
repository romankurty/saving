"""Discovery run 17: Kaufland store numbers from OpenStreetMap -> regionalized flyers on the Schwarz leaflet platform.

Personal, non-commercial use. One slow pass, identifies itself honestly.
"""
import json
import re
import time
import urllib.parse

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


q = """[out:json][timeout:25];
(nwr["brand"="Kaufland"](around:2500,49.2154,16.6041);
 nwr["brand"="Kaufland"](around:4000,49.1372,20.4300););
out tags center;"""
r = session.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=60)
print("[overpass]", r.status_code)
stores = []
for el in r.json().get("elements", []):
    tg = el.get("tags", {})
    stores.append((tg.get("ref"), tg.get("addr:city"), tg.get("addr:street"), tg.get("website"), tg.get("name")))
    print("  store:", tg.get("ref"), tg.get("addr:city"), tg.get("addr:street"), tg.get("addr:housenumber"), tg.get("website"))

for ref, city, street, web, name in stores:
    if not ref:
        continue
    locale = "kaufland/sk-SK" if (city or "").lower().startswith("ke") or "kaufland.sk" in (web or "") else "kaufland/cs-CZ"
    for sid in (ref, ref.lstrip("0")):
        time.sleep(3)
        u = f"https://endpoints.leaflets.schwarz/v4/overview?client_locale={urllib.parse.quote(locale)}&store_id={sid}"
        o = session.get(u, timeout=40)
        print(f"[{o.status_code}] {u}")
        j = o.json() if o.headers.get("content-type", "").startswith("application/json") else {}
        print("   ", j.get("message"))
        flyers = []
        for cat in j.get("categories", []) or []:
            for sub in cat.get("subcategories", []) or []:
                for f in sub.get("flyers", []) or []:
                    flyers.append((sub.get("name"), f))
        for subn, f in flyers[:12]:
            print("    -", subn, "|", {k: f.get(k) for k in ("identifier", "flyerIdentifier", "slug", "name", "title", "startDate", "endDate", "offerStartDate", "offerEndDate")})
        if flyers:
            f = flyers[0][1]
            ident = f.get("flyerIdentifier") or f.get("identifier") or f.get("slug") or f.get("id")
            time.sleep(3)
            fu = f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(str(ident))}&store_id={sid}"
            fr = session.get(fu, timeout=40)
            print(f"[{fr.status_code}] {fu}")
            if fr.status_code == 200:
                fl = fr.json().get("flyer", {})
                prods = fl.get("products") or {}
                print("   flyer:", fl.get("name"), fl.get("offerStartDate"), fl.get("offerEndDate"), "| products:", len(prods), "| pages:", len(fl.get("pages") or []))
                for k, v in list(prods.items())[:3]:
                    print("    product:", c(v, 700))
                for pg in (fl.get("pages") or [])[1:3]:
                    print("    page", pg.get("number"), "links:", c((pg.get("links") or [])[:2], 700))
                    print("    keywords:", (pg.get("keyWords") or "")[:300])
            break
        if flyers:
            break
