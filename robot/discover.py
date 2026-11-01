"""Discovery run 10: Teta product pages with prices, Kaufland flyers via the Schwarz leaflet overview.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import json
import re
import time
import urllib.parse
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

UA = "saving-pricebot/1.0 (personal grocery price check; non-commercial; github.com/romankurty/saving)"
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
            rp.parse(r.text.splitlines() if status == 200 and "<html" not in r.text[:200].lower() else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status)
        time.sleep(DELAY_S)
    rp, status = _robots[base]
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url)


def get(url, as_json=False, ok_any=False):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, headers={"Accept": "application/json"} if as_json else {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:170]} ({len(r.content)} B)")
    return r if (r.status_code == 200 or ok_any) else None


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


def walk(o, pred, out, limit=5):
    if len(out) >= limit:
        return out
    if isinstance(o, dict):
        if pred(o):
            out.append(o)
        for v in o.values():
            walk(v, pred, out, limit)
    elif isinstance(o, list):
        for v in o:
            walk(v, pred, out, limit)
    return out


def unflatten_nuxt(payload):
    memo = {}

    def res(i, depth=0):
        if not isinstance(i, int) or i < 0 or i >= len(payload):
            return i
        if i in memo:
            return memo[i]
        if depth > 80:
            return None
        v = payload[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef"):
                out = res(v[1], depth + 1) if len(v) > 1 else None
            elif v and isinstance(v[0], str) and v[0] in ("Set", "Map", "Date", "RegExp", "BigInt", "null", "undefined", "NaN"):
                out = v[1] if v[0] == "Date" and len(v) > 1 else None
            else:
                out = []
                memo[i] = out
                out.extend(res(x, depth + 1) for x in v)
                return out
        elif isinstance(v, dict):
            out = {}
            memo[i] = out
            for k, x in v.items():
                out[k] = res(x, depth + 1)
            return out
        else:
            out = v
        memo[i] = out
        return out

    return res(0)


def nuxt(r):
    s = BeautifulSoup(r.text, "html.parser").find("script", id="__NUXT_DATA__")
    return unflatten_nuxt(json.loads(s.string)) if s else None


print("=== 1. Teta: leaflet page + menu categories ===")
r = get("https://www.tetadrogerie.cz/akce/letak")
if r is not None:
    d = (nuxt(r) or {}).get("data", {})
    print("  data keys:", [k[:120] for k in d.keys()])
    prods = walk(d, lambda x: isinstance(x, dict) and "name" in x and any("price" in k.lower() for k in x.keys()), [], 3)
    for p in prods:
        print("   product:", c(p, 1500))
r = get("https://www.tetadrogerie.cz/")
cats = []
if r is not None:
    d = (nuxt(r) or {}).get("data", {})
    menu = d.get("/api/v2/shop/search/taxons/menu_category")
    items = walk(menu, lambda x: isinstance(x, dict) and "slug" in x and "name" in x, [], 60)
    cats = [(i.get("name"), i.get("slug"), i.get("url")) for i in items]
    print("  categories:", cats[:40])
    hrefs = list(dict.fromkeys(a["href"] for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True)))
    print("  hrefs:", [h for h in hrefs if h.startswith("/") and h.count("/") >= 1][:50])
for url in ("https://www.tetadrogerie.cz/drogerie/zubni-pasty", "https://www.tetadrogerie.cz/vyhledavani?q=zubni%20pasta"):
    r = get(url)
    if r is not None:
        d = (nuxt(r) or {}).get("data", {})
        print("  data keys:", [k[:120] for k in d.keys()][:12])
        prods = walk(d, lambda x: isinstance(x, dict) and "name" in x and any("price" in k.lower() for k in x.keys()), [], 2)
        for p in prods:
            print("   product:", c(p, 1500))

print("=== 2. Kaufland flyers via Schwarz overview ===")
for url in ("https://endpoints.leaflets.schwarz/v4/overview?client_locale=cs-CZ",
            "https://endpoints.leaflets.schwarz/v4/overview?client_locale=cs_CZ"):
    r = get(url, as_json=True, ok_any=True)
    if r is None:
        continue
    print("   body start:", r.text[:300].replace("\n", " "))
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        continue
    flyers = walk(j, lambda x: isinstance(x, dict) and ("flyerIdentifier" in x or "identifier" in x or "slug" in x) and ("name" in x or "title" in x), [], 60)
    print("   flyers:", len(flyers))
    for f in flyers[:30]:
        print("    -", f.get("flyerIdentifier") or f.get("identifier") or f.get("slug"), "|", f.get("name") or f.get("title"), "|", f.get("client") or f.get("brand") or f.get("clientName"), f.get("startDate"), f.get("endDate"))
    kf = [f for f in flyers if "kaufland" in json.dumps(f, ensure_ascii=False).lower()]
    if kf:
        ident = kf[0].get("flyerIdentifier") or kf[0].get("identifier") or kf[0].get("slug")
        fr = get(f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={ident}&region_id=0&region_code=0", as_json=True)
        if fr is not None:
            fl = fr.json().get("flyer", {})
            print("   kaufland flyer:", fl.get("name"), fl.get("startDate"), fl.get("endDate"), "| products:", len(fl.get("products") or {}), "| pages:", len(fl.get("pages") or []))
            for k2, v2 in list((fl.get("products") or {}).items())[:2]:
                print("    product:", c(v2, 700))
            pages = fl.get("pages") or []
            if len(pages) > 2:
                print("    page2 keywords:", (pages[2].get("keyWords") or "")[:500])
                print("    page2 links:", c(pages[2].get("links"), 600))
    break
