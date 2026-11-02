"""Discovery run 18: Kaufland store 4310 leaflet — search endpoint / page data for product-price pairs.

Personal, non-commercial use. One slow pass, identifies itself honestly.
"""
import json
import time

import requests

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


def get(u):
    time.sleep(3)
    r = session.get(u, timeout=40)
    print(f"[{r.status_code}] {u[:170]} ({len(r.content)} B)")
    return r


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


o = get("https://endpoints.leaflets.schwarz/v4/overview?client_locale=kaufland%2Fcs-CZ&store_id=4310").json()
fl = []
for cat in o.get("categories", []):
    for sub in cat.get("subcategories", []):
        for f in sub.get("flyers", []):
            fl.append((sub.get("name"), f))
print("flyer keys:", list(fl[0][1].keys()) if fl else None)
cur = [f for s, f in fl if s in ("KDZ", "Hyper1")]
f0 = cur[0] if cur else fl[0][1]
ident = f0.get("id") or f0.get("uuid")
print("ident:", ident, f0.get("title"))

for path in (f"search?flyer_identifier={ident}&query=m%C3%A1slo&store_id=4310",
             f"search?flyer_identifier={ident}&q=m%C3%A1slo&store_id=4310",
             f"search?flyer_identifier={ident}&term=m%C3%A1slo",
             f"flyer/search?flyer_identifier={ident}&query=m%C3%A1slo"):
    r = get("https://endpoints.leaflets.schwarz/v4/" + path)
    print("   ", r.text[:700].replace("\n", " "))

r = get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={ident}&store_id=4310")
f = r.json().get("flyer", {})
print("flyer top keys:", list(f.keys()))
print("pdfUrl:", f.get("pdfUrl"))
pages = f.get("pages") or []
for pg in pages[4:6]:
    print("page", pg.get("number"), "keys:", list(pg.keys()))
    print("  alt:", (pg.get("altText") or "")[:400])
    print("  links:", c(pg.get("links"), 500))
    print("  image:", (pg.get("image") or "")[:160])
for host in ("https://imgproxy.leaflets.schwarz", "https://assets.leaflets.schwarz"):
    try:
        rr = session.get(host + "/robots.txt", timeout=20)
        print("robots", host, rr.status_code, rr.text[:200].replace("\n", " | "))
    except Exception as e:  # noqa: BLE001
        print("robots err", host, e)
print("texts:", c(f.get("texts"), 600))
print("topics:", c(f.get("topics"), 600))
