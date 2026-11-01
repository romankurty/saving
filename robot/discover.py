"""Discovery run 7: Billa promo/loyalty price fields and search, Lidl.sk + Billa.sk for Kezmarok, Albert leaflet text search.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import html as htmlmod
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

UA = "saving-pricebot/0.1 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
DELAY_S = 3
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status = None
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status = r.status_code
            rp.parse(r.text.splitlines() if status == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, json_ok=False):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, headers={"Accept": "application/json"} if json_ok else {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:160]} ({len(r.content)} B)")
    return r if r.status_code == 200 else None


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


def walk(nodes, depth=0, out=None):
    out = [] if out is None else out
    for n in nodes:
        out.append((depth, n.get("name"), n.get("slug")))
        walk(n.get("children") or [], depth + 1, out)
    return out


print("=== 1. Billa: categories, promo fields, search param ===")
tree = get("https://www.billa.cz/api/product-discovery/categories/tree", json_ok=True)
slugs = {}
if tree is not None:
    flat = walk(tree.json())
    print("  top categories:", [n for d, n, s in flat if d == 0])
    for d, n, s in flat:
        slugs[n] = s
    dairy = [s for d, n, s in flat if n and any(k in n.lower() for k in ("mléčné", "mléko", "sýr", "vejce"))][:4]
    meat = [s for d, n, s in flat if n and any(k in n.lower() for k in ("drůbež", "maso"))][:3]
    print("  dairy slugs:", dairy, "| meat slugs:", meat)
    for slug in (dairy[:1] + meat[:1]):
        r = get(f"https://www.billa.cz/api/product-discovery/categories/{slug}/products?page=0&pageSize=60", json_ok=True)
        if r is not None:
            j = r.json()
            res = j.get("results", [])
            promo = [p for p in res if p.get("inPromotion")]
            print(f"  {slug}: total={j.get('total')} returned={len(res)} in promotion={len(promo)}")
            for p in promo[:2]:
                print("   PROMO:", p.get("name"), "|", c(p.get("price"), 1200), "| badges:", c(p.get("badges"), 300))
            for p in res[:2]:
                print("   ITEM:", p.get("name"), "|", c(p.get("price"), 500))
for param in ("searchTerm", "query", "q", "term"):
    r = get(f"https://www.billa.cz/api/product-discovery/products?page=0&pageSize=3&{param}=m%C3%A1slo", json_ok=True)
    if r is not None:
        print(f"   {param}:", [p.get("name") for p in r.json().get("results", [])])

print("=== 2. Lidl.sk offer pages (Kezmarok) ===")
home = get("https://www.lidl.sk/")
if home is not None:
    links = list(dict.fromkeys(re.findall(r'href="(/c/[a-z0-9-]+/a\d+)"', home.text)))
    print("  offer pages:", links[:10])
    for l in links[:2]:
        r = get("https://www.lidl.sk" + l)
        if r is None:
            continue
        tiles = re.findall(r'data-grid-data="([^"]+)"', r.text)
        food = []
        for t in tiles:
            try:
                d = json.loads(htmlmod.unescape(t))
                d = d[0] if isinstance(d, list) else d
                if "Food" in str(d.get("category")) or "Potrav" in str(d.get("keyfacts", {}).get("wonCategoryPrimary", "")):
                    pr = (d.get("price") or {}).get("price")
                    lp = [x.get("price", {}).get("price") for x in (d.get("lidlPlus") or [])]
                    food.append((d.get("fullTitle"), pr, lp))
            except Exception:  # noqa: BLE001
                pass
        print(f"  {l}: tiles={len(tiles)} food={len(food)} sample={food[:6]}")

print("=== 3. Billa.sk API ===")
r = get("https://www.billa.sk/api/product-discovery/products?page=0&pageSize=2", json_ok=True)
if r is not None:
    j = r.json()
    print("  total:", j.get("total"), "| first:", [p.get("name") for p in j.get("results", [])], c(j.get("results", [{}])[0].get("price"), 300))

print("=== 4. Albert leaflet text search ===")
for url in ("https://letaky.albert.cz/44hm_akcni_letak/search?q=maslo",
            "https://letaky.albert.cz/44hm_akcni_letak/search.json?q=maslo",
            "https://letaky.albert.cz/44hm_akcni_letak/text.json"):
    r = get(url, json_ok=True)
    if r is not None:
        print("   ", r.headers.get("content-type"), r.text[:500].replace("\n", " "))
