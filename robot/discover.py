"""Discovery run 4: look inside the embedded offer data of each chain and test leaflet APIs.

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
DELAY_S = 4
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs-CZ,cs;q=0.9,sk;q=0.8,en;q=0.5"})
_robots = {}


def robots(base):
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        status, text = None, ""
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            status, text = r.status_code, r.text
            rp.parse(text.splitlines() if status == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[base] = (rp, status, text)
        time.sleep(DELAY_S)
    return _robots[base]


def allowed(url):
    p = urllib.parse.urlsplit(url)
    rp, status, _ = robots(f"{p.scheme}://{p.netloc}")
    if status in (401, 403):
        return False
    return rp.can_fetch(UA, url) and rp.can_fetch("*", url)


def get(url, **kw):
    if not allowed(url):
        print(f"[SKIP blocked/robots] {url}")
        return None
    time.sleep(DELAY_S)
    try:
        r = session.get(url, timeout=30, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {url}: {e}")
        return None
    print(f"[{r.status_code}] {url[:140]} ({len(r.content)} B, {r.headers.get('content-type')})")
    return r if r.status_code == 200 else None


def robots_lines(base, keys):
    _, status, text = robots(base)
    lines = [l.strip() for l in text.splitlines() if any(k in l.lower() for k in keys)]
    print(f"  robots {base} ({status}):", lines[:20])


def unflatten_nuxt(payload):
    """Resolve Nuxt 3 __NUXT_DATA__ (devalue) flat array into nested Python objects."""
    memo = {}

    def res(i, depth=0):
        if not isinstance(i, int) or i < 0 or i >= len(payload):
            return i
        if i in memo:
            return memo[i]
        if depth > 60:
            return None
        v = payload[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef"):
                out = res(v[1], depth + 1) if len(v) > 1 else None
            elif v and isinstance(v[0], str) and v[0] in ("Set", "Map", "Date", "RegExp", "BigInt", "null", "undefined", "NaN"):
                out = None
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


def find_price_objects(obj, path="$", out=None, limit=6):
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if isinstance(obj, dict):
        keys = [k.lower() for k in obj.keys()]
        has_price = any("price" in k or "cena" in k for k in keys)
        has_name = any(k in ("name", "title", "productname", "displayname", "label", "nazev") for k in keys)
        if has_price and has_name:
            out.append((path, obj))
            return out
        for k, v in obj.items():
            find_price_objects(v, f"{path}.{k}", out, limit)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:400]):
            find_price_objects(v, f"{path}[{i}]", out, limit)
    return out


def count_price_objects(obj):
    n = 0
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            keys = [k.lower() for k in o.keys()]
            if any("price" in k for k in keys) and any(k in ("name", "title", "productname", "displayname") for k in keys):
                n += 1
                continue
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return n


def compact(o, n=700):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


def inspect_embedded(r, label):
    soup = BeautifulSoup(r.text, "html.parser")
    data = None
    nuxt = soup.find("script", id="__NUXT_DATA__")
    nxt = soup.find("script", id="__NEXT_DATA__")
    try:
        if nuxt is not None:
            data = unflatten_nuxt(json.loads(nuxt.string))
        elif nxt is not None:
            data = json.loads(nxt.string)
    except Exception as e:  # noqa: BLE001
        print(f"  {label}: could not parse embedded JSON: {e}")
        return
    if data is None:
        print(f"  {label}: no embedded JSON")
        return
    total = count_price_objects(data)
    hits = find_price_objects(data)
    print(f"  {label}: price-like objects ≈ {total}")
    for p, o in hits[:3]:
        print(f"   path {p}: {compact(o)}")
    apis = sorted(set(re.findall(r"https?://[a-z0-9.-]+/[a-z0-9/_-]*api[a-z0-9/_-]*", r.text)))[:10]
    if apis:
        print(f"  {label}: api urls referenced: {apis}")


print("=== Lidl: robots + leaflet API ===")
robots_lines("https://www.lidl.cz", ("/q/", "/l/", "disallow: /c", "api"))
r = get("https://www.lidl.cz/c/akcni-letak/s10008644")
if r is not None:
    found = sorted(set(re.findall(r"https?://[a-z0-9.-]*schwarz[a-z0-9./_-]*", r.text)))[:10]
    print("  schwarz urls:", found)
    flyers = sorted(set(re.findall(r"/l/cs/letak/([a-z0-9-]+)/", r.text)))[:10]
    print("  flyer slugs:", flyers)
robots_lines("https://endpoints.leaflets.schwarz", ("disallow", "allow"))
if r is not None:
    for slug in sorted(set(re.findall(r"/l/cs/letak/([a-z0-9-]+)/", r.text)))[:2]:
        api = f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={slug}&region_id=0&region_code=0"
        a = get(api)
        if a is not None:
            try:
                j = a.json()
                print("   top keys:", list(j.keys())[:15])
                hits = find_price_objects(j)
                print("   price-like objects ≈", count_price_objects(j))
                for p, o in hits[:2]:
                    print("   ", p, compact(o, 600))
            except Exception as e:  # noqa: BLE001
                print("   not JSON:", e, a.text[:200])

print("=== Kaufland leaflets via same platform ===")
for url in ("https://endpoints.leaflets.schwarz/v4/flyers?brand=kaufland&country=CZ",
            "https://leaflets.kaufland.com/cs-CZ"):
    r = get(url)
    if r is not None:
        print("   ", r.text[:300].replace("\n", " "))

print("=== Billa ===")
robots_lines("https://www.billa.cz", ("disallow", "api"))
for url in ("https://www.billa.cz/akcni-letaky", "https://www.billa.cz/akcni-nabidka"):
    r = get(url)
    if r is not None:
        inspect_embedded(r, url)

print("=== Albert ===")
robots_lines("https://www.albert.cz", ("disallow", "api"))
for url in ("https://www.albert.cz/aktualni-letaky", "https://www.albert.cz/akcni-nabidka", "https://www.albert.cz/slevy"):
    r = get(url)
    if r is not None:
        inspect_embedded(r, url)

print("=== Teta ===")
robots_lines("https://www.tetadrogerie.cz", ("disallow", "api"))
r = get("https://www.tetadrogerie.cz/akce")
if r is not None:
    inspect_embedded(r, "teta akce")

print("=== dm ===")
robots_lines("https://www.dm.cz", ("disallow", "api", "search"))
robots_lines("https://product-search.services.dmtech.com", ("disallow", "allow"))
r = get("https://product-search.services.dmtech.com/cz/search?query=zubn%C3%AD%20pasta&pageSize=5")
if r is not None:
    try:
        j = r.json()
        print("   keys:", list(j.keys())[:12], "| price-like:", count_price_objects(j))
        for p, o in find_price_objects(j)[:2]:
            print("   ", p, compact(o, 600))
    except Exception as e:  # noqa: BLE001
        print("   not JSON", e)

print("=== akcniceny.cz (possible source for Tesco/Kaufland) ===")
robots_lines("https://www.akcniceny.cz", ("disallow", "allow", "crawl"))
r = get("https://www.akcniceny.cz/")
if r is not None:
    soup = BeautifulSoup(r.text, "html.parser")
    for f in soup.find_all("form"):
        print("  form:", f.get("action"), [i.get("name") for i in f.find_all("input")])
    hrefs = list(dict.fromkeys(a["href"] for a in soup.find_all("a", href=True)))
    print("  links:", [h for h in hrefs if any(k in h.lower() for k in ("tesco", "kaufland", "podmin", "pravidl", "hledat", "vyhled"))][:20])

print("=== Kupino.sk product page ===")
robots_lines("https://www.kupino.sk", ("disallow",))
r = get("https://www.kupino.sk/akcia/euro-standard-bravcova-sunka")
if r is not None:
    txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    print("  euro prices found:", re.findall(r"\d+[,.]\d{2}\s*€", txt)[:10])
    print("  text sample:", txt[:600])
r = get("https://www.kupino.sk/letaky/lidl/akcie")
if r is not None:
    txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    print("  euro prices found:", len(re.findall(r"\d+[,.]\d{2}\s*€", txt)))
    print("  text sample:", txt[:500])
