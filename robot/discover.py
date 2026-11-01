"""Discovery run 5: Lidl food leaflet structure, Kaufland flyer list, Billa/Albert/Teta data endpoints.

Personal, non-commercial use. One slow pass, identifies itself honestly, respects robots.txt and blocks.
"""
import json
import re
import time
import urllib.parse
import urllib.robotparser
from collections import Counter

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


def get(url):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:150]} ({len(r.content)} B)")
    return r if r.status_code == 200 else None


def c(o, n=900):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


print("=== 1. Lidl food leaflet: structure ===")
r = get("https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=akcni-letak-od-pondeli-2-11-4-11-2026&region_id=0&region_code=0")
if r is not None:
    f = r.json().get("flyer", {})
    print("  flyer keys:", list(f.keys()))
    prods = f.get("products") or {}
    print("  products:", len(prods))
    for k, v in list(prods.items())[:2]:
        print("  product keys:", list(v.keys()))
        print("  product:", c(v, 1400))
    pages = f.get("pages") or []
    print("  pages:", len(pages))
    if pages:
        print("  page[1] keys:", list(pages[min(1, len(pages)-1)].keys()) if isinstance(pages[0], dict) else type(pages[0]))
        print("  page[1]:", c(pages[min(1, len(pages)-1)], 1200))

print("=== 2. Schwarz overview endpoints (to list Kaufland flyers) ===")
js = get("https://esi.leaflets.schwarz/assets/build/esi/overview/index.12a0779a.js")
if js is not None:
    eps = sorted(set(re.findall(r"/v\d/[a-zA-Z_/-]+", js.text)))
    print("  endpoint paths in overview JS:", eps[:30])
    params = sorted(set(re.findall(r"[?&]([a-z_]+)=", js.text)))
    print("  query params:", params[:30])
k = get("https://leaflets.kaufland.com/cs-CZ")
if k is not None:
    soup = BeautifulSoup(k.text, "html.parser")
    print("  kaufland leaflets scripts:", [s.get("src") for s in soup.find_all("script") if s.get("src")][:10])
    print("  html:", k.text[:900].replace("\n", " "))

print("=== 3. Billa: API endpoints in front-end code ===")
r = get("https://www.billa.cz/akcni-letaky")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    srcs = [urllib.parse.urljoin(r.url, s.get("src")) for s in soup.find_all("script") if s.get("src")]
    links = [urllib.parse.urljoin(r.url, l.get("href")) for l in soup.find_all("link") if l.get("href", "").endswith(".js")]
    allsrc = list(dict.fromkeys(srcs + links))
    print("  js files:", len(allsrc))
    found = Counter()
    for u in allsrc[:12]:
        j = get(u)
        if j is not None:
            for m in re.findall(r"[\"'`](/api/[a-zA-Z0-9/_{}.$-]+)", j.text):
                found[m] += 1
    print("  api paths:", [p for p, _ in found.most_common(40)])

print("=== 4. Albert: API usage in front-end code ===")
r = get("https://www.albert.cz/slevy")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    srcs = [urllib.parse.urljoin(r.url, s.get("src")) for s in soup.find_all("script") if s.get("src")]
    print("  js files:", len(srcs))
    ops, paths = Counter(), Counter()
    for u in srcs[:20]:
        j = get(u)
        if j is not None:
            for m in re.findall(r"operationName[\"']?\s*[:=]\s*[\"']([A-Za-z]+)", j.text):
                ops[m] += 1
            for m in re.findall(r"(?:query|mutation)\s+([A-Z][A-Za-z]+)\s*[({]", j.text):
                ops[m] += 1
            for m in re.findall(r"[\"'`](/api/v1/[a-zA-Z0-9/_{}.$?=&-]*)", j.text):
                paths[m] += 1
    print("  graphql ops:", [o for o, _ in ops.most_common(60) if any(k in o.lower() for k in ("promo", "leaflet", "discount", "product", "offer", "category", "search"))][:40])
    print("  api paths:", [p for p, _ in paths.most_common(20)])

print("=== 5. Albert leaflet viewer data ===")
r = get("https://letaky.albert.cz/44hm_akcni_letak/page/1")
if r is not None:
    txt = r.text
    print("  'price' occurrences:", txt.count("price"), "| 'Kč':", txt.count("Kč"))
    m = re.search(r".{200}price.{400}", txt)
    print("  sample:", m.group(0)[:600] if m else None)
    hosts = sorted(set(re.findall(r"https://[a-z0-9.-]+\.[a-z]{2,}", txt)))
    print("  hosts:", hosts[:15])

print("=== 6. Teta: price keys in embedded data ===")
r = get("https://www.tetadrogerie.cz/akce")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    s = soup.find("script", id="__NUXT_DATA__")
    if s is not None:
        payload = json.loads(s.string)
        keys = Counter()
        for v in payload:
            if isinstance(v, dict):
                for kk in v.keys():
                    keys[kk] += 1
        print("  frequent object keys:", [k for k, _ in keys.most_common(60)])
