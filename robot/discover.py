"""Discovery run 9: Albert leaflet validity objects, Teta action products, Kaufland overview params, Billa loyalty tags.

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


print("=== 1. Albert leaflet validity ===")
r = get("https://www.albert.cz/aktualni-letaky")
if r is not None:
    nd = BeautifulSoup(r.text, "html.parser").find("script", id="__NEXT_DATA__")
    j = json.loads(nd.string)
    hits = walk(j, lambda d: "validityEndDate" in d, [], 8)
    for h in hits:
        small = {k: v for k, v in h.items() if not isinstance(v, (dict, list))}
        print("  ", c(small, 700))

print("=== 2. Teta action products ===")
r = get("https://www.tetadrogerie.cz/akce")
actions = []
if r is not None:
    s = BeautifulSoup(r.text, "html.parser").find("script", id="__NUXT_DATA__")
    data = unflatten_nuxt(json.loads(s.string))
    acts = data["data"]["/api/v2/shop/actions?page=1&itemsPerPage=24"]
    actions = acts.get("result") or []
    print("  actions:", acts.get("count"), [(a.get("slug"), a.get("name"), a.get("type"), a.get("dateFrom"), a.get("dateTo")) for a in actions[:24]])
for a in actions[:2]:
    r = get(f"https://www.tetadrogerie.cz/akce/{a.get('slug')}")
    if r is None:
        continue
    s = BeautifulSoup(r.text, "html.parser").find("script", id="__NUXT_DATA__")
    data = unflatten_nuxt(json.loads(s.string))
    d = data.get("data", {}) if isinstance(data, dict) else {}
    print("  data keys:", [k[:110] for k in d.keys()])
    prods = walk(d, lambda x: ("price" in x or "variants" in x or "priceWithVat" in x) and ("name" in x or "title" in x), [], 3)
    for p in prods:
        print("   product:", c(p, 1500))
    cnt = len(walk(d, lambda x: ("price" in x or "variants" in x) and "name" in x, [], 500))
    print("   product-like count:", cnt)

print("=== 3. Kaufland overview params ===")
for url in ("https://endpoints.leaflets.schwarz/v4/overview?country=cz&brand=kaufland&locale=cs-CZ",
            "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=x&region_id=0&region_code=0"):
    r = get(url, as_json=True, ok_any=True)
    if r is not None:
        print("   body:", r.text[:400].replace("\n", " "))

print("=== 4. Billa loyalty/club price fields ===")
tags, pkeys, regkeys = Counter(), Counter(), Counter()
samples = []
for slug in ("chlazene-mlecne-a-rostlinne-vyrobky-1207", "maso-a-ryby-1263", "drogerie-a-kosmetika-1599", "trvanlive-potraviny-1343"):
    r = get(f"https://www.billa.cz/api/product-discovery/categories/{slug}/products?page=0&pageSize=100", as_json=True)
    if r is None:
        continue
    for p in r.json().get("results", []):
        pr = p.get("price") or {}
        for k in pr.keys():
            pkeys[k] += 1
        for k in (pr.get("regular") or {}).keys():
            regkeys[k] += 1
        for t in (pr.get("regular") or {}).get("tags") or []:
            tags[t] += 1
        if any(("club" in str(t).lower() or "klub" in str(t).lower() or "loyal" in str(t).lower()) for t in (pr.get("regular") or {}).get("tags") or []) or any(k not in ("baseUnitLong", "baseUnitShort", "basePriceFactor", "regular", "crossed", "discountPercentage", "standard", "lowestPrice") for k in pr.keys()):
            if len(samples) < 3:
                samples.append((p.get("name"), pr))
print("  price keys:", dict(pkeys))
print("  regular keys:", dict(regkeys))
print("  tags:", dict(tags))
for n, pr in samples:
    print("  sample:", n, c(pr, 900))
