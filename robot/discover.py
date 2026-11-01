"""Discovery run 6: confirm machine-readable offers for the three centre shops (Lidl, Billa, Albert) + Kupino.sk.

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


def get(url, headers=None):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, headers=headers or {})
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:160]} ({len(r.content)} B, {r.headers.get('content-type')})")
    return r if r.status_code == 200 else None


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


print("=== 1. Lidl offer pages (product tiles) ===")
for url in ("https://www.lidl.cz/c/pondelni-nabidka/a10106398",
            "https://www.lidl.cz/c/hity-tydne/a10004407",
            "https://www.lidl.cz/c/ctvrtecni-nabidka/a10105841"):
    r = get(url)
    if r is None:
        continue
    grids = re.findall(r'data-grid-data="([^"]+)"', r.text)
    print(f"  data-grid-data tiles: {len(grids)} | 'Kč' count: {r.text.count('Kč')}")
    for g in grids[:2]:
        try:
            d = json.loads(htmlmod.unescape(g))
            if isinstance(d, list):
                d = d[0]
            print("   tile keys:", list(d.keys())[:40])
            print("   tile:", c({k: d.get(k) for k in ("fullTitle", "title", "price", "lidlPlus", "category", "ians", "stockAvailability", "keyfacts") if k in d}, 1400))
        except Exception as e:  # noqa: BLE001
            print("   parse error", e, g[:200])
    titles = re.findall(r'"fullTitle"\s*:\s*"([^"]+)"', htmlmod.unescape(r.text))
    print("   sample titles:", titles[:12])

print("=== 2. Billa product API ===")
hdr = {"Accept": "application/json"}
for url in ("https://www.billa.cz/api/product-discovery/categories/tree",
            "https://www.billa.cz/api/product-discovery/products?page=0&pageSize=5&search=m%C3%A1slo",
            "https://www.billa.cz/api/product-discovery/products?page=0&pageSize=5"):
    r = get(url, hdr)
    if r is not None:
        try:
            j = r.json()
            if isinstance(j, dict):
                print("   keys:", list(j.keys())[:20])
                items = j.get("results") or j.get("products") or j.get("items") or j.get("data") or []
                if isinstance(items, list) and items:
                    print("   first item:", c(items[0], 1500))
                else:
                    print("   body:", c(j, 800))
            else:
                print("   list len", len(j), c(j[:1], 800))
        except Exception as e:  # noqa: BLE001
            print("   not JSON", e, r.text[:300])

print("=== 3. Albert leaflet (Publitas) data ===")
for url in ("https://letaky.albert.cz/44hm_akcni_letak/spreads.json",
            "https://letaky.albert.cz/44hm_akcni_letak/data.json",
            "https://letaky.albert.cz/44hm_akcni_letak/products.json"):
    r = get(url, hdr)
    if r is not None:
        t = r.text
        print("   'price' count:", t.count('"price'), "| sample:", t[:600].replace("\n", " "))
r = get("https://letaky.albert.cz/44hm_akcni_letak/page/1")
if r is not None:
    m = re.findall(r"https?://[a-z0-9./_-]*(?:spreads|products|hotspots|data)[a-z0-9./_?=&-]*\.json[a-z0-9?=&_-]*", r.text)
    print("  json urls referenced:", sorted(set(m))[:10])
    m2 = re.findall(r'"(?:jsonUrl|dataUrl|spreadsUrl|productsUrl)"\s*:\s*"([^"]+)"', r.text)
    print("  data url fields:", m2[:10])

print("=== 4. Kupino.sk category listing ===")
r = get("https://www.kupino.sk/kategoria/hypermarkety-a-supermarkety")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    akcie = list(dict.fromkeys(a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("/akcia/")))
    print("  product links on page:", len(akcie), akcie[:10])
    txt = soup.get_text(" ", strip=True)
    print("  euro prices on listing:", len(re.findall(r"\d+[,.]\d{2}\s*€", txt)))
    nxt = [a["href"] for a in soup.find_all("a", href=True) if "strana" in a["href"] or "page" in a["href"]]
    print("  pagination:", nxt[:5])
r = get("https://www.kupino.sk/akcia/euro-standard-bravcova-sunka")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.get_text(" | ", strip=True)
    i = main.find("€")
    print("  around prices:", main[max(0, i - 700): i + 900])
