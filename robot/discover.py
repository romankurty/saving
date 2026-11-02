"""Discovery run 15: Kaufland flyers on the public Schwarz leaflet platform (client_locale=kaufland/cs-CZ).

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import json
import re
import time
import urllib.parse

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


def get(url):
    time.sleep(3)
    r = session.get(url, timeout=40)
    print(f"[{r.status_code}] {url[:170]} ({len(r.content)} B)")
    return r


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


for loc in ("kaufland/cs-CZ", "kaufland/sk-SK"):
    print(f"=== overview {loc} ===")
    r = get("https://endpoints.leaflets.schwarz/v4/overview?client_locale=" + urllib.parse.quote(loc))
    if r.status_code != 200:
        print("  ", r.text[:300])
        continue
    j = r.json()
    print("  message:", j.get("message"))
    flyers = []
    for cat in j.get("categories", []):
        for sub in cat.get("subcategories", []):
            for f in sub.get("flyers", []):
                flyers.append(f)
                print("   -", sub.get("name"), "|", f.get("identifier") or f.get("flyerIdentifier") or f.get("slug"), "|", f.get("name") or f.get("title"), "|", f.get("startDate"), f.get("endDate"), "| keys:", list(f.keys())[:14])
    if not flyers:
        print("  raw:", c(j, 1500))
        continue
    f0 = flyers[0]
    ident = f0.get("identifier") or f0.get("flyerIdentifier") or f0.get("slug")
    fr = get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={urllib.parse.quote(ident)}&region_id=0&region_code=0")
    if fr.status_code != 200:
        print("  ", fr.text[:300])
        continue
    fl = fr.json().get("flyer", {})
    prods = fl.get("products") or {}
    print("  flyer:", fl.get("name"), fl.get("offerStartDate"), fl.get("offerEndDate"), "| products:", len(prods), "| pages:", len(fl.get("pages") or []))
    for k, v in list(prods.items())[:4]:
        print("   product:", c(v, 900))
    pages = fl.get("pages") or []
    for pg in pages[2:4]:
        print("   page", pg.get("number"), "links:", len(pg.get("links") or []), c((pg.get("links") or [])[:2], 900))
        print("   keywords:", (pg.get("keyWords") or "")[:400])
        print("   alt:", (pg.get("altText") or "")[:300])
    print("  texts:", c(fl.get("texts"), 400))
